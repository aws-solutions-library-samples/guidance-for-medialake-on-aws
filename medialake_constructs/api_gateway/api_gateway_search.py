from dataclasses import dataclass
from typing import Optional

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from constants import Lambda as LambdaConstants
from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.shared_constructs.lambda_layers import SearchLayer
from medialake_constructs.shared_constructs.s3bucket import S3Bucket


def apply_custom_authorization(
    method: apigateway.Method, authorizer: apigateway.IAuthorizer
) -> None:
    """
    Apply custom authorization to an API Gateway method.

    Args:
        method: The API Gateway method to apply authorization to
        authorizer: The custom authorizer to use
    """
    cfn_method = method.node.default_child
    cfn_method.authorization_type = "CUSTOM"
    cfn_method.authorizer_id = authorizer.authorizer_id


@dataclass
class SearchProps:
    asset_table: dynamodb.TableV2
    media_assets_bucket: S3Bucket
    api_resource: apigateway.IResource
    authorizer: apigateway.IAuthorizer
    x_origin_verify_secret: secretsmanager.Secret
    open_search_endpoint: str
    open_search_arn: str
    open_search_index: str
    system_settings_table: str
    s3_vector_bucket_name: str
    connector_table: Optional[dynamodb.TableV2] = None
    vpc: Optional[ec2.IVpc] = None
    security_group: Optional[ec2.SecurityGroup] = None


class SearchConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: SearchProps,
    ) -> None:
        super().__init__(scope, construct_id)

        search_layer = SearchLayer(self, "SearchLayer")

        # Create connectors resource
        search_resource = props.api_resource.root.add_resource("search")
        # High-traffic search API with VPC and heavy compute needs
        search_get_lambda = Lambda(
            self,
            "SearchGetLambda",
            config=LambdaConfig(
                name="search_get",
                vpc=props.vpc,
                security_groups=[props.security_group],
                entry="lambdas/api/search/get_search",
                layers=[search_layer.layer],
                memory_size=9000,  # High memory for vector/semantic search operations
                timeout_minutes=10,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.open_search_index,
                    # Marengo 3.0 embeddings are stored in a separate index
                    "ASSET_EMBEDDINGS_INDEX": "asset-embeddings",
                    "SCOPE": "es",
                    "MEDIA_ASSETS_BUCKET": props.media_assets_bucket.bucket_name,
                    "SYSTEM_SETTINGS_TABLE": props.system_settings_table,
                    "S3_VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
                    "S3_VECTOR_INDEX_NAME": "media-vectors",
                    # CLOUDFRONT_DISTRIBUTION_DOMAIN removed to break circular dependency
                    # Lambda will fetch this from SSM parameter at runtime
                    # Bedrock inference profile: Auto-selected based on DynamoDB config (2.7 or 3.0)
                    # BEDROCK_INFERENCE_PROFILE_ARN removed - Lambda auto-selects based on system settings
                    # Thumbnail index for video posters (0-4, default 2 = middle thumbnail)
                    "THUMBNAIL_INDEX": "2",
                    # Connector table for /search/connectors endpoint
                    # Allows search API to return connector summaries without
                    # requiring separate connectors:view permission
                    **(
                        {
                            "MEDIALAKE_CONNECTOR_TABLE": props.connector_table.table_name,
                        }
                        if props.connector_table
                        else {}
                    ),
                },
            ),
        )

        # Lambda warming for search API (replaces provisioned concurrency)
        events.Rule(
            self,
            "SearchLambdaWarmerRule",
            schedule=events.Schedule.rate(
                Duration.minutes(LambdaConstants.WARMER_INTERVAL_MINUTES)
            ),
            targets=[
                targets.LambdaFunction(
                    search_get_lambda.function,
                    event=events.RuleTargetInput.from_object({"lambda_warmer": True}),
                ),
            ],
            description="Keeps search API Lambda warm via scheduled EventBridge rule.",
        )

        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Grant read access to connector table for /search/connectors endpoint
        if props.connector_table:
            props.connector_table.grant_read_data(search_get_lambda.function)

        # Add OpenSearch read permissions to the Lambda
        search_get_lambda.function.add_to_role_policy(
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

        # Add S3 and KMS permissions for generating presigned URLs
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:GetObjectVersion",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
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

        # Add permissions to access Secrets Manager and the system settings table
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],
            )
        )

        # Add permissions to access the system settings table
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{props.system_settings_table}"
                ],
            )
        )

        # Add S3 Vector permissions
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:GetVectorBucket",
                    "s3vectors:ListVectorBuckets",
                    "s3vectors:GetIndex",
                    "s3vectors:ListIndexes",
                    "s3vectors:GetVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}",
                    f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:bucket/{props.s3_vector_bucket_name}/*",
                ],
            )
        )

        # Add Bedrock permissions for TwelveLabs embedding generation (both 2.7 and 3.0)
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:StartAsyncInvoke",
                    "bedrock:GetAsyncInvoke",
                    "bedrock:ListAsyncInvokes",
                    "bedrock:StopAsyncInvoke",
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-3-0-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/us.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/us.twelvelabs.marengo-embed-3-0-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/eu.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/eu.twelvelabs.marengo-embed-3-0-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/apac.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/apac.twelvelabs.marengo-embed-3-0-v1:0",
                    f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:async-invoke/*",
                ],
            )
        )

        # Add S3 permissions for Bedrock async invoke output
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=[
                    f"arn:aws:s3:::{props.s3_vector_bucket_name}",
                    f"arn:aws:s3:::{props.s3_vector_bucket_name}/*",
                ],
            )
        )

        # Add SSM GetParameter permissions
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=["*"],
            )
        )

        # Add Bedrock InvokeModel permissions for TwelveLabs embedding generation (both 2.7 and 3.0)
        # Using system-defined cross-Region inference profiles
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=[
                    # Foundation model ARNs - required for InvokeModel calls (both 2.7 and 3.0)
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-3-0-v1:0",
                    # System-defined cross-Region inference profiles for TwelveLabs Marengo (all regions, both versions)
                    "arn:aws:bedrock:*:*:inference-profile/us.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/us.twelvelabs.marengo-embed-3-0-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/eu.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/eu.twelvelabs.marengo-embed-3-0-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/apac.twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*:*:inference-profile/apac.twelvelabs.marengo-embed-3-0-v1:0",
                ],
            )
        )

        # Add permissions to list and get inference profiles (for debugging/monitoring)
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:ListInferenceProfiles",
                    "bedrock:GetInferenceProfile",
                ],
                resources=["*"],
            )
        )

        # Add permissions access marketplace bedrock models under new simplified model access policy (both 2.7 and 3.0)
        # https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html
        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aws-marketplace:Subscribe",
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-2-7-v1:0",
                    "arn:aws:bedrock:*::foundation-model/twelvelabs.marengo-embed-3-0-v1:0",
                ],
                conditions={
                    "StringEquals": {"aws:CalledViaLast": "lambda.amazonaws.com"}
                },
            )
        )

        search_get_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aws-marketplace:ViewSubscriptions",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {"aws:CalledViaLast": "lambda.amazonaws.com"}
                },
            )
        )

        search_get = search_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_get_lambda.function),
        )
        apply_custom_authorization(search_get, props.authorizer)

        # Create /search/connectors resource for returning connector summaries
        # under search:view permission (avoids requiring connectors:view)
        connectors_resource = search_resource.add_resource("connectors")
        search_connectors_get = connectors_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_get_lambda.function),
        )
        apply_custom_authorization(search_connectors_get, props.authorizer)

        # Add CORS support

        # Create fields resource under search
        fields_resource = search_resource.add_resource("fields")

        # Create Lambda for search fields endpoint
        # Requires VPC access to reach the OpenSearch domain
        search_fields_lambda = Lambda(
            self,
            "SearchFieldsLambda",
            config=LambdaConfig(
                name="get_search_fields",
                vpc=props.vpc,
                security_groups=[props.security_group],
                entry="lambdas/api/search/fields/get_fields",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": (
                        props.x_origin_verify_secret.secret_arn
                    ),
                    "SYSTEM_SETTINGS_TABLE": props.system_settings_table,
                    "OPENSEARCH_ENDPOINT": props.open_search_endpoint,
                    "OPENSEARCH_INDEX": props.open_search_index,
                    "SCOPE": "es",
                },
            ),
        )

        # VPC ENI management permissions (required for VPC-deployed Lambdas)
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )

        # Add permissions to access Secrets Manager
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],
            )
        )

        # Add permissions to access the system settings table
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{props.system_settings_table}"
                ],
            )
        )

        # Add OpenSearch read permissions for fields mapping endpoint
        search_fields_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["es:ESHttpGet", "es:ESHttpPost"],
                resources=[props.open_search_arn, f"{props.open_search_arn}/*"],
            )
        )

        # Add the GET method to the fields resource
        search_fields_get = fields_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_fields_lambda.function),
        )
        apply_custom_authorization(search_fields_get, props.authorizer)

        # Add /search/fields/mapping sub-resource
        mapping_resource = fields_resource.add_resource("mapping")
        search_fields_mapping_get = mapping_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(search_fields_lambda.function),
        )
        apply_custom_authorization(search_fields_mapping_get, props.authorizer)

        # Add /search/fields/values sub-resource for fetching distinct field values
        values_resource = fields_resource.add_resource("values")
        search_fields_values_post = values_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(search_fields_lambda.function),
        )
        apply_custom_authorization(search_fields_values_post, props.authorizer)

        add_cors_options_method(search_resource)
        add_cors_options_method(connectors_resource)
        add_cors_options_method(fields_resource)
        add_cors_options_method(mapping_resource)
        add_cors_options_method(values_resource)

    def _get_regional_inference_profile_id(self) -> str:
        """
        Get the appropriate TwelveLabs Marengo Embed v2.7 inference profile ID based on deployment region.

        Returns:
            Regional inference profile ID for TwelveLabs Marengo Embed v2.7
        """
        # Get the deployment region from the stack
        deployment_region = Stack.of(self).region

        # Common suffix for all TwelveLabs Marengo Embed v2.7 inference profiles
        model_suffix = ".twelvelabs.marengo-embed-2-7-v1:0"

        # Map regions to regional prefixes based on AWS documentation
        if deployment_region.startswith("us-"):
            # US regions: us-east-1, us-east-2, us-west-1, us-west-2
            regional_prefix = "us"
        elif deployment_region.startswith("eu-"):
            # EU regions: eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3
            regional_prefix = "eu"
        elif deployment_region.startswith("ap-"):
            # APAC regions: ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4
            regional_prefix = "apac"
        else:
            # Default to US profile for unknown regions
            regional_prefix = "us"

        return f"{regional_prefix}{model_suffix}"
