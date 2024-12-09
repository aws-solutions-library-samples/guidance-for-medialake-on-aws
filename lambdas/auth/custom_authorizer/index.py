from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
import os
import json
import time
import boto3
import jwt
import urllib.request
from jwt.algorithms import RSAAlgorithm

logger = Logger(service="custom-authorizer")
tracer = Tracer(service="custom-authorizer")
metrics = Metrics(namespace="CustomAuthorizer")


@tracer.capture_method
def get_cognito_public_keys(region, user_pool_id):
    url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    with urllib.request.urlopen(url) as response:
        keys = json.loads(response.read())["keys"]
    return {key["kid"]: RSAAlgorithm.from_jwk(json.dumps(key)) for key in keys}


@tracer.capture_method
def validate_jwt(token, region, user_pool_id, public_keys):
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]
        public_key = public_keys.get(kid)

        if not public_key:
            logger.warning("Invalid KID in token")
            return False

        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_exp": True},
            audience=os.environ["USER_POOL_CLIENT_ID"],
        )

        logger.info(
            "JWT validation successful",
            extra={
                "user_pool_id": user_pool_id,
                "token_use": claims.get("token_use"),
                "auth_time": claims.get("auth_time"),
            },
        )
        return True
    except Exception as e:
        logger.warning("JWT validation failed", extra={"error_type": type(e).__name__})
        return False


@tracer.capture_method
def validate_api_key(api_key):
    try:
        client = boto3.client("apigateway")
        response = client.get_api_key(
            apiKey=api_key, includeValue=False  # Never log API key values
        )

        logger.info(
            "API key validation successful",
            extra={
                "key_id": response["id"],
                "key_name": response["name"],
                "enabled": response["enabled"],
            },
        )
        return response["enabled"]
    except Exception as e:
        logger.warning(
            "API key validation failed", extra={"error_type": type(e).__name__}
        )
        return False


def generate_policy(principal_id, effect, resource):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}
            ],
        },
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    try:
        auth_header = event.get("authorizationToken", "")
        method_arn = event["methodArn"]

        auth_type = "api_key" if auth_header.startswith("ApiKey ") else "jwt"
        logger.info(
            "Processing authorization request",
            extra={"method_arn": method_arn, "auth_type": auth_type},
        )

        metrics.add_metric(name="AuthorizationAttempt", unit=MetricUnit.Count, value=1)
        metrics.add_dimension(name="AuthType", value=auth_type)

        if auth_header.startswith("ApiKey "):
            api_key = auth_header.split(" ")[1]
            if validate_api_key(api_key):
                metrics.add_metric(
                    name="SuccessfulAuth", unit=MetricUnit.Count, value=1
                )
                response = generate_policy("apikey_user", "Allow", method_arn)
                response["context"] = {"auth_type": "api_key"}
                return response

        elif auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            region = os.environ["AWS_REGION"]
            user_pool_id = os.environ["USER_POOL_ID"]

            public_keys = get_cognito_public_keys(region, user_pool_id)

            if validate_jwt(token, region, user_pool_id, public_keys):
                metrics.add_metric(
                    name="SuccessfulAuth", unit=MetricUnit.Count, value=1
                )
                response = generate_policy("cognito_user", "Allow", method_arn)
                response["context"] = {"auth_type": "jwt"}
                return response

        metrics.add_metric(name="FailedAuth", unit=MetricUnit.Count, value=1)
        return generate_policy("user", "Deny", method_arn)

    except Exception as e:
        logger.exception("Authorization failed")
        metrics.add_metric(name="AuthorizationError", unit=MetricUnit.Count, value=1)
        return generate_policy("user", "Deny", method_arn)
