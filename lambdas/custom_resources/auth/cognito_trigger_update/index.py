import json
import logging

import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client("cognito-idp")
ssm = boto3.client("ssm")

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
        cloudfront_domain_ssm_param = event["ResourceProperties"].get(
            "CloudFrontDomainSsmParam", ""
        )

        if request_type in ["Create", "Update"]:
            logger.info(f"Updating triggers for user pool {user_pool_id}")

            # Resolve CloudFront domain from SSM for email templates
            cloudfront_url = ""
            if cloudfront_domain_ssm_param:
                try:
                    resp = ssm.get_parameter(Name=cloudfront_domain_ssm_param)
                    domain = resp["Parameter"]["Value"].strip().strip("/")
                    if domain and not domain.startswith("PENDING"):
                        cloudfront_url = f"https://{domain}"
                        logger.info(
                            f"Resolved CloudFront URL for emails: {cloudfront_url}"
                        )
                except Exception as e:
                    logger.warning(f"Could not read CloudFront domain from SSM: {e}")

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

            # Update AdminCreateUserConfig with CloudFront URL in invite email
            admin_config = current_config.get("AdminCreateUserConfig", {})
            if cloudfront_url:
                admin_config["InviteMessageTemplate"] = {
                    "EmailMessage": (
                        "<html><body>"
                        "<p>Hello,</p>"
                        "<p>Welcome to Media Lake! Your account has been created successfully.</p>"
                        "<p><strong>Your login credentials:</strong><br/>"
                        "Username: {username}<br/>"
                        "Temporary Password: {####}</p>"
                        "<p><strong>To get started:</strong></p>"
                        "<ol>"
                        f'<li>Go to <a href="{cloudfront_url}">{cloudfront_url}</a></li>'
                        "<li>Sign in with your credentials above</li>"
                        "<li>You'll be prompted to create a new password on your first login</li>"
                        "</ol>"
                        "<p><em>For security reasons, please change your password immediately upon signing in.</em></p>"
                        "<p>If you need assistance, please contact your Media Lake administrator.</p>"
                        "<p>Best regards,<br/>The Media Lake Team</p>"
                        "</body></html>"
                    ),
                    "EmailSubject": "Welcome to Media Lake",
                }
                logger.info("Updated invite email template with CloudFront URL")
            update_params["AdminCreateUserConfig"] = admin_config

            # Update VerificationMessageTemplate with CloudFront URL in reset email
            verification_template = current_config.get(
                "VerificationMessageTemplate", {}
            )
            if cloudfront_url:
                reset_link = f"{cloudfront_url}?action=reset-password"
                verification_template["EmailMessage"] = (
                    "<html><body>"
                    "<p>Hello,</p>"
                    "<p>You have requested to reset your Media Lake password.</p>"
                    "<p>Your verification code is: <strong>{####}</strong></p>"
                    f'<p>Enter this code at <a href="{reset_link}">{reset_link}</a> '
                    "to set a new password.</p>"
                    "<p>If you did not request this password reset, please ignore this email.</p>"
                    "<p>Best regards,<br/>The Media Lake Team</p>"
                    "</body></html>"
                )
                verification_template["EmailSubject"] = (
                    "Media Lake - Password Reset Code"
                )
                logger.info("Updated verification email template with CloudFront URL")
            update_params["VerificationMessageTemplate"] = verification_template

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
