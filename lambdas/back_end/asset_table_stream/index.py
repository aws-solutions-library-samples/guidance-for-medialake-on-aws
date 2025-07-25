#Change the DynamoDB Stream Setting to Both (New and Old Image)
#Create the SQS Queue using CDK
#Assign the Lambda to the DynamoDB Stream

# #IAM Permissions - This policy below.
#Include SQS Queue write access to particular queue
#Lambda basic execution role
# {
#     "Version": "2012-10-17",
#     "Statement": [
#         {
#             "Sid": "VisualEditor0",
#             "Effect": "Allow",
#             "Action": [
#                 "ec2:CreateNetworkInterface",
#                 "ec2:DescribeNetworkInterfaces",
#                 "ec2:DeleteNetworkInterface",
#                 "dynamodb:ListStreams"
#             ],
#             "Resource": "*"
#         },
#         {
#             "Sid": "VisualEditor1",
#             "Effect": "Allow",
#             "Action": [
#                 "es:ESHttpHead",
#                 "es:ESHttpPost",
#                 "dynamodb:GetShardIterator",
#                 "es:ESHttpGet",
#                 "dynamodb:DescribeStream",
#                 "logs:CreateLogGroup",
#                 "es:ESHttpPut",
#                 "dynamodb:ListStreams",
#                 "dynamodb:GetRecords"
#             ],
#             "Resource": [
#                 "arn:aws:logs:us-east-2:881490114702:*",
#                 "arn:aws:es:us-east-2:881490114702:domain/mlake-demo-os-us-east-1-dev/*",
#                 "arn:aws:dynamodb:us-east-2:881490114702:table/mlake-demo-asset-table-dev/stream/2025-07-23T12:53:59.485"
#             ]
#         },
#         {
#             "Sid": "VisualEditor2",
#             "Effect": "Allow",
#             "Action": [
#                 "logs:CreateLogStream",
#                 "logs:PutLogEvents"
#             ],
#             "Resource": "arn:aws:logs:us-east-2:881490114702:log-group:/aws/lambda/mlake-dydb-to-os:*"
#         }
#     ]
# }


import json
import boto3
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# OpenSearch configuration
REGION = os.environ["OS_DOMAIN_REGION"]
HOST = os.environ["OPENSEARCH_ENDPOINT"]
INDEX = os.environ["OPENSEARCH_INDEX"]
SQS_URL = os.environ["SQS_URL"]

# Initialize AWS credentials
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    'es',
    session_token=credentials.token
)

# Initialize SQS client
sqs = boto3.client('sqs')

# Initialize OpenSearch client
opensearch_client = OpenSearch(
    hosts=[{'host': HOST, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            # Get the DynamoDB record
            print(record['eventName'])
            if record['eventName'] == 'REMOVE':

                # Handle DELETE operations
                document_id = record['dynamodb']['OldImage']['InventoryID']['S']  # Adjust key name as needed
                print(f" deleting document {document_id}")
                try:
                    opensearch_client.delete(
                        index=INDEX,
                        id=document_id
                    )


                except Exception as e:
                    try:
                        document_id = record['dynamodb']['OldImage']['InventoryID']['S'] 
                        print(f"Error deleting document {document_id}: {str(e)}")
                        # Send message to SQS queue
                        olddocument = deserialize_dynamodb_json(record['dynamodb']['OldImage'])
                        response = sqs.send_message(
                            QueueUrl=SQS_URL,
                            MessageBody=json.dumps(olddocument),
                            # Optional: Add message attributes if needed
                            MessageAttributes={
                            'MessageType': {
                                'DataType': 'String',
                                'StringValue': 'Delete the Index'
                                }
                            }
                        )
                        return {
                            'statusCode': 200,
                              'body': json.dumps({
                            'message': 'Message sent successfully',
                            'messageId': response['MessageId']
                            })
                        }
                    except Exception as e:
                        return {
                            'statusCode': 500,
                            'body': json.dumps({
                            'error': str(e)
                                })
                            }
                    
            else:
                # Handle INSERT and MODIFY operations
                print(record['dynamodb'])
                if 'NewImage' in record['dynamodb']:
                    # Convert DynamoDB JSON to regular JSON
                    document = deserialize_dynamodb_json(record['dynamodb']['NewImage'])
                    document_id = document['InventoryID']  # Adjust key name as needed
                    print(f" inserting document {document_id}")
                    # Index the document in OpenSearch
                    try:
                        opensearch_client.index(
                            index=INDEX,
                            body=document,
                            id=document_id,
                            refresh=True
                        )

                    except Exception as e:
                        try:
                            document_id = record['dynamodb']['NewImage']['InventoryID']['S'] 
                            print(f"Error indexing document {document_id}: {str(e)}")
                            # Send message to SQS queue
                            document = deserialize_dynamodb_json(record['dynamodb']['NewImage'])
                            response = sqs.send_message(
                                QueueUrl=SQS_URL,
                                MessageBody=json.dumps(document),
                                # Optional: Add message attributes if needed
                                MessageAttributes={
                                'MessageType': {
                                    'DataType': 'String',
                                    'StringValue': 'Inserting/Modifying the  Index'
                                    }
                                }
                            )
                            return {
                                'statusCode': 200,
                                'body': json.dumps({
                                'message': 'Message sent successfully',
                                'messageId': response['MessageId']
                                })
                            }
                        except Exception as e:
                            return {
                                'statusCode': 500,
                                'body': json.dumps({
                                'error': str(e)
                                    })
                                }
        
        return {
            'statusCode': 200,
            'body': json.dumps('Processing completed successfully')
        }
        
    except Exception as e:
        print(f"Error processing stream: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing stream: {str(e)}')
        }


def deserialize_dynamodb_json(dynamodb_json):
    """Convert DynamoDB JSON to regular JSON"""
    result = {}
    
    for key, value in dynamodb_json.items():
        # Handle different DynamoDB types
        if 'S' in value:
            result[key] = value['S']
        elif 'N' in value:
            result[key] = float(value['N'])
        elif 'BOOL' in value:
            result[key] = value['BOOL']
        elif 'NULL' in value:
            result[key] = None
        elif 'L' in value:
            result[key] = [deserialize_dynamodb_json(item) if isinstance(item, dict) else item for item in value['L']]
        elif 'M' in value:
            result[key] = deserialize_dynamodb_json(value['M'])
    
    return result
