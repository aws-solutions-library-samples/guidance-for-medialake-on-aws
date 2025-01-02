import os
import json
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PipelineTrigger")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    print(json.dumps(event))
    # Get the Step Function ARN from environment variables

    # Initialize the Step Functions client
    sfn_client = boto3.client("stepfunctions")

    try:
        # Process each record from SQS
        for record in event["Records"]:
            # Parse the message body which contains the EventBridge event
            message_body = json.loads(record["body"])

            # Extract the assets array from the detail
            asset = message_body["Asset"]
            step_function_arn = message_body["StateMachineArn"]
            format = asset["DigitalSourceAsset"]["MainRepresentation"]["Format"]
            # Start execution of the Step Function for each asset
            # for asset in assets:
            # Prepare the input for the Step Function
            step_function_input = {
                "pipeline_id": asset["InventoryID"],  # Using asset ID as pipeline_id
                "input": asset,  # Pass the entire asset object
            }

            # Start the Step Function execution

            response = sfn_client.start_execution(
                stateMachineArn=step_function_arn,
                input=json.dumps(step_function_input),
            )

            logger.info(
                f"Started execution for asset {asset['InventoryID']}: {response['executionArn']}"
            )

            print(
                f"Started execution for asset {asset['InventoryID']}: {response['executionArn']}"
            )

        return {"statusCode": 200, "body": "Successfully processed all assets"}

    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return {"statusCode": 500, "body": str(e)}
