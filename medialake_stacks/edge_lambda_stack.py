"""Stack for Lambda@Edge function that must be deployed in us-east-1."""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import config
from medialake_constructs.edge_lambda_construct import EdgeLambdaConstruct


class EdgeLambdaStack(Stack):
    """
    Stack that deploys Lambda@Edge function to us-east-1.

    Lambda@Edge functions must be deployed in us-east-1 regardless of
    where the main application stack is deployed. This stack creates
    the edge lambda and exports its version ARN for use by CloudFront
    in the UserInterfaceStack.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create the edge lambda
        edge_lambda = EdgeLambdaConstruct(self, "EdgeLambda")

        # Store lambda version ARN in SSM parameter (in us-east-1)
        # This allows cross-region access from other stacks
        ssm.StringParameter(
            self,
            "EdgeLambdaVersionArnParameter",
            parameter_name=f"/medialake/{config.environment}/edge-lambda-version-arn",
            string_value=edge_lambda.lambda_version.function_arn,
            description="Lambda@Edge function version ARN for CloudFront",
        )

        # Export as CloudFormation output as well
        CfnOutput(
            self,
            "EdgeLambdaVersionArn",
            value=edge_lambda.lambda_version.function_arn,
            export_name="MediaLakeEdgeLambda-VersionArn",
            description="Lambda@Edge version ARN for CloudFront distribution",
        )

        # Store reference for potential property access
        self._edge_lambda = edge_lambda

    @property
    def lambda_version(self):
        """Returns the Lambda@Edge version."""
        return self._edge_lambda.lambda_version
