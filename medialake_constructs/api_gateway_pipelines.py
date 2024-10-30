from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from medialake_constructs.shared_constructs.lambda_base import (
    Lambda,
    LambdaConfig,
)


class PipelinesConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_resource: apigateway.IResource,
        cognito_authorizer: apigateway.IAuthorizer,
        x_origin_verify_secret: secretsmanager.Secret,
    ) -> None:
        super().__init__(scope, id)

        # Create pipelines resource
        pipelines_resource = api_resource.root.add_resource("pipelines")

        # GET /api/pipelines
        get_pipelines_lambda_config = LambdaConfig(
            name="GetPipelinesHandler",
            entry="lambdas/api/pipelines/get_pipelines",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (
                    x_origin_verify_secret.secret_arn
                ),
            }
        )
        get_pipelines_handler = Lambda(
            self,
            "GetPipelinesHandler",
            config=get_pipelines_lambda_config,
        )

        pipelines_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipelines_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # POST /api/pipelines
        post_pipelines_lambda_config = LambdaConfig(
            name="PostPipelinesHandler",
            entry="lambdas/api/pipelines/post_pipelines",
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (
                    x_origin_verify_secret.secret_arn
                ),
            }
        )
        post_pipelines_handler = Lambda(
            self,
            "PostPipelinesHandler",
            config=post_pipelines_lambda_config,
        )
        
        post_pipelines_handler.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:GetQueueAttributes",
                    "sqs:CreateQueue",
                    "sqs:DeleteQueue",
                    "sqs:SetQueueAttributes",
                ],
                resources=["*"],
            )
        )

        pipelines_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(post_pipelines_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # Pipeline ID specific endpoints
        pipeline_id_resource = pipelines_resource.add_resource("{pipelineId}")

        # GET /api/pipelines/{pipelineId}
        get_pipeline_id_lambda_config = LambdaConfig(
            name="GetPipelineIdHandler",
            entry=(
                "lambdas/api/pipelines/rp_pipeline_id/get_pipeline_id"
            ),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (
                    x_origin_verify_secret.secret_arn
                ),
            }
        )
        get_pipeline_id_handler = Lambda(
            self,
            "GetPipelineIdHandler",
            config=get_pipeline_id_lambda_config,
        )

        pipeline_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # PUT /api/pipelines/{pipelineId}
        put_pipeline_id_lambda_config = LambdaConfig(
            name="PutPipelineIdHandler",
            entry=(
                "lambdas/api/pipelines/rp_pipeline_id/put_pipeline_id"
            ),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (
                    x_origin_verify_secret.secret_arn
                ),
            }
        )
        put_pipeline_id_handler = Lambda(
            self,
            "PutPipelineIdHandler",
            config=put_pipeline_id_lambda_config,
        )

        pipeline_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(put_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )

        # DELETE /api/pipelines/{pipelineId}
        del_pipeline_id_lambda_config = LambdaConfig(
            name="DeletePipelineIdHandler",
            entry=(
                "lambdas/api/pipelines/rp_pipeline_id/del_pipeline_id"
            ),
            environment_variables={
                "X_ORIGIN_VERIFY_SECRET_ARN": (
                    x_origin_verify_secret.secret_arn
                ),
            }
        )
        del_pipeline_id_handler = Lambda(
            self,
            "DeletePipelineIdHandler",
            config=del_pipeline_id_lambda_config,
        )

        pipeline_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(del_pipeline_id_handler.function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=cognito_authorizer,
        )
