from dataclasses import dataclass

from aws_cdk import CfnOutput, Fn, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_s3 as s3
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
    ApiGatewayProps,
)


@dataclass
class ApiGatewayCoreStackProps:
    """Configuration for API Gateway Core Stack."""

    access_log_bucket: s3.Bucket
    cognito_user_pool: cognito.IUserPool


class ApiGatewayCoreStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayCoreStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Store the Cognito User Pool from props
        self._cognito_user_pool = props.cognito_user_pool

        # Create API Gateway construct
        self._api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            props=ApiGatewayProps(
                user_pool=props.cognito_user_pool,
                access_log_bucket=props.access_log_bucket,
                deploy_api=False,
            ),
        )

        # Export the API Gateway ID and root resource ID
        CfnOutput(
            self,
            "ApiGatewayId",
            value=self._api_gateway.rest_api.rest_api_id,
            export_name=f"{self.stack_name}-ApiGatewayId",
        )

        CfnOutput(
            self,
            "RootResourceId",
            value=self._api_gateway.rest_api.rest_api_root_resource_id,
            export_name=f"{self.stack_name}-RootResourceId",
        )

        CfnOutput(
            self,
            "ApiGatwayWAFACLARN",
            value=self._api_gateway.api_gateway_waf_acl.attr_arn,
            export_name=f"{self.stack_name}-ApiGatwayWAFACLARN",
        )

    @property
    def rest_api(self):
        return self._api_gateway.rest_api

    @property
    def cognito_authorizer(self):
        return self._api_gateway.cognito_authorizer

    @property
    def x_origin_verify_secret(self):
        return self._api_gateway.x_origin_verify_secret

    @property
    def user_pool(self) -> cognito.IUserPool:
        return self._cognito_user_pool

    @property
    def user_pool_arn(self):
        # Import from the CognitoStack export
        return Fn.import_value("MediaLakeCognito-UserPoolArn")

    @property
    def identity_pool(self):
        # Import from the CognitoStack export
        return Fn.import_value("MediaLakeCognito-IdentityPoolId")

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        # Since we can't return the actual client object from exports,
        # this will need to be handled differently or removed
        raise NotImplementedError(
            "user_pool_client property not available when using separate Cognito stack"
        )

    @property
    def user_pool_client_id(self):
        # Import from the CognitoStack export
        return Fn.import_value("MediaLakeCognito-UserPoolClientId")

    @property
    def user_pool_id(self):
        # Import from the CognitoStack export
        return Fn.import_value("MediaLakeCognito-UserPoolId")

    @property
    def waf_acl_arn(self):
        return self._api_gateway.api_gateway_waf_acl.attr_arn

    @property
    def cognito_domain_prefix(self):
        # Import from the CognitoStack export
        return Fn.import_value("MediaLakeCognito-CognitoDomainPrefix")

    @property
    def cognito_construct(self):
        # This property is no longer available since Cognito is in a separate stack
        raise NotImplementedError(
            "cognito_construct property not available when using separate Cognito stack"
        )
