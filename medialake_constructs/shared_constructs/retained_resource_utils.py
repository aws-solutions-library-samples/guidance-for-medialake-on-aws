from typing import Any, Dict, Optional, Tuple

import boto3

from config import config


def check_retained_resource(
    resource_type: str, resource_id: str, region: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if a retained resource exists in SSM parameters.

    Args:
        resource_type: The type of resource (e.g., 'dynamodb-table', 's3-bucket')
        resource_id: The ID of the resource
        region: The AWS region

    Returns:
        A tuple containing:
        - A boolean indicating if the resource exists
        - A dictionary containing the resource information if it exists, None otherwise
    """
    if config.environment != "prod":
        # Only check for retained resources in production
        return False, None

    try:
        ssm_client = boto3.client("ssm", region_name=region)
        param_prefix = f"/medialake/{config.environment}/retained-resources/{resource_type}/{resource_id}"

        # Get the ARN parameter
        arn_param = f"{param_prefix}/arn"
        arn_response = ssm_client.get_parameter(Name=arn_param)
        resource_arn = arn_response["Parameter"]["Value"]

        # Get all parameters for this resource
        resource_info = {"arn": resource_arn}

        # Try to get additional parameters
        try:
            paginator = ssm_client.get_paginator("get_parameters_by_path")
            for page in paginator.paginate(Path=param_prefix, Recursive=True):
                for param in page["Parameters"]:
                    # Extract the attribute name from the parameter name
                    param_name = param["Name"]
                    attribute = param_name.split("/")[-1]
                    if attribute != "arn":  # We already have the ARN
                        resource_info[attribute] = param["Value"]
        except Exception:
            # It's okay if we can't get additional parameters
            pass

        return True, resource_info
    except Exception as e:
        print(
            f"Could not find retained resource {resource_type}/{resource_id}: {str(e)}"
        )
        return False, None
