import ast
import importlib.util
import json
import os
import sys
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import boto3
import requests
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader

# Import the lambda_middleware from the local module
from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats
from requests_aws4auth import AWS4Auth

# Initialize clients and Powertools utilities
s3_client = boto3.client("s3")
secretsmanager_client = boto3.client("secretsmanager")
logger = Logger()
tracer = Tracer(disabled=True)
metrics = Metrics(namespace="ApiStandardLambda")

################################################################################
# THE EXISTING LAMBDA FUNCTION CODE
################################################################################


@tracer.capture_method
def make_api_call(
    url: str,
    method: str,
    headers: Dict[str, str],
    data: Optional[Any] = None,
    api_auth_type: Optional[str] = None,
    params: Optional[Dict[str, str]] = None,
    region: Optional[str] = None,
    service: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        logger.info(f"Making {method} API call to: {url}")

        logger.info(f"Data: {data}")
        logger.info(f"API Auth Type: {api_auth_type}")
        logger.info(f"Region: {region}")
        logger.info(f"Service: {service}")

        if api_auth_type == "AWSSigV4":
            session = boto3.Session()
            credentials = session.get_credentials()
            region = region or session.region_name or "us-east-1"
            service = service or "execute-api"

            logger.info(f"Using region: {region}")
            logger.info(f"Using service: {service}")

            auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                service,
                session_token=credentials.token,
            )

            logger.info("Created AWS4Auth object")

            if method.lower() == "get":
                response = requests.get(url, auth=auth, headers=headers, params=params)
            elif method.lower() == "post":
                response = requests.post(url, auth=auth, headers=headers, data=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        else:
            if method.lower() == "get":
                response = (
                    requests.get(url, headers=headers, params=params)
                    if params
                    else requests.get(url, headers=headers)
                )
            elif method.lower() == "post":
                if data:
                    # Check if data is in TwelveLabs multipart format (list of tuples)
                    # or standard JSON format (dict)
                    if (
                        isinstance(data, list)
                        and len(data) > 0
                        and isinstance(data[0], tuple)
                    ):
                        # TwelveLabs format: use files parameter for multipart form data
                        response = requests.post(url, headers=headers, files=data)
                    else:
                        # Standard JSON format: use json parameter
                        response = requests.post(url, headers=headers, json=data)
                else:
                    response = requests.post(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response content: {response.text}")

        if 200 <= response.status_code < 300:
            response_data = response.json()
            truncated = _truncate_floats(response_data, max_items=10)

            logger.info(f"Raw API call response: {truncated}")
            return {
                "statusCode": response.status_code,
                "body": json.dumps(response_data),
            }
        else:
            logger.error(f"API call failed with status code: {response.status_code}")
            logger.error(f"API call failed with reason: {response.text}")
            return {
                "statusCode": response.status_code,
                "body": json.dumps(
                    {"error": "API call failed", "details": response.text}
                ),
            }

    except requests.RequestException as e:
        error_message = f"Error making API call: {str(e)}"
        logger.exception(error_message)
        raise Exception(error_message)


def build_environment_dict(config):
    env_vars = {}
    possible_vars = [
        "API_SERVICE_NAME",
        "API_SERVICE_PATH",
        "API_SERVICE_RESOURCE",
        "API_SERVICE_METHOD",
        "API_SERVICE_URL",
        "API_TEMPLATE_BUCKET",
        "API_AUTH_TYPE",
    ]
    for var in possible_vars:
        if hasattr(config, var) and getattr(config, var) is not None:
            env_vars[var] = getattr(config, var)
    default_headers = {"accept": "application/json", "Content-Type": "application/json"}
    headers = config.custom_headers if config.custom_headers else default_headers
    for key, value in headers.items():
        env_vars[f"HEADER_{key.upper()}"] = value
    return env_vars


def retrieve_api_key(api_key_secret_arn: str) -> Dict[str, str]:
    logger.info(f"Retrieving API key for arn: {api_key_secret_arn}")
    try:
        get_secret_value_response = secretsmanager_client.get_secret_value(
            SecretId=api_key_secret_arn
        )
        secret = get_secret_value_response["SecretString"]
        return secret
    except ClientError as e:
        logger.error(f"Error retrieving secret: {e}")
        raise


def load_and_execute_function_from_s3(
    bucket: str, key: str, function_name: str, event: dict
):
    s3_client = boto3.client("s3")
    try:
        logger.info(
            f"Loading function from S3: bucket={bucket}, key=api_templates/{key}, function={function_name}"
        )
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        logger.info(f"File content loaded: {len(file_content)} characters")
        logger.info(f"File content preview: {file_content[:200]}...")

        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(
            file_content, module.__dict__
        )  # nosec B102 - Controlled execution of trusted S3 templates
        if not hasattr(module, function_name):
            available_functions = [
                name
                for name in dir(module)
                if callable(getattr(module, name)) and not name.startswith("_")
            ]
            logger.error(
                f"Function '{function_name}' not found. Available functions: {available_functions}"
            )
            raise AttributeError(
                f"Function '{function_name}' not found in the downloaded file. Available functions: {available_functions}"
            )

        dynamic_function = getattr(module, function_name)
        logger.info(f"Calling function {function_name} with event type: {type(event)}")
        logger.info(f"Event parameter: {event}")

        result = dynamic_function(event)
        logger.info(
            f"Function {function_name} returned: {result} (type: {type(result)})"
        )
        return result
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            print(f"The object {key} does not exist in bucket {bucket}.")
        elif error_code == "NoSuchBucket":
            print(f"The bucket {bucket} does not exist.")
        else:
            print(f"An S3 error occurred: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise


def download_s3_object(bucket: str, key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        print(f"Error downloading S3 object: {e}")
        raise


def create_authentication(api_auth_type: str, api_key_secret_arn: str):
    if api_auth_type == "api_key":
        api_key = retrieve_api_key(api_key_secret_arn)
        return {"x-api-key": api_key}
    else:
        return None


def build_full_url(
    api_service_url: str,
    api_service_resource: Optional[str] = None,
    api_service_path: Optional[str] = None,
) -> str:
    base_url = (
        api_service_url if api_service_url.endswith("/") else api_service_url + "/"
    )
    if api_service_path:
        path = api_service_path.strip("/")
        if api_service_resource:
            path += f"/{api_service_resource.strip('/')}"
    elif api_service_resource:
        path = api_service_resource.strip("/")
    else:
        path = ""
    return urljoin(base_url, path)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)


def build_s3_templates_path(
    api_service_name: str,
    api_service_path: str,
    api_service_method: str,
    templates_path: str,
    api_service_resource: Optional[str] = None,
) -> dict:
    logger.info(f"Building S3 templates path with:")
    logger.info(f"  api_service_name: {api_service_name}")
    logger.info(f"  api_service_path: {api_service_path}")
    logger.info(f"  api_service_method: {api_service_method}")
    logger.info(f"  templates_path: {templates_path}")
    logger.info(f"  api_service_resource: {api_service_resource}")

    if not api_service_resource:
        raise ValueError("API service resource must be provided.")
    base_path = api_service_resource.rstrip("/")
    if api_service_path and api_service_name:
        full_path = f"{api_service_name}/{api_service_path}{base_path}".translate(
            str.maketrans("", "", "{}")
        )
    resource_name = base_path.split("/")[-1]
    file_prefix = f"{resource_name}_{api_service_method.lower()}".translate(
        str.maketrans("", "", "{}")
    )
    request_template = f"{full_path}/{file_prefix}_request.jinja"
    mapping_file = f"{full_path}/{file_prefix}_request_mapping.py"
    url_template = f"{full_path}/{file_prefix}_url.jinja"
    url_mapping_file = f"{full_path}/{file_prefix}_url_mapping.py"
    response_template = f"{full_path}/{file_prefix}_response.jinja"
    response_mapping_file = f"{full_path}/{file_prefix}_response_mapping.py"
    custom_code_file = f"{full_path}/{file_prefix}_custom_code.py"

    templates_dict = {
        "request_template": request_template,
        "mapping_file": mapping_file,
        "url_template": url_template,
        "url_mapping_file": url_mapping_file,
        "response_template": response_template,
        "response_mapping_file": response_mapping_file,
        "custom_code_file": custom_code_file,
    }

    logger.info(f"Generated template paths: {templates_dict}")
    return templates_dict


def request_header_creation():
    headers = json.loads(os.environ.get("CUSTOM_HEADERS", "{}"))
    return headers


def create_request_body(s3_templates, api_template_bucket, event):
    logger.info("Building a request body")
    function_name = "translate_event_to_request"
    request_template_path = f"api_templates/{s3_templates['request_template']}"
    mapping_path = s3_templates["mapping_file"]
    logger.info(api_template_bucket + " " + request_template_path)
    request_template = download_s3_object(api_template_bucket, request_template_path)
    mapping = load_and_execute_function_from_s3(
        api_template_bucket, mapping_path, function_name, event
    )
    env = Environment(
        loader=FileSystemLoader("/tmp/")
    )  # nosec B701 - Controlled template rendering with trusted input
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    request_body = query_template.render(variables=mapping)
    request_body = ast.literal_eval(request_body)
    return request_body


def create_custom_url(s3_templates, api_template_bucket, event):
    logger.info("Building a custom URL")
    logger.info(f"S3 templates dict: {s3_templates}")
    logger.info(f"API template bucket: {api_template_bucket}")

    function_name = "translate_event_to_request"
    url_template_path = f"api_templates/{s3_templates['url_template']}"
    url_mapping_path = s3_templates["url_mapping_file"]

    logger.info(f"Looking for URL template at: {url_template_path}")
    logger.info(f"Looking for URL mapping at: api_templates/{url_mapping_path}")

    try:
        request_template = download_s3_object(api_template_bucket, url_template_path)
        logger.info(f"Successfully downloaded URL template: {url_template_path}")
    except Exception as e:
        logger.error(f"Failed to download URL template {url_template_path}: {str(e)}")
        raise

    try:
        mapping = load_and_execute_function_from_s3(
            api_template_bucket, url_mapping_path, function_name, event
        )
        logger.info(f"Successfully executed URL mapping: {url_mapping_path}")
        logger.info(f"Mapping result: {mapping}")
    except Exception as e:
        logger.error(f"Failed to execute URL mapping {url_mapping_path}: {str(e)}")
        raise

    env = Environment(loader=FileSystemLoader("/tmp/"))  # nosec B701
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    custom_url = query_template.render(variables=mapping)
    logger.info(f"Generated custom URL: {custom_url}")
    return custom_url


def create_response_output(s3_templates, api_template_bucket, response_body, event):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]

    logger.info(f"=== RESPONSE MAPPING DEBUG ===")
    logger.info(f"Response template path: {response_template_path}")
    logger.info(f"Response mapping path: {response_mapping_path}")
    logger.info(f"Response body type: {type(response_body)}")
    logger.info(f"Response body content: {response_body}")
    logger.info(f"Event type: {type(event)}")
    logger.info(
        f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}"
    )

    response_template = download_s3_object(api_template_bucket, response_template_path)
    logger.info(f"Response template loaded: {len(response_template)} characters")

    # Create the combined parameter as expected by the response mapping function
    response_body_and_event = {"response_body": response_body, "event": event}

    logger.info(f"Calling response mapping function with combined parameter")
    logger.info(f"Combined parameter keys: {list(response_body_and_event.keys())}")

    try:
        response_mapping = load_and_execute_function_from_s3(
            api_template_bucket,
            response_mapping_path,
            function_name,
            response_body_and_event,  # Pass as single parameter, not as kwargs
        )
        logger.info(f"Response mapping result type: {type(response_mapping)}")
        logger.info(f"Response mapping result: {response_mapping}")

        # Check for undefined values in response_mapping
        if response_mapping is None:
            logger.error("Response mapping returned None!")
            raise ValueError("Response mapping function returned None")

        # Check for any undefined/None values in the mapping
        for key, value in (
            response_mapping.items() if isinstance(response_mapping, dict) else []
        ):
            if value is None:
                logger.warning(f"Response mapping contains None value for key: {key}")
            elif hasattr(value, "__name__") and "Undefined" in str(type(value)):
                logger.error(
                    f"Response mapping contains Undefined value for key: {key}, type: {type(value)}"
                )
                raise ValueError(
                    f"Response mapping contains undefined value for key: {key}"
                )

    except Exception as e:
        logger.error(f"Error in response mapping execution: {str(e)}")
        logger.error(f"Response mapping function: {function_name}")
        logger.error(f"Response mapping file: {response_mapping_path}")
        raise

    env = Environment(loader=FileSystemLoader("/tmp/"))  # nosec B701
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)

    logger.info(f"Rendering template with variables: {response_mapping}")
    try:
        response_output = query_template.render(variables=response_mapping)
        logger.info(f"Template rendered successfully: {response_output}")
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        logger.error(f"Template: {response_template}")
        logger.error(f"Variables: {response_mapping}")
        raise

    try:
        dict_output = json.loads(response_output)
        logger.info(f"JSON parsed successfully: {dict_output}")
        logger.info(f"=== END RESPONSE MAPPING DEBUG ===")
        return dict_output
    except Exception as e:
        logger.error(f"Error parsing JSON: {str(e)}")
        logger.error(f"JSON string: {response_output}")
        raise


def load_custom_modules(api_template_bucket: str, custom_code_paths: list):
    """
    Load custom code modules from S3 and make them available for import
    """
    loaded_modules = {}
    logger.info(f"=== CUSTOM CODE LOADING DEBUG ===")
    logger.info(f"Bucket: {api_template_bucket}")
    logger.info(f"Custom code paths: {custom_code_paths}")

    for module_path in custom_code_paths:
        try:
            logger.info(f"Loading custom code module from: {module_path}")
            logger.info(f"Full S3 path: s3://{api_template_bucket}/{module_path}")

            # Check if the object exists first
            try:
                s3_client.head_object(Bucket=api_template_bucket, Key=module_path)
                logger.info(f"✓ S3 object exists: {module_path}")
            except ClientError as head_error:
                logger.error(f"✗ S3 object does not exist: {module_path}")
                logger.error(f"Head object error: {head_error}")

                # List objects in the parent directory for debugging
                try:
                    parent_path = "/".join(module_path.split("/")[:-1]) + "/"
                    logger.info(f"Listing objects in parent directory: {parent_path}")
                    list_response = s3_client.list_objects_v2(
                        Bucket=api_template_bucket, Prefix=parent_path, MaxKeys=20
                    )
                    if "Contents" in list_response:
                        logger.info(
                            f"Found {len(list_response['Contents'])} objects in {parent_path}:"
                        )
                        for obj in list_response["Contents"]:
                            logger.info(
                                f"  - {obj['Key']} (size: {obj['Size']}, modified: {obj['LastModified']})"
                            )
                    else:
                        logger.info(f"No objects found in {parent_path}")
                except Exception as list_error:
                    logger.error(f"Error listing parent directory: {list_error}")

                raise head_error

            response = s3_client.get_object(Bucket=api_template_bucket, Key=module_path)
            file_content = response["Body"].read().decode("utf-8")
            logger.info(
                f"✓ Successfully downloaded file: {len(file_content)} characters"
            )
            logger.info(
                f"File content preview (first 200 chars): {file_content[:200]}..."
            )

            # Extract module name from path (e.g., "coactive/shared/coactive_auth.py" -> "coactive_auth")
            module_name = module_path.split("/")[-1].replace(".py", "")
            logger.info(f"Module name extracted: {module_name}")

            spec = importlib.util.spec_from_loader(module_name, loader=None)
            module = importlib.util.module_from_spec(spec)
            exec(file_content, module.__dict__)

            # Make module available in sys.modules for import
            sys.modules[module_name] = module
            loaded_modules[module_name] = module

            # Log available functions in the module
            available_functions = [
                name
                for name in dir(module)
                if callable(getattr(module, name)) and not name.startswith("_")
            ]
            logger.info(f"✓ Successfully loaded custom code module: {module_name}")
            logger.info(f"Available functions in {module_name}: {available_functions}")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(f"✗ AWS S3 ClientError loading {module_path}:")
            logger.error(f"  Error Code: {error_code}")
            logger.error(f"  Error Message: {error_message}")
            logger.error(f"  Bucket: {api_template_bucket}")
            logger.error(f"  Key: {module_path}")

            # Additional debugging for NoSuchKey errors
            if error_code == "NoSuchKey":
                logger.error(f"NoSuchKey Debug Info:")
                logger.error(
                    f"  - Verify the file exists at: s3://{api_template_bucket}/{module_path}"
                )
                logger.error(
                    f"  - Check if the bucket name is correct: {api_template_bucket}"
                )
                logger.error(f"  - Check if the key path is correct: {module_path}")
                logger.error(
                    f"  - Verify Lambda has s3:GetObject permission on arn:aws:s3:::{api_template_bucket}/*"
                )

            raise
        except Exception as e:
            logger.error(
                f"✗ Unexpected error loading custom code module {module_path}: {str(e)}"
            )
            logger.error(f"Error type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    logger.info(f"=== CUSTOM CODE LOADING COMPLETE ===")
    logger.info(f"Total modules loaded: {len(loaded_modules)}")

    return loaded_modules


def load_and_execute_pre_request_custom_code(api_template_bucket: str, event: dict):
    """
    Execute pre-request custom code (before API call)
    """
    try:
        logger.info("=== PRE-REQUEST CUSTOM CODE EXECUTION ===")

        # Check for PRE_CUSTOM_CODE first, then fall back to legacy CUSTOM_CODE
        pre_custom_code_location = os.environ.get("PRE_CUSTOM_CODE")
        legacy_custom_code_location = os.environ.get("CUSTOM_CODE")

        logger.info(f"PRE_CUSTOM_CODE environment variable: {pre_custom_code_location}")
        logger.info(
            f"CUSTOM_CODE environment variable (legacy): {legacy_custom_code_location}"
        )

        if not pre_custom_code_location:
            # Fall back to legacy CUSTOM_CODE for backward compatibility
            pre_custom_code_location = legacy_custom_code_location
            if pre_custom_code_location:
                logger.info(f"Using legacy CUSTOM_CODE: {pre_custom_code_location}")

        if pre_custom_code_location:
            custom_code_paths = [
                path.strip() for path in pre_custom_code_location.split(",")
            ]
            logger.info(f"Loading pre-request custom code modules: {custom_code_paths}")
            logger.info(f"API template bucket: {api_template_bucket}")

            loaded_modules = load_custom_modules(api_template_bucket, custom_code_paths)
            logger.info(
                f"Successfully loaded {len(loaded_modules)} modules: {list(loaded_modules.keys())}"
            )

            # Look for process_api_request in the loaded modules
            process_api_request_found = False
            for module_name, module in loaded_modules.items():
                logger.info(
                    f"Checking module '{module_name}' for process_api_request function..."
                )

                if hasattr(module, "process_api_request"):
                    logger.info(f"✓ Found process_api_request in module: {module_name}")
                    process_api_request_found = True

                    try:
                        custom_function = getattr(module, "process_api_request")
                        logger.info(f"Executing process_api_request from {module_name}")
                        logger.info(
                            f"Input event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}"
                        )

                        result = custom_function(event)

                        logger.info(
                            f"✓ process_api_request execution completed successfully"
                        )
                        logger.info(f"Result type: {type(result)}")
                        if isinstance(result, dict):
                            logger.info(f"Result keys: {list(result.keys())}")
                            if "headers" in result:
                                logger.info(
                                    f"Headers added by custom code: {result['headers']}"
                                )

                        return result

                    except Exception as func_error:
                        logger.error(
                            f"✗ Error executing process_api_request in {module_name}: {str(func_error)}"
                        )
                        import traceback

                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                else:
                    available_functions = [
                        name
                        for name in dir(module)
                        if callable(getattr(module, name)) and not name.startswith("_")
                    ]
                    logger.info(
                        f"✗ No process_api_request in {module_name}. Available functions: {available_functions}"
                    )

            # If no process_api_request found in loaded modules, return original event
            if not process_api_request_found:
                logger.warning(
                    f"No process_api_request function found in any of the loaded modules: {list(loaded_modules.keys())}"
                )
                logger.info("Returning original event unchanged")

            return event

        # No custom code specified, return original event
        logger.info("No pre-request custom code specified, returning original event")
        return event

    except Exception as e:
        logger.error(f"✗ Error in pre-request custom code execution: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def load_and_execute_custom_code(
    api_template_bucket: str, s3templates: dict, api_response: dict, event: dict
):
    try:
        # Check for POST_CUSTOM_CODE first, then fall back to legacy CUSTOM_CODE
        post_custom_code_location = os.environ.get("POST_CUSTOM_CODE")
        if not post_custom_code_location:
            # Fall back to legacy CUSTOM_CODE for backward compatibility
            post_custom_code_location = os.environ.get("CUSTOM_CODE")

        if post_custom_code_location:
            custom_code_paths = [
                path.strip() for path in post_custom_code_location.split(",")
            ]
            logger.info(
                f"Loading post-request custom code modules: {custom_code_paths}"
            )
            loaded_modules = load_custom_modules(api_template_bucket, custom_code_paths)

            # Look for process_api_response in the loaded modules
            for module_name, module in loaded_modules.items():
                if hasattr(module, "process_api_response"):
                    logger.info(f"Found process_api_response in module: {module_name}")
                    custom_function = getattr(module, "process_api_response")
                    result = custom_function(api_response, event)
                    return result

            # If no process_api_response found in loaded modules, return original response
            logger.warning(
                "No process_api_response function found in loaded modules, returning original response"
            )
            return api_response

        # Fallback to individual custom code file if no shared modules
        if "custom_code_file" in s3templates:
            response = s3_client.get_object(
                Bucket=api_template_bucket, Key=s3templates["custom_code_file"]
            )
            file_content = response["Body"].read().decode("utf-8")
            spec = importlib.util.spec_from_loader("custom_module", loader=None)
            module = importlib.util.module_from_spec(spec)
            exec(file_content, module.__dict__)

            if not hasattr(module, "process_api_response"):
                raise AttributeError(
                    "Function 'process_api_response' not found in the custom code file."
                )
            custom_function = getattr(module, "process_api_response")
            result = custom_function(api_response, event)
            return result

        # No custom code specified, return original response
        logger.info("No custom code specified, returning original response")
        return api_response
    except Exception as e:
        logger.error(f"Error in custom code execution: {str(e)}")
        raise


################################################################################
# LAMBDA HANDLER (DECORATED WITH IMPORTED MIDDLEWARE)
################################################################################


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    time.time()

    # Log all environment variables for debugging
    logger.info("=== ENVIRONMENT VARIABLES ===")
    workflow_step_name = os.environ.get("WORKFLOW_STEP_NAME")
    api_service_url = os.environ.get("API_SERVICE_URL")
    api_key_secret_arn = os.environ.get("API_KEY_SECRET_ARN")
    request_templates_path = os.environ.get("REQUEST_TEMPLATES_PATH")
    os.environ.get("RESPONSE_TEMPLATES_PATH")
    api_service_resource = os.environ.get("API_SERVICE_RESOURCE")
    api_service_path = os.environ.get("API_SERVICE_PATH")
    api_service_method = os.environ.get("API_SERVICE_METHOD")
    api_auth_type = os.environ.get("API_AUTH_TYPE")
    api_service_name = os.environ.get("API_SERVICE_NAME")
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET")
    api_custom_url = os.environ.get("API_CUSTOM_URL", "false").lower() == "true"
    api_custom_code = os.environ.get("API_CUSTOM_CODE", "false").lower() == "true"
    is_last_step = os.environ.get("IS_LAST_STEP", "false").lower() == "true"

    logger.info(f"WORKFLOW_STEP_NAME: {workflow_step_name}")
    logger.info(f"API_SERVICE_URL: {api_service_url}")
    logger.info(f"API_SERVICE_RESOURCE: {api_service_resource}")
    logger.info(f"API_SERVICE_PATH: {api_service_path}")
    logger.info(f"API_SERVICE_METHOD: {api_service_method}")
    logger.info(f"API_SERVICE_NAME: {api_service_name}")
    logger.info(f"API_TEMPLATE_BUCKET: {api_template_bucket}")
    logger.info(f"REQUEST_TEMPLATES_PATH: {request_templates_path}")
    logger.info(f"API_CUSTOM_URL: {api_custom_url}")
    logger.info("=== END ENVIRONMENT VARIABLES ===")

    try:
        s3_templates = build_s3_templates_path(
            api_service_name=api_service_name,
            api_service_path=api_service_path,
            api_service_resource=api_service_resource,
            templates_path=request_templates_path,
            api_service_method=api_service_method,
        )
    except ValueError as e:
        raise RuntimeError(f"Error building S3 template paths: {str(e)}")

    request_headers = request_header_creation()
    logger.info(f"Request headers are: {request_headers}")

    auth_credentials = create_authentication(api_auth_type, api_key_secret_arn)
    if api_auth_type == "api_key" and auth_credentials:
        request_headers.update(auth_credentials)

    if api_service_method.upper() != "GET":
        request_body = create_request_body(s3_templates, api_template_bucket, event)
        # Check if the request mapping added headers to the event
        if "headers" in event and event["headers"]:
            logger.info(f"Found headers from request mapping: {event['headers']}")
            request_headers.update(event["headers"])
    else:
        request_body = None

    try:
        if api_custom_url:
            api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
        else:
            api_full_url = build_full_url(
                api_service_url=api_service_url,
                api_service_resource=api_service_resource,
                api_service_path=api_service_path,
            )
    except ValueError as e:
        raise RuntimeError(f"Error building URL: {str(e)}")

    try:
        # Execute pre-request custom code if available (for authentication, etc.)
        # Check for PRE_CUSTOM_CODE first, then fall back to legacy CUSTOM_CODE
        pre_custom_code_location = os.environ.get("PRE_CUSTOM_CODE")
        if not pre_custom_code_location:
            # Fall back to legacy CUSTOM_CODE for backward compatibility
            pre_custom_code_location = os.environ.get("CUSTOM_CODE")

        if pre_custom_code_location:
            try:
                logger.info("Executing pre-request custom code")
                event = load_and_execute_pre_request_custom_code(
                    api_template_bucket, event
                )
                # Check if the pre-request custom code added headers to the event
                if "headers" in event and event["headers"]:
                    logger.info(
                        f"Found headers from pre-request custom code: {event['headers']}"
                    )
                    request_headers.update(event["headers"])
            except Exception as e:
                logger.error(f"Error executing pre-request custom code: {str(e)}")
                raise RuntimeError(f"Error executing pre-request custom code: {str(e)}")

        api_response = make_api_call(
            url=api_full_url,
            method=api_service_method,
            headers=request_headers,
            data=request_body if api_service_method.lower() != "get" else None,
            api_auth_type=api_auth_type,
        )

        response_body = json.loads(api_response["body"])

        # Check if custom code file exists and use it, otherwise fall back to standard response mapping
        # Use standard response mapping for all integrations
        logger.info("Using standard response mapping")
        response_output = create_response_output(
            s3_templates, api_template_bucket, response_body, event
        )

        truncated = _truncate_floats(response_output, max_items=10)
        logger.info(
            f"Formatted response output (truncated) is {response_body} {truncated}"
        )

        return response_output

    except Exception as e:
        error_message = f"Error in lambda_handler: {str(e)}"
        logger.error(error_message)
        raise Exception(error_message)
