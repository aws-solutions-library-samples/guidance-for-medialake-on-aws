import boto3
import json
import os
import ast
import importlib.util
import re
from urllib.parse import urljoin
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
import botocore
from lambda_middleware import lambda_middleware


# Initialize Powertools
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")


def clean_asset_id(input_string: str) -> str:
    parts = input_string.split(":")
    uuid = parts[-1]
    if uuid == "master":
        uuid = parts[-2]
    return f"asset:uuid:{uuid}"


def load_and_execute_function_from_s3(bucket: str, key: str, function_name: str, event: dict):
    try:
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in the downloaded file.")
        dynamic_function = getattr(module, function_name)
        result = dynamic_function(event)
        return result
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.error(f"The object {key} does not exist in bucket {bucket}.")
        elif error_code == "NoSuchBucket":
            logger.error(f"The bucket {bucket} does not exist.")
        else:
            logger.error(f"An S3 error occurred: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def download_s3_object(bucket: str, key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Error downloading S3 object: {e}")
        raise


def create_custom_url(s3_templates, api_template_bucket, event):
    logger.info("Building a custom URL")
    function_name = "translate_event_to_request"
    url_template_path = f"api_templates/{s3_templates['url_template']}"
    url_mapping_path = s3_templates["url_mapping_file"]
    request_template = download_s3_object(api_template_bucket, url_template_path)
    mapping = load_and_execute_function_from_s3(api_template_bucket, url_mapping_path, function_name, event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    custom_url = query_template.render(variables=mapping)
    return custom_url


def create_response_output(s3_templates, api_template_bucket, response_body, event):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket,
        response_mapping_path,
        function_name,
        {"response_body": response_body, "event": event}
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    dict_output = json.loads(response_output)
    return dict_output


def build_s3_templates_path(service_name: str, resource: str, method: str) -> dict:
    """Build paths to the S3 templates for the given service, resource, and method."""
    resource_name = resource.split("/")[-1]
    file_prefix = f"{resource_name}_{method.lower()}"
    
    return {
        "url_template": f"{service_name}/{resource}/{file_prefix}_url.jinja",
        "url_mapping_file": f"{service_name}/{resource}/{file_prefix}_url_mapping.py",
        "response_template": f"{service_name}/{resource}/{file_prefix}_response.jinja",
        "response_mapping_file": f"{service_name}/{resource}/{file_prefix}_response_mapping.py",
    }


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    # Get DynamoDB table name from environment variable
    table_name = os.environ["MEDIALAKE_ASSET_TABLE"]
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET", "medialake-assets")

    # Check if we have video or audio result
    if "VideoProxyandThumbnailResult" in event["previous_task_output"]:
        media_type = "Video"
        proxy_and_thumbnail_result = event["previous_task_output"]["VideoProxyandThumbnailResult"]
    elif "AudioProxyandThumbnailResult" in event["previous_task_output"]:
        media_type = "Audio"
        proxy_and_thumbnail_result = event["previous_task_output"]["AudioProxyandThumbnailResult"]
    else:
        raise ValueError(
            "Neither VideoProxyandThumbnailResult nor AudioProxyandThumbnailResult found in event"
        )

    # Parse the payload body if it's a string
    if isinstance(proxy_and_thumbnail_result["Payload"]["body"], str):
        proxy_and_thumbnail_result["Payload"]["body"] = json.loads(
            proxy_and_thumbnail_result["Payload"]["body"]
        )

    job_id = proxy_and_thumbnail_result["Payload"]["body"]["JobId"]
    inventory_id = event["input"]["InventoryID"]
    clean_inventory_id = clean_asset_id(inventory_id)
    asset_id = clean_asset_id(event["input"]["DigitalSourceAsset"]["ID"])

    # Build the S3 template paths
    s3_templates = build_s3_templates_path(
        service_name="mediaconvert",
        resource="check_status",
        method="get"
    )

    # Create the custom URL using the template
    try:
        api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
    except Exception as e:
        logger.error(f"Error creating custom URL: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": f"Error creating custom URL: {str(e)}"})}

    # Make the API call to MediaConvert
    try:
        mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")
        response = mediaconvert.get_job(Id=job_id)
        logger.info(response)
        
        # Process the response using the template
        try:
            result = create_response_output(s3_templates, api_template_bucket, response, event)
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return {"statusCode": 500, "body": json.dumps({"error": f"Error processing response: {str(e)}"})}
        
        # If job is complete, update DynamoDB
        if response["Job"]["Status"] == "COMPLETE":
            # Get the output bucket and base path
            output_group_settings = response["Job"]["Settings"]["OutputGroups"][0][
                "OutputGroupSettings"
            ]["FileGroupSettings"]
            output_bucket = (
                output_group_settings["Destination"].split("s3://")[1].split("/")[0]
            )
            base_path = output_group_settings["Destination"].split(
                f"s3://{output_bucket}/"
            )[1]

            # Determine output format and paths based on media type
            if media_type == "Video":
                proxy_path = f"{base_path}.mp4"
                thumbnail_path = f"{base_path}_thumbnail.0000000.jpg"
                proxy_format = "MP4"
                has_thumbnail = True
            else:  # Audio
                # For audio, the output is typically an MP3 file without a thumbnail
                proxy_path = f"{base_path}.mp3"
                thumbnail_path = None
                proxy_format = "MP3"
                has_thumbnail = False
                
                # Check if the output group name contains information about the format
                for output_group in response["Job"]["Settings"]["OutputGroups"]:
                    if "Name" in output_group and "Audio" in output_group["Name"]:
                        # Check if there are audio codec settings that specify the format
                        if "Outputs" in output_group and len(output_group["Outputs"]) > 0:
                            if "AudioDescriptions" in output_group["Outputs"][0]:
                                audio_desc = output_group["Outputs"][0]["AudioDescriptions"][0]
                                if "CodecSettings" in audio_desc:
                                    codec_settings = audio_desc["CodecSettings"]
                                    if "Codec" in codec_settings:
                                        proxy_format = codec_settings["Codec"]

            # Get file sizes (mocked here, replace with actual S3 metadata retrieval if needed)
            proxy_size = 5000000  # Replace with actual size in bytes from S3
            thumbnail_size = 12670  # Replace with actual size in bytes from S3

            try:
                # Create proxy representation
                proxy_representation = {
                    "ID": f"{asset_id}:proxy",
                    "Type": media_type,
                    "Format": proxy_format,
                    "Purpose": "proxy",
                    "StorageInfo": {
                        "PrimaryLocation": {
                            "Bucket": output_bucket,
                            "ObjectKey": {
                                "FullPath": proxy_path,
                            },
                            "FileInfo": {
                                "Size": proxy_size,
                            },
                            "Provider": "aws",
                            "Status": "active",
                            "StorageType": "s3",
                        }
                    },
                }

                # Create representations list
                representations = [proxy_representation]

                # Create thumbnail representation if applicable (for video)
                if has_thumbnail:
                    thumbnail_representation = {
                        "ID": f"{asset_id}:thumbnail",
                        "Type": "Image",
                        "Format": "JPEG",
                        "Purpose": "thumbnail",
                        "ImageSpec": {
                            "Resolution": {
                                "Height": 400,
                                "Width": 300,
                            }
                        },
                        "StorageInfo": {
                            "PrimaryLocation": {
                                "Bucket": output_bucket,
                                "ObjectKey": {
                                    "FullPath": thumbnail_path,
                                },
                                "FileInfo": {
                                    "Size": thumbnail_size,
                                },
                                "Provider": "aws",
                                "Status": "active",
                                "StorageType": "s3",
                            }
                        },
                    }
                    representations.append(thumbnail_representation)

                # Update DynamoDB
                try:
                    db_response = table.update_item(
                        Key={"InventoryID": clean_inventory_id},
                        UpdateExpression="SET DerivedRepresentations = list_append(if_not_exists(DerivedRepresentations, :empty_list), :new_reps)",
                        ConditionExpression="attribute_not_exists(DerivedRepresentations) OR NOT contains(DerivedRepresentations, :proxy_id)",
                        ExpressionAttributeValues={
                            ":new_reps": representations,
                            ":empty_list": [],
                            ":proxy_id": proxy_representation["ID"],
                        },
                        ReturnValues="UPDATED_NEW",
                    )
                    logger.info(
                        "DynamoDB update response",
                        extra={"response": db_response, "inventory_id": clean_inventory_id},
                    )
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                        logger.info("Proxy representation already exists, skipping update")
                    else:
                        raise
            except Exception as e:
                logger.exception(
                    "Error updating DynamoDB",
                    extra={
                        "inventory_id": clean_inventory_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise
        
        return result
    except Exception as e:
        logger.exception(f"Error in lambda_handler: {str(e)}")
        return {
            "externalJobResult": "Failed",
            "externalJobStatus": "Started",
            "error": str(e)
        }
