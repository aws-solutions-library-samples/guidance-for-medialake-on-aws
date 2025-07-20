import ast
import importlib.util
import json
import os
import re
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
                response = (
                    requests.post(url, headers=headers, files=data)
                    if data
                    else requests.post(url, headers=headers)
                )
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
                "body": json.dumps({"error": "API call failed"}),
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
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in the downloaded file."
            )
        dynamic_function = getattr(module, function_name)
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
    return {
        "request_template": request_template,
        "mapping_file": mapping_file,
        "url_template": url_template,
        "url_mapping_file": url_mapping_file,
        "response_template": response_template,
        "response_mapping_file": response_mapping_file,
        "custom_code_file": custom_code_file,
    }


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
    env = Environment(loader=FileSystemLoader("/tmp/"))  # nosec B701
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    request_body = query_template.render(variables=mapping)
    request_body = ast.literal_eval(request_body)
    return request_body


def create_custom_url(s3_templates, api_template_bucket, event):
    logger.info("Building a custom URL")
    function_name = "translate_event_to_request"
    url_template_path = f"api_templates/{s3_templates['url_template']}"
    url_mapping_path = s3_templates["url_mapping_file"]
    request_template = download_s3_object(api_template_bucket, url_template_path)
    mapping = load_and_execute_function_from_s3(
        api_template_bucket, url_mapping_path, function_name, event
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))  # nosec B701
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    custom_url = query_template.render(variables=mapping)
    return custom_url


def create_response_output(s3_templates, api_template_bucket, response_body, event):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(
        api_template_bucket,
        response_mapping_path,
        function_name,
        {"response_body": response_body, "event": event},
    )
    env = Environment(loader=FileSystemLoader("/tmp/"))  # nosec B701
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    dict_output = json.loads(response_output)
    return dict_output


def load_and_execute_custom_code(
    api_template_bucket: str, s3templates: dict, api_response: dict, event: dict
):
    try:
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

    os.environ.get("WORKFLOW_STEP_NAME")
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

    try:
        s3_templates = build_s3_templates_path(
            api_service_name=api_service_name,
            api_service_path=api_service_path,
            api_service_resource=api_service_resource,
            templates_path=request_templates_path,
            api_service_method=api_service_method,
        )
    except ValueError as e:
        return {
            "statusCode": 500,
            "body": f"Error building S3 template paths: {str(e)}",
        }

    request_headers = request_header_creation()
    logger.info(f"Request headers are: {request_headers}")

    auth_credentials = create_authentication(api_auth_type, api_key_secret_arn)
    if api_auth_type == "api_key" and auth_credentials:
        request_headers.update(auth_credentials)

    if api_service_method.upper() != "GET":
        request_body = create_request_body(s3_templates, api_template_bucket, event)
    else:
        request_body = None

    try:
        if api_service_resource and re.search(r"{\w+}", api_service_resource):
            api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
        else:
            api_full_url = build_full_url(
                api_service_url=api_service_url,
                api_service_resource=api_service_resource,
                api_service_path=api_service_path,
            )
    except ValueError as e:
        return {"statusCode": 500, "body": f"Error building URL: {str(e)}"}

    try:
        api_response = make_api_call(
            url=api_full_url,
            method=api_service_method,
            headers=request_headers,
            data=request_body if api_service_method.lower() != "get" else None,
            api_auth_type=api_auth_type,
        )

        response_body = json.loads(api_response["body"])

        if api_custom_code:
            try:
                response_output = load_and_execute_custom_code(
                    api_template_bucket, s3_templates, response_body, event
                )
            except Exception as e:
                return {
                    "statusCode": 500,
                    "body": f"Error executing custom code: {str(e)}",
                }
        else:
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
