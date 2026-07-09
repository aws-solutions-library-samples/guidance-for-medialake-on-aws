"""
Collections API Gateway module for MediaLake.

This module defines the CollectionsApi class which sets up API Gateway endpoints
and a consolidated Lambda function for managing collections using Lambda Powertools routing.

The module handles:
- Collection types and metadata management
- Collection item management with batch operations
- Collection rules for automatic item assignment
- Collection sharing and permissions
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_secretsmanager as secrets_manager
from aws_cdk import aws_sns as sns
from aws_cdk import custom_resources as cr
from constructs import Construct

from constants import Lambda as LambdaConstants
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
from medialake_constructs.shared_constructs.s3bucket import S3Bucket
from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class CollectionsApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer
    open_search_endpoint: str
    open_search_arn: str
    opensearch_index: str
    vpc: ec2.IVpc
    security_group: ec2.SecurityGroup
    media_assets_bucket: S3Bucket
    asset_table: dynamodb.ITable  # For copying asset thumbnails to collections
    # Internal application-service-events bus delivering AssetDeleted events.
    asset_events_bus: events.IEventBus
    cognito_user_pool: Optional[cognito.UserPool] = (
        None  # For /collections/users endpoint
    )


class CollectionsApi(Construct):
    """
    Collections API Gateway deployment with single Lambda and routing
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: CollectionsApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        from config import config

        # Get the current account ID
        Stack.of(self).account

        # Create single Collections table with GSIs following the schema design
        gsi_list = [
            # GSI1: UserCollectionsGSI - Find all collections a user has access to
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="UserCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI1_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI1_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI2: ItemCollectionsGSI - Find all collections containing a specific item
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ItemCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI2_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI2_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI3: CollectionTypeGSI - Find collections by type
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="CollectionTypeGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI3_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI3_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI4: ParentChildGSI - Find all parent collections of a child collection
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ParentChildGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI4_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI4_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI5: RecentlyModifiedGSI - Find recently modified collections system-wide
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="RecentlyModifiedGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI5_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI5_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI6: SharesGrantedByGSI - Find all shares granted by a specific user
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="SharesGrantedByGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI6_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI6_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
        ]

        self._collections_table = DynamoDB(
            self,
            "CollectionsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_collections_{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                global_secondary_indexes=gsi_list,
                ttl_attribute="expiresAt",
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            ),
        )

        # Get environment for SSM parameter path
        from config import config

        # Create single consolidated Collections Lambda with routing
        # High-traffic API with VPC access needs higher memory
        collections_lambda = Lambda(
            self,
            "CollectionsLambda",
            config=LambdaConfig(
                name="collections_api",
                entry="lambdas/api/collections_api",
                vpc=props.vpc,
                security_groups=[props.security_group],
                memory_size=1024,  # VPC Lambdas need more memory for ENI setup
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.opensearch_index,
                    "SCOPE": "es",
                    "ENVIRONMENT": config.environment,
                    # Needed by url_utils._get_cloudfront_domain() to resolve the
                    # CloudFront domain SSM parameter (/{prefix}/{env}/cloudfront-
                    # distribution-domain). Without this it falls back to
                    # "/medialake/{env}", the wrong path for custom resource
                    # prefixes, so collection thumbnail URLs come back null.
                    "SSM_PREFIX": config.ssm_prefix,
                    "COLLECTIONS_INDEX_NAME": f"{config.resource_prefix}_collections_{config.environment}",
                    "MEDIA_ASSETS_BUCKET_NAME": props.media_assets_bucket.bucket.bucket_name,
                    "MEDIALAKE_ASSET_TABLE": props.asset_table.table_name,
                    # User table holds per-user favorites; the collection-delete
                    # path cleans up favorite rows referencing the deleted collection.
                    "USER_TABLE_NAME": f"{config.resource_prefix}-user-{config.environment}",
                    # Cognito user pool for /collections/users endpoint
                    # Allows sharing UI to list users without requiring users:view
                    **(
                        {
                            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
                        }
                        if props.cognito_user_pool
                        else {}
                    ),
                },
            ),
        )

        # Lambda warming for collections API (replaces provisioned concurrency)
        events.Rule(
            self,
            "CollectionsLambdaWarmerRule",
            schedule=events.Schedule.rate(
                Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
            ),
            targets=[
                targets.LambdaFunction(
                    collections_lambda.function,
                    event=events.RuleTargetInput.from_object({"lambda_warmer": True}),
                ),
            ],
            description="Keeps collections API Lambda warm via scheduled EventBridge rule.",
        )

        # Grant DynamoDB permissions
        self._collections_table.table.grant_read_write_data(collections_lambda.function)

        # Grant read access to asset table (for copying asset thumbnails)
        props.asset_table.grant_read_data(collections_lambda.function)

        # User table access for the collections Lambda:
        # 1. Collection-delete path cleans up favorite rows (GSI4 query + delete)
        # 2. Recent endpoint queries GSI4 for per-user recent collections (read).
        #    GSI4 is overloaded: FAVCOLLECTION# rows back favorite cleanup and
        #    USER# rows back the recent-collections list on the same index.
        # 3. Add/remove item handlers write activity records via
        #    record_collection_activity (UpdateItem/PutItem)
        # Granted by name/ARN to avoid a cross-stack table dependency.
        _user_table_arn = Stack.of(self).format_arn(
            service="dynamodb",
            resource="table",
            resource_name=f"{config.resource_prefix}-user-{config.environment}",
        )
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:DeleteItem",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[
                    _user_table_arn,
                    f"{_user_table_arn}/index/GSI4",
                ],
            )
        )

        # ------------------------------------------------------------------
        # Asset deletion cleanup consumer
        # ------------------------------------------------------------------
        # When an asset is deleted elsewhere in MediaLake an "AssetDeleted"
        # event is published to the internal application-service-events bus.
        # This Lambda removes the asset (full file + any clips) from every
        # collection that referenced it, preventing orphaned collection items.
        asset_cleanup_lambda = Lambda(
            self,
            "CollectionsAssetCleanupLambda",
            config=LambdaConfig(
                name="collections_asset_deleted_cleanup",
                entry="lambdas/collections/asset_deleted_cleanup",
                memory_size=256,
                timeout_minutes=5,
                environment_variables={
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                },
            ),
        )

        # Cleanup Lambda scans the collections table by asset id and deletes
        # matching item rows.
        self._collections_table.table.grant_read_write_data(
            asset_cleanup_lambda.function
        )

        # Route AssetDeleted events from the internal bus to the cleanup Lambda
        events.Rule(
            self,
            "CollectionsAssetDeletedRule",
            event_bus=props.asset_events_bus,
            description=(
                "Removes deleted assets from all collections when an "
                "AssetDeleted event is published to the internal bus."
            ),
            event_pattern=events.EventPattern(
                source=["medialake.assets"],
                detail_type=["AssetDeleted"],
            ),
            targets=[targets.LambdaFunction(asset_cleanup_lambda.function)],
        )

        # Grant Cognito permissions for /collections/users endpoint
        if props.cognito_user_pool:
            collections_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cognito-idp:ListUsers",
                    ],
                    resources=[props.cognito_user_pool.user_pool_arn],
                )
            )

        # Grant VPC network interface permissions for Lambda in VPC
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add OpenSearch read permissions to the Lambda
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                    "es:DescribeElasticsearchDomain",
                    "es:ListDomainNames",
                    "es:ESHttpHead",
                ],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add S3 and KMS permissions for generating CloudFront URLs and uploading thumbnails
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:PutObject",  # For uploading collection thumbnails
                    "s3:DeleteObject",  # For removing collection thumbnails
                    "s3:CopyObject",  # For copying asset thumbnails
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                ],
                resources=[
                    f"{props.media_assets_bucket.bucket.bucket_arn}/*",
                    f"{props.media_assets_bucket.bucket.bucket_arn}",
                    props.media_assets_bucket.kms_key.key_arn,
                ],
            )
        )

        # Add SSM GetParameter permissions for CloudFront domain retrieval
        collections_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter{config.ssm_prefix}/*"
                ],
            )
        )

        # Create Lambda integration
        collections_integration = api_gateway.LambdaIntegration(
            collections_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # /collection-types resource
        collection_types_resource = props.api_resource.root.add_resource(
            "collection-types"
        )

        collection_types_method = collection_types_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_types_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections resource
        collections_resource = props.api_resource.root.add_resource("collections")

        # Add ANY method to /collections for list and create operations
        collections_method = collections_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collections_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/shared-with-me (static route must come before variable route)
        shared_with_me_resource = collections_resource.add_resource("shared-with-me")
        shared_with_me_method = shared_with_me_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = shared_with_me_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/shared-by-me (static route must come before variable route)
        shared_by_me_resource = collections_resource.add_resource("shared-by-me")
        shared_by_me_method = shared_by_me_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = shared_by_me_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/collection-types (static route — returns types under collections:view)
        collection_types_sub_resource = collections_resource.add_resource(
            "collection-types"
        )
        collection_types_sub_method = collection_types_sub_resource.add_method(
            "GET",
            collections_integration,
        )
        cfn_method = collection_types_sub_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/users (static route — returns user summaries under collections:edit)
        collections_users_resource = collections_resource.add_resource("users")
        collections_users_method = collections_users_resource.add_method(
            "GET",
            collections_integration,
        )
        cfn_method = collections_users_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId} - Variable path for specific collections
        collection_id_resource = collections_resource.add_resource("{collectionId}")

        # Add ANY method to /collections/{collectionId}
        collection_id_method = collection_id_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_id_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/{proxy+} - Catch all sub-resources
        collection_proxy_resource = collection_id_resource.add_resource("{proxy+}")

        collection_proxy_method = collection_proxy_resource.add_method(
            "ANY",
            collections_integration,
        )
        cfn_method = collection_proxy_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(collection_types_resource)
        add_cors_options_method(collections_resource)
        add_cors_options_method(shared_with_me_resource)
        add_cors_options_method(shared_by_me_resource)
        add_cors_options_method(collection_types_sub_resource)
        add_cors_options_method(collections_users_resource)
        add_cors_options_method(collection_id_resource)
        add_cors_options_method(collection_proxy_resource)

        # =====================================================================
        # Collections DynamoDB-to-OpenSearch Sync Pipeline
        # Follows the AssetTableStream pattern from asset_table_stream.py
        # =====================================================================

        stack = Stack.of(self)

        # Collections index name following the environment naming pattern
        collections_index_name = (
            f"{config.resource_prefix}_collections_{config.environment}"
        )

        # --- Task 3.4: Create SQS DLQ for failed sync events ---
        # Visibility timeout must be >= Lambda timeout (15 min) + buffer
        self._collections_sync_dlq = SQSConstruct(
            self,
            "CollectionsSyncDLQ",
            props=SQSProps(
                queue_name="collections-sync-dlq",
                visibility_timeout=Duration.minutes(
                    20
                ),  # 15 min Lambda timeout + 5 min buffer
                retention_period=Duration.days(14),
                encryption=False,  # Use SSE-SQS (AWS managed) for consistency
                enforce_ssl=True,
                max_receive_count=0,  # No DLQ for this queue as it's already a DLQ
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        # --- Task 3.2: Create Sync Lambda ---
        search_layer = SearchLayer(self, "CollectionsSyncSearchLayer")

        self._collections_sync_lambda = Lambda(
            self,
            "CollectionsSyncLambda",
            LambdaConfig(
                name="collections-sync",
                entry="lambdas/sync/collections_sync",
                timeout_minutes=15,
                memory_size=2048,
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "COLLECTIONS_INDEX_NAME": collections_index_name,
                    "OS_DOMAIN_REGION": stack.region,
                },
                reserved_concurrent_executions=5,
            ),
        )

        # --- Task 3.3: Add DynamoDB Stream event source ---
        # NOTE: StartingPosition.LATEST means any writes between stream enablement
        # and event source creation are missed. This is acceptable because the
        # backfill lambda (triggered on initial deployment) indexes all existing
        # records. If the event source mapping is ever recreated, re-run the
        # backfill to close the gap.
        self._collections_sync_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._collections_table.table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                bisect_batch_on_error=True,
                report_batch_item_failures=True,
                on_failure=lambda_event_sources.SqsDlq(
                    self._collections_sync_dlq.queue
                ),
            )
        )

        # --- Task 3.6: Grant Sync Lambda IAM permissions ---
        # OpenSearch permissions (domain-level + index-level)
        self._collections_sync_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpHead",
                    "es:ESHttpPost",
                    "es:ESHttpGet",
                    "es:ESHttpPut",
                    "es:ESHttpDelete",
                ],
                resources=[
                    props.open_search_arn,
                    f"{props.open_search_arn}/*",
                ],
            )
        )

        # DynamoDB Stream permissions
        self._collections_table.table.grant_stream_read(
            self._collections_sync_lambda.function
        )

        # SQS permissions for DLQ
        self._collections_sync_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[self._collections_sync_dlq.queue_arn],
            )
        )

        # EC2 permissions for VPC Lambda
        self._collections_sync_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # --- Task 3.5: Create Backfill Lambda ---
        self._collections_backfill_lambda = Lambda(
            self,
            "CollectionsBackfillLambda",
            LambdaConfig(
                name="collections-backfill",
                entry="lambdas/sync/collections_backfill",
                timeout_minutes=15,
                memory_size=2048,
                vpc=props.vpc,
                security_groups=[props.security_group],
                layers=[search_layer.layer],
                environment_variables={
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "COLLECTIONS_INDEX_NAME": collections_index_name,
                    "OS_DOMAIN_REGION": stack.region,
                },
            ),
        )

        # Grant Backfill Lambda read permissions on Collections table
        self._collections_table.table.grant_read_data(
            self._collections_backfill_lambda.function
        )

        # Grant Backfill Lambda OpenSearch write permissions
        self._collections_backfill_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "es:ESHttpHead",
                    "es:ESHttpPost",
                    "es:ESHttpGet",
                    "es:ESHttpPut",
                ],
                resources=[
                    props.open_search_arn,
                    f"{props.open_search_arn}/*",
                ],
            )
        )

        # EC2 permissions for VPC Lambda
        self._collections_backfill_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # --- Trigger Backfill once on initial deploy ---
        # Uses AwsCustomResource to invoke the backfill Lambda via the AWS SDK
        # on CREATE only. Subsequent deploys skip it (no properties change).
        cr.AwsCustomResource(
            self,
            "CollectionsBackfillTrigger",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": self._collections_backfill_lambda.function.function_name,
                    "InvocationType": "Event",  # Async — don't wait for completion
                    "Payload": '{"RequestType": "Create"}',
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "collections-backfill-trigger"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["lambda:InvokeFunction"],
                        resources=[
                            self._collections_backfill_lambda.function.function_arn
                        ],
                    )
                ]
            ),
        )

        # --- Task 3.7: Create CloudWatch alarm on DLQ depth ---
        collections_sync_dlq_alarm_topic = sns.Topic(
            self,
            "CollectionsSyncDLQAlarmTopic",
            display_name="Collections Sync DLQ Alarm",
        )

        collections_sync_dlq_alarm = cloudwatch.Alarm(
            self,
            "CollectionsSyncDLQAlarm",
            metric=self._collections_sync_dlq.queue.metric_approximate_number_of_messages_visible(),
            threshold=10,
            evaluation_periods=1,
            alarm_description="Collections sync DLQ depth exceeds 10 messages",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        collections_sync_dlq_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(collections_sync_dlq_alarm_topic)
        )

        # --- Task 3.8: Add DLQ queue access policy ---
        # Allow only the Lambda function to send messages to the queue
        self._collections_sync_dlq.queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowLambdaSendMessage",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                ],
                resources=[self._collections_sync_dlq.queue_arn],
                conditions={
                    "ArnEquals": {
                        "aws:SourceArn": self._collections_sync_lambda.function.function_arn
                    }
                },
            )
        )

        # Explicitly deny all actions from any principal outside the account
        self._collections_sync_dlq.queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyPublicAccess",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[self._collections_sync_dlq.queue_arn],
                conditions={"StringNotEquals": {"aws:PrincipalAccount": stack.account}},
            )
        )

    @property
    def collections_table(self) -> DynamoDB:
        """
        Get the Collections DynamoDB table construct.

        Returns:
            DynamoDB: The Collections table construct
        """
        return self._collections_table
