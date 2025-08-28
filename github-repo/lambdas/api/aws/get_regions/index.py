import json

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()

ec2_client = boto3.client("ec2")


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler to list available AWS regions."""
    logger.info("Received request to list AWS regions")

    try:
        response = ec2_client.describe_regions(
            AllRegions=False
        )  # Only get opted-in regions
        regions = [
            {"value": region["RegionName"], "label": region["RegionName"]}
            for region in response.get("Regions", [])
        ]

        # Sort regions alphabetically by name (value)
        regions.sort(key=lambda x: x["value"])

        logger.info(f"Successfully retrieved {len(regions)} regions.")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",  # Adjust CORS as needed
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "body": json.dumps(
                {
                    "message": "Regions retrieved successfully",
                    "data": {"regions": regions},
                }
            ),
        }
    except ClientError as e:
        logger.error(f"Error describing regions: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"message": "Failed to retrieve AWS regions"}),
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"message": "An unexpected error occurred"}),
        }
