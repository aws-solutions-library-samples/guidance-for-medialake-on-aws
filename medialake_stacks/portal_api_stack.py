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
from aws_cdk import Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from config import config
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


@dataclass
class PortalApiStackProps:
    """Configuration for the Portal API nested stack."""

    system_settings_table: str
    cognito_user_pool_id: str
    connector_table: dynamodb.TableV2
    iac_assets_bucket: S3Bucket
    cloudfront_domain: str = ""


class PortalApiStack(cdk.NestedStack):
    """Dedicated nested stack hosting the public upload-portal API."""

    def __init__(self, scope: Construct, id: str, props: PortalApiStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        self._props = props

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
                    resources=[
                        f"arn:aws:ses:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:identity/{config.ses_from_address}"
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

    @property
    def portal_authorizer_lambda(self) -> lambda_.Function:
        return self._portal_authorizer_lambda.function

    @property
    def portal_management_lambda(self) -> lambda_.Function:
        return self._portal_management_lambda.function

    @property
    def portal_public_lambda(self) -> lambda_.Function:
        return self._portal_public_lambda.function
