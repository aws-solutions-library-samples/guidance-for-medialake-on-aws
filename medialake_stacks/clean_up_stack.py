import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CustomResource,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr
)
from constructs import Construct

class CleanupStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the cleanup Lambda function
        cleanup_lambda = lambda_.Function(
            self, "CleanupLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_inline(),
            timeout=cdk.Duration.minutes(15)
        )

        # Grant permissions to the Lambda
        cleanup_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'dynamodb:Scan',
                    'dynamodb:GetItem',
                    'dynamodb:DeleteItem'
                ],
                resources=['*']  # Scope this down to specific resources in production
            )
        )

        # Create the Custom Resource that will trigger the cleanup
        provider = cr.Provider(
            self, "CleanupProvider",
            on_event_handler=cleanup_lambda,
        )

        # Create the Custom Resource
        CustomResource(
            self, "CleanupResource",
            service_token=provider.service_token,
            properties={
                "TableName": "your-dynamodb-table-name",  # Replace with your table name
                "Version": "1.0.0"  # Change this to force recreation
            },
            removal_policy=RemovalPolicy.RETAIN  # Important: Retain until cleanup is done
        )