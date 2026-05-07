from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate_input

logger = Logger()
tracer = Tracer()

# Schema for the event validation
POST_CONFIRMATION_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "triggerSource": {"type": "string"},
        "region": {"type": "string"},
        "userPoolId": {"type": "string"},
        "userName": {"type": "string"},
        "request": {
            "type": "object",
            "properties": {
                "userAttributes": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "sub": {"type": "string"},
                    },
                    "required": ["email", "sub"],
                }
            },
            "required": ["userAttributes"],
        },
    },
    "required": [
        "version",
        "triggerSource",
        "region",
        "userPoolId",
        "userName",
        "request",
    ],
}


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@validate_input(schema=POST_CONFIRMATION_SCHEMA)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Handle post confirmation logic for Cognito users.

    Args:
        event: The Lambda event object containing Cognito trigger information
        context: Lambda context object

    Returns:
        Dict containing the event data (required by Cognito)
    """
    try:
        logger.info(
            "Processing post confirmation for user",
            user_name=event["userName"],
            email=event["request"]["userAttributes"]["email"],
        )

        # Add your custom post-confirmation logic here
        # For example:
        # - Add user to default groups
        # - Create user profile in database
        # - Send welcome email
        # - etc.

        return event

    except Exception as e:
        logger.exception("Error in post confirmation handler")
        raise e
