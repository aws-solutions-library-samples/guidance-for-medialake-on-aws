import datetime
import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()

dynamodb = boto3.resource("dynamodb")
ssm_client = boto3.client("ssm")

MEDIALAKE_CONNECTOR_TABLE = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
PERSONAL_ASSETS_BUCKET_SSM_PARAM = os.environ.get("PERSONAL_ASSETS_BUCKET_SSM_PARAM")
REGION = os.environ.get("REGION")

_cached_bucket_name = None


def get_user_id_from_event(event):
    try:
        authorizer = event["requestContext"]["authorizer"]
    except (KeyError, TypeError):
        raise ValueError("User ID not found in request context")

    # Direct authorizer.sub (custom authorizer context)
    user_id = authorizer.get("sub") if isinstance(authorizer, dict) else None
    if user_id:
        return user_id

    # Nested authorizer.claims.sub (Cognito authorizer context)
    claims = authorizer.get("claims") if isinstance(authorizer, dict) else None
    if isinstance(claims, str):
        try:
            claims = json.loads(claims)
        except (json.JSONDecodeError, ValueError):
            claims = None
    if isinstance(claims, dict):
        user_id = claims.get("sub")
        if user_id:
            return user_id

    raise ValueError("User ID not found in request context")


def get_personal_bucket_name():
    global _cached_bucket_name
    if _cached_bucket_name:
        return _cached_bucket_name
    response = ssm_client.get_parameter(
        Name=PERSONAL_ASSETS_BUCKET_SSM_PARAM, WithDecryption=False
    )
    _cached_bucket_name = response["Parameter"]["Value"]
    return _cached_bucket_name


def build_connector_item(user_id, bucket_name, region):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "id": f"my-assets-{user_id}",
        "type": "my-assets",
        "name": "My Assets",
        "status": "active",
        "storageIdentifier": bucket_name,
        "objectPrefix": f"personal/{user_id}/",
        "region": region,
        "userId": user_id,
        "createdAt": now,
        "updatedAt": now,
        "isInternal": False,
    }


def format_connector(item):
    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "usage": {"total": item.get("usage", {}).get("total", 0)},
        "type": item.get("type", ""),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "storageIdentifier": item.get("storageIdentifier", ""),
        "sqsArn": item.get("sqsArn", ""),
        "region": item.get("region", ""),
        "status": item.get("status", ""),
        "integrationMethod": item.get("integrationMethod", ""),
        "iamRoleArn": item.get("iamRoleArn", ""),
        "lambdaArn": item.get("lambdaArn", ""),
        "queueUrl": item.get("queueUrl", ""),
        "objectPrefix": item.get("objectPrefix", ""),
        "configuration": {
            "queueUrl": item.get("queueUrl", ""),
            "lambdaArn": item.get("lambdaArn", ""),
            "iamRoleArn": item.get("iamRoleArn", ""),
        },
        "settings": {
            "bucket": item.get("storageIdentifier", ""),
            "region": item.get("region", ""),
            "path": item.get("objectPrefix", ""),
        },
    }


def get_or_create_connector(user_id):
    table_name = MEDIALAKE_CONNECTOR_TABLE
    if not table_name:
        raise RuntimeError("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")

    table = dynamodb.Table(table_name)
    connector_id = f"my-assets-{user_id}"

    response = table.get_item(Key={"id": connector_id})
    if "Item" in response:
        return response["Item"]

    bucket_name = get_personal_bucket_name()
    item = build_connector_item(user_id, bucket_name, REGION)

    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            response = table.get_item(Key={"id": connector_id}, ConsistentRead=True)
            if "Item" not in response:
                logger.error(
                    f"Item not found after ConditionalCheckFailedException for {connector_id}"
                )
                raise RuntimeError("Connector conflict detected but item not readable")
            return response["Item"]
        raise

    return item


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body),
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
        user_id = get_user_id_from_event(event)
    except ValueError:
        return _response(401, {"status": "401", "message": "Unauthorized", "data": {}})

    try:
        item = get_or_create_connector(user_id)
        return _response(
            200,
            {
                "status": "200",
                "message": "ok",
                "data": {"connector": format_connector(item)},
            },
        )
    except Exception as e:
        logger.exception(f"Error in get_my_assets: {str(e)}")
        return _response(
            500, {"status": "500", "message": "Internal server error", "data": {}}
        )
