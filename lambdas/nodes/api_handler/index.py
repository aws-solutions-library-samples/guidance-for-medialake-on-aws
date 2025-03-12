# import os
# import json
# import time
# import ast
# import boto3
# from botocore.exceptions import ClientError
# import requests
# from typing import Dict, Any, Optional
# from urllib.parse import urljoin
# import importlib.util
# from aws_lambda_powertools import Logger, Tracer, Metrics
# from aws_lambda_powertools.metrics import MetricUnit
# from jinja2 import Environment, FileSystemLoader
# from requests_aws4auth import AWS4Auth

# s3_client = boto3.client("s3")
# secretsmanager_client = boto3.client("secretsmanager")

# # Initialize Powertools
# logger = Logger()
# tracer = Tracer(disabled=True)
# metrics = Metrics(namespace="ApiStandardLambda")


# @tracer.capture_method
# def make_api_call(
#     url: str,
#     method: str,
#     headers: Dict[str, str],
#     data: Optional[Any] = None,
#     api_auth_type: Optional[str] = None,
#     params: Optional[Dict[str, str]] = None,
#     region: Optional[str] = None,
#     service: Optional[str] = None,
# ) -> Dict[str, Any]:
#     try:
#         logger.info(f"Making {method} API call to: {url}")
#         logger.info(f"Headers: {headers}")
#         logger.info(f"Data: {data}")
#         logger.info(f"API Auth Type: {api_auth_type}")
#         logger.info(f"Region: {region}")
#         logger.info(f"Service: {service}")

#         if api_auth_type == "AWSSigV4":
#             session = boto3.Session()
#             credentials = session.get_credentials()
#             region = region or session.region_name or "us-east-1"
#             service = service or "execute-api"

#             logger.info(f"Using region: {region}")
#             logger.info(f"Using service: {service}")

#             auth = AWS4Auth(
#                 credentials.access_key,
#                 credentials.secret_key,
#                 region,
#                 service,
#                 session_token=credentials.token,
#             )

#             logger.info("Created AWS4Auth object")

#             if method.lower() == "get":
#                 response = requests.get(url, auth=auth, headers=headers, params=params)
#             elif method.lower() == "post":
#                 response = requests.post(url, auth=auth, headers=headers, data=data)
#             else:
#                 raise ValueError(f"Unsupported HTTP method: {method}")
#         else:
#             # Existing code for other authentication types
#             if method.lower() == "get":
#                 if params:
#                     response = requests.get(url, headers=headers, params=params)
#                 else:
#                     response = requests.get(url, headers=headers)
#             elif method.lower() == "post":
#                 if data:
#                     response = requests.post(url, headers=headers, files=data)
#                 else:
#                     response = requests.post(url, headers=headers)
#             else:
#                 raise ValueError(f"Unsupported HTTP method: {method}")

#         logger.info(f"Response status code: {response.status_code}")
#         logger.info(f"Response headers: {response.headers}")
#         logger.info(f"Response content: {response.text}")

#         if response.status_code >= 200 and response.status_code < 300:
#             response_data = response.json()
#             logger.info(f"API call successful: {response_data}")
#             metrics.add_metric(
#                 name="SuccessfulApiCalls", unit=MetricUnit.Count, value=1
#             )
#             return {
#                 "statusCode": response.status_code,
#                 "body": json.dumps(response_data),
#             }
#         else:
#             logger.error(f"API call failed with status code: {response.status_code}")
#             logger.error(f"API call failed with reason: {response.text}")
#             metrics.add_metric(name="FailedApiCalls", unit=MetricUnit.Count, value=1)
#             return {
#                 "statusCode": response.status_code,
#                 "body": json.dumps({"error": "API call failed"}),
#             }

#     except requests.RequestException as e:
#         logger.exception(f"Error making API call: {str(e)}")
#         metrics.add_metric(name="ApiCallErrors", unit=MetricUnit.Count, value=1)
#         return {
#             "body": json.dumps({"error": "Internal server error"}),
#         }


# def build_environment_dict(config):
#     """
#     Build the environment dictionary for the Lambda function,
#     only including variables that are defined in the config.
#     """
#     env_vars = {}
#     possible_vars = [
#         "API_SERVICE_NAME",
#         "API_SERVICE_PATH",
#         "API_SERVICE_RESOURCE",
#         "API_SERVICE_METHOD",
#         "API_SERVICE_URL",
#         "API_TEMPLATE_BUCKET",
#         "API_AUTH_TYPE",
#     ]

#     for var in possible_vars:
#         if hasattr(config, var) and getattr(config, var) is not None:
#             env_vars[var] = getattr(config, var)

#     # Default headers
#     default_headers = {
#         "accept": "application/json",
#         "Content-Type": "application/json",
#     }

#     # Include custom headers if provided, otherwise use default headers
#     headers = config.custom_headers if config.custom_headers else default_headers
#     for key, value in headers.items():
#         env_vars[f"HEADER_{key.upper()}"] = value

#     return env_vars


# def retrieve_api_key(api_key_secret_arn: str) -> Dict[str, str]:
#     """Retrieve the API key from AWS Secrets Manager using the provided ARN."""
#     logger.info(f"Retrieving API key for arn: {api_key_secret_arn}")

#     try:
#         get_secret_value_response = secretsmanager_client.get_secret_value(
#             SecretId=api_key_secret_arn  # Use the provided ARN here
#         )

#         secret = get_secret_value_response["SecretString"]
#         return secret
#     except ClientError as e:
#         logger.error(f"Error retrieving secret: {e}")
#         raise


# def load_and_execute_function_from_s3(
#     bucket: str, key: str, function_name: str, event: dict
# ):
#     """
#     Download a Python file from S3, load the specified function, and execute it with the given event.

#     :param bucket: Name of the S3 bucket
#     :param key: Key of the S3 object (file path within the bucket)
#     :param function_name: Name of the function to execute from the downloaded file
#     :param event: Event data to pass to the function
#     :return: Result of the executed function
#     """
#     s3_client = boto3.client("s3")

#     try:
#         # Download the file from S3
#         response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
#         file_content = response["Body"].read().decode("utf-8")

#         # Create a temporary module
#         spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
#         module = importlib.util.module_from_spec(spec)

#         # Execute the downloaded code in the module's context
#         exec(file_content, module.__dict__)

#         # Get the specified function from the module
#         if not hasattr(module, function_name):
#             raise AttributeError(
#                 f"Function '{function_name}' not found in the downloaded file."
#             )

#         dynamic_function = getattr(module, function_name)

#         # Execute the function with the provided event
#         result = dynamic_function(event)

#         return result

#     except ClientError as e:
#         error_code = e.response["Error"]["Code"]
#         if error_code == "NoSuchKey":
#             print(f"The object {key} does not exist in bucket {bucket}.")
#         elif error_code == "NoSuchBucket":
#             print(f"The bucket {bucket} does not exist.")
#         else:
#             print(f"An S3 error occurred: {e}")
#         raise

#     except SyntaxError as e:
#         print(f"Syntax error in the downloaded Python file: {e}")
#         raise

#     except AttributeError as e:
#         print(f"Function not found error: {e}")
#         raise

#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         raise


# def download_s3_object(bucket: str, key: str) -> str:
#     """Download an object from S3 and return its content."""
#     try:

#         response = s3_client.get_object(Bucket=bucket, Key=key)
#         return response["Body"].read().decode("utf-8")
#     except ClientError as e:
#         print(f"Error downloading S3 object: {e}")
#         raise


# ##todo
# def create_authentication(api_auth_type: str, api_key_secret_arn: str):
#     if api_auth_type == "api_key":
#         api_key = retrieve_api_key(api_key_secret_arn)
#         return {"x-api-key": api_key}
#     else:
#         return None


# def build_full_url(
#     api_service_url: str,
#     api_service_resource: Optional[str] = None,
#     api_service_path: Optional[str] = None,
# ) -> str:
#     """
#     Construct the full API URL based on the host URL, resource, and path.

#     :param api_service_url: The host URL (e.g., "https://api.example.com")
#     :param api_service_resource: Optional resource to append to the URL
#     :param api_service_path: Optional path to insert between the host and resource
#     :return: The full constructed URL
#     """
#     # Ensure api_service_url ends with a slash
#     base_url = (
#         api_service_url if api_service_url.endswith("/") else api_service_url + "/"
#     )

#     # Construct the path
#     if api_service_path:
#         path = api_service_path.strip("/")
#         if api_service_resource:
#             path += f"/{api_service_resource.strip('/')}"
#     elif api_service_resource:
#         path = api_service_resource.strip("/")
#     else:
#         path = ""

#     # Join the base URL and path
#     return urljoin(base_url, path)


# class CustomJSONEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if hasattr(obj, "__dict__"):
#             return obj.__dict__
#         return str(obj)


# def build_s3_templates_path(
#     api_service_name: str,
#     api_service_path: str,
#     api_service_method: str,
#     templates_path: str,  # remains for backward compatibility if needed
#     api_service_resource: Optional[str] = None,
# ) -> dict:
#     """
#     Builds S3 object paths for templates using the API service resource as the base.
#     It creates keys such as:
#       /embed/tasks/tasks_post_request.jinja

#     :param api_service_method: The HTTP method (e.g., "post")
#     :param templates_path: Unused in this modified version (kept for signature consistency)
#     :param api_service_resource: The API service resource (e.g., "/embed/tasks")
#     :return: A dictionary containing keys for the request template, mapping file, etc.
#     """
#     if not api_service_resource:
#         raise ValueError("API service resource must be provided.")

#     # Preserve the leading slash and remove any trailing slashes
#     base_path = api_service_resource.rstrip("/")

#     if api_service_path and api_service_name:
#         full_path = f"{api_service_name}/{api_service_path}{base_path}".translate(str.maketrans('', '', '{}'))

#     # Use the last segment of the resource for the file prefix
#     resource_name = base_path.split("/")[-1]
#     file_prefix = f"{resource_name}_{api_service_method.lower()}".translate(str.maketrans('', '', '{}'))


#     request_template = f"{full_path}/{file_prefix}_request.jinja"
#     mapping_file = f"{full_path}/{file_prefix}_request_mapping.py"
#     url_template = f"{full_path}/{file_prefix}_url.jinja"
#     url_mapping_file = f"{full_path}/{file_prefix}_url_mapping.py"
#     response_template = f"{full_path}/{file_prefix}_response.jinja"
#     response_mapping_file = f"{full_path}/{file_prefix}_response_mapping.py"
#     custom_code_file = f"{full_path}/{file_prefix}_custom_code.py"

#     return {
#         "request_template": request_template,
#         "mapping_file": mapping_file,
#         "url_template": url_template,
#         "url_mapping_file": url_mapping_file,
#         "response_template": response_template,
#         "response_mapping_file": response_mapping_file,
#         "custom_code_file": custom_code_file,
#     }


# def request_header_creation():
#     headers = json.loads(os.environ.get("CUSTOM_HEADERS", "{}"))
#     return headers


# def create_request_body(s3_templates, api_template_bucket, event):
#     logger.info("Building a request body")
#     function_name = "translate_event_to_request"
#     request_template_path = f"api_templates/{s3_templates['request_template']}"
#     mapping_path = s3_templates["mapping_file"]
#     print(api_template_bucket,request_template_path)
#     request_template = download_s3_object(api_template_bucket, request_template_path)
#     mapping = load_and_execute_function_from_s3(
#         api_template_bucket, mapping_path, function_name, event
#     )

#     env = Environment(loader=FileSystemLoader("/tmp/"))
#     env.filters["jsonify"] = json.dumps
#     query_template = env.from_string(request_template)
#     request_body = query_template.render(variables=mapping)
#     request_body = ast.literal_eval(request_body)
#     return request_body


# def create_custom_url(s3_templates, api_template_bucket, event):
#     print("Building a custom URL ")
#     function_name = "translate_event_to_request"
#     url_template_path = f"api_templates/{s3_templates["url_template"]}"
#     url_mapping_path = s3_templates["url_mapping_file"]

#     request_template = download_s3_object(api_template_bucket, url_template_path)
#     mapping = load_and_execute_function_from_s3(
#         api_template_bucket, url_mapping_path, function_name, event
#     )
#     print(f"Mapping is: {mapping}")
#     print(f"Event is: {event}")
#     env = Environment(loader=FileSystemLoader("/tmp/"))
#     env.filters["jsonify"] = json.dumps
#     query_template = env.from_string(request_template)
#     custom_url = query_template.render(variables=mapping)
#     print(f"custom url is {custom_url}")
#     return custom_url


# def create_response_output(s3_templates, api_template_bucket, response_body):
#     function_name = "translate_event_to_request"
#     response_template_path = f"api_templates/{s3_templates["response_template"]}"

#     response_mapping_path = s3_templates["response_mapping_file"]

#     response_template = download_s3_object(api_template_bucket, response_template_path)
#     response_mapping = load_and_execute_function_from_s3(
#         api_template_bucket, response_mapping_path, function_name, response_body
#     )
#     print(f"Mapping is: {response_mapping}")
#     print(f"Event is: {response_body}")
#     env = Environment(loader=FileSystemLoader("/tmp/"))
#     env.filters["jsonify"] = json.dumps
#     query_template = env.from_string(response_template)
#     response_output = query_template.render(variables=response_mapping)
#     dict_output = json.loads(response_output)
#     return dict_output


# def load_and_execute_custom_code(
#     api_template_bucket: str, s3templates: str, api_response: dict, event: dict
# ):
#     """
#     Download a Python file from S3, load the 'process_api_response' function, and execute it with the given API response and event.

#     :param bucket: Name of the S3 bucket
#     :param key: Key of the S3 object (file path within the bucket)
#     :param api_response: The API response to process
#     :param event: The original event data
#     :return: Result of the executed function
#     """
#     try:
#         # Download the file from S3
#         response = s3_client.get_object(
#             Bucket=api_template_bucket, Key=s3templates["custom_code_file"]
#         )
#         file_content = response["Body"].read().decode("utf-8")

#         # Create a temporary module
#         spec = importlib.util.spec_from_loader("custom_module", loader=None)
#         module = importlib.util.module_from_spec(spec)

#         # Execute the downloaded code in the module's context
#         exec(file_content, module.__dict__)

#         # Get the specified function from the module
#         if not hasattr(module, "process_api_response"):
#             raise AttributeError(
#                 "Function 'process_api_response' not found in the custom code file."
#             )

#         custom_function = getattr(module, "process_api_response")

#         # Execute the function with the provided API response and event
#         result = custom_function(api_response, event)

#         return result

#     except Exception as e:
#         logger.error(f"Error in custom code execution: {str(e)}")
#         raise


# @tracer.capture_lambda_handler
# def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
#     """Main Lambda handler function."""
#     start_time = time.time()

#     workflow_step_name = os.environ.get("WORKFLOW_STEP_NAME")
#     api_service_url = os.environ.get("API_SERVICE_URL")
#     api_key_secret_arn = os.environ.get("API_KEY_SECRET_ARN")
#     request_templates_path = os.environ.get("REQUEST_TEMPLATES_PATH")
#     response_templates_path = os.environ.get("RESPONSE_TEMPLATES_PATH")
#     api_service_resource = os.environ.get("API_SERVICE_RESOURCE")
#     api_service_path = os.environ.get("API_SERVICE_PATH")
#     api_service_method = os.environ.get("API_SERVICE_METHOD")
#     api_auth_type = os.environ.get("API_AUTH_TYPE")
#     api_service_name = os.environ.get("API_SERVICE_NAME")
#     api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET")
#     api_custom_url = os.environ.get("API_CUSTOM_URL", "false").lower() == "true"
#     api_custom_code = os.environ.get("API_CUSTOM_CODE", "false").lower() == "true"
#     is_last_step = os.environ.get("IS_LAST_STEP", "false").lower() == "true"

#     # Extract metadata from the event
#     metadata = event.get("metadata", {})

#     # build s3 object keys and paths for templates
#     try:
#         s3_templates = build_s3_templates_path(
#             api_service_name=api_service_name,
#             api_service_path=api_service_path,
#             api_service_resource=api_service_resource,
#             templates_path=request_templates_path,
#             api_service_method=api_service_method,
#         )
#     except ValueError as e:
#         return {
#             "statusCode": 500,
#             "body": f"Error building S3 template paths: {str(e)}",
#         }

#     # Get API header
#     request_headers = request_header_creation()
#     logger.info(f"Request headers are: {request_headers}")
#     # Build auth
#     auth_credentials = create_authentication(api_auth_type, api_key_secret_arn)

#     if api_auth_type == "api_key":
#         request_headers.update(auth_credentials)

#     # Create request body
#     if api_service_method.upper() != "GET":
#         request_body = create_request_body(s3_templates, api_template_bucket, event)

#     # Build the full URL used in the API call
#     try:
#         import re
#         # Look for any pattern like {id} (or any word within {})
#         pattern = re.compile(r'{\w+}')
#         if api_service_resource and pattern.search(api_service_resource):
#             # Resource contains a placeholder variable, so create a custom URL
#             api_full_url = create_custom_url(s3_templates, api_template_bucket, event)
#         else:
#             # Otherwise, build the URL normally
#             api_full_url = build_full_url(
#                 api_service_url=api_service_url,
#                 api_service_resource=api_service_resource,
#                 api_service_path=api_service_path,
#             )
#     except ValueError as e:
#         return {"statusCode": 500, "body": f"Error building URL: {str(e)}"}

#     # Make API call
#     try:
#         api_response = make_api_call(
#             url=api_full_url,
#             method=api_service_method,
#             headers=request_headers,
#             data=request_body if api_service_method.lower() != "get" else None,
#             api_auth_type=api_auth_type,
#         )

#         response_body = json.loads(api_response["body"])

#         # print(f"right before response output{response_body}")

#         ##
#         if api_custom_code:
#             # Execute custom code from S3
#             try:
#                 response_output = load_and_execute_custom_code(
#                     api_template_bucket, s3_templates, response_body, event
#                 )
#                 print(f"API Custome code response output is {response_output}")
#             except Exception as e:
#                 return {
#                     "statusCode": 500,
#                     "body": f"Error executing custom code: {str(e)}",
#                 }
#         else:
#             # Use the default response processing
#             print(json.dumps(response_body))
#             response_output = create_response_output(
#                 s3_templates, api_template_bucket, response_body
#             )

#         print(f"Response output is {response_output}")
#         # Update metadata
#         metadata.update(
#             {
#                 "service": api_service_name,
#                 "stepName": workflow_step_name,
#                 "stepStatus": "Completed",
#                 "stepId": metadata.get("stepId", ""),  # Preserve existing stepId
#                 "workflowName": metadata.get(
#                     "workflowName", ""
#                 ),  # Preserve existing workflowName
#                 "workflowStatus": "completed" if is_last_step else "inProgress",
#                 "workflowId": metadata.get(
#                     "workflowId", ""
#                 ),  # Preserve existing workflowId
#                 "workflowExecutionId": metadata.get(
#                     "workflowExecutionId", ""
#                 ),  # Preserve existing workflowExecutionId
#                 "duration": round(time.time() - start_time, 3),  # Duration in seconds
#             }
#         )

#         # Add metadata to response_output
#         # response_output["metadata"] = metadata

#         # Get the payload from the event
#         payload = event.get("payload", {})

#         # Merge the payload with response_output, prioritizing response_output data
#         merged_output = payload.copy()  # Start with a copy of payload

#         merged_output.update(response_output["payload"])  # Update with response_output

#         # Create the final output structure
#         final_output = {
#             "metadata": metadata,
#             "payload": merged_output,  # Place the merged output in "payload"
#             # Keep metadata at the top level
#         }

#         output_size = len(json.dumps(final_output).encode("utf-8"))

#         if output_size > 240 * 1024:  # 240KB in bytes
#             # Get the S3 bucket name from environment variable
#             external_payload_s3_bucket = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")

#             # Generate a unique key for the S3 object
#             workflow_id = event["metadata"].get("workflowId", "unknown")
#             execution_id = event["metadata"].get("executionId", "unknown")
#             step_id = event["metadata"].get("stepId", "unknown")
#             s3_key = f"{workflow_id}/{execution_id}/{step_id}-payload.json"

#             if not external_payload_s3_bucket:
#                 logger.error(
#                     "external_payload_s3_bucket environment variable is not set"
#                 )
#                 return {
#                     "statusCode": 500,
#                     "body": json.dumps(
#                         {"error": "External payload S3 bucket not configured"}
#                     ),
#                 }
#             try:
#                 logger.info(external_payload_s3_bucket)
#                 logger.info(json.dumps(final_output["payload"]))
#                 s3_client.put_object(
#                     Bucket=external_payload_s3_bucket,
#                     Key=s3_key,
#                     Body=json.dumps(final_output["payload"]),
#                 )

#                 # Update the final_output
#                 final_output["metadata"]["externalPayload"] = True
#                 final_output["payload"] = {}
#                 final_output["payload"]["externalPayloadLocation"] = {
#                     "bucket": external_payload_s3_bucket,
#                     "key": s3_key,
#                 }
#                 # logger.info(f"Large payload written to S3: {s3_key}")
#             except Exception as e:
#                 logger.error(f"Failed to write payload to S3: {str(e)}")
#                 return {
#                     "statusCode": 500,
#                     "body": json.dumps(
#                         {"error": "Failed to write large payload to S3"}
#                     ),
#                 }

#         print("Final output:", json.dumps(final_output, cls=CustomJSONEncoder))
#         return final_output

#     except Exception as e:
#         # Handle any exceptions that occur during the API call or processing
#         error_message = f"Error in lambda_handler: {str(e)}"
#         logger.error(error_message)
#         return {
#             "statusCode": 500,
#             "body": json.dumps({"error": error_message}),
#         }


import os
import json
import time
import uuid
import ast
import boto3
import importlib.util
import requests
import re
from urllib.parse import urljoin
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from requests_aws4auth import AWS4Auth

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator

# Initialize clients and Powertools utilities
s3_client = boto3.client("s3")
secretsmanager_client = boto3.client("secretsmanager")
logger = Logger()
tracer = Tracer(disabled=True)
metrics = Metrics(namespace="ApiStandardLambda")

################################################################################
# CUSTOM MIDDLEWARE
################################################################################

class LambdaMiddleware:
    """
    Middleware for AWS Lambda functions that provides:
      - EventBridge integration for progress/status updates
      - CloudWatch metrics for monitoring
      - Payload size management with S3 fallback
      - Standardized error handling
      - Input/output payload standardization

    The standardized output format is:

    {
      "metadata": {
          "service": "S3EventIngest",       # Mandatory
          "stepName": "assetRegistration",  # Mandatory
          "stepStatus": "Completed",        # Mandatory: ENUM (Started, InProgress, Completed)
          "stepId": "",                     # Mandatory - UID generated
          "externalTaskId": "",             # Optional
          "externalTaskStatus": "",         # Optional enum (completed, inProgress, Started)
          "externalPayload": "",            # Mandatory ("True" or "False")
          "externalPayloadLocation": {      # Optional, required if externalPayload is "True"
              "bucket": "bucket-name",
              "key": "object-key"
          },
          "stepCost": "",                   # Optional
          "stepResult": "",                 # Optional
          "stepDuration": ""                # Optional
      },
      "payload": {                        # Mandatory
          "assets": [],
          "rights": [],
          "titles": [],
          "tasks": []
      }
    }
    """

    def __init__(
        self,
        event_bus_name: str,
        metrics_namespace: str = "MediaLake",
        max_event_size: int = 256000,  # EventBridge max size is 256KB
        cleanup_s3: bool = True,
        large_payload_bucket: Optional[str] = None,
        max_retries: int = 3,
        standardize_payloads: bool = True,
    ):
        self.event_bus = boto3.client("events")
        self.event_bus_name = event_bus_name
        self.max_event_size = max_event_size
        self.cleanup_s3 = cleanup_s3
        self.max_retries = max_retries
        self.s3 = boto3.client("s3")

        self.large_payload_bucket = large_payload_bucket or os.environ.get("LARGE_PAYLOAD_BUCKET")
        if not self.large_payload_bucket:
            raise ValueError("large_payload_bucket must be provided or LARGE_PAYLOAD_BUCKET env variable must be set")

        self.service_name = os.getenv("SERVICE_NAME", "undefined_service")
        self.logger = Logger(service=self.service_name)
        self.metrics = Metrics(namespace=metrics_namespace, service=self.service_name)
        self.tracer = Tracer(service=self.service_name)

        self.temp_s3_objects = []
        self.standardize_payloads = standardize_payloads

        self.retry_count = 0
        self.retry_errors = set()

    def should_retry(self, error: Exception) -> bool:
        RETRYABLE_ERRORS = (
            "RequestTimeout",
            "InternalServerError",
            "ServiceUnavailable",
            "ConnectionError",
            "ThrottlingException",
            "TooManyRequestsException",
            "ProvisionedThroughputExceededException",
        )
        error_type = error.__class__.__name__
        self.retry_errors.add(error_type)
        return self.retry_count < self.max_retries and any(err in error_type for err in RETRYABLE_ERRORS)

    def emit_progress(self, context: LambdaContext, progress: float, status: str, detail: Optional[Dict[str, Any]] = None) -> None:
        progress_details = {
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "progress": progress,
            "status": status,
            "timestamp": int(time.time()),
        }
        if detail:
            progress_details.update(detail)
        self.emit_event(
            detail_type="FunctionExecutionProgress",
            detail=progress_details,
            resources=[context.invoked_function_arn],
        )

    def standardize_input(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not self.standardize_payloads:
            return event
        if "s3_bucket" in event and "s3_key" in event:
            try:
                response = self.s3.get_object(Bucket=event["s3_bucket"], Key=event["s3_key"])
                event = json.loads(response["Body"].read().decode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to fetch payload from S3: {str(e)}")
                raise
        if "metadata" not in event:
            event["metadata"] = {}
        event["metadata"].update({"timestamp": int(time.time()), "service": self.service_name})
        return event

    def standardize_output(self, result: Any) -> Dict[str, Any]:
        if not self.standardize_payloads:
            return result

        # If result already appears standardized, return as-is.
        if isinstance(result, dict) and "metadata" in result and "payload" in result:
            return result

        # Otherwise, wrap the result
        payload_content = result if isinstance(result, dict) else {"data": result}
        metadata = {
            "service": self.service_name,
            "stepName": "assetRegistration",
            "stepStatus": "Completed",
            "stepId": str(uuid.uuid4()),
            "externalTaskId": "",
            "externalTaskStatus": "",
            "externalPayload": "False",
            "externalPayloadLocation": None,
            "stepCost": "",
            "stepResult": "",
            "stepDuration": ""
        }
        return {"metadata": metadata, "payload": payload_content}

    def emit_event(self, detail_type: str, detail: Dict[str, Any], resources: Optional[list] = None) -> None:
        try:
            event = {
                "Source": self.service_name,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": self.event_bus_name,
                "Resources": resources or [],
            }
            event_size = len(json.dumps(event).encode("utf-8"))
            if event_size > self.max_event_size:
                self.logger.info(f"Event size {event_size} exceeds limit {self.max_event_size}, using S3")
                key = f"events/{int(time.time())}-{detail_type}.json"
                self.s3.put_object(Bucket=self.large_payload_bucket, Key=key, Body=json.dumps(detail))
                self.temp_s3_objects.append(key)
                event["Detail"] = json.dumps({"s3_bucket": self.large_payload_bucket, "s3_key": key, "original_size": event_size})
            self.event_bus.put_events(Entries=[event])
        except Exception as e:
            self.logger.error(f"Failed to emit event: {str(e)}")
            self.metrics.add_metric(name="FailedEvents", unit=MetricUnit.Count, value=1)

    def cleanup_temp_s3_objects(self) -> None:
        if not self.cleanup_s3 or not self.temp_s3_objects:
            return
        try:
            self.s3.delete_objects(
                Bucket=self.large_payload_bucket,
                Delete={"Objects": [{"Key": key} for key in self.temp_s3_objects]},
            )
            self.temp_s3_objects = []
        except Exception as e:
            self.logger.error(f"Failed to cleanup S3 objects: {str(e)}")

    def handle_failure(self, error: Exception, context: LambdaContext) -> None:
        error_type = error.__class__.__name__
        error_details = {
            "error_type": error_type,
            "error_message": str(error),
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "function_version": context.function_version,
        }
        self.logger.exception("Function execution failed")
        self.emit_event(
            detail_type="FunctionExecutionFailure",
            detail=error_details,
            resources=[context.invoked_function_arn],
        )
        self.metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
        self.metrics.add_metric(name=f"Errors_{error_type}", unit=MetricUnit.Count, value=1)

    def __call__(self, handler):
        @lambda_handler_decorator
        def wrapper(inner_handler, event, context):
            start_time = time.time()
            try:
                self.emit_event(
                    detail_type="FunctionExecutionStart",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "remaining_time": context.get_remaining_time_in_millis(),
                    },
                    resources=[context.invoked_function_arn],
                )

                self.metrics.add_dimension(name="FunctionName", value=context.function_name)
                self.metrics.add_dimension(name="Environment", value=os.getenv("ENVIRONMENT", "undefined"))

                processed_event = self.standardize_input(event)
                context.emit_progress = lambda progress, status, detail=None: self.emit_progress(context, progress, status, detail)

                self.retry_count = 0
                self.retry_errors.clear()

                while True:
                    try:
                        result = inner_handler(processed_event, context)
                        break
                    except Exception as e:
                        if self.should_retry(e):
                            self.retry_count += 1
                            retry_delay = min(2 ** self.retry_count, 30)
                            self.logger.warning(
                                f"Retrying after error (attempt {self.retry_count}/{self.max_retries})",
                                extra={"error": str(e), "error_type": e.__class__.__name__, "retry_delay": retry_delay},
                            )
                            self.emit_event(
                                detail_type="FunctionExecutionRetry",
                                detail={
                                    "function_name": context.function_name,
                                    "request_id": context.aws_request_id,
                                    "error": str(e),
                                    "error_type": e.__class__.__name__,
                                    "retry_count": self.retry_count,
                                    "retry_delay": retry_delay,
                                },
                                resources=[context.invoked_function_arn],
                            )
                            time.sleep(retry_delay)
                            continue
                        raise

                if self.retry_count > 0:
                    self.metrics.add_metric(name="RetryAttempts", unit=MetricUnit.Count, value=self.retry_count)
                    for error_type in self.retry_errors:
                        self.metrics.add_metric(name=f"RetryErrors_{error_type}", unit=MetricUnit.Count, value=1)

                processed_result = self.standardize_output(result)
                execution_time = (time.time() - start_time) * 1000

                self.metrics.add_metric(name="Invocations", unit=MetricUnit.Count, value=1)
                self.metrics.add_metric(name="ExecutionTime", unit=MetricUnit.Milliseconds, value=execution_time)
                self.metrics.add_metric(name="MemoryUsed", unit=MetricUnit.Megabytes, value=float(context.memory_limit_in_mb))

                if not hasattr(LambdaMiddleware, "_cold_start_recorded"):
                    self.metrics.add_metric(name="ColdStart", unit=MetricUnit.Count, value=1)
                    LambdaMiddleware._cold_start_recorded = True

                self.emit_event(
                    detail_type="FunctionExecutionComplete",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "execution_time_ms": execution_time,
                        "memory_used": context.memory_limit_in_mb,
                    },
                    resources=[context.invoked_function_arn],
                )
                return processed_result

            except Exception as e:
                self.handle_failure(e, context)
                raise

            finally:
                self.cleanup_temp_s3_objects()

        return wrapper(handler)

def lambda_middleware(
    event_bus_name: str,
    metrics_namespace: str = "MediaLake",
    max_event_size: int = 256000,
    cleanup_s3: bool = True,
    large_payload_bucket: Optional[str] = None,
    max_retries: int = 3,
    standardize_payloads: bool = True,
):
    middleware = LambdaMiddleware(
        event_bus_name=event_bus_name,
        metrics_namespace=metrics_namespace,
        max_event_size=max_event_size,
        cleanup_s3=cleanup_s3,
        large_payload_bucket=large_payload_bucket,
        max_retries=max_retries,
        standardize_payloads=standardize_payloads,
    )
    return middleware

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
            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=params) if params else requests.get(url, headers=headers)
            elif method.lower() == "post":
                response = requests.post(url, headers=headers, files=data) if data else requests.post(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response content: {response.text}")

        if 200 <= response.status_code < 300:
            response_data = response.json()
            logger.info(f"API call successful: {response_data}")
            return {"statusCode": response.status_code, "body": json.dumps(response_data)}
        else:
            logger.error(f"API call failed with status code: {response.status_code}")
            logger.error(f"API call failed with reason: {response.text}")
            return {"statusCode": response.status_code, "body": json.dumps({"error": "API call failed"})}

    except requests.RequestException as e:
        logger.exception(f"Error making API call: {str(e)}")
        return {"body": json.dumps({"error": "Internal server error"})}

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
        get_secret_value_response = secretsmanager_client.get_secret_value(SecretId=api_key_secret_arn)
        secret = get_secret_value_response["SecretString"]
        return secret
    except ClientError as e:
        logger.error(f"Error retrieving secret: {e}")
        raise

def load_and_execute_function_from_s3(bucket: str, key: str, function_name: str, event: dict):
    s3_client = boto3.client("s3")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=f"api_templates/{key}")
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("dynamic_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in the downloaded file.")
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

def build_full_url(api_service_url: str, api_service_resource: Optional[str] = None, api_service_path: Optional[str] = None) -> str:
    base_url = api_service_url if api_service_url.endswith("/") else api_service_url + "/"
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

def build_s3_templates_path(api_service_name: str, api_service_path: str, api_service_method: str, templates_path: str, api_service_resource: Optional[str] = None) -> dict:
    if not api_service_resource:
        raise ValueError("API service resource must be provided.")
    base_path = api_service_resource.rstrip("/")
    if api_service_path and api_service_name:
        full_path = f"{api_service_name}/{api_service_path}{base_path}".translate(str.maketrans('', '', '{}'))
    resource_name = base_path.split("/")[-1]
    file_prefix = f"{resource_name}_{api_service_method.lower()}".translate(str.maketrans('', '', '{}'))
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
    mapping = load_and_execute_function_from_s3(api_template_bucket, mapping_path, function_name, event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
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
    mapping = load_and_execute_function_from_s3(api_template_bucket, url_mapping_path, function_name, event)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(request_template)
    custom_url = query_template.render(variables=mapping)
    return custom_url

def create_response_output(s3_templates, api_template_bucket, response_body):
    function_name = "translate_event_to_request"
    response_template_path = f"api_templates/{s3_templates['response_template']}"
    response_mapping_path = s3_templates["response_mapping_file"]
    response_template = download_s3_object(api_template_bucket, response_template_path)
    response_mapping = load_and_execute_function_from_s3(api_template_bucket, response_mapping_path, function_name, response_body)
    env = Environment(loader=FileSystemLoader("/tmp/"))
    env.filters["jsonify"] = json.dumps
    query_template = env.from_string(response_template)
    response_output = query_template.render(variables=response_mapping)
    dict_output = json.loads(response_output)
    return dict_output

def load_and_execute_custom_code(api_template_bucket: str, s3templates: dict, api_response: dict, event: dict):
    try:
        response = s3_client.get_object(Bucket=api_template_bucket, Key=s3templates["custom_code_file"])
        file_content = response["Body"].read().decode("utf-8")
        spec = importlib.util.spec_from_loader("custom_module", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(file_content, module.__dict__)
        if not hasattr(module, "process_api_response"):
            raise AttributeError("Function 'process_api_response' not found in the custom code file.")
        custom_function = getattr(module, "process_api_response")
        result = custom_function(api_response, event)
        return result
    except Exception as e:
        logger.error(f"Error in custom code execution: {str(e)}")
        raise

################################################################################
# LAMBDA HANDLER (DECORATED WITH CUSTOM MIDDLEWARE)
################################################################################

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
    large_payload_bucket=os.environ.get("LARGE_PAYLOAD_BUCKET")
)
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    start_time = time.time()

    workflow_step_name = os.environ.get("WORKFLOW_STEP_NAME")
    api_service_url = os.environ.get("API_SERVICE_URL")
    api_key_secret_arn = os.environ.get("API_KEY_SECRET_ARN")
    request_templates_path = os.environ.get("REQUEST_TEMPLATES_PATH")
    response_templates_path = os.environ.get("RESPONSE_TEMPLATES_PATH")
    api_service_resource = os.environ.get("API_SERVICE_RESOURCE")
    api_service_path = os.environ.get("API_SERVICE_PATH")
    api_service_method = os.environ.get("API_SERVICE_METHOD")
    api_auth_type = os.environ.get("API_AUTH_TYPE")
    api_service_name = os.environ.get("API_SERVICE_NAME")
    api_template_bucket = os.environ.get("API_TEMPLATE_BUCKET")
    api_custom_url = os.environ.get("API_CUSTOM_URL", "false").lower() == "true"
    api_custom_code = os.environ.get("API_CUSTOM_CODE", "false").lower() == "true"
    is_last_step = os.environ.get("IS_LAST_STEP", "false").lower() == "true"

    metadata = event.get("metadata", {})

    try:
        s3_templates = build_s3_templates_path(
            api_service_name=api_service_name,
            api_service_path=api_service_path,
            api_service_resource=api_service_resource,
            templates_path=request_templates_path,
            api_service_method=api_service_method,
        )
    except ValueError as e:
        return {"statusCode": 500, "body": f"Error building S3 template paths: {str(e)}"}

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
        if api_service_resource and re.search(r'{\w+}', api_service_resource):
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
                response_output = load_and_execute_custom_code(api_template_bucket, s3_templates, response_body, event)
            except Exception as e:
                return {"statusCode": 500, "body": f"Error executing custom code: {str(e)}"}
        else:
            response_output = create_response_output(s3_templates, api_template_bucket, response_body)

        logger.info(f"Response output is {response_output}")

        metadata.update({
            "service": api_service_name,
            "stepName": workflow_step_name,
            "stepStatus": "Completed",
            "stepId": metadata.get("stepId", ""),
            "workflowName": metadata.get("workflowName", ""),
            "workflowStatus": "completed" if is_last_step else "inProgress",
            "workflowId": metadata.get("workflowId", ""),
            "workflowExecutionId": metadata.get("workflowExecutionId", ""),
            "duration": round(time.time() - start_time, 3)
        })

        payload = event.get("payload", {})
        merged_output = payload.copy()
        merged_output.update(response_output.get("payload", {}))

        final_output = {"metadata": metadata, "payload": merged_output}

        output_size = len(json.dumps(final_output).encode("utf-8"))
        if output_size > 240 * 1024:
            external_payload_s3_bucket = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
            workflow_id = metadata.get("workflowId", "unknown")
            execution_id = metadata.get("executionId", "unknown")
            step_id = metadata.get("stepId", "unknown")
            s3_key = f"{workflow_id}/{execution_id}/{step_id}-payload.json"
            if not external_payload_s3_bucket:
                logger.error("External payload S3 bucket not configured")
                return {"statusCode": 500, "body": json.dumps({"error": "External payload S3 bucket not configured"})}
            try:
                s3_client.put_object(Bucket=external_payload_s3_bucket, Key=s3_key, Body=json.dumps(final_output["payload"]))
                final_output["metadata"]["externalPayload"] = True
                final_output["payload"] = {"externalPayloadLocation": {"bucket": external_payload_s3_bucket, "key": s3_key}}
            except Exception as e:
                logger.error(f"Failed to write payload to S3: {str(e)}")
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to write large payload to S3"})}

        logger.info("Final output: " + json.dumps(final_output, cls=CustomJSONEncoder))
        return final_output

    except Exception as e:
        error_message = f"Error in lambda_handler: {str(e)}"
        logger.error(error_message)
        return {"statusCode": 500, "body": json.dumps({"error": error_message})}
