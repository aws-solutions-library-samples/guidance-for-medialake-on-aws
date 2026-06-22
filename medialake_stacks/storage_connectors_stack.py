from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_pipes as pipes
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import (
    CommonLibrariesLayer,
    IngestMediaProcessorLayer,
)
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3BucketProps
from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class StorageConnectorsStackProps:
    """Configuration for Storage Connectors Stack."""

    cloudfront_domain_ssm_param: str
    # Ingest Lambda dependencies
    asset_table_arn: str
    pipelines_event_bus_name: str
    opensearch_endpoint: str
    opensearch_index: str
    vpc: ec2.IVpc
    security_group: ec2.SecurityGroup
    s3_vector_bucket_name: str
    s3_vector_index_name: str
    system_settings_table_name: str


class StorageConnectorsStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: StorageConnectorsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create SQS DLQ for API Gateway
        self.storage_ingest_connector_dlq = SQSConstruct(
            self,
            "StorageIngestConnectorDLQ",
            props=SQSProps(
                queue_name="storage-ingest-connector-dlq",
                visibility_timeout=Duration.seconds(60),
                retention_period=Duration.days(14),
                encryption=True,
                fifo=True,
                content_based_deduplication=True,
                enforce_ssl=True,
                max_receive_count=0,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # --- Personal Assets Bucket (Step 1) ---
        # S3 CORS uses a permissive wildcard origin. Actual access control is enforced
        # by presigned URLs and the API/Lambda layer (which reads the CloudFront domain
        # from SSM at runtime). This avoids a deploy-time dependency on the SSM parameter
        # /medialake/{env}/cloudfront-distribution-domain which is created by the
        # UserInterface stack and may not exist on first deploy.
        self._personal_assets_bucket = S3Bucket(
            self,
            "PersonalAssetsBucket",
            props=S3BucketProps(
                bucket_name=(
                    f"{config.resource_prefix}-personal-assets-"
                    f"{config.account_id[:7]}-{config.primary_region}-"
                    f"{config.environment}"
                ).lower(),
                destroy_on_delete=True,
                versioned=False,
                cors=[
                    s3.CorsRule(
                        allowed_methods=[
                            s3.HttpMethods.GET,
                            s3.HttpMethods.PUT,
                            s3.HttpMethods.POST,
                            s3.HttpMethods.DELETE,
                            s3.HttpMethods.HEAD,
                        ],
                        allowed_origins=["*"],
                        allowed_headers=["*"],
                        exposed_headers=["ETag"],
                    )
                ],
            ),
        )

        # --- Ingest SQS Queue (Step 2) ---
        self._personal_assets_ingest_queue = SQSConstruct(
            self,
            "PersonalAssetsIngestQueue",
            props=SQSProps(
                queue_name="personal-assets-ingest",
                # Must exceed the ingest Lambda's 15-min timeout so a full
                # (batched) invocation finishes before messages become visible
                # again and get redelivered/duplicated. 960s = 900s Lambda
                # timeout + 60s buffer for the Pipe batching window + overhead.
                visibility_timeout=Duration.seconds(960),
                retention_period=Duration.days(14),
                encryption=True,
                enforce_ssl=True,
                max_receive_count=3,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        self._personal_assets_ingest_queue.queue.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                actions=["sqs:SendMessage"],
                resources=[self._personal_assets_ingest_queue.queue_arn],
                conditions={
                    "ArnLike": {
                        "aws:SourceArn": self._personal_assets_bucket.bucket_arn
                    }
                },
            )
        )

        if self._personal_assets_ingest_queue.encryption_key:
            self._personal_assets_ingest_queue.encryption_key.grant_encrypt_decrypt(
                iam.ServicePrincipal("s3.amazonaws.com")
            )

        # --- S3 Event Notification → SQS (Step 3) ---
        self._personal_assets_bucket.concrete_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(self._personal_assets_ingest_queue.queue),
            s3.NotificationKeyFilter(prefix="personal/"),
        )

        # --- Ingest Lambda for personal bucket ---
        ingest_media_processor_layer = IngestMediaProcessorLayer(
            self, "PersonalIngestMediaProcessorLayer"
        )
        common_libraries_layer = CommonLibrariesLayer(
            self, "PersonalIngestCommonLibrariesLayer"
        )

        self._ingest_lambda = Lambda(
            self,
            "PersonalAssetsIngestLambda",
            config=LambdaConfig(
                name="personal_assets_ingest",
                entry="lambdas/ingest/s3",
                memory_size=10240,
                timeout_minutes=15,
                lambda_handler="handler",
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[
                    ingest_media_processor_layer.layer,
                    common_libraries_layer.layer,
                ],
                environment_variables={
                    "PIPELINES_EVENT_BUS": props.pipelines_event_bus_name,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table_arn,
                    "ASSETS_TABLE": props.asset_table_arn,
                    "EVENT_BUS_NAME": props.pipelines_event_bus_name,
                    "DO_NOT_INGEST_DUPLICATES": "True",
                    # Process a batched Pipe payload concurrently. Memory-safe:
                    # each record streams its object (chunked MD5), never loading
                    # the whole file, so concurrent large files do not risk OOM.
                    "INGEST_MAX_WORKERS": "10",
                    "OPENSEARCH_ENDPOINT": props.opensearch_endpoint,
                    "INDEX_NAME": props.opensearch_index,
                    "OPENSEARCH_SERVICE": "es",
                    "REGION": Stack.of(self).region,
                    "VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
                    "VECTOR_INDEX_NAME": props.s3_vector_index_name,
                    "SYSTEM_SETTINGS_TABLE": props.system_settings_table_name,
                },
            ),
        )

        # Grant ingest Lambda permissions
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[props.asset_table_arn, f"{props.asset_table_arn}/index/*"],
            )
        )
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                ],
                resources=[
                    self._personal_assets_bucket.bucket_arn,
                    f"{self._personal_assets_bucket.bucket_arn}/*",
                ],
            )
        )
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/{props.pipelines_event_bus_name}",
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/default",
                ],
            )
        )
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:ESHttpHead",
                ],
                resources=[
                    f"arn:aws:es:{Stack.of(self).region}:{Stack.of(self).account}:domain/*"
                ],
            )
        )
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=["*"],
            )
        )
        self._ingest_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # --- EventBridge Pipe: SQS → Ingest Lambda (Step 4) ---
        ingest_lambda_arn = self._ingest_lambda.function.function_arn

        pipe_role = iam.Role(
            self,
            "PersonalAssetsIngestPipeRole",
            assumed_by=iam.ServicePrincipal("pipes.amazonaws.com"),
        )

        pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ],
                resources=[self._personal_assets_ingest_queue.queue_arn],
            )
        )
        pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[ingest_lambda_arn],
            )
        )
        if self._personal_assets_ingest_queue.encryption_key:
            pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["kms:Decrypt"],
                    resources=[
                        self._personal_assets_ingest_queue.encryption_key.key_arn
                    ],
                )
            )

        pipes.CfnPipe(
            self,
            "PersonalAssetsIngestPipe",
            role_arn=pipe_role.role_arn,
            source=self._personal_assets_ingest_queue.queue_arn,
            target=ingest_lambda_arn,
            source_parameters=pipes.CfnPipe.PipeSourceParametersProperty(
                sqs_queue_parameters=pipes.CfnPipe.PipeSourceSqsQueueParametersProperty(
                    # Batch uploads so the ingest Lambda's existing parallel
                    # record processor (INGEST_MAX_WORKERS) is utilized instead
                    # of one cold-start-prone invocation per object. Concurrency
                    # (and thus memory) is bounded inside the handler, and the
                    # batching window keeps single-upload latency low.
                    batch_size=10,
                    maximum_batching_window_in_seconds=5,
                )
            ),
        )

        # --- SSM Parameter for bucket name (Step 6) ---
        ssm.StringParameter(
            self,
            "PersonalAssetsBucketNameParam",
            parameter_name=f"/medialake/{config.environment}/personal-assets-bucket-name",
            string_value=self._personal_assets_bucket.bucket_name,
            description="MediaLake Personal Assets Bucket Name",
        )

    # --- Stack Properties (Step 7) ---
    @property
    def storage_ingest_connector_dlq_url(self) -> str:
        return self.storage_ingest_connector_dlq.queue_url

    @property
    def storage_ingest_connector_dlq_arn(self) -> str:
        return self.storage_ingest_connector_dlq.queue_arn

    @property
    def storage_ingest_connector_dlq_name(self) -> str:
        return self.storage_ingest_connector_dlq.queue_name

    @property
    def personal_assets_bucket(self) -> s3.IBucket:
        return self._personal_assets_bucket.bucket

    @property
    def personal_assets_bucket_name(self) -> str:
        return self._personal_assets_bucket.bucket_name
