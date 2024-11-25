# lambda/ingestion_pipeline.py
import json
import boto3
import os

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
    - {index_name}_route: '/DigitalSourceAsset.Type == "Image"'
  
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
    return {
        'statusCode': 200,
        'body': json.dumps('Ingestion pipeline created successfully!')
    }