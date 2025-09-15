from aws_cdk import (
    Duration,
)
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class EdgeLambdaConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, props=None):
        super().__init__(scope, construct_id)

        # Create Lambda function with simplified code
        self.lambda_function = _lambda.Function(
            self,
            "CSPHeaderLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_inline(
                """
import re

def lambda_handler(event, context):
    # Only handle origin-request events
    request = event['Records'][0]['cf']['request']
    original_uri = request['uri']

    # Pattern to match /media/{bucket-name}/ where bucket name contains 'mediaassetss3bucket'
    # This makes it work regardless of the random suffix CDK adds
    pattern = r'^/media/[^/]*mediaassetss3bucket[^/]*/(.*)$'

    match = re.match(pattern, original_uri)
    if match:
        # Extract the path after /media/{bucket-name}/
        request['uri'] = '/' + match.group(1)
    elif original_uri.startswith('/media/'):
        # Fallback: just strip /media/ if no bucket pattern found
        request['uri'] = original_uri[6:]

    return request
"""
            ),
            role=iam.Role(
                self,
                "EdgeLambdaRole",
                assumed_by=iam.CompositePrincipal(
                    iam.ServicePrincipal("lambda.amazonaws.com"),
                    iam.ServicePrincipal("edgelambda.amazonaws.com"),
                ),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "service-role/AWSLambdaBasicExecutionRole"
                    )
                ],
            ),
            timeout=Duration.seconds(5),
            memory_size=128,
        )

        # Publish version for Lambda@Edge
        self.lambda_version = self.lambda_function.current_version
