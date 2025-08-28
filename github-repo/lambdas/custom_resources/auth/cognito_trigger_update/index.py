import json
import logging

import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client("cognito-idp")

# CloudFormation response constants and helper function
SUCCESS = "SUCCESS"
FAILED = "FAILED"


def send_response(
    event,
    context,
    response_status,
    response_data,
    physical_resource_id=None,
    no_echo=False,
):
    """
    Send response to CloudFormation custom resource.
    """
    response_url = event["ResponseURL"]

    response_body = {
        "Status": response_status,
        "Reason": f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_resource_id or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": no_echo,
        "Data": response_data,
    }

    json_response_body = json.dumps(response_body)

    headers = {"content-type": "", "content-length": str(len(json_response_body))}

    try:
        http = urllib3.PoolManager()
        response = http.request(
            "PUT", response_url, body=json_response_body, headers=headers
        )
        logger.info(f"Status code: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {str(e)}")


def lambda_handler(event, context):
    logger.info(f"Event: {event}")

    request_type = event["RequestType"]
    physical_id = event.get("PhysicalResourceId", "CognitoTriggerUpdate")

    try:
        user_pool_id = event["ResourceProperties"]["UserPoolId"]
        pre_token_generation_lambda_arn = event["ResourceProperties"][
            "PreTokenGenerationLambdaArn"
        ]

        if request_type in ["Create", "Update"]:
            logger.info(f"Updating triggers for user pool {user_pool_id}")

            # Get current user pool configuration
            response = cognito.describe_user_pool(UserPoolId=user_pool_id)
            current_config = response["UserPool"]
            lambda_config = current_config.get("LambdaConfig", {})

            # Add or update the Pre-Token Generation trigger
            lambda_config["PreTokenGenerationConfig"] = {
                "LambdaArn": pre_token_generation_lambda_arn,
                "LambdaVersion": "V2_0",
            }

            # Update the user pool with the new Lambda configuration
            # Only include parameters that are valid for update_user_pool API
            update_params = {"UserPoolId": user_pool_id, "LambdaConfig": lambda_config}

            # Preserve existing configuration - only include updateable parameters
            if "Policies" in current_config:
                update_params["Policies"] = current_config["Policies"]
            if "AutoVerifiedAttributes" in current_config:
                update_params["AutoVerifiedAttributes"] = current_config[
                    "AutoVerifiedAttributes"
                ]
            if "AdminCreateUserConfig" in current_config:
                update_params["AdminCreateUserConfig"] = current_config[
                    "AdminCreateUserConfig"
                ]
            if "VerificationMessageTemplate" in current_config:
                update_params["VerificationMessageTemplate"] = current_config[
                    "VerificationMessageTemplate"
                ]
            if "UserPoolAddOns" in current_config:
                update_params["UserPoolAddOns"] = current_config["UserPoolAddOns"]
            # Note: UsernameAttributes cannot be updated after user pool creation

            cognito.update_user_pool(**update_params)

            logger.info("Successfully updated Cognito triggers")
            send_response(event, context, SUCCESS, {}, physical_id)

        elif request_type == "Delete":
            logger.info(
                f"Delete request for Cognito triggers on user pool {user_pool_id}"
            )
            # On delete, we can optionally remove our triggers
            try:
                response = cognito.describe_user_pool(UserPoolId=user_pool_id)
                lambda_config = response["UserPool"].get("LambdaConfig", {})

                # Remove our Pre-Token Generation trigger if it matches
                pre_token_config = lambda_config.get("PreTokenGenerationConfig", {})
                if pre_token_config.get("LambdaArn") == pre_token_generation_lambda_arn:
                    lambda_config.pop("PreTokenGenerationConfig", None)

                    cognito.update_user_pool(
                        UserPoolId=user_pool_id, LambdaConfig=lambda_config
                    )
                    logger.info("Removed Cognito triggers during cleanup")
            except Exception as cleanup_error:
                logger.warning(f"Error during trigger cleanup: {str(cleanup_error)}")
                # Don't fail the stack deletion for cleanup errors

            send_response(event, context, SUCCESS, {}, physical_id)
        else:
            logger.error(f"Unexpected request type: {request_type}")
            send_response(event, context, FAILED, {}, physical_id)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        send_response(event, context, FAILED, {"Error": str(e)}, physical_id)
