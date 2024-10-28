from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBConfig,
)


class ConnectorsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        lambda_execution_role: iam.Role,
        x_origin_verify_secret: secretsmanager.Secret,
    ) -> None:
        super().__init__(scope, id)

        dynamo_config = DynamoDBConfig(
            name="connectors",
            partition_key_name="id",
            partition_key_type=dynamodb.AttributeType.STRING,
        )
        dynamo_table = DynamoDB(
            self,
            "ConnectorsTable",
            config=dynamo_config,
        )

        # Create connectors resource
        connectors_resource = api_resource.root.add_resource("connectors")
        connectors_get_lambda_config = LambdaConfig(
            name="connectors_get_lambda",
            entry="lambdas/api/connectors/get_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
            },
        )
        connectors_get_lambda = Lambda(
            self,
            "ConnectorsGetLambda",
            config=connectors_get_lambda_config,
        )

        connectors_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
            )
        )

        connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connectors_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Create s3list resource and Lambda function
        s3list_resource = connectors_resource.add_resource("s3list")
        s3list_lambda_config = LambdaConfig(
            name="s3list",
            entry="lambdas/api/connectors/s3list",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
            },
        )
        s3list_handler = Lambda(
            self,
            "S3ListHandler",
            config=s3list_lambda_config,
        )

        s3list_handler.function.role.add_to_policy(
            iam.PolicyStatement(actions=["s3:ListAllMyBuckets"], resources=["*"])
        )

        s3list_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(s3list_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Create s3connector resource and Lambda function
        connector_s3_resource = connectors_resource.add_resource("s3")

        connector_s3_get_lambda_config = LambdaConfig(
            name="connector_s3_get",
            entry="lambdas/api/connectors/s3/get_s3",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
            },
        )
        connector_s3_get_lambda = Lambda(
            self,
            "ConnectorS3GetLambda",
            config=connector_s3_get_lambda_config,
        )

        connector_s3_get_lambda.function.role.add_to_policy(
            iam.PolicyStatement(actions=["s3:ListAllMyBuckets"], resources=["*"])
        )

        connector_s3_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connector_s3_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        connector_s3_post_lambda_config = LambdaConfig(
            name="connector_s3_post",
            entry="lambdas/api/connectors/s3/post_s3",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": x_origin_verify_secret.secret_arn,
                "DYNAMO_TABLE_ARN": dynamo_table.table_arn,
            },
        )

        connector_s3_post_lambda = Lambda(
            self,
            "ConnectorS3PostLambda",
            config=connector_s3_post_lambda_config,
        )

        # Policy for DynamoDB actions on a specific table
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[dynamo_table.table_arn],  # Specific DynamoDB table
            )
        )

        # Policy for S3 actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",  # Allow subscribing S3 buckets to SQS/SNS
                ],
                resources=["arn:aws:s3:::*"],  # Correct resource ARN for S3
            )
        )

        # Policy for SQS actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:CreateQueue",
                    "sns:CreateTopic",  # Allow creating SQS queues
                ],
                resources=["*"],  # Allow on all resources
            )
        )

        connector_s3_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(connector_s3_post_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )
