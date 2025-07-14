from dataclasses import dataclass

from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from config import config


@dataclass
class ApiGatewayProps:
    access_log_bucket: s3.Bucket
    user_pool: cognito.UserPool
    deploy_api: bool = False


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
                            "ruleActionOverrides": [
                                {
                                    "name": "SizeRestrictions_BODY",
                                    "actionToUse": {"allow": {}},
                                }
                            ],
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

        # Save the deployment options for later
        self.deploy_options = apigateway.StageOptions(
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
        )

        # # Create Cognito Authorizer first
        # self.cognito_user_pool_authorizer = apigateway.CognitoUserPoolsAuthorizer(
        #     self,
        #     "CognitoAuthorizer",
        #     identity_source="method.request.header.Authorization",
        #     cognito_user_pools=[self.props.user_pool],
        #     # rest_api=self.api_gateway_rest_api
        # )

        # Create the API without deploying it by default
        rest_api_props = {
            "endpoint_types": [apigateway.EndpointType.EDGE],
            "cloud_watch_role": True,
            "default_cors_preflight_options": apigateway.CorsOptions(
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
            "deploy": props.deploy_api,
            # "default_method_options": apigateway.MethodOptions(
            #     authorization_type=apigateway.AuthorizationType.COGNITO,
            #     authorizer=self.cognito_user_pool_authorizer,
            # ),
        }

        # Only include deploy_options when deploy is True
        if props.deploy_api:
            rest_api_props["deploy_options"] = self.deploy_options

        self.api_gateway_rest_api = apigateway.RestApi(
            self, "MediaLakeApi", **rest_api_props
        )

        # # Create Cognito Authorizer first
        # self.cognito_user_pool_authorizer = apigateway.CognitoUserPoolsAuthorizer(
        #     self,
        #     "CognitoAuthorizer",
        #     identity_source="method.request.header.Authorization",
        #     cognito_user_pools=[self.props.user_pool],
        #     # rest_api=self.api_gateway_rest_api
        # )

        # Set the default method options after creating the authorizer
        self.api_gateway_rest_api.add_gateway_response(
            "DEFAULT_4XX",
            type=apigateway.ResponseType.DEFAULT_4_XX,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'*'",
            },
        )

        self.api_gateway_rest_api.add_gateway_response(
            "DEFAULT_5XX",
            type=apigateway.ResponseType.DEFAULT_5_XX,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'*'",
            },
        )

        # Add proxy resource, but let the recursive function handle adding the OPTIONS method
        # try:
        #     # Add a proxy resource for catch-all routing
        #     self.api_gateway_rest_api.root.add_resource("{proxy+}")
        # except Exception as e:
        #     # Resource already exists, just log and continue
        #     print(f"Note: {e} - This is expected if the proxy resource already exists")

        # Output the RestApi ID for reference
        CfnOutput(self, "RestApiId", value=self.api_gateway_rest_api.rest_api_id)

        # Add a utility method to add CORS OPTIONS methods to all resources
        # Do this before accessing other resources to avoid dependency issues
        # Commenting out because this conflicts with default_cors_preflight_options at the API level
        # self._add_cors_options_to_all_resources(self.api_gateway_rest_api.root)

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

        # If deploying in this stack, associate WAF
        if props.deploy_api:
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

    def add_cors_options_to_resource(self, resource):
        """
        Public method to add CORS OPTIONS to a single resource.
        Other constructs can call this when they create new resources.
        """
        try:
            resource.add_method(
                "OPTIONS",
                apigateway.MockIntegration(
                    integration_responses=[
                        {
                            "statusCode": "200",
                            "responseParameters": {
                                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Origin-Verify'",
                                "method.response.header.Access-Control-Allow-Origin": "'*'",
                                "method.response.header.Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD'",
                            },
                        }
                    ],
                    passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                    request_templates={"application/json": '{"statusCode": 200}'},
                ),
                method_responses=[
                    {
                        "statusCode": "200",
                        "responseParameters": {
                            "method.response.header.Access-Control-Allow-Headers": True,
                            "method.response.header.Access-Control-Allow-Methods": True,
                            "method.response.header.Access-Control-Allow-Origin": True,
                        },
                    }
                ],
                authorization_type=apigateway.AuthorizationType.NONE,
            )
            return True
        except Exception as e:
            print(f"Note: Could not add OPTIONS method to resource: {e}")
            return False

    # @property
    # def cognito_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
    #     return self.cognito_user_pool_authorizer

    def _add_cors_options_to_all_resources(self, resource):
        """Recursively adds OPTIONS methods with CORS headers to all API resources"""
        try:
            # Add OPTIONS method to current resource
            resource.add_method(
                "OPTIONS",
                apigateway.MockIntegration(
                    integration_responses=[
                        {
                            "statusCode": "200",
                            "responseParameters": {
                                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Origin-Verify'",
                                "method.response.header.Access-Control-Allow-Origin": "'*'",
                                "method.response.header.Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD'",
                            },
                        }
                    ],
                    passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                    request_templates={"application/json": '{"statusCode": 200}'},
                ),
                method_responses=[
                    {
                        "statusCode": "200",
                        "responseParameters": {
                            "method.response.header.Access-Control-Allow-Headers": True,
                            "method.response.header.Access-Control-Allow-Methods": True,
                            "method.response.header.Access-Control-Allow-Origin": True,
                        },
                    }
                ],
                authorization_type=apigateway.AuthorizationType.NONE,
            )
        except Exception as e:
            # Method may already exist, just log and continue
            print(f"Note: Could not add OPTIONS method to resource: {e}")

        # Recursively process all child resources if they exist
        # Some resources (like imported ones) may not have children attribute
        if hasattr(resource, "children") and resource.children:
            for child_resource in resource.children.values():
                self._add_cors_options_to_all_resources(child_resource)
