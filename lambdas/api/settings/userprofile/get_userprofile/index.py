import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

# Initialize PowerTools
logger = Logger(service="user-profile-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="user-profile-service")
metrics = Metrics(namespace="MediaLake", service="user-profile-service")
app = APIGatewayRestResolver()


class UserProfileResponse(BaseModel):
    """Response model for user profile data"""

    username: str
    user_id: str
    email: str
    given_name: str | None = None
    family_name: str | None = None
    custom_settings: Dict[str, Any] | None = None


@tracer.capture_method
def extract_user_claims(event: APIGatewayProxyEvent) -> Dict[str, Any]:
    """
    Extract and validate user claims from the request context
    """
    try:
        authorizer_context = event.request_context.authorizer
        claims = authorizer_context.get("claims", {})

        if not claims:
            logger.error("No claims found in authorizer context")
            raise ValueError("No authorization claims found")

        logger.debug("Extracted user claims", extra={"claims": claims})
        return claims
    except Exception as e:
        logger.error("Failed to extract user claims", extra={"error": str(e)})
        raise ValueError("Invalid authorization context")


@tracer.capture_method
def validate_user_access(route_user_id: str, claims: Dict[str, Any]) -> bool:
    """
    Validate that the requesting user has access to the requested user profile
    """
    try:
        # Get the user ID from the claims
        token_user_id = claims.get("sub")

        if not token_user_id:
            logger.error("No user ID found in token claims")
            return False

        # Check if the user ID in the route matches the token
        is_authorized = route_user_id == token_user_id

        if not is_authorized:
            logger.warning(
                "User ID mismatch",
                extra={"route_user_id": route_user_id, "token_user_id": token_user_id},
            )

        return is_authorized
    except Exception as e:
        logger.error("Error validating user access", extra={"error": str(e)})
        return False


@tracer.capture_method
def build_user_profile(user_id: str, claims: Dict[str, Any]) -> UserProfileResponse:
    """
    Build user profile from claims
    """
    try:
        profile = UserProfileResponse(
            username=claims.get("cognito:username"),
            user_id=user_id,
            email=claims.get("email"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            custom_settings=claims.get("custom:settings"),
        )

        logger.debug("Built user profile", extra={"profile": profile.dict()})
        return profile
    except Exception as e:
        logger.error("Failed to build user profile", extra={"error": str(e)})
        raise ValueError("Invalid user profile data")


@app.get("/settings/user/<user_id>")
@tracer.capture_method
def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Get user profile endpoint handler
    """
    try:
        # Extract current request event
        event = app.current_event

        # Extract user claims from the request
        claims = extract_user_claims(event)

        # Validate user access
        if not validate_user_access(user_id, claims):
            metrics.add_metric(
                name="UnauthorizedAccessAttempts", unit=MetricUnit.Count, value=1
            )
            return {"statusCode": 403, "body": {"error": "Unauthorized access"}}

        # Build user profile
        profile = build_user_profile(user_id, claims)

        # Record metric for successful profile retrieval
        metrics.add_metric(
            name="SuccessfulProfileRetrievals", unit=MetricUnit.Count, value=1
        )

        logger.info(
            "Successfully retrieved user profile",
            extra={"username": profile.username, "user_id": user_id},
        )

        return {"statusCode": 200, "body": profile.dict()}

    except ValueError as ve:
        logger.error("Validation error in get_user_profile", extra={"error": str(ve)})
        metrics.add_metric(
            name="ProfileRetrievalErrors", unit=MetricUnit.Count, value=1
        )
        return {"statusCode": 400, "body": {"error": str(ve)}}
    except Exception as e:
        logger.error("Unexpected error in get_user_profile", extra={"error": str(e)})
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return {"statusCode": 500, "body": {"error": "Internal server error"}}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for user profile API
    """
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.error("Failed to process request", extra={"error": str(e)})
        return {"statusCode": 500, "body": {"error": "Internal server error"}}
