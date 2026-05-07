import json
import os
import time

import boto3
from botocore.exceptions import ClientError


def generate_body_config():
    table_arn = os.environ["TABLE_ARN"]
    bucket_name = os.environ["BUCKET_NAME"]
    index_name = os.environ["INDEX_NAME"]
    collection_endpoint = os.environ["COLLECTION_ENDPOINT"]
    pipeline_role_arn = os.environ["PIPELINE_ROLE_ARN"]
    region = os.environ["REGION"]

    return f"""
    version: "2"
    dynamodb-pipeline:
      source:
        dynamodb:
          acknowledgments: true
          tables:
          - table_arn: "{table_arn}"
            stream:
              start_position: "LATEST"
            export:
              s3_bucket: "{bucket_name}"
              s3_region: "{region}"
              s3_prefix: "export/"
          aws:
            sts_role_arn: "{pipeline_role_arn}"
            region: "{region}"
      routes:
        - {index_name}_route: '1 == 1'

      sink:
        - opensearch:
            hosts: ["{collection_endpoint}"]
            index: "{index_name}"
            index_type: custom
            routes: ["{index_name}_route"]
            document_id: "${{getMetadata(\\"primary_key\\")}}"
            action: "${{getMetadata(\\"opensearch_action\\")}}"
            document_version: "${{getMetadata(\\"document_version\\")}}"
            document_version_type: "external"
            aws:
              sts_role_arn: "{pipeline_role_arn}"
              region: "{region}"
              serverless: false
            dlq:
              s3:
                bucket: "{bucket_name}"
                key_path_prefix: "dlq/{index_name}"
                region: "{region}"
                sts_role_arn: "{pipeline_role_arn}"
    """


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    if "IsComplete" in event:
        return is_complete(event, context)

    request_type = event["RequestType"]

    if request_type == "Create":
        return on_create(event, context)
    elif request_type == "Update":
        return on_update(event, context)
    elif request_type == "Delete":
        return on_delete(event, context)
    else:
        raise Exception(f"Invalid request type: {request_type}")


def on_create(event, context):
    osis_client = boto3.client("osis")
    pipeline_name = os.environ["PIPELINE_NAME"]
    log_group_name = os.environ["LOG_GROUP_NAME"]

    try:
        osis_client.get_pipeline(PipelineName=pipeline_name)
        print(f"Pipeline {pipeline_name} already exists. ")
        return {
            "PhysicalResourceId": pipeline_name,
            "Status": "SUCCESS",
            "Reason": "Ingestion pipeline already exists. No action taken.",
        }
    except osis_client.exceptions.ResourceNotFoundException:
        print(f"Pipeline {pipeline_name} does not exist. Proceeding with creation.")
    except ClientError as e:
        print(f"An error occurred: {e}")
        return {"Status": "FAILED", "Reason": f"Error occurred: {str(e)}"}

    body_config = generate_body_config()

    try:
        response = osis_client.create_pipeline(
            PipelineName=pipeline_name,
            MinUnits=2,
            MaxUnits=4,
            LogPublishingOptions={
                "IsLoggingEnabled": True,
                "CloudWatchLogDestination": {
                    "LogGroup": log_group_name,
                },
            },
            VpcOptions={
                "SubnetIds": json.loads(os.environ["SUBNET_IDS_PIPELINE"]),
                "SecurityGroupIds": json.loads(os.environ["SECURITY_GROUP_IDS"]),
            },
            PipelineConfigurationBody=body_config,
        )
        print(f"Pipeline {pipeline_name} created successfully.")
        return {
            "PhysicalResourceId": pipeline_name,
            "Status": "SUCCESS",
            "Reason": "Ingestion pipeline created successfully!",
        }
    except ClientError as e:
        print(f"An error occurred while creating the pipeline: {e}")
        return {
            "Status": "FAILED",
            "Reason": f"Error occurred while creating pipeline: {str(e)}",
        }


def on_update(event, context):
    osis_client = boto3.client("osis")
    pipeline_name = os.environ["PIPELINE_NAME"]

    # Generate the current body_config
    current_body_config = generate_body_config()

    try:
        # Get the existing pipeline configuration
        existing_pipeline = osis_client.get_pipeline(PipelineName=pipeline_name)

        existing_body_config = existing_pipeline["Pipeline"][
            "PipelineConfigurationBody"
        ]

        # Compare configurations
        if current_body_config.strip() == existing_body_config.strip():
            print(
                f"Pipeline {pipeline_name} configuration unchanged. No action needed."
            )
            return {
                "PhysicalResourceId": pipeline_name,
                "Status": "SUCCESS",
                "Reason": "Pipeline configuration unchanged. No action taken.",
            }
        else:
            print(
                f"Pipeline {pipeline_name} configuration changed. Recreating pipeline."
            )
            # Delete the existing pipeline
            delete_result = on_delete(event, context)
            if delete_result["Status"] == "FAILED":
                return delete_result

            # Create the pipeline with the new configuration
            return on_create(event, context)

    except osis_client.exceptions.ResourceNotFoundException:
        print(f"Pipeline {pipeline_name} not found. Creating new pipeline.")
        return on_create(event, context)
    except ClientError as e:
        print(f"An error occurred: {e}")
        return {"Status": "FAILED", "Reason": f"Error occurred: {str(e)}"}


def on_delete(event, context):
    osis_client = boto3.client("osis")
    pipeline_name = os.environ["PIPELINE_NAME"]

    try:
        # Delete the pipeline
        osis_client.delete_pipeline(PipelineName=pipeline_name)
        print(f"Pipeline {pipeline_name} deletion initiated.")

        # Wait for the pipeline to be deleted
        wait_for_pipeline_deletion(osis_client, pipeline_name)

        return {
            "PhysicalResourceId": event["PhysicalResourceId"],
            "Status": "SUCCESS",
            "Reason": f"Pipeline {pipeline_name} deleted successfully",
        }
    except Exception as e:
        print(f"Error deleting pipeline: {str(e)}")
        return {
            "PhysicalResourceId": event["PhysicalResourceId"],
            "Status": "FAILED",
            "Reason": f"Failed to delete pipeline: {str(e)}",
        }


def is_complete(event, context):
    request_type = event["RequestType"]
    pipeline_name = os.environ["PIPELINE_NAME"]
    osis_client = boto3.client("osis")

    if request_type == "Delete":
        try:
            osis_client.get_pipeline(PipelineName=pipeline_name)
            return {"IsComplete": False}
        except osis_client.exceptions.ResourceNotFoundException:
            return {"IsComplete": True}
    elif request_type in ["Create", "Update"]:
        try:
            response = osis_client.get_pipeline(PipelineName=pipeline_name)
            status = response["PipelineStatus"]
            return {"IsComplete": status == "ACTIVE"}
        except Exception as e:
            print(f"Error checking pipeline status: {str(e)}")
            return {"IsComplete": False}


def wait_for_pipeline_deletion(osis_client, pipeline_name, max_attempts=30, delay=10):
    for attempt in range(max_attempts):
        try:
            osis_client.get_pipeline(PipelineName=pipeline_name)
            print(
                f"Waiting for pipeline {pipeline_name} to be deleted... (Attempt {attempt + 1})"
            )
            time.sleep(delay)
        except osis_client.exceptions.ResourceNotFoundException:
            print(f"Pipeline {pipeline_name} has been deleted.")
            return

    raise TimeoutError(
        f"Pipeline {pipeline_name} deletion timed out after {max_attempts} attempts."
    )
