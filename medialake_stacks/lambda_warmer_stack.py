from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class LambdaWarmerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for warmer state
        self.warmer_table = dynamodb.Table(
            self,
            "WarmerStateTable",
            table_name=f"{construct_id}-warmer-state",
            partition_key=dynamodb.Attribute(
                name="extensionId", type=dynamodb.AttributeType.STRING
            ),
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Create Lambda layer for warmer extension
        self.warmer_layer = lambda_.LayerVersion(
            self,
            "WarmerLayer",
            code=lambda_.Code.from_asset("lambdas/layers/warmer"),
            # compatible_runtimes=[
            #     lambda_.Runtime.PYTHON_3_9,
            #     lambda_.Runtime.NODEJS_18_X,
            # ],
            description="Lambda Warmer Extension Layer",
            layer_version_name=f"{construct_id}-warmer-layer",
        )

        # Create base IAM role for warmed functions
        self.lambda_role = iam.Role(
            self,
            "WarmerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Base role for Lambda functions using the warmer extension",
        )

        # Add permissions to the role
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"],  # Will be limited to self-invocation
                effect=iam.Effect.ALLOW,
            )
        )

        self.warmer_table.grant_read_write_data(self.lambda_role)

        # CloudWatch permissions
        self.lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # Create metric filters for warming events
        # TODO: Add CloudWatch metric filters and alarms

        # Outputs
        CfnOutput(
            self,
            "WarmerTableName",
            value=self.warmer_table.table_name,
            description="DynamoDB table name for warmer state",
        )
        CfnOutput(
            self,
            "WarmerLayerArn",
            value=self.warmer_layer.layer_version_arn,
            description="Lambda layer ARN for warmer extension",
        )

    def add_function_to_warming(self, function: lambda_.Function) -> None:
        """
        Add a Lambda function to the warming configuration.

        Args:
            function: The Lambda function to configure for warming
        """
        # Add warmer layer
        function.add_layers(self.warmer_layer)

        # Grant permissions
        function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[function.function_arn],
                effect=iam.Effect.ALLOW,
            )
        )
        self.warmer_table.grant_read_write_data(function)

        # Add environment variables
        function.add_environment("WARMER_TABLE", self.warmer_table.table_name)
        function.add_environment("EXTENSION_TTL", "300")
        function.add_environment("WARMER_ENABLED", "true")
