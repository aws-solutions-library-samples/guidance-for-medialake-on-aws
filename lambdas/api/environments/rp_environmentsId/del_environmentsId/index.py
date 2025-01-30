import os
import boto3
from typing import Dict, Any
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from lambdas.api.environments.utils import (
    logger,
    metrics,
    tracer,
    setup_logging,
    create_error_response,
    create_success_response,
    handle_dynamodb_error,
    get_environment_pk,
    get_environment_sk,
)

app = APIGatewayRestResolver()
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ENVIRONMENTS_TABLE"])


@app.delete("/environments/<environment_id>")
@tracer.capture_method
def delete_environment(environment_id: str):
    """Delete an environment."""
    try:
        # Delete the environment
        response = table.delete_item(
            Key={
                "PK": get_environment_pk(environment_id),
                "SK": get_environment_sk(),
            },
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_OLD",
        )

        deleted_item = response.get("Attributes", {})

        metrics.add_metric(name="DeleteEnvironment", unit=MetricUnit.Count, value=1)
        logger.info(f"Deleted environment {environment_id}")

        return create_success_response(
            200,
            {"message": "Environment deleted successfully"},
        )

    except ClientError as e:
        return handle_dynamodb_error(e, environment_id)
    except Exception as e:
        logger.exception("Error deleting environment")
        return create_error_response(500, str(e))


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for environment operations."""
    setup_logging()
    return app.resolve(event, context)
