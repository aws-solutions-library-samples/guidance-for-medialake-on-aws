import time
from dataclasses import dataclass

import aws_cdk as cdk
import aws_cdk.aws_iam as iam
from aws_cdk import CustomResource, Fn, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from aws_cdk import custom_resources as cr
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_deployment_construct import (
    ApiGatewayDeploymentConstruct,
    ApiGatewayDeploymentProps,
)


@dataclass
class ApiGatewayDeploymentStackProps:
    """Configuration for API Gateway Stack."""

    # waf_acl_arn has been removed as it will be retrieved from CloudFormation output
    api_dependencies: list = (
        None  # Optional list of dependencies to ensure all API resources are created before deployment
    )


class ApiGatewayDeploymentStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: ApiGatewayDeploymentStackProps, **kwargs
    ):

        super().__init__(scope, id, **kwargs)

        waf_acl_arn = Fn.import_value("MediaLakeApiGatewayCore-ApiGatwayWAFACLARN")

        self.api_deployment = ApiGatewayDeploymentConstruct(
            self,
            "ApiDeployment",
            props=ApiGatewayDeploymentProps(
                waf_acl_arn=waf_acl_arn,
                dependencies=props.api_dependencies,
            ),
        )

        # Create a custom resource to ensure API is deployed correctly
        # This will run after all other resources are created
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        stage_name = self.api_deployment.stage.stage_name

        # Create a Lambda function to create a new deployment
        deployment_function = lambda_.Function(
            self,
            "ApiDeploymentLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                """
import boto3
import cfnresponse
import time

def handler(event, context):
    api_id = event['ResourceProperties']['ApiId']
    stage_name = event['ResourceProperties']['StageName']

    try:
        if event['RequestType'] in ['Create', 'Update']:
            # Small delay to ensure all resources are fully propagated
            time.sleep(2)

            # Create a new deployment
            api_client = boto3.client('apigateway')
            response = api_client.create_deployment(
                restApiId=api_id,
                stageName=stage_name,
                description=f"Post-deployment update {time.time()}"
            )

            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'DeploymentId': response['id']
            })
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Error': str(e)
        })
            """
            ),
            timeout=cdk.Duration.seconds(30),
        )

        # Grant permissions to the Lambda function
        deployment_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["apigateway:POST", "apigateway:GET"],
                resources=[f"arn:aws:apigateway:*::/restapis/{api_id}/*"],
            )
        )

        # Create the custom resource
        cr.Provider(self, "ApiDeploymentProvider", on_event_handler=deployment_function)

        deployment_resource = CustomResource(
            self,
            "ApiDeploymentCustomResource",
            service_token=deployment_function.function_arn,
            properties={
                "ApiId": api_id,
                "StageName": stage_name,
                "Timestamp": int(time.time()),  # Force update on each deployment
            },
        )

        # Add explicit dependency on the stage
        deployment_resource.node.add_dependency(self.api_deployment.stage)

    @property
    def api_deployment_stage(self) -> apigateway.Stage:
        return self.api_deployment.stage
