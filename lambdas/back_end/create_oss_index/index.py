from requests import request
import json
import os
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, ClientError
from time import sleep

def handler(event, context):
    
    print(event)
    
    if event['RequestType'] == 'Create':
        # 1. Defining the request body for the index and field creation
        host = os.environ["COLLECTION_ENDPOINT"]
        print(f"Collection Endpoint: " + host)
        
        index_names = os.environ["INDEX_NAMES"]
        print(f"Index names: " + index_names)

        headers = {
            'content-type': 'application/json', 
            'accept': 'application/json',
        }
        payload = {
        "settings": {
                "index.knn": True,
                "number_of_shards": 2
            }
        }
        
        # 2. Obtaining AWS credentials and signing the AWS API request 
        region = os.environ["REGION"]
        service = os.environ["SCOPE"]
        credentials = boto3.Session().get_credentials()
        
        params = None
        payload_json = json.dumps(payload)
        
        signer = SigV4Auth(credentials, service, region)
        indexes = index_names.split(",")
        for index_name in indexes:
            while True:
                try:        
                    url = host + "/" + index_name
                    print(f"URL: " + url)
                    req = AWSRequest(method='PUT', url=url, data=payload_json, params=params, headers=headers)
                    req.headers['X-Amz-Content-SHA256'] = signer.payload(req) # Add the payload hash to the headers as aoss/es requires it !
                    SigV4Auth(credentials, service, region).add_auth(req)
                    req = req.prepare()

                    response = request(
                        method=req.method,
                        url=req.url,
                        headers=req.headers,
                        data=req.body
                    )

                    if response.status_code != 200:
                        raise Exception(f"Failed to create OS index - status: {response.status_code} {response.text}")
                
                except Exception as e:
                    print('Retrying to create aoss/es index...')
                    sleep(5)
                    continue
            
                print(f"Index create SUCCESS - status: {response.text}")
                break   