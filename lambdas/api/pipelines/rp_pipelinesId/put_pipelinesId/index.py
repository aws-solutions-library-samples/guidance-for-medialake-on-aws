import json
import os
from typing import Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel

# Initialize Power Tools
logger = Logger(service="put_pipeline_service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="put_pipeline_service")
metrics = Metrics(namespace="MediaLake", service="put_pipeline_service")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_TABLE_NAME"])

# CORS Configuration
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict]


def update_eventbridge_rule_state(rule_name: str, enabled: bool) -> None:
    """
    Enable or disable an EventBridge rule.

    Args:
        rule_name: Name of the rule
        enabled: True to enable, False to disable
    """
    # Get the event bus name from environment variable
    event_bus_name = os.environ.get("PIPELINES_EVENT_BUS_NAME")
    events_client = boto3.client("events")

    try:
        if enabled:
            events_client.enable_rule(Name=rule_name, EventBusName=event_bus_name)
            logger.info(f"Enabled EventBridge rule: {rule_name}")
        else:
            events_client.disable_rule(Name=rule_name, EventBusName=event_bus_name)
            logger.info(f"Disabled EventBridge rule: {rule_name}")
    except Exception as e:
        logger.error(f"Error updating EventBridge rule state for {rule_name}: {e}")
        raise


def update_pipeline_active_state(pipeline_id: str, active: bool) -> None:
    """
    Update the active state of a pipeline and enable/disable its EventBridge rules.

    Args:
        pipeline_id: ID of the pipeline
        active: New active state
    """
    try:
        # Get the pipeline record to find its EventBridge rules
        response = table.get_item(Key={"id": pipeline_id})
        pipeline = response.get("Item")

        if not pipeline:
            logger.error(f"Pipeline not found: {pipeline_id}")
            return

        # Update EventBridge rules
        dependent_resources = pipeline.get("dependentResources", [])
        for resource_type, resource_value in dependent_resources:
            if resource_type == "eventbridge_rule":
                # Handle both string ARNs and dictionary objects
                if isinstance(resource_value, dict):
                    rule_name = resource_value.get("rule_name")
                else:
                    # Extract rule name from ARN
                    rule_name = resource_value.split("/")[-1]

                if rule_name:
                    update_eventbridge_rule_state(rule_name, active)
                    logger.info(
                        f"Updated EventBridge rule {rule_name} state to {'enabled' if active else 'disabled'}"
                    )

    except Exception as e:
        logger.error(f"Error updating pipeline active state: {e}")
        raise


@app.put("/pipelines/<pipeline_id>")
@tracer.capture_method
def put_pipeline(pipeline_id: str):
    try:
        logger.debug(f"Updating pipeline details for ID: {pipeline_id}")
        metrics.add_metric(name="PutPipelineAttempt", unit="Count", value=1)

        # Validate pipeline_id is not empty
        if not pipeline_id:
            logger.error("Pipeline ID is required")
            return PipelineResponse(
                status="error", message="Pipeline ID is required", data=None
            ).dict()

        # Get the request body
        body = app.current_event.json_body
        if not body:
            logger.error("Request body is required")
            return PipelineResponse(
                status="error", message="Request body is required", data=None
            ).dict()

        # Check if active state is being updated
        if "active" in body:
            active = body.get("active")
            try:
                # Update EventBridge rules based on active state
                update_pipeline_active_state(pipeline_id, active)
                logger.info(f"Updated pipeline {pipeline_id} active state to {active}")
            except Exception as e:
                logger.error(f"Failed to update EventBridge rules: {e}")
                # Continue with the update even if EventBridge update fails

        # Update DynamoDB
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in body.items():
            update_expression += f"#{key} = :{key}, "
            expression_attribute_values[f":{key}"] = value
            expression_attribute_names[f"#{key}"] = key

        update_expression = update_expression.rstrip(", ")

        response = table.update_item(
            Key={"id": pipeline_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW",
        )

        logger.info(f"Successfully updated pipeline: {pipeline_id}")
        metrics.add_metric(name="SuccessfulPipelineUpdate", unit="Count", value=1)

        return PipelineResponse(
            status="success",
            message="Pipeline updated successfully",
            data={"pipeline": response.get("Attributes", {})},
        ).dict()

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        metrics.add_metric(name="DynamoDBError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        metrics.add_metric(name="UnexpectedError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    return app.resolve(event, context)
