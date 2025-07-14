import logging

import boto3
import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client("cognito-idp")


def handler(event, context):
    logger.info(f"Event: {event}")

    request_type = event["RequestType"]
    physical_id = event.get("PhysicalResourceId", "PreTokenGenerationTrigger")

    try:
        user_pool_id = event["ResourceProperties"]["UserPoolId"]
        lambda_arn = event["ResourceProperties"]["LambdaArn"]

        if request_type in ["Create", "Update"]:
            logger.info(
                f"Adding Pre-Token Generation trigger to user pool {user_pool_id}"
            )

            # Get current Lambda config
            response = cognito.describe_user_pool(UserPoolId=user_pool_id)
            lambda_config = response.get("UserPool", {}).get("LambdaConfig", {})

            # Update with our trigger - use PreTokenGeneration key for the Lambda config
            lambda_config["PreTokenGeneration"] = lambda_arn

            # Update the user pool
            cognito.update_user_pool(
                UserPoolId=user_pool_id, LambdaConfig=lambda_config
            )

            logger.info("Successfully added Pre-Token Generation trigger")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        elif request_type == "Delete":
            # Optionally remove the trigger on delete
            logger.info(
                f"Delete request for Pre-Token Generation trigger on user pool {user_pool_id}"
            )
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        else:
            logger.error(f"Unexpected request type: {request_type}")
            cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cfnresponse.send(
            event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_id
        )
