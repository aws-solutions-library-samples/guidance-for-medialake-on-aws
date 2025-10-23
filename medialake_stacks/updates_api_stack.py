"""
Updates API Stack for MediaLake Auto-Upgrade System.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_updates import (
    UpdatesConstruct,
    UpdatesConstructProps,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class UpdatesApiStackProps:
    """Configuration for Updates API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret
    system_settings_table_name: str
    system_settings_table_arn: str


class UpdatesApiStack(cdk.NestedStack):
    """
    Stack for MediaLake Auto-Upgrade System API endpoints.

    This stack creates:
    - Single Lambda function with APIGatewayRestResolver for all /updates endpoints
    - API Gateway integration with proxy resources
    - IAM permissions for upgrade operations
    """

    def __init__(
        self, scope: Construct, id: str, props: UpdatesApiStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create the Updates Lambda function
        self.updates_lambda = Lambda(
            self,
            "UpdatesLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}-updates-api-{config.environment}",
                entry="lambdas/api/updates",
                timeout_minutes=5,  # 5 minutes for API operations
                memory_size=512,  # More memory for GitHub API calls and processing
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table_name,
                    "GITHUB_REPO_URL": "https://github.com/aws-solutions-library-samples/guidance-for-medialake-on-aws",
                    "GITHUB_API_TIMEOUT": "30",
                    "ENVIRONMENT": config.environment,
                    "POWERTOOLS_SERVICE_NAME": "medialake-updates-api",
                    "POWERTOOLS_METRICS_NAMESPACE": "MediaLake/Updates",
                    "LOG_LEVEL": "INFO",
                },
            ),
        )

        # Grant DynamoDB permissions to the Lambda function
        # Read/write access to system settings table for version tracking
        self.updates_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    props.system_settings_table_arn,
                    f"{props.system_settings_table_arn}/index/*",
                ],
            )
        )

        # Grant CodePipeline permissions for upgrade triggering
        self.updates_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "codepipeline:StartPipelineExecution",
                    "codepipeline:GetPipeline",
                    "codepipeline:UpdatePipeline",
                    "codepipeline:GetPipelineExecution",
                    "codepipeline:ListPipelineExecutions",
                    "codepipeline:GetPipelineState",
                ],
                resources=[
                    f"arn:aws:codepipeline:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:pipeline/{config.resource_prefix}-*",
                ],
            )
        )

        # Grant EventBridge permissions for scheduled upgrades
        self.updates_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:PutRule",
                    "events:DeleteRule",
                    "events:PutTargets",
                    "events:RemoveTargets",
                    "events:ListRules",
                    "events:DescribeRule",
                ],
                resources=[
                    f"arn:aws:events:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:rule/{config.resource_prefix}-upgrade-*",
                ],
            )
        )

        # Grant Lambda invoke permissions for scheduled upgrades (using wildcard to avoid circular dependency)
        self.updates_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                ],
                resources=[
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:{config.resource_prefix}-updates-api-{config.environment}",
                ],
            )
        )

        # Grant CloudFormation permissions for pipeline updates (if needed)
        self.updates_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:ListStackResources",
                ],
                resources=[
                    f"arn:aws:cloudformation:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:stack/{config.resource_prefix}-*",
                ],
            )
        )

        # Create Updates API Gateway construct
        self.updates_construct = UpdatesConstruct(
            self,
            "UpdatesApiGateway",
            props=UpdatesConstructProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                cognito_user_pool=props.cognito_user_pool,
                cognito_app_client=props.cognito_app_client,
                x_origin_verify_secret=props.x_origin_verify_secret,
                updates_lambda=self.updates_lambda.function,
            ),
        )

        # Output the Lambda function ARN for reference
        cdk.CfnOutput(
            self,
            "UpdatesLambdaArn",
            value=self.updates_lambda.function.function_arn,
            description="ARN of the Updates API Lambda function",
        )

    @property
    def updates_lambda_function(self):
        """Get the Updates Lambda function."""
        return self.updates_lambda.function
