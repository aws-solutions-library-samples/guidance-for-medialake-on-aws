from aws_cdk import (
    aws_apigateway as apigateway,
    aws_logs as logs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_wafv2 as wafv2,
    aws_ec2 as ec2,
    Duration,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_s3 as s3,
    aws_wafv2 as wafv2,
    RemovalPolicy,
)
from dataclasses import dataclass
from constructs import Construct
from typing import Optional
from config import config


@dataclass
class ApiGatewayProps:
    access_log_bucket: s3.Bucket
    user_pool: cognito.UserPool


class ApiGatewayConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayProps,
    ) -> None:
        super().__init__(scope, id)

        self.props = props or ApiGatewayProps()

        self.api_gateway_waf_log_group = logs.LogGroup(
            self,
            "WafLogGroup",
            log_group_name=f"aws-waf-logs-{config.resource_prefix}-api-gateway-waf-logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.api_gateway_waf_acl = wafv2.CfnWebACL(
            self,
            "ApiGatewayWAF",
            default_action={"allow": {}},
            scope="REGIONAL",
            visibility_config={
                "sampledRequestsEnabled": True,
                "cloudWatchMetricsEnabled": True,
                "metricName": "ApiGatewayWAFMetrics",
            },
            rules=[
                {
                    "name": "AWSManagedRulesCommonRuleSet",
                    "priority": 1,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesCommonRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "AWSManagedRulesCommonRuleSetMetric",
                    },
                },
                {
                    "name": "AWSManagedRulesKnownBadInputsRuleSet",
                    "priority": 2,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesKnownBadInputsRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "KnownBadInputsRuleSetMetric",
                    },
                },
                {
                    "name": "AWSManagedRulesSQLiRuleSet",
                    "priority": 3,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesSQLiRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "SQLiRuleSetMetric",
                        "sampledRequestsEnabled": True,
                    },
                },
            ],
        )

        self.api_gateway_waf_logging_config = wafv2.CfnLoggingConfiguration(
            self,
            "WafLoggingConfig",
            resource_arn=self.api_gateway_waf_acl.attr_arn,
            log_destination_configs=[self.api_gateway_waf_log_group.log_group_arn],
        )

        # Create the Log Group
        rest_api_log_group = logs.LogGroup(
            self,
            "RestAPILogGroup",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.THREE_MONTHS,
            log_group_name=f"/aws/apigateway/medialake-access-logs",
        )

        access_log_format = apigateway.AccessLogFormat.json_with_standard_fields(
            caller=True,
            http_method=True,
            ip=True,
            protocol=True,
            request_time=True,
            resource_path=True,
            response_length=True,
            status=True,
            user=True,
        )

        # Create Cognito Authorizer first
        self.cognito_user_pool_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[self.props.user_pool],
        )

        # Create a resource policy
        # resource_policy = iam.PolicyDocument(
        #     statements=[
        #         iam.PolicyStatement(
        #             actions=["execute-api:Invoke"],
        #             effect=iam.Effect.ALLOW,
        #             principals=[iam.AnyPrincipal()],
        #             resources=["execute-api:/*"],
        #             conditions={
        #                 "StringEquals": {
        #                     "aws:SourceVpce": [
        #                         props.api_gateway_vpc_endpoint.vpc_endpoint_id,
        #                     ]
        #                 }
        #             },
        #         )
        #     ]
        # )

        self.api_gateway_rest_api = apigateway.RestApi(
            self,
            "MediaLakeApi",
            endpoint_types=[apigateway.EndpointType.EDGE],
            # endpoint_types=[apigateway.EndpointType.PRIVATE],
            # policy=resource_policy,
            cloud_watch_role=True,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=[
                    "http://localhost:5173",
                ],
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "x-api-key",
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Amz-Security-Token",
                    "X-Origin-Verify",
                ],
                max_age=Duration.minutes(5),
            ),
            deploy=True,
            deploy_options=apigateway.StageOptions(
                stage_name=config.api_path,
                tracing_enabled=True,
                metrics_enabled=True,
                throttling_rate_limit=2500,
                data_trace_enabled=True,
                access_log_destination=apigateway.LogGroupLogDestination(
                    rest_api_log_group
                ),
                access_log_format=access_log_format,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                # cache_cluster_enabled=False,
                # cache_cluster_size="0.5",
                # cache_data_encrypted=True,
                # caching_enabled=True,
                # cache_ttl=Duration.minutes(5),
            ),
            default_method_options=apigateway.MethodOptions(
                authorization_type=apigateway.AuthorizationType.COGNITO,
                authorizer=self.cognito_user_pool_authorizer,
            ),
        )
        rest_api_log_group.grant_write(iam.ServicePrincipal("apigateway.amazonaws.com"))

        self.api_gateway_x_origin_verify_secret = secretsmanager.Secret(
            self,
            "XOriginVerifySecret",
            removal_policy=RemovalPolicy.DESTROY,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                generate_string_key="headerValue",
                secret_string_template="{}",
            ),
        )

        # Associate WAF with API Gateway
        self.api_gateway_waf_association = wafv2.CfnWebACLAssociation(
            self,
            "ApiWafAssociation",
            resource_arn=self.api_gateway_rest_api.deployment_stage.stage_arn,
            web_acl_arn=self.api_gateway_waf_acl.attr_arn,
        )

        self.api_gateway_waf_association.node.add_dependency(
            self.api_gateway_rest_api.deployment_stage
        )

    @property
    def rest_api(self) -> apigateway.RestApi:
        return self.api_gateway_rest_api

    @property
    def x_origin_verify_secret(self) -> secretsmanager.Secret:
        return self.api_gateway_x_origin_verify_secret

    @property
    def cognito_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
        return self.cognito_user_pool_authorizer
