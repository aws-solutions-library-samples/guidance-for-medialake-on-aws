import aws_cdk.aws_apigateway as apigateway


def add_cors_headers_to_response(response, allow_origins="*"):
    """
    Adds CORS headers to API Gateway method responses
    """
    if response.response_parameters is None:
        response.response_parameters = {}

    response.response_parameters[
        "method.response.header.Access-Control-Allow-Origin"
    ] = f"'{allow_origins}'"
    response.response_parameters[
        "method.response.header.Access-Control-Allow-Headers"
    ] = "'Content-Type,X-Amz-Date,Authorization,authorization,X-Api-Key,X-Amz-Security-Token,X-Origin-Verify'"
    response.response_parameters[
        "method.response.header.Access-Control-Allow-Methods"
    ] = "'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD'"

    return response


def add_cors_options_method(resource):
    """
    Adds an OPTIONS method with CORS headers to an API Gateway resource.
    Call this when creating new resources in feature-specific constructs.

    Usage:
    my_resource = api.root.add_resource("my-resource")
    add_cors_options_method(my_resource)
    """
    try:
        resource.add_method(
            "OPTIONS",
            apigateway.MockIntegration(
                integration_responses=[
                    {
                        "statusCode": "200",
                        "responseParameters": {
                            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,authorization,X-Api-Key,X-Amz-Security-Token,X-Origin-Verify'",
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
        print(f"Note: Could not add OPTIONS method to resource {resource.path}: {e}")
        return False


def create_resource_with_cors(parent_resource, path_part):
    """
    Creates a new API Gateway resource with CORS OPTIONS method.
    This is a convenience wrapper around add_resource() that automatically adds
    the OPTIONS method to support CORS.

    Usage:
    Instead of:
      my_resource = api.root.add_resource("my-resource")
      add_cors_options_method(my_resource)

    Use:
      my_resource = create_resource_with_cors(api.root, "my-resource")

    Args:
        parent_resource: The parent resource (e.g., api.root)
        path_part: The path part for the new resource

    Returns:
        The created API Gateway resource
    """
    resource = parent_resource.add_resource(path_part)
    add_cors_options_method(resource)
    return resource
