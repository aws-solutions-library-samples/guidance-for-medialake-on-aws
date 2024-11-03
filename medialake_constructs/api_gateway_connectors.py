from attr import dataclass
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_dynamodb as dynamodb,
    aws_s3_deployment as s3deploy,
    Duration,
    aws_s3 as s3,
    aws_events as events,
    RemovalPolicy
)
# from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from aws_cdk import Fn, Stack
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)
from dataclasses import dataclass
import os
import shutil
from medialake_constructs.shared_constructs.lam_deployment import LambdaDeployment
from config import config

@dataclass
class ConnectorsProps:
    """Configuration for Lambda function creation."""
    asset_table: dynamodb.TableV2

class ConnectorsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        x_origin_verify_secret: secretsmanager.Secret,
        ingest_event_bus: events.EventBus,
        iac_assets_bucket: s3.Bucket,
        props: ConnectorsProps,
    ) -> None:
        super().__init__(scope, id)
        


        # Use the new LambdaDeployment construct
        self.lambda_deployment = LambdaDeployment(
            self,
            "IngestS3LambdaDeployment",
            destination_bucket=iac_assets_bucket.bucket,
            code_path=["lambdas", "ingest", "s3"]
        )

        dynamo_table = DynamoDB(
            self,
            "ConnectorsTable",
            props=DynamoDBProps(
                name=f"medialake_connector_table_{id}",
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
                # removal_policy=RemovalPolicy.DESTROY
            ),
        )

        # Create connectors resource
        connectors_resource = api_resource.root.add_resource("connectors")
        connectors_get_lambda_config = LambdaConfig(
            name="connectors_get_lambda",
            entry="lambdas/api/connectors/get_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn
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

        # Add KMS decrypt permission for the DynamoDB table's KMS key
        # connectors_get_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["kms:Decrypt"],
        #         resources=[dynamo_table.table.encryption_key],
        #     )
        # )

        connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(connectors_get_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )
        
        #Delete Connector
        connectors_del_lambda_config = LambdaConfig(
            name="connectors_del_lambda",
            entry="lambdas/api/connectors/del_connectors",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (x_origin_verify_secret.secret_arn),
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn
            },
        )
        connectors_del_lambda = Lambda(
            self,
            "ConnectorsDelLambda",
            config=connectors_del_lambda_config,
        )

        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Scan"], resources=[dynamo_table.table_arn]
            )
        )
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"], resources=[dynamo_table.table_arn]
            )
        )

        # Add KMS decrypt permission for the DynamoDB table's KMS key
        # connectors_del_lambda.function.role.add_to_policy(
        #     iam.PolicyStatement(
        #         actions=["kms:Decrypt"],
        #         resources=[dynamo_table.kms_key.key_arn],
        #     )
        # )
        connectors_del_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=['dynamodb:DeleteItem'],
                resources=[dynamo_table.table_arn]
            )
        )

        connectors_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(connectors_del_lambda.function),
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
                "MEDIALAKE_CONNECTOR_TABLE": dynamo_table.table_arn,
                "S3_CONNECTOR_LAMBDA": self.lambda_deployment.deployment_key,
                "IAC_ASSETS_BUCKET": iac_assets_bucket.bucket.bucket_name,
                "INGEST_EVENT_BUS": ingest_event_bus.event_bus_name,
                "MEDIALAKE_ASSET_TABLE": props.asset_table.table_arn,
            },
        )

        connector_s3_post_lambda = Lambda(
            self,
            "ConnectorS3PostLambda",
            config=connector_s3_post_lambda_config,
        )
                
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:GetQueueAttributes",
                    "sqs:CreateQueue",
                    "sqs:DeleteQueue",
                    "sqs:SetQueueAttributes",
                ],
                resources=["*"],
            )
        )
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:DeleteFunction",
                    "lambda:TagResource",
                    "lambda:CreateEventSourceMapping"
                ],
                resources=["*"],
            )
        )
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                    "s3:DeleteBucketNotification",
                ],
                resources=["*"],
            )
        )
        
        connector_s3_post_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:DeleteRole",
                    "iam:UpdateRole",
                    "iam:PutRolePolicy",
                    "iam:AttachRolePolicy",
                    "iam:PassRole",
                    "iam:DeleteRolePolicy",
                    "iam:CreateRole",
                    "iam:TagRole",
                    "iam:DetachRolePolicy"
                ],
                resources=["*"],
            )
        )
        

        
        
        # Grant permissions correctly
        iac_assets_bucket.bucket.grant_read_write(connector_s3_post_lambda.function)

        # Policy for DynamoDB actions on a specific table
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[dynamo_table.table_arn],
            )
        )

        # Policy for S3 actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutBucketNotification",
                ],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Policy for SQS actions
        connector_s3_post_lambda.function.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:CreateQueue",
                    "sns:CreateTopic",
                ],
                resources=["*"],
            )
        )

        connector_s3_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(connector_s3_post_lambda.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )
