from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cognito as cognito,
    RemovalPolicy,
    CfnOutput
)
import aws_cdk as cdk

from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.cognito import CognitoConstruct, CognitoProps
from medialake_constructs.api_gateway.api_gateway_main_construct import (
    ApiGatewayConstruct,
    ApiGatewayProps,
)


@dataclass
class ApiGatewayCoreStackProps:
    """Configuration for API Gateway Core Stack."""
    access_log_bucket: s3.Bucket


class ApiGatewayCoreStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayCoreStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Cognito construct first
        self._cognito_construct = CognitoConstruct(
            self,
            "Cognito",
            props=CognitoProps(
                self_sign_up_enabled=False,
                auto_verify_email=True,
                auto_verify_phone=True,
                sign_in_with_email=True,
                generate_secret=False,
                admin_user_password=True,
                user_password=True,
                user_srp=True,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # Create API Gateway construct
        self._api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            props=ApiGatewayProps(
                user_pool=self._cognito_construct.user_pool,
                access_log_bucket=props.access_log_bucket,
                deploy_api=False,
            ),
        )
        
        # Export the API Gateway ID and root resource ID
        CfnOutput(self, "ApiGatewayId", 
            value=self._api_gateway.rest_api.rest_api_id,
            export_name=f"{self.stack_name}-ApiGatewayId"
        )
        
        CfnOutput(self, "RootResourceId", 
            value=self._api_gateway.rest_api.rest_api_root_resource_id,
            export_name=f"{self.stack_name}-RootResourceId"
        )
        
        CfnOutput(self, "ApiGatwayWAFACLARN", 
            value=self._api_gateway.api_gateway_waf_acl.attr_arn,
            export_name=f"{self.stack_name}-ApiGatwayWAFACLARN"
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
    def user_pool(self):
        return self._cognito_construct.user_pool

    @property
    def user_pool_arn(self):
        return self._cognito_construct.user_pool_arn
    
    @property
    def identity_pool(self):
        return self._cognito_construct.identity_pool
    
    @property
    def user_pool_client(self):
        return self._cognito_construct.user_pool_client
    
    @property
    def user_pool_id(self):
        return self._cognito_construct.user_pool_id
        
    @property
    def waf_acl_arn(self):
        return self._api_gateway.api_gateway_waf_acl.attr_arn 