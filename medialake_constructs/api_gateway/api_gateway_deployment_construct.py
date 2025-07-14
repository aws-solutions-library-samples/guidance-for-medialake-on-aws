import time
from dataclasses import dataclass

from aws_cdk import Fn, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from config import config


@dataclass
class ApiGatewayDeploymentProps:
    """Properties for API Gateway Deployment Construct"""

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

        # Import the API Gateway from CloudFormation outputs
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        rest_api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "ImportedRestApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        # Create a deployment for the RestApi
        self._deployment = apigateway.Deployment(
            self,
            "ApiDeployment",
            api=rest_api,
            description=f"MediaLake API Deployment {int(time.time())}",
        )

        # Add dependencies if provided
        if props.dependencies:
            for dependency in props.dependencies:
                self._deployment.node.add_dependency(dependency)
                print(f"Added dependency to API deployment: {dependency.node.id}")

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
            access_log_destination=apigateway.LogGroupLogDestination(
                rest_api_log_group
            ),
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
