"""
CDK construct for CloudFront Edge Lambda functions
"""

import os
from dataclasses import dataclass

from aws_cdk import (
    Duration,
    RemovalPolicy,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


@dataclass
class EdgeLambdaConstructProps:
    """Properties for EdgeLambdaConstruct"""

    # Optional properties for customization
    log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK
    removal_policy: RemovalPolicy = RemovalPolicy.DESTROY


class EdgeLambdaConstruct(Construct):
    """
    Construct for CloudFront Edge Lambda functions
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: EdgeLambdaConstructProps,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the CSP header modifier Lambda function
        self.csp_header_modifier = lambda_.Function(
            self,
            "CSPHeaderModifier",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "lambdas/edge/csp_header_modifier",
                )
            ),
            description="CloudFront Edge Lambda to modify CSP headers and clean URIs",
            timeout=Duration.seconds(5),  # Edge Lambda max timeout
            memory_size=128,  # Edge Lambda max memory
            log_retention=props.log_retention,
        )

        # Create CloudWatch Log Group for the Lambda function
        self.log_group = logs.LogGroup(
            self,
            "CSPHeaderModifierLogGroup",
            log_group_name=f"/aws/lambda/{self.csp_header_modifier.function_name}",
            retention=props.log_retention,
            removal_policy=props.removal_policy,
        )

        # Create Lambda@Edge version (required for CloudFront)
        self.lambda_version = lambda_.Version(
            self,
            "CSPHeaderModifierVersion",
            lambda_=self.csp_header_modifier,
            description="Version for CSP header modifier Edge Lambda",
        )

    def get_origin_request_function(self) -> cloudfront.Function:
        """
        Get the Lambda@Edge function for origin request events
        """
        return cloudfront.Function(
            self,
            "CSPOriginRequestFunction",
            code=cloudfront.FunctionCode.from_inline(
                """
                function handler(event) {
                var request = event.request;
                var uri = request.uri;

                // Strip /*/*/ pattern from URI
                var cleanedUri = uri.replace(/\/\*\/\*/g, '/');
                request.uri = cleanedUri;

                return request;
                }
            """
            ),
            comment="Strips /*/*/ from URI before forwarding to origin",
        )

    def get_viewer_response_function(self) -> cloudfront.Function:
        """
        Get the Lambda@Edge function for viewer response events
        """
        return cloudfront.Function(
            self,
            "CSPViewerResponseFunction",
            code=cloudfront.FunctionCode.from_inline(
                """
                function handler(event) {
                var response = event.response;
                var headers = response.headers;

                // Modify CSP header to allow WASM
                if (headers['content-security-policy']) {
                    var csp = headers['content-security-policy'].value;

                    // Add wasm-unsafe-eval to script-src if not present
                    if (csp.includes('script-src') && !csp.includes('wasm-unsafe-eval')) {
                        csp = csp.replace(/script-src([^;]*)/, 'script-src$1 \'wasm-unsafe-eval\'');
                    }

                    // Add blob: to script-src if not present
                    if (csp.includes('script-src') && !csp.includes('blob:')) {
                        csp = csp.replace(/script-src([^;]*)/, 'script-src$1 blob:');
                    }

                    // Add data: to connect-src if not present
                    if (csp.includes('connect-src') && !csp.includes('data:')) {
                        csp = csp.replace(/connect-src([^;]*)/, 'connect-src$1 data:');
                    }

                    // Add blob: to connect-src if not present
                    if (csp.includes('connect-src') && !csp.includes('blob:')) {
                        csp = csp.replace(/connect-src([^;]*)/, 'connect-src$1 blob:');
                    }

                    headers['content-security-policy'] = {
                        value: csp
                    };
                }

                return response;
                }
            """
            ),
            comment="Modifies CSP headers to allow WASM and blob URLs",
        )
