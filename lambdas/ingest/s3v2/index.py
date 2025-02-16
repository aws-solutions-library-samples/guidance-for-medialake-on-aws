import boto3
import os
import magic

def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    
    bucket_name = event['bucket']
    object_key = event['key']
    
    # Read only first 2048 bytes
    response = s3_client.get_object(
        Bucket=bucket_name,
        Key=object_key,
        Range='bytes=0-2047'
    )
    
    # Get the bytes from the response
    file_bytes = response['Body'].read()
    
    # Use python-magic to detect file type
    file_type = magic.from_buffer(file_bytes, mime=True)
    
    return {
        'statusCode': 200,
        'body': {
            'fileType': file_type,
            'fileName': object_key
        }
    }
