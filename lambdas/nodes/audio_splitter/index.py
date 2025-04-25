import boto3
import os
import subprocess
import json
import re
import requests
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware
from nodes_utils import format_duration

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize AWS clients
s3_client = boto3.client('s3')

def clean_asset_id(input_string: str) -> str:
    """
    Ensures the asset ID has the correct format without duplicates.
    Extracts just the UUID part and adds the proper prefix.
    """
    parts = input_string.split(":")
    uuid_part = parts[-1]
    if uuid_part == "master":
        uuid_part = parts[-2]
    return f"asset:uuid:{uuid_part}"

def create_output_directory():
    """Create output directory for chunks if it doesn't exist"""
    output_dir = '/tmp/segments'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def get_audio_duration(file_path: str) -> float:
    """
    Uses ffmpeg to get the duration of the audio file.
    Parses the stderr output to extract the Duration.
    """
    try:
        # ffmpeg outputs metadata (including duration) to stderr
        command = ["./ffmpeg", "-i", file_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr
        logger.info(f"ffmpeg output: {output}")
        
        # Use regex to extract the duration from the ffmpeg output
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", output)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            total_duration = hours * 3600 + minutes * 60 + seconds
            logger.info(f"Parsed duration: {total_duration} seconds")
            return total_duration
        else:
            logger.error("Could not parse duration from ffmpeg output")
            return 0.0
    except Exception as e:
        logger.error(f"Failed to get audio duration using ffmpeg: {e}")
        return 0.0
    
# def get_audio_duration(file_path: str) -> float:
#     """
#     Uses ffprobe to get the duration of the audio file.
#     """
#     try:
#         result = subprocess.run(
#             ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
#              '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
#             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
#         )
#         return float(result.stdout.strip())
#     except Exception as e:
#         logger.error(f"Failed to get audio duration: {e}")
#         return 0.0

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),

)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})
        
        # Extract payload from the event (new event structure)
        payload = event.get("payload", {})
        if not payload:
            logger.warning("No payload found in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No payload found in event"})
            }
        
        presigned_url = payload.get("presignedUrl")
        if not presigned_url:
            logger.warning("No presignedUrl found in payload")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No presignedUrl found in payload"})
            }
        
        s3_source_bucket = payload.get("bucket")
        s3_source_key = payload.get("key")
        if not all([s3_source_bucket, s3_source_key]):
            logger.warning("Missing required S3 bucket or key information")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required S3 bucket or key information"})
            }
        
        # Check for assets in payload; if missing, attempt to retrieve from metadata.pipelineAssets
        assets = payload.get("assets")
        pipeline_assets = event.get("metadata", {}).get("pipelineAssets", [])
        if not assets or not isinstance(assets, list) or len(assets) == 0:
            if pipeline_assets and isinstance(pipeline_assets, list) and len(pipeline_assets) > 0:
                assets = [pipeline_assets[0].get("assetId")]
                logger.info("No assets provided in payload. Using asset from pipelineAssets", extra={"asset": assets[0]})
            else:
                logger.warning("No assets provided in payload and no pipeline assets found")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "No assets provided in payload"})
                }
        clean_inventory_id = clean_asset_id(assets[0])

        # Get chunk duration from node configuration (default to 10 seconds if not provided)
        chunk_duration = event.get("CHUNK_DURATION", 10)
        try:
            chunk_duration = int(chunk_duration)
        except ValueError:
            logger.warning(f"Invalid chunk_duration: {chunk_duration}, using default of 10 seconds")
            chunk_duration = 10
        
        # Define file paths
        input_file_path = f'/tmp/{os.path.basename(s3_source_key)}'
        output_dir = create_output_directory()
        
        # Extract the base name from the source key (without extension)
        base_name = os.path.splitext(os.path.basename(s3_source_key))[0]
        
        # Download the source audio file using the presigned URL
        try:
            response = requests.get(presigned_url)
            response.raise_for_status()
            with open(input_file_path, "wb") as f:
                f.write(response.content)
            logger.info("Downloaded file successfully", extra={"url": presigned_url})
        except Exception as e:
            error_msg = f"Failed to download file: {str(e)}"
            logger.error(error_msg, extra={"url": presigned_url})
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
        
        # Determine the total duration of the audio file
        total_duration = get_audio_duration(input_file_path)
        logger.info(f"Total audio duration: {total_duration} seconds")
        
        # Set the ffmpeg binary path in the current directory and build the output pattern including the base name
        ffmpeg_path = "./ffmpeg"
        output_pattern = os.path.join(output_dir, f"{base_name}_segment_%03d.mp3")
        
        # Build the ffmpeg command to split the audio
        command = [
            ffmpeg_path,
            '-i', input_file_path,
            '-f', 'segment',
            '-segment_time', str(chunk_duration),
            '-c:a', 'libmp3lame',
            '-q:a', '2',  # Quality setting for MP3 (lower is better)
            output_pattern
        ]
        
        # Execute the ffmpeg command
        try:
            logger.info(f"Running ffmpeg command: {' '.join(command)}")
            subprocess.check_call(command)
            logger.info("ffmpeg processing completed successfully")
        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg command failed: {str(e)}"
            logger.error(error_msg)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg})
            }
        
        # Upload each generated segment to S3 and collect their locations
        chunk_locations = []
        # Use the MEDIA_ASSETS_BUCKET_NAME environment variable for uploading segments
        output_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME", s3_source_bucket)
        
        # Get file info for the original audio file
        original_file_size = os.path.getsize(input_file_path)
        
        segment_index = 0
        for filename in sorted(os.listdir(output_dir)):
            if filename.startswith(f"{base_name}_segment_") and filename.endswith('.mp3'):
                file_path = os.path.join(output_dir, filename)
                segment_index += 1
                
                # Calculate start time for this segment
                start_time = (segment_index - 1) * chunk_duration
                
                # Adjust segment duration if this is the last segment (or if it goes beyond the total duration)
                if start_time + chunk_duration > total_duration:
                    segment_duration = total_duration - start_time
                else:
                    segment_duration = chunk_duration
                
                end_time = start_time + segment_duration
                
                # Create an output key to organize the segments in S3
                output_key = f"chunks/{clean_inventory_id}/{filename}"
                
                try:
                    # Get segment file size
                    segment_size = os.path.getsize(file_path)
                    
                    # Upload the segment to S3
                    s3_client.upload_file(file_path, output_bucket, output_key)
                    logger.info(f"Uploaded segment {segment_index} to s3://{output_bucket}/{output_key}")
                    
                    # Append metadata for this segment
                    chunk_locations.append({
                        "bucket": output_bucket,
                        "key": output_key,
                        "url": f"s3://{output_bucket}/{output_key}",
                        "index": segment_index,
                        "start_time": start_time,
                        "end_time": end_time,
                        "start_time_formatted": format_duration(start_time),
                        "end_time_formatted": format_duration(end_time),
                        "duration": segment_duration,
                        "duration_formatted": format_duration(segment_duration),
                        "size_bytes": segment_size,
                        "mediaType": "Audio",
                        "pipelineAssets": pipeline_assets
                    })
                except Exception as e:
                    error_msg = f"Error uploading segment {segment_index} to S3: {str(e)}"
                    logger.error(error_msg)
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": error_msg})
                    }
        
        # Return success response with chunk locations and source metadata
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully processed {s3_source_key} into {len(chunk_locations)} chunks",
                "asset_id": clean_inventory_id,
                "source": {
                    "bucket": s3_source_bucket,
                    "key": s3_source_key,
                    "size_bytes": original_file_size,
                    "duration": total_duration,
                    "duration_formatted": format_duration(total_duration) if total_duration else None
                },
                "chunking": {
                    "target_chunk_duration": chunk_duration,
                    "target_chunk_duration_formatted": format_duration(chunk_duration),
                    "chunk_count": len(chunk_locations),
                    "total_duration": total_duration,
                    "total_duration_formatted": format_duration(total_duration)
                }
            }),
            "externalTaskResults": chunk_locations
        }
        
    except Exception as e:
        error_message = f"Error processing audio chunks: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
