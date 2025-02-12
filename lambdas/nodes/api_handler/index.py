import os
import json
import time
import boto3
from botocore.exceptions import ClientError
import requests
from typing import Dict, Any, Optional
from urllib.parse import urljoin
import importlib.util
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from jinja2 import Environment, FileSystemLoader
from requests_aws4auth import AWS4Auth

s3_client = boto3.client("s3")
secretsmanager_client = boto3.client("secretsmanager")

# Initialize Powertools
logger = Logger()
tracer = Tracer(disabled=True)
metrics = Metrics(namespace="ApiStandardLambda")


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
        logger.info(f"Headers: {headers}")
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
            # Existing code for other authentication types
            if method.lower() == "get":
                if params:
                    response = requests.get(url, headers=headers, params=params)
                else:
                    response = requests.get(url, headers=headers)
            elif method.lower() == "post":
                if data:
                    response = requests.post(url, headers=headers, data=data)
                else:
                    response = requests.post(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response content: {response.text}")

        if response.status_code >= 200 and response.status_code < 300:
            response_data = response.json()
            logger.info(f"API call successful: {response_data}")
            metrics.add_metric(
                name="SuccessfulApiCalls", unit=MetricUnit.Count, value=1
            )
            return {
                "statusCode": response.status_code,
                "body": json.dumps(response_data),
            }
        else:
            logger.error(f"API call failed with status code: {response.status_code}")
            logger.error(f"API call failed with reason: {response.text}")
            metrics.add_metric(name="FailedApiCalls", unit=MetricUnit.Count, value=1)
            return {
                "statusCode": response.status_code,
                "body": json.dumps({"error": "API call failed"}),
            }

    except requests.RequestException as e:
        logger.exception(f"Error making API call: {str(e)}")
        metrics.add_metric(name="ApiCallErrors", unit=MetricUnit.Count, value=1)
        return {
            "body": json.dumps({"error": "Internal server error"}),
        }


def build_environment_dict(config):
    """
    Build the environment dictionary for the Lambda function,
    only including variables that are defined in the config.
    """
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

    # Default headers
    default_headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    # Include custom headers if provided, otherwise use default headers
    headers = config.custom_headers if config.custom_headers else default_headers
    for key, value in headers.items():
        env_vars[f"HEADER_{key.upper()}"] = value

    return env_vars


def retrieve_api_key(service_name: str) -> Dict[str, str]:
    """Retrieve the API key from AWS Secrets Manager."""
    secret_name = f"{service_name}_api_key"
    try:
        get_secret_value_response = secretsmanager_client.get_secret_value(
            SecretId=secret_name
        )
        secret = json.loads(get_secret_value_response["SecretString"])
        return secret
    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise


def load_and_execute_function_from_s3(
    bucket: str, key: str, function_name: str, event: dict
):
    """
    Download a Python file from S3, load the specified function, and execute it with the given event.

    :param bucket: Name of the S3 bucket
    :param key: Key of the S3 object (file path within the bucket)
    :param function_name: Name of the function to execute from the downloaded file
    :param event: Event data to pass to the function
    :return: Result of the executed function
    """
    s3_client = boto3.client("s3")

    try:
        # Download the file from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response["Body"].read().decode("utf-8")

        # Create a temporary module
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)

        # Execute the downloaded code in the module's context
        exec(file_content, module.__dict__)

        # Get the specified function from the module
        if not hasattr(module, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in the downloaded file."
            )

        dynamic_function = getattr(module, function_name)

        # Execute the function with the provided event
        result = dynamic_function(event)

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

    except SyntaxError as e:
        print(f"Syntax error in the downloaded Python file: {e}")
        raise

    except AttributeError as e:
        print(f"Function not found error: {e}")
        raise

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise


def download_s3_object(bucket: str, key: str) -> str:
    """Download an object from S3 and return its content."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        print(f"Error downloading S3 object: {e}")
        raise


def create_authentication(api_auth_type: str, api_service_name: str):
    if api_auth_type == "api_key":
        api_key = retrieve_api_key(api_service_name)
        return api_key
    else:
        return None


def build_full_url(
    api_service_url: str,
    api_service_resource: Optional[str] = None,
    api_service_path: Optional[str] = None,
) -> str:
    """
    Construct the full API URL based on the host URL, resource, and path.

    :param api_service_url: The host URL (e.g., "https://api.example.com")
    :param api_service_resource: Optional resource to append to the URL
    :param api_service_path: Optional path to insert between the host and resource
    :return: The full constructed URL
    """
    # Ensure api_service_url ends with a slash
    base_url = (
        api_service_url if api_service_url.endswith("/") else api_service_url + "/"
    )

    # Construct the path
    if api_service_path:
        path = api_service_path.strip("/")
        if api_service_resource:
            path += f"/{api_service_resource.strip('/')}"
    elif api_service_resource:
        path = api_service_resource.strip("/")
    else:
        path = ""

    # Join the base URL and path
    return urljoin(base_url, path)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)


def build_s3_templates_path(
    api_service_name: str,
    api_service_method: str,
    api_service_resource: Optional[str] = None,
    api_service_path: Optional[str] = None,
) -> dict:
    """
    Builds S3 object paths for request template and mapping file based on service name, method, resource, and path.
    Handles cases where input variables may or may not have leading/trailing slashes.

    :param api_service_name: The name of the API service
    :param api_service_method: The HTTP method (e.g., GET, POST)
    :param api_service_resource: Optional resource name
    :param api_service_path: Optional path
    :return: A dictionary containing paths for request template and mapping file
    """

    def clean_path(path: str) -> str:
        """Remove leading and trailing slashes from a path."""
        return path.strip("/")

    base_path = clean_path(api_service_name)

    if api_service_path and api_service_resource:
        full_path = f"{base_path}/{clean_path(api_service_path)}/{clean_path(api_service_resource)}"
    elif api_service_resource:
        full_path = f"{base_path}/{clean_path(api_service_resource)}"
    else:
        full_path = base_path

    # Construct the file names with method included
    if api_service_resource:
        file_prefix = f"{clean_path(api_service_resource)}_{api_service_method.lower()}"
    else:
        file_prefix = api_service_method.lower()

    request_template = f"{full_path}/{file_prefix}_request.jinja"
    mapping_file = f"{full_path}/{file_prefix}_request_mapping.py"
    url_template = f"{full_path}/{file_prefix}_url.jinja"
    url_mapping_file = f"{full_path}/{file_prefix}_url_mapping.py"
    response_template = f"{full_path}/{file_prefix}_response.jinja"
    response_mapping_file = f"{full_path}/{file_prefix}_response_mapping.py"
    custom_code_file = f"{full_path}/{file_prefix}_custom_code.py"

    template_mapping = {
        "request_template": request_template,
        "mapping_file": mapping_file,
        "url_template": url_template,
        "url_mapping_file": url_mapping_file,
        "response_template": response_template,
        "response_mapping_file": response_mapping_file,
        "custom_code_file": custom_code_file,
    }
    return template_mapping


def request_header_creation():
    request_headers = json.loads(os.environ.get("CUSTOM_HEADERS", "{}"))
    return request_headers


def create_request_body(s3_templates, api_template_bucket, event):
    function_name = "translate_event_to_request"
    request_template_path = s3_templates["request_template"]
    mapping_path = s3_templates["mapping_file"]

    request_template = download_s3_object(api_template_bucket, request_template_path)
    mapping = load_and_execute_function_from_s3(
        api_template_bucket, mapping_path, function_name, event
    )

    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    request_body = query_template.render(variables=mapping)

    return request_body


def create_custom_url(s3_templates, api_template_bucket, event):
    print("Building a custom URL ")
    function_name = "translate_event_to_request"
    url_template_path = s3_templates["url_template"]
    url_mapping_path = s3_templates["url_mapping_file"]

    print(url_template_path)
    request_template = download_s3_object(api_template_bucket, url_template_path)
    mapping = load_and_execute_function_from_s3(
        api_template_bucket, url_mapping_path, function_name, event
    )
    print(f"Mapping is: {mapping}")
    print(f"Event is: {event}")
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    custom_url = query_template.render(variables=mapping)
    print(f"custom url is {custom_url}")
    return custom_url


def create_response_output(s3_templates, api_template_bucket, response_body):
    function_name = "translate_event_to_request"
    response_template_path = s3_templates["response_template"]
    response_mapping_path = s3_templates["response_mapping_file"]

    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket, response_mapping_path, function_name, response_body
    )
    print(f"Mapping is: {response_mapping}")
    print(f"Event is: {response_body}")
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    dict_output = json.loads(response_output)
    return dict_output


def load_and_execute_custom_code(
    api_template_bucket: str, s3templates: str, api_response: dict, event: dict
):
    """
    Download a Python file from S3, load the 'process_api_response' function, and execute it with the given API response and event.

    :param bucket: Name of the S3 bucket
    :param key: Key of the S3 object (file path within the bucket)
    :param api_response: The API response to process
    :param event: The original event data
    :return: Result of the executed function
    """
    try:
        # Download the file from S3
        response = s3_client.get_object(
            Bucket=api_template_bucket, Key=s3templates["custom_code_file"]
        )
        file_content = response["Body"].read().decode("utf-8")

        # Create a temporary module
        spec = importlib.util.spec_from_loader("custom_module", loader=None)
        module = importlib.util.module_from_spec(spec)

        # Execute the downloaded code in the module's context
        exec(file_content, module.__dict__)

        # Get the specified function from the module
        if not hasattr(module, "process_api_response"):
            raise AttributeError(
                "Function 'process_api_response' not found in the custom code file."
            )

        custom_function = getattr(module, "process_api_response")

        # Execute the function with the provided API response and event
        result = custom_function(api_response, event)

        return result

    except Exception as e:
        logger.error(f"Error in custom code execution: {str(e)}")
        raise


@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function."""
    start_time = time.time()

    workflow_step_name = os.environ.get("WORKFLOW_STEP_NAME")
    api_service_url = os.environ.get("API_SERVICE_URL")
    api_service_resource = os.environ.get("API_SERVICE_RESOURCE")
    api_service_path = os.environ.get("API_SERVICE_PATH")
    api_service_method = os.environ.get("API_SERVICE_METHOD")
    api_auth_type = os.environ.get("API_AUTH_TYPE")
    api_service_name = os.environ.get("API_SERVICE_NAME")
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET")
    api_custom_url = os.environ.get("API_CUSTOM_URL", "false").lower() == "true"
    api_custom_code = os.environ.get("API_CUSTOM_CODE", "false").lower() == "true"
    is_last_step = os.environ.get("IS_LAST_STEP", "false").lower() == "true"

    # Extract metadata from the event
    metadata = event.get("metadata", {})

    # build s3 object keys and paths for templates
    try:
        s3_templates = build_s3_templates_path(
            api_service_name=api_service_name,
            api_service_path=api_service_path,
            api_service_resource=api_service_resource,
            api_service_method=api_service_method,
        )
    except ValueError as e:
        return {
            "statusCode": 500,
            "body": f"Error building S3 template paths: {str(e)}",
        }

    # Get API header
    request_headers = request_header_creation()

    # Build auth
    auth_credentials = create_authentication(api_auth_type, api_service_name)

    if api_auth_type == "api_key":
        request_headers.update(auth_credentials)

    # Create request body
    if api_service_method != "GET":
        request_body = create_request_body(s3_templates, api_template_bucket, event)

    # Build the full URL used in the API call
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
        return {"statusCode": 500, "body": f"Error building URL: {str(e)}"}

    # Make API call
    try:
        api_response = make_api_call(
            url=api_full_url,
            method=api_service_method,
            headers=request_headers,
            data=request_body if api_service_method.lower() != "get" else None,
            api_auth_type=api_auth_type,
        )

        response_body = json.loads(api_response["body"])

        # print(f"right before response output{response_body}")

        ##
        if api_custom_code:
            # Execute custom code from S3
            try:
                response_output = load_and_execute_custom_code(
                    api_template_bucket, s3_templates, response_body, event
                )
                print(f"API Custome code response output is {response_output}")
            except Exception as e:
                return {
                    "statusCode": 500,
                    "body": f"Error executing custom code: {str(e)}",
                }
        else:
            # Use the default response processing
            response_output = create_response_output(
                s3_templates, api_template_bucket, response_body
            )

        print(f"Response output is {response_output}")
        # Update metadata
        metadata.update(
            {
                "service": api_service_name,
                "stepName": workflow_step_name,
                "stepStatus": "Completed",
                "stepId": metadata.get("stepId", ""),  # Preserve existing stepId
                "workflowName": metadata.get(
                    "workflowName", ""
                ),  # Preserve existing workflowName
                "workflowStatus": "completed" if is_last_step else "inProgress",
                "workflowId": metadata.get(
                    "workflowId", ""
                ),  # Preserve existing workflowId
                "workflowExecutionId": metadata.get(
                    "workflowExecutionId", ""
                ),  # Preserve existing workflowExecutionId
                "duration": round(time.time() - start_time, 3),  # Duration in seconds
            }
        )

        # Add metadata to response_output
        # response_output["metadata"] = metadata

        # Get the payload from the event
        payload = event.get("payload", {})

        # Merge the payload with response_output, prioritizing response_output data
        merged_output = payload.copy()  # Start with a copy of payload

        merged_output.update(response_output["payload"])  # Update with response_output

        # Create the final output structure
        final_output = {
            "metadata": metadata,
            "payload": merged_output,  # Place the merged output in "payload"
            # Keep metadata at the top level
        }

        output_size = len(json.dumps(final_output).encode("utf-8"))

        if output_size > 240 * 1024:  # 240KB in bytes
            # Get the S3 bucket name from environment variable
            external_payload_s3_bucket = os.environ.get("EXTERNAL_PAYLOAD_S3_BUCKET")

            # Generate a unique key for the S3 object
            workflow_id = event["metadata"].get("workflowId", "unknown")
            execution_id = event["metadata"].get("executionId", "unknown")
            step_id = event["metadata"].get("stepId", "unknown")
            s3_key = f"{workflow_id}/{execution_id}/{step_id}-payload.json"

            if not external_payload_s3_bucket:
                logger.error(
                    "external_payload_s3_bucket environment variable is not set"
                )
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {"error": "External payload S3 bucket not configured"}
                    ),
                }
            try:
                logger.info(external_payload_s3_bucket)
                logger.info(json.dumps(final_output["payload"]))
                s3_client.put_object(
                    Bucket=external_payload_s3_bucket,
                    Key=s3_key,
                    Body=json.dumps(final_output["payload"]),
                )

                # Update the final_output
                final_output["metadata"]["externalPayload"] = True
                final_output["payload"] = {}
                final_output["payload"]["externalPayloadLocation"] = {
                    "bucket": external_payload_s3_bucket,
                    "key": s3_key,
                }
                # logger.info(f"Large payload written to S3: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to write payload to S3: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {"error": "Failed to write large payload to S3"}
                    ),
                }

        print("Final output:", json.dumps(final_output, cls=CustomJSONEncoder))
        return final_output

    except Exception as e:
        # Handle any exceptions that occur during the API call or processing
        error_message = f"Error in lambda_handler: {str(e)}"
        logger.error(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message}),
        }
