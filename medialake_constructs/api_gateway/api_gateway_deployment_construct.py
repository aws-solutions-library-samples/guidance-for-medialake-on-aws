from aws_cdk import (
    aws_apigateway as apigateway,
    aws_wafv2 as wafv2,
    aws_logs as logs,
    aws_iam as iam,
    RemovalPolicy,
)
from constructs import Construct
from dataclasses import dataclass
from config import config


@dataclass
class ApiGatewayDeploymentProps:
    """Properties for API Gateway Deployment Construct"""
    rest_api: apigateway.RestApi
    waf_acl_arn: str
    dependencies: list = None  # List of resources that deployment depends on


class ApiGatewayDeploymentConstruct(Construct):
    """
    Creates a deployment for an existing API Gateway RestApi.
    This allows separating the API definition from its deployment,
    which can help resolve circular dependencies between stacks.
    """
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: ApiGatewayDeploymentProps,
    ) -> None:
        super().__init__(scope, id)

        # Create a log group for API Gateway access logs
        rest_api_log_group = logs.LogGroup(
            self,
            "RestAPILogGroup",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.THREE_MONTHS,
            log_group_name=f"/aws/apigateway/medialake-access-logs-deployment",
        )

        # Create an access log format
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

        # Create a deployment for the RestApi
        self._deployment = apigateway.Deployment(
            self,
            "ApiDeployment",
            api=props.rest_api,
            description="MediaLake API Deployment",
        )

        # Add dependencies if provided
        if props.dependencies:
            for dependency in props.dependencies:
                self._deployment.node.add_dependency(dependency)

        # Create a stage for the deployment with the same configuration as original
        stage = apigateway.Stage(
            self,
            "ApiStage",
            deployment=self._deployment,
            stage_name=config.api_path,  # Use the same stage name from config
            tracing_enabled=True,
            metrics_enabled=True,
            throttling_rate_limit=2500,
            throttling_burst_limit=5000,
            data_trace_enabled=True,
            logging_level=apigateway.MethodLoggingLevel.INFO,
            access_log_destination=apigateway.LogGroupLogDestination(rest_api_log_group),
            access_log_format=access_log_format,
        )

        # Grant permissions to the log group
        rest_api_log_group.grant_write(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Associate WAF with API Gateway stage
        self.api_gateway_waf_association = wafv2.CfnWebACLAssociation(
            self,
            "ApiWafAssociation",
            resource_arn=stage.stage_arn,
            web_acl_arn=props.waf_acl_arn,
        )

        self.api_gateway_waf_association.node.add_dependency(stage)
        
        self._stage = stage
    
    @property
    def stage(self) -> apigateway.Stage:
        return self._stage
        
    @property
    def deployment(self) -> apigateway.Deployment:
        return self._deployment