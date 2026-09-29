"""
Bulk Download Subclips Get Settings Lambda

This Lambda function returns the input/output settings for subclips by:
1. Retrieving path for source asset
2. Generating an output path to write the sub-clip out to.
3. Generating the set of output mediaconvert configs.
4. Updating the job record with input/output information.

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
from datetime import datetime
from typing import Any, Dict, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-subclips-get-settings")
tracer = Tracer(service="bulk-download-subclips-get-settings")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-subclips-get-settings"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs
asset_table = dynamodb.Table(ASSET_TABLE)

# Valid MediaConvert AAC-LC CODING_MODE_2_0 (stereo) CBR bitrates per output
# sample rate. Source: "AAC output reference tables" in the MediaConvert
# user guide (https://docs.aws.amazon.com/mediaconvert/latest/ug/aac-support.html).
# MediaConvert rejects the whole job for any other value.
AAC_LC_STEREO_CBR_BITRATES: Dict[int, Tuple[int, ...]] = {
    8000: (16000, 20000),
    12000: (16000, 20000),
    16000: (16000, 20000, 24000, 28000, 32000),
    22050: (32000,),
    24000: (32000,),
    32000: (
        40000,
        48000,
        56000,
        64000,
        80000,
        96000,
        112000,
        128000,
        160000,
        192000,
        224000,
        256000,
        288000,
        320000,
        384000,
    ),
    44100: (
        64000,
        80000,
        96000,
        112000,
        128000,
        160000,
        192000,
        224000,
        256000,
        288000,
        320000,
        384000,
        448000,
        512000,
    ),
    48000: (
        64000,
        80000,
        96000,
        112000,
        128000,
        160000,
        192000,
        224000,
        256000,
        288000,
        320000,
        384000,
        448000,
        512000,
        576000,
    ),
    88200: (576000,),
    96000: (256000, 288000, 320000, 384000, 448000, 512000, 576000),
}

# H.264 Bitrate / MaxBitrate range accepted by MediaConvert.
H264_MIN_BITRATE = 1000
H264_MAX_BITRATE = 1_152_000_000

# Extension MediaConvert appends for the MP4 container used for sub-clips.
SUBCLIP_OUTPUT_EXTENSION = ".mp4"


def aac_output_sample_rate(source_sample_rate: int) -> int:
    """Nearest AAC-LC stereo output sample rate to the source's.

    Ties go to the higher rate. Common rates (44100, 48000) are unchanged.
    """
    return min(
        AAC_LC_STEREO_CBR_BITRATES,
        key=lambda rate: (abs(rate - source_sample_rate), -rate),
    )


def aac_output_bitrate(source_bitrate: int, sample_rate: int) -> int:
    """Nearest valid AAC-LC stereo CBR bitrate for the output sample rate.

    The source value is a measurement (e.g. 128089 bps for nominal 128 kbps
    AAC, or 1536000 bps for 48 kHz 16-bit PCM), not a valid encoder setting.
    Ties go to the higher bitrate; values beyond the table are clamped.
    """
    allowed = AAC_LC_STEREO_CBR_BITRATES[sample_rate]
    return min(allowed, key=lambda rate: (abs(rate - source_bitrate), -rate))


def _h264_bitrate(value: int) -> int:
    return max(H264_MIN_BITRATE, min(H264_MAX_BITRATE, value))


@tracer.capture_method
def get_existing_job_item_key(job_id: str) -> str:
    """
    Get the existing itemKey for a job by querying GSI3.

    Args:
        job_id: The job ID to find

    Returns:
        The itemKey of the existing job record

    Raises:
        ValueError: If job is not found
    """
    try:
        response = user_table.query(
            IndexName="GSI3",
            KeyConditionExpression="gsi3Pk = :gsi3_pk",
            ExpressionAttributeValues={":gsi3_pk": f"JOB#{job_id}"},
            Limit=1,
        )

        if not response.get("Items"):
            raise ValueError(f"Job {job_id} not found")

        return response["Items"][0]["itemKey"]

    except Exception as e:
        logger.error(f"Failed to find existing job record: {str(e)}")
        raise


@tracer.capture_method
def get_asset_details(asset_id: str) -> Tuple[str, str]:
    """
    Retrieve asset details from DynamoDB.

    Args:
        asset_id: ID of the asset to retrieve

    Returns:
        Bucket: the name of the s3 bucket
        File Path: the path to the file in S3 (includes the filename)

    Raises:
        Exception: If asset retrieval fails
    """
    try:
        response = asset_table.get_item(
            Key={"InventoryID": asset_id},
            ConsistentRead=True,
        )

        if "Item" not in response:
            raise Exception(f"Asset {asset_id} not found")

        main_rep = (
            response["Item"].get("DigitalSourceAsset", {}).get("MainRepresentation", {})
        )
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        bucket = storage_info.get("Bucket")
        file_path = storage_info.get("ObjectKey", {}).get("FullPath")

        if not file_path or not bucket:
            logger.error(
                f"Could not determine file path or bucket for asset {asset_id}",
                extra={"assetId": asset_id},
            )

        return bucket, file_path

    except ClientError as e:
        logger.error(
            "Failed to retrieve asset details",
            extra={
                "error": str(e),
                "assetId": asset_id,
            },
        )
        raise Exception(f"Failed to retrieve asset details: {str(e)}")


@tracer.capture_method
def create_paths(
    job_id: str, bucket: str, file_path: str, start_time: str, end_time: str
) -> Tuple[str, str]:
    """
    Create input and output paths for sub-clip job

    Args:
        job_id: The job id
        bucket: The S3 bucket name storing the source file
        file_path: The S3 object path to the source file
        start_time: The start time stamp of the desired clip
        end_time: The end time stamp of the desired clip

    Returns:
        source_location: The path to the input source file from which to clip
        output_location: The path to write the sub-clip out to, with extension

    Raises:
        Exception: If missing required information
    """
    try:
        # The path to the input source file from which to clip
        source_location = f"s3://{bucket}/{file_path.lstrip("/")}"

        # Change timecode formats to be compatible with object naming conventions
        formatted_start_time = start_time.replace(":", "-").replace(";", "-")
        formatted_end_time = end_time.replace(":", "-").replace(";", "-")

        # The path for the output sub-clip. MediaConvert always writes an MP4
        # container (see generate_mediaconvert_job_settings) and names the file
        # "<destination>.mp4", so the expected output must use ".mp4" rather
        # than the source's extension. Using the source's (".mov", or ".MP4" on
        # camera files) made the size-sort step HeadObject a key that does not
        # exist, which S3 reports as 403 Forbidden.
        name = os.path.splitext(os.path.basename(file_path))[0]
        output_location = f"s3://{MEDIA_ASSETS_BUCKET}/temp/subClips/{job_id}/{name}_{formatted_start_time}_{formatted_end_time}{SUBCLIP_OUTPUT_EXTENSION}"

        return source_location, output_location

    except Exception as e:
        logger.error(f"Failed to create paths: {str(e)}")
        raise


@tracer.capture_method
def generate_mediaconvert_output_video_description(video_in_info: Dict) -> Dict:
    """Create an output video description block for MediaConvert

    Args:
        video_in_info (Dict): Required MediaInfo for the input source file video.

    Returns:
        Dict: A video description block for mediaconvert output

    Raises:
        ValueError: Missing required input video information.
    """
    h264_settings = {}
    rate_control_mode = video_in_info.get("RateControlMode", "")
    bitrate = int(video_in_info.get("Bitrate", 0))
    max_bitrate = int(video_in_info.get("MaxBitrate", 0))

    if not rate_control_mode or not bitrate or not max_bitrate:
        raise ValueError("Video-In missing required information.")

    # Keep the measured source values inside MediaConvert's accepted range,
    # and never ask for a peak below the average.
    bitrate = _h264_bitrate(bitrate)
    max_bitrate = max(_h264_bitrate(max_bitrate), bitrate)

    h264_settings["RateControlMode"] = rate_control_mode
    h264_settings["Bitrate"] = bitrate

    # CBR outputs do not take a MaxBitrate parameter
    if rate_control_mode == "VBR":
        h264_settings["MaxBitrate"] = max_bitrate

    return {
        "CodecSettings": {
            "Codec": "H_264",
            "H264Settings": h264_settings,
        }
    }


@tracer.capture_method
def generate_mediaconvert_output_audio_description(audio_in_info: Dict) -> Dict:
    """Create an output audio description block for MediaConvert

    Args:
        audio_in_info (Dict): Required MediaInfo for the input source file audio.

    Returns:
        Dict: An audio description block for mediaconvert output

    Raises:
        ValueError: Missing required input audio information
    """
    aac_settings = {}
    bitrate = int(audio_in_info.get("Bitrate", 0))
    sample_rate = int(audio_in_info.get("SampleRate", 0))
    rate_control_mode = audio_in_info.get("RateControlMode", "")

    if not rate_control_mode or not bitrate or not sample_rate:
        raise ValueError("Audio-In missing required information.")

    # The source's measured values are rarely valid AAC settings (e.g. 128089
    # bps, or 1536000 bps for PCM), and MediaConvert rejects the whole job.
    sample_rate = aac_output_sample_rate(sample_rate)

    aac_settings["CodingMode"] = "CODING_MODE_2_0"
    aac_settings["SampleRate"] = sample_rate
    aac_settings["RateControlMode"] = rate_control_mode
    aac_settings["CodecProfile"] = "LC"

    if rate_control_mode == "CBR":
        aac_settings["Bitrate"] = aac_output_bitrate(bitrate, sample_rate)
    elif rate_control_mode == "VBR":
        aac_settings["VbrQuality"] = "HIGH"

    return {
        "AudioSourceName": "Dynamic Audio Selector 1",
        "CodecSettings": {
            "Codec": "AAC",
            "AacSettings": aac_settings,
        },
    }


@tracer.capture_method
def generate_mediaconvert_job_settings(
    source_location: str,
    output_location_no_ext: str,
    start_time: str,
    end_time: str,
    video_in_info: Dict,
    audio_in_info: Dict,
) -> Dict:
    """
    Generate MediaConvert job settings for sub-clipping.

    Args:
        source_location: The path to the source file to sub-clip
        output_location_no_ext: The desired output path for the sub-clip, without a file extension.
        start_time: The time code in the source to start the sub-clip at.
        end_time: The time code in the source to end the sub-clip at.
        video_in_info: Required MediaInfo for the input source file video.
        audio_in_info: Required MediaInfo for the input source file audio.

    Returns:
        Dict: MediaConvert job settings
    """
    job_settings = {
        "TimecodeConfig": {"Source": "ZEROBASED"},
        "OutputGroups": [
            {
                "Name": "File Group",
                "Outputs": [
                    {
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {},
                        },
                        "VideoDescription": generate_mediaconvert_output_video_description(
                            video_in_info
                        ),
                        "AudioDescriptions": [
                            generate_mediaconvert_output_audio_description(
                                audio_in_info
                            )
                        ],
                    }
                ],
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {"Destination": output_location_no_ext},
                },
            }
        ],
        "FollowSource": 1,
        "Inputs": [
            {
                "InputClippings": [
                    {
                        "EndTimecode": end_time,
                        "StartTimecode": start_time,
                    }
                ],
                "DynamicAudioSelectors": {"Dynamic Audio Selector 1": {}},
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "FileInput": source_location,
            }
        ],
    }
    return job_settings


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for getting input/output settings for sub-clips

    Args:
        event: Event containing job details and sub-clips specs
        context: Lambda context

    Returns:
        Updated job details with sub-clip source and output locations
    """
    try:
        job_id = event.get("jobId")
        user_id = event.get("userId")

        if not job_id:
            raise ValueError("Missing jobId in event")

        if not user_id:
            raise ValueError("Missing userId in event")

        sub_clips = event.get("subClips", [])
        if not sub_clips:
            logger.error("No sub-clips found in event")
            raise ValueError("No sub-clips found in event")

        logger.info(
            "Gathering sub-clip input/output settings for processing",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "subClipFileCount": len(sub_clips),
            },
        )

        bucket: str = ""
        file_path: str = ""

        # Update sub_clip entries with input/output path details
        for sub_clip in sub_clips:
            bucket, file_path = get_asset_details(sub_clip["assetId"])

            if not bucket or not file_path:
                raise ValueError(
                    f"Missing asset details: Bucket: {bucket}, File Path: {file_path}"
                )

            start_time = sub_clip.get("clipBoundary", {}).get("startTime", "")
            end_time = sub_clip.get("clipBoundary", {}).get("endTime", "")
            video_in_info = sub_clip.get("video", {})
            audio_in_info = sub_clip.get("audio", {})
            if not start_time:
                raise ValueError("Missing sub-clip start_time in event")
            if not end_time:
                raise ValueError("Missing sub-clip end_time in event")
            if not video_in_info:
                raise ValueError("Missing source video info in event")
            if not audio_in_info:
                raise ValueError("Missing source audio info in event")

            source_location, output_location = create_paths(
                job_id, bucket, file_path, start_time, end_time
            )
            sub_clip["sourceLocation"] = source_location
            sub_clip["outputLocation"] = output_location
            sub_clip["outputLocationNoExt"] = os.path.splitext(output_location)[0]
            sub_clip["mediaConvertJobSettings"] = generate_mediaconvert_job_settings(
                source_location,
                os.path.splitext(output_location)[0],
                start_time,
                end_time,
                sub_clip["video"],
                sub_clip["audio"],
            )

        # Update dynamo job status in user table
        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=("SET #status = :status, " "#updatedAt = :updatedAt"),
            ExpressionAttributeNames={
                "#status": "status",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "GENERATING_SUB_CLIPS",
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Completed get subclips settings.",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "subClipFileCount": len(sub_clips),
            },
        )

        return event

    except Exception as e:
        logger.error(
            f"Error getting sub-clips settings: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("jobId")},
        )

        # Update job status to FAILED
        try:
            if "jobId" in event and "userId" in event:
                # Format user_id only if it doesn't already have the USER# prefix
                formatted_user_id = (
                    event["userId"]
                    if event["userId"].startswith("USER#")
                    else f"USER#{event['userId']}"
                )

                # Get the existing job's itemKey
                try:
                    item_key = get_existing_job_item_key(event["jobId"])

                    user_table.update_item(
                        Key={"userId": formatted_user_id, "itemKey": item_key},
                        UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                        ExpressionAttributeNames={
                            "#status": "status",
                            "#error": "error",
                            "#updatedAt": "updatedAt",
                        },
                        ExpressionAttributeValues={
                            ":status": "FAILED",
                            ":error": f"Failed to process large files: {str(e)}",
                            ":updatedAt": datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as query_error:
                    logger.error(
                        f"Failed to find job record for error update: {str(query_error)}"
                    )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"userId": event.get("userId"), "jobId": event.get("jobId")},
            )

        metrics.add_metric(
            name="SubClipsGetSettingsErrors", unit=MetricUnit.Count, value=1
        )

        # Re-raise the exception to be handled by Step Functions
        raise
