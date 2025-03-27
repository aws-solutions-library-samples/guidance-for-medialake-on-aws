"""
CDK construct for the asynchronous pipeline creation API.
This extends the existing ApiGatewayPipelinesConstruct to add the async pipeline creation functionality.
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, List

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    Duration,
)
from constructs import Construct

from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)
from medialake_constructs.shared_constructs.lambda_layers import (
    PyamlLayer,
    ShortuuidLayer,
)


class ApiGatewayPipelinesAsyncConstruct(Construct):
    """
    CDK construct for the asynchronous pipeline creation API.
    This extends the existing ApiGatewayPipelinesConstruct to add the async pipeline creation functionality.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        post_lambda_iam_boundary_policy: iam.ManagedPolicy,
        pyaml_layer: PyamlLayer,
        shortuuid_layer: ShortuuidLayer,
        environment_variables: Dict[str, str],
    ) -> None:
        super().__init__(scope, id)

        # Determine the current stack
        stack = Stack.of(self)

        # Get the region and account ID
        self.region = stack.region
        self.account_id = stack.account

        # Create a single worker Lambda function that will handle all steps
        self._pipeline_worker_lambda = Lambda(
            self,
            "PipelineWorkerLambda",
            config=LambdaConfig(
                name="pipeline_worker",
                entry="lambdas/api/pipelines/post_pipelines_steps/pipeline_worker",  # Use our new wrapper Lambda
                layers=[pyaml_layer.layer, shortuuid_layer.layer],
                iam_role_boundary_policy=post_lambda_iam_boundary_policy,
                environment_variables=environment_variables,
                timeout_minutes=15,  # This step can take a while
            ),
        )

        # Create a simple Step Function that just invokes the worker Lambda
        pipeline_worker_task = tasks.LambdaInvoke(
            self,
            "PipelineWorkerTask",
            lambda_function=self._pipeline_worker_lambda.function,
            output_path="$",
            retry_on_service_exceptions=True,
            payload_response_only=True
        )
        
        # Define the success state
        success_state = sfn.Succeed(self, "SuccessState")
        
        # Create a simple state machine definition
        definition = pipeline_worker_task.next(success_state)
        
        # Create the state machine
        self._pipeline_creation_state_machine = sfn.StateMachine(
            self,
            "PipelineCreationStateMachine",
            definition=definition,
            timeout=Duration.minutes(30),
        )

        # Create the front-end Lambda
        self._post_pipelines_async_handler = Lambda(
            self,
            "PostPipelinesAsyncHandler",
            config=LambdaConfig(
                name="pipeline_post_async",
                entry="lambdas/api/pipelines/post_pipelines_async",
                layers=[pyaml_layer.layer, shortuuid_layer.layer],
                iam_role_boundary_policy=post_lambda_iam_boundary_policy,
                environment_variables={
                    **environment_variables,
                    "PIPELINE_CREATION_STATE_MACHINE_ARN": self._pipeline_creation_state_machine.state_machine_arn,
                },
            ),
        )

        # Grant the front-end Lambda permission to start the Step Function
        self._pipeline_creation_state_machine.grant_start_execution(self._post_pipelines_async_handler.function)

        # Connect the API Gateway to the front-end Lambda
        # Get the existing pipelinesv2 resource instead of creating a new one
        pipelines_v2_resource = api_resource.root.get_resource("pipelinesv2")
        if not pipelines_v2_resource:
            # If it doesn't exist for some reason, create it
            pipelines_v2_resource = api_resource.root.add_resource("pipelinesv2")
            
        # Add the POST method to the existing resource
        pipelines_v2_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self._post_pipelines_async_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Add the status checking endpoint
        # Check if the status resource already exists
        pipelines_status_resource = pipelines_v2_resource.get_resource("status")
        if not pipelines_status_resource:
            # If it doesn't exist, create it
            pipelines_status_resource = pipelines_v2_resource.add_resource("status")
        pipelines_status_resource.add_resource("{executionArn}").add_method(
            "GET",
            apigateway.LambdaIntegration(self._post_pipelines_async_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

    @property
    def pipeline_creation_state_machine(self) -> sfn.StateMachine:
        return self._pipeline_creation_state_machine

    @property
    def post_pipelines_async_handler(self) -> Lambda:
        return self._post_pipelines_async_handler