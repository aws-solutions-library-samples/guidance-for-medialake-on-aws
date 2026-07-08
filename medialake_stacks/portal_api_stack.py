"""
Portal API nested stack.

The public upload-portal API was extracted out of ``ApiGatewayStack`` because
that stack hit CloudFormation's hard limit of 500 resources per stack. The
portal feature (four Lambdas plus their routes, IAM, and a dedicated request
authorizer) is self-contained and a natural unit to host in its own nested
stack, which gives it a fresh 500-resource budget.

The shared REST API is imported by ID via the ``MediaLakeApiGatewayCore``
CloudFormation exports — exactly the same pattern ``ApiGatewayStack`` uses — so
the portal routes are attached to the same physical API Gateway.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Duration, Fn, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.s3bucket import S3Bucket
from medialake_constructs.sqs import SQSConstruct, SQSProps


@dataclass
class PortalApiStackProps:
    """Configuration for the Portal API nested stack."""

    system_settings_table: str
    cognito_user_pool_id: str
    connector_table: dynamodb.TableV2
    iac_assets_bucket: S3Bucket
    cloudfront_domain: str = ""
    pipelines_event_bus_name: str = ""
    pipelines_event_bus_arn: str = ""


class PortalApiStack(cdk.NestedStack):
    """Dedicated nested stack hosting the public upload-portal API."""

    def __init__(self, scope: Construct, id: str, props: PortalApiStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        self._props = props

        # --- Upload Sessions DynamoDB table ---
        upload_sessions_table_construct = DynamoDB(
            self,
            "UploadSessionsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}-upload-sessions-{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                ttl_attribute="ttl",
                billing_mode=dynamodb.Billing.on_demand(),
                global_secondary_indexes=[
                    dynamodb.GlobalSecondaryIndexPropsV2(
                        index_name="GSI1",
                        partition_key=dynamodb.Attribute(
                            name="GSI1_PK",
                            type=dynamodb.AttributeType.STRING,
                        ),
                        sort_key=dynamodb.Attribute(
                            name="GSI1_SK",
                            type=dynamodb.AttributeType.STRING,
                        ),
                        projection_type=dynamodb.ProjectionType.ALL,
                    ),
                ],
            ),
        )
        self._upload_sessions_table = upload_sessions_table_construct.table
        self._upload_sessions_table_name = upload_sessions_table_construct.table_name
        self._upload_sessions_table_arn = upload_sessions_table_construct.table_arn

        # Import the shared REST API by ID (same pattern as ApiGatewayStack).
        api_id = Fn.import_value(
            config.cfn_export("MediaLakeApiGatewayCore", "ApiGatewayId")
        )
        root_resource_id = Fn.import_value(
            config.cfn_export("MediaLakeApiGatewayCore", "RootResourceId")
        )
        self._rest_api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "PortalImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        wildcard_source_arn = (
            f"arn:aws:execute-api:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:{api_id}/*"
        )

        system_settings_table_arn = (
            f"arn:aws:dynamodb:{self.region}:{self.account}:table/"
            f"{props.system_settings_table}"
        )

        # --- Portal Auth Lambda (must be created before portal route integrations) ---
        self._portal_auth_lambda = Lambda(
            self,
            "PortalAuthLambda",
            config=LambdaConfig(
                name="portal_auth",
                entry="lambdas/api/portal_auth",
                # 1024 MB → ~0.58 vCPU (vs ~0.25 at 256 MB). Cold-start init is
                # CPU-bound (unzip + import jose/bcrypt/powertools), so more CPU
                # roughly halves the ~1.7s init on the public first-load path.
                memory_size=1024,
                timeout_minutes=1,
                snap_start=False,
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
                    "RESOURCE_PREFIX": config.resource_prefix,
                },
            ),
        )

        self._portal_auth_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[
                    system_settings_table_arn,
                    f"{system_settings_table_arn}/index/*",
                ],
            )
        )
        self._portal_auth_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:{config.resource_prefix}/portals/*"
                ],
            )
        )

        self._portal_auth_lambda.function.add_permission(
            "ApiGatewayInvokePortalAuth",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=wildcard_source_arn,
        )

        # --- Portal Authorizer and API Gateway resources ---

        # Portal authorizer Lambda
        self._portal_authorizer_lambda = Lambda(
            self,
            "PortalAuthorizerLambda",
            config=LambdaConfig(
                name="portal_authorizer",
                entry="lambdas/auth/portal_authorizer",
                # Bumped from 128 MB: the authorizer runs on every GET
                # /portal/{slug} request (results_cache_ttl=0), so its cold
                # start is on the public first-load critical path.
                memory_size=512,
                timeout_minutes=1,
                snap_start=False,
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
                    "RESOURCE_PREFIX": config.resource_prefix,
                },
            ),
        )

        self._portal_authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[
                    system_settings_table_arn,
                    f"{system_settings_table_arn}/index/*",
                ],
            )
        )
        self._portal_authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:{config.resource_prefix}/portals/*"
                ],
            )
        )

        self._portal_authorizer_lambda.function.add_permission(
            "ApiGatewayInvokePortalAuthorizer",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=wildcard_source_arn,
        )

        self._portal_authorizer = apigateway.RequestAuthorizer(
            self,
            "PortalRequestAuthorizer",
            handler=self._portal_authorizer_lambda.function,
            identity_sources=[apigateway.IdentitySource.context("requestId")],
            results_cache_ttl=cdk.Duration.seconds(0),
        )

        # Portal Public Lambda
        self._portal_public_lambda = Lambda(
            self,
            "PortalPublicLambda",
            config=LambdaConfig(
                name="portal_public",
                entry="lambdas/api/portal_public",
                # 1024 MB → ~0.58 vCPU to cut the ~1.4s cold-start init that
                # gates the public portal's GET /portal/{slug} first load.
                memory_size=1024,
                timeout_minutes=1,
                snap_start=False,
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table,
                    "MEDIALAKE_CONNECTOR_TABLE": props.connector_table.table_name,
                    "CLOUDFRONT_DOMAIN": props.cloudfront_domain,
                    # Portal images (logo/banner/favicon) live in the IAC assets
                    # bucket and are served to the browser via presigned S3 GET
                    # URLs resolved at read time.
                    "IAC_ASSETS_BUCKET_NAME": props.iac_assets_bucket.bucket_name,
                    "UPLOAD_SESSIONS_TABLE_NAME": self._upload_sessions_table_name,
                },
            ),
        )

        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[
                    system_settings_table_arn,
                    f"{system_settings_table_arn}/index/*",
                ],
            )
        )

        connector_table_arn = props.connector_table.table_arn
        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[
                    connector_table_arn,
                    f"{connector_table_arn}/index/*",
                ],
            )
        )

        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                    "s3:CreateMultipartUpload",
                    "s3:CompleteMultipartUpload",
                ],
                resources=["arn:aws:s3:::*", "arn:aws:s3:::*/*"],
            )
        )

        # Portal images live in the KMS-encrypted IAC assets bucket. Serving
        # them via presigned S3 GET URLs requires the signing principal (this
        # Lambda's role) to be able to decrypt with the bucket's CMK, otherwise
        # S3 returns AccessDenied at GET time.
        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["kms:Decrypt"],
                resources=[props.iac_assets_bucket.key_arn],
            )
        )

        # Upload-sessions table access for the portal_public Lambda
        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:TransactWriteItems",
                    "dynamodb:Query",
                ],
                resources=[
                    self._upload_sessions_table_arn,
                    f"{self._upload_sessions_table_arn}/index/*",
                ],
            )
        )

        # CloudWatch metrics for upload-session observability
        self._portal_public_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        self._portal_public_lambda.function.add_permission(
            "ApiGatewayInvokePortalPublic",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=wildcard_source_arn,
        )

        portal_public_integration = apigateway.LambdaIntegration(
            self._portal_public_lambda.function, proxy=True
        )

        # /portal/{slug} resource group
        portal_resource = self._rest_api.root.add_resource("portal")
        portal_slug_resource = portal_resource.add_resource("{slug}")
        portal_slug_auth_resource = portal_slug_resource.add_resource("auth")
        portal_slug_upload_resource = portal_slug_resource.add_resource("upload")
        portal_slug_browse_resource = portal_slug_resource.add_resource("browse")
        portal_slug_folder_resource = portal_slug_resource.add_resource("folder")
        portal_slug_multipart_resource = portal_slug_upload_resource.add_resource(
            "multipart"
        )
        portal_slug_multipart_sign_resource = (
            portal_slug_multipart_resource.add_resource("sign")
        )
        portal_slug_multipart_complete_resource = (
            portal_slug_multipart_resource.add_resource("complete")
        )
        portal_slug_multipart_abort_resource = (
            portal_slug_multipart_resource.add_resource("abort")
        )

        # Upload-session routes under /portal/{slug}/upload-session
        portal_slug_upload_session_resource = portal_slug_resource.add_resource(
            "upload-session"
        )
        portal_slug_upload_session_id_resource = (
            portal_slug_upload_session_resource.add_resource("{sessionId}")
        )
        portal_slug_upload_session_heartbeat_resource = (
            portal_slug_upload_session_id_resource.add_resource("heartbeat")
        )
        portal_slug_upload_session_submit_resource = (
            portal_slug_upload_session_id_resource.add_resource("submit")
        )
        portal_slug_upload_session_release_key_resource = (
            portal_slug_upload_session_id_resource.add_resource("release-key")
        )

        portal_method_config = {
            "authorizer": self._portal_authorizer,
            "authorization_type": apigateway.AuthorizationType.CUSTOM,
        }

        portal_slug_auth_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._portal_auth_lambda.function, proxy=True),
            **portal_method_config,
        )
        portal_slug_resource.add_method(
            "GET", portal_public_integration, **portal_method_config
        )
        portal_slug_upload_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_browse_resource.add_method(
            "GET", portal_public_integration, **portal_method_config
        )
        portal_slug_folder_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_multipart_sign_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_multipart_complete_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_multipart_abort_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )

        # Upload-session endpoint methods
        portal_slug_upload_session_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_upload_session_id_resource.add_method(
            "GET", portal_public_integration, **portal_method_config
        )
        portal_slug_upload_session_heartbeat_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_upload_session_submit_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )
        portal_slug_upload_session_release_key_resource.add_method(
            "POST", portal_public_integration, **portal_method_config
        )

        for res in [
            portal_resource,
            portal_slug_resource,
            portal_slug_auth_resource,
            portal_slug_upload_resource,
            portal_slug_browse_resource,
            portal_slug_folder_resource,
            portal_slug_multipart_resource,
            portal_slug_multipart_sign_resource,
            portal_slug_multipart_complete_resource,
            portal_slug_multipart_abort_resource,
            portal_slug_upload_session_resource,
            portal_slug_upload_session_id_resource,
            portal_slug_upload_session_heartbeat_resource,
            portal_slug_upload_session_submit_resource,
            portal_slug_upload_session_release_key_resource,
        ]:
            add_cors_options_method(res)

        # --- Portal Management Lambda ---
        ses_from_arn = (
            f"arn:aws:ses:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:identity/{config.ses_from_address}"
            if config.ses_from_address
            else ""
        )

        self._portal_management_lambda = Lambda(
            self,
            "PortalManagementLambda",
            config=LambdaConfig(
                name="portal_management",
                entry="lambdas/api/portals",
                memory_size=256,
                timeout_minutes=1,
                snap_start=False,
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table,
                    "IAC_ASSETS_BUCKET_NAME": props.iac_assets_bucket.bucket_name,
                    "RESOURCE_PREFIX": config.resource_prefix,
                    "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
                    "CLOUDFRONT_DOMAIN": props.cloudfront_domain,
                    "SES_FROM_ARN": ses_from_arn,
                    "SES_FROM_EMAIL": config.ses_from_address or "",
                },
            ),
        )

        # DynamoDB permissions
        self._portal_management_lambda.function.add_to_role_policy(
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
                    system_settings_table_arn,
                    f"{system_settings_table_arn}/index/*",
                ],
            )
        )

        # S3 permissions
        props.iac_assets_bucket.bucket.grant_read_write(
            self._portal_management_lambda.function
        )

        # Secrets Manager permissions
        self._portal_management_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:PutSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:{config.resource_prefix}/portals/*"
                ],
            )
        )

        # SES permissions (conditional)
        if config.ses_from_address:
            self._portal_management_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ses:SendEmail"],
                    # ses:SendEmail is authorized against the From identity, but
                    # in the SES sandbox it is also checked against any recipient
                    # that is itself a verified identity in this account. Scoping
                    # to only the From ARN gets AccessDenied when emailing such a
                    # recipient, so allow all identities in this account/region.
                    resources=[
                        f"arn:aws:ses:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:identity/*"
                    ],
                )
            )

        # API Gateway invoke permission
        self._portal_management_lambda.function.add_permission(
            "ApiGatewayInvokePortalManagement",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=wildcard_source_arn,
        )

        # --- Upload Session Stream Processor Lambda ---
        # DLQ for failed stream processing records
        self._upload_session_stream_dlq = SQSConstruct(
            self,
            "UploadSessionStreamDLQ",
            props=SQSProps(
                queue_name="upload-session-stream-dlq",
                visibility_timeout=Duration.minutes(2),
                retention_period=Duration.days(14),
                encryption=False,
                enforce_ssl=True,
                max_receive_count=0,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        self._upload_session_stream_lambda = Lambda(
            self,
            "UploadSessionStreamLambda",
            config=LambdaConfig(
                name="upload_session_stream",
                entry="lambdas/back_end/upload_session_stream",
                memory_size=256,
                timeout_minutes=1,
                snap_start=False,
                environment_variables={
                    "UPLOAD_SESSIONS_TABLE_NAME": self._upload_sessions_table_name,
                    "PIPELINES_EVENT_BUS_NAME": props.pipelines_event_bus_name,
                },
            ),
        )

        # DynamoDB event source on the upload-sessions table stream
        self._upload_session_stream_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._upload_sessions_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                bisect_batch_on_error=True,
                report_batch_item_failures=True,
                on_failure=lambda_event_sources.SqsDlq(
                    self._upload_session_stream_dlq.queue
                ),
            )
        )

        # Grant stream read permissions
        self._upload_sessions_table.grant_stream_read(
            self._upload_session_stream_lambda.function
        )

        # Grant events:PutEvents on the pipelines event bus
        if props.pipelines_event_bus_arn:
            self._upload_session_stream_lambda.function.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["events:PutEvents"],
                    resources=[props.pipelines_event_bus_arn],
                )
            )

        # Grant DynamoDB read + conditional emittedAt update on the upload-sessions table
        self._upload_session_stream_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[self._upload_sessions_table_arn],
            )
        )

        # --- Upload Session Reconciliation Sweep Lambda ---
        self._upload_session_sweep_lambda = Lambda(
            self,
            "UploadSessionSweepLambda",
            config=LambdaConfig(
                name="upload_session_sweep",
                entry="lambdas/back_end/upload_session_sweep",
                memory_size=256,
                timeout_minutes=5,
                snap_start=False,
                environment_variables={
                    "UPLOAD_SESSIONS_TABLE_NAME": self._upload_sessions_table_name,
                    "IDLE_TIMEOUT_HOURS": str(config.upload_portals.idle_timeout_hours),
                    "COMPLETION_GRACE_HOURS": str(
                        config.upload_portals.completion_grace_hours
                    ),
                    "MAX_SESSION_AGE_HOURS": str(
                        config.upload_portals.max_session_age_hours
                    ),
                },
            ),
        )

        # Schedule the sweep on a recurring interval
        events.Rule(
            self,
            "UploadSessionSweepScheduleRule",
            schedule=events.Schedule.rate(
                Duration.minutes(config.upload_portals.sweep_interval_minutes)
            ),
            targets=[
                targets.LambdaFunction(
                    self._upload_session_sweep_lambda.function,
                ),
            ],
            description="Periodically sweeps OPEN upload sessions for idle/grace/max-age reconciliation.",
        )

        # Grant DynamoDB read/write on the upload-sessions table and GSI
        self._upload_session_sweep_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                ],
                resources=[
                    self._upload_sessions_table_arn,
                    f"{self._upload_sessions_table_arn}/index/*",
                ],
            )
        )

        # Grant cloudwatch:PutMetricData for observability metrics
        self._upload_session_sweep_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

    @property
    def portal_authorizer_lambda(self) -> lambda_.Function:
        return self._portal_authorizer_lambda.function

    @property
    def portal_management_lambda(self) -> lambda_.Function:
        return self._portal_management_lambda.function

    @property
    def portal_public_lambda(self) -> lambda_.Function:
        return self._portal_public_lambda.function

    @property
    def upload_sessions_table(self) -> dynamodb.ITable:
        return self._upload_sessions_table

    @property
    def upload_sessions_table_name(self) -> str:
        return self._upload_sessions_table_name

    @property
    def upload_sessions_table_arn(self) -> str:
        return self._upload_sessions_table_arn
