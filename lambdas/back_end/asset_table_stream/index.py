import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Initialize AWS clients
opensearch_client = boto3.client('opensearch')
credentials = boto3.Session().get_credentials()
region = 'us-east-1'  # Replace with your region

# OpenSearch Serverless configuration
host = 'your-opensearch-serverless-endpoint.us-east-1.aoss.amazonaws.com'  # Replace with your endpoint
index_name = 'your-index-name'  # Replace with your index name

# Create AWS4Auth instance for OpenSearch Serverless
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, 'aoss',
                   session_token=credentials.token)

# Initialize OpenSearch client
opensearch = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            # Ensure this is a DynamoDB Stream event
            if record['eventSource'] != 'aws:dynamodb':
                continue

            # Get the DynamoDB data
            if 'NewImage' in record['dynamodb']:
                data = record['dynamodb']['NewImage']
                
                # Convert DynamoDB data types to Python types
                processed_data = {k: list(v.values())[0] for k, v in data.items()}
                
                # Generate a document ID (you might want to use a specific field from your data)
                doc_id = record['dynamodb']['Keys']['id']['S']  # Assuming 'id' is your primary key
                
                # Index the document in OpenSearch
                response = opensearch.index(
                    index=index_name,
                    body=processed_data,
                    id=doc_id,
                    refresh=True
                )
                
                print(f"Indexed document {doc_id}: {response}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed DynamoDB Stream event')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing DynamoDB Stream event: {str(e)}')
        }
