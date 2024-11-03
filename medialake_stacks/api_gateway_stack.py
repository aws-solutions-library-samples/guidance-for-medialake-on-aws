from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
)
from constructs import Construct
from medialake_constructs.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.api_gateway import (
    ConnectorsConstruct,
)
from medialake_constructs.api_gateway_pipelines import (
    PipelinesConstruct,
)



class ApiGatewayStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        id: str, 
        user_pool: cognito.UserPool,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create main API Gateway construct using provided user pool
        self.api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=user_pool,
        )

        # Create Lambda execution role
        lambda_execution_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Add necessary permissions to Lambda role
        lambda_execution_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListAllMyBuckets"],
                resources=["*"],
            )
        )

        # Create connectors construct
        _ = ConnectorsConstruct(
            self,
            "Connectors",
            api_resource=self.api_gateway.api_resource,
            cognito_authorizer=self.api_gateway.cognito_authorizer,
            lambda_execution_role=lambda_execution_role,
            x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            iac_assets_bucket = self.iac_assets_bucket
        )

        # Create pipelines construct
        _ = PipelinesConstruct(
            self,
            "Pipelines",
            api_resource=self.api_gateway.api_resource,
            cognito_authorizer=self.api_gateway.cognito_authorizer,
            lambda_execution_role=lambda_execution_role,
            x_origin_verify_secret=self.api_gateway.x_origin_verify_secret,
            iac_assets_bucket = self.iac_assets_bucket
            media_assets_bucket = self.media_assets_bucket
        )
