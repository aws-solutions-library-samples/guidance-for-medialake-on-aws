import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import ValidationError

from lambdas.api.environments.models import EnvironmentUpdate
from lambdas.api.environments.utils import (
    create_error_response,
    create_success_response,
    format_environment,
    get_current_time,
    get_environment_pk,
    get_environment_sk,
    handle_dynamodb_error,
    logger,
    metrics,
    setup_logging,
    tracer,
)

app = APIGatewayRestResolver()
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ENVIRONMENTS_TABLE"])


@app.put("/environments/<environment_id>")
@tracer.capture_method
def update_environment(environment_id: str):
    """Update an existing environment."""
    try:
        body = app.current_event.json_body
        environment_data = EnvironmentUpdate(**body)
        current_time = get_current_time()

        # Build update expression
        update_expressions = []
        expression_values = {":updatedAt": current_time}

        if environment_data.name is not None:
            update_expressions.append("name = :name")
            expression_values[":name"] = environment_data.name

        if environment_data.status is not None:
            update_expressions.append("status = :status")
            expression_values[":status"] = environment_data.status

        if environment_data.region is not None:
            update_expressions.append("region = :region")
            expression_values[":region"] = environment_data.region

        if environment_data.tags is not None:
            update_expressions.append("tags = :tags")
            expression_values[":tags"] = environment_data.tags

        update_expressions.append("updatedAt = :updatedAt")

        # Update the item
        response = table.update_item(
            Key={
                "PK": get_environment_pk(environment_id),
                "SK": get_environment_sk(),
            },
            UpdateExpression="SET " + ", ".join(update_expressions),
            ExpressionAttributeValues=expression_values,
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_NEW",
        )

        updated_item = response.get("Attributes", {})

        metrics.add_metric(name="UpdateEnvironment", unit=MetricUnit.Count, value=1)
        logger.info(f"Updated environment {environment_id}")

        return create_success_response(
            200,
            format_environment(updated_item),
        )

    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return create_error_response(400, str(e))
    except ClientError as e:
        return handle_dynamodb_error(e, environment_id)
    except Exception as e:
        logger.exception("Error updating environment")
        return create_error_response(500, str(e))


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for environment operations."""
    setup_logging()
    return app.resolve(event, context)
