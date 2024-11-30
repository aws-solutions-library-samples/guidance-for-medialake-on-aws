# lambda/ingestion_pipeline.py
import json
import boto3
import os
import time
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    osis_client = boto3.client('osis')
    pipeline_name = os.environ['PIPELINE_NAME']
    table_arn = os.environ['TABLE_ARN']
    bucket_name = os.environ['BUCKET_NAME']
    index_name = os.environ["INDEX_NAME"]
    collection_endpoint = os.environ['COLLECTION_ENDPOINT']
    # network_policy_name = os.environ['NETWORK_POLICY_NAME']
    pipeline_role_arn = os.environ['PIPELINE_ROLE_ARN']
    region = os.environ['REGION']
    log_group_name = os.environ['LOG_GROUP_NAME']
    
    
    # Check if the pipeline already exists
    try:
      osis_client.get_pipeline(PipelineName=pipeline_name)
      print(f"Pipeline {pipeline_name} already exists. Deleting it...")

      # Delete the existing pipeline
      # osis_client.delete_pipeline(PipelineName=pipeline_name)
      
      # Wait for the pipeline to be deleted
      # wait_for_pipeline_deletion(osis_client, pipeline_name)
      
      # print(f"Pipeline {pipeline_name} has been deleted.")
    except osis_client.exceptions.ResourceNotFoundException:
      print(f"Pipeline {pipeline_name} does not exist. Proceeding with creation.")
    except ClientError as e:
      print(f"An error occurred: {e}")
      return {
          'statusCode': 500,
          'body': json.dumps(f'Error occurred: {str(e)}')
      }
    
    # Define the pipeline configuration
    body_config = f"""
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
     # Create the new pipeline
    try:
      response = osis_client.create_pipeline(
          PipelineName=pipeline_name,
          MinUnits=2,
          MaxUnits=4,
          LogPublishingOptions={
              'IsLoggingEnabled': True,
              'CloudWatchLogDestination': {
                  'LogGroup': log_group_name,
              }
          },
          VpcOptions={
              'SubnetIds': json.loads(os.environ['SUBNET_IDS_PIPELINE']),
              'SecurityGroupIds': json.loads(os.environ['SECURITY_GROUP_IDS']),
          },
          PipelineConfigurationBody=body_config
      )
      print(f"Pipeline {pipeline_name} created successfully.")
      return {
          'statusCode': 200,
          'body': json.dumps('Ingestion pipeline created successfully!')
      }
    except ClientError as e:
      print(f"An error occurred while creating the pipeline: {e}")
      return {
          'statusCode': 500,
          'body': json.dumps(f'Error occurred while creating pipeline: {str(e)}')
      }
      
def wait_for_pipeline_deletion(osis_client, pipeline_name, max_attempts=30, delay=10):
    """
    Wait for the pipeline to be deleted by polling the OSIS service.
    
    :param osis_client: Boto3 OSIS client
    :param pipeline_name: Name of the pipeline to wait for
    :param max_attempts: Maximum number of polling attempts
    :param delay: Delay between polling attempts in seconds
    """
    for attempt in range(max_attempts):
        try:
            osis_client.get_pipeline(PipelineName=pipeline_name)
            print(f"Waiting for pipeline {pipeline_name} to be deleted... (Attempt {attempt + 1})")
            time.sleep(delay)
        except osis_client.exceptions.ResourceNotFoundException:
            print(f"Pipeline {pipeline_name} has been deleted.")
            return
    
    # If we've exhausted all attempts and the pipeline still exists
    raise TimeoutError(f"Pipeline {pipeline_name} deletion timed out after {max_attempts} attempts.")

