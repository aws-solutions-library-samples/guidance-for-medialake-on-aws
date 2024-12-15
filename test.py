import json
import boto3
from botocore.exceptions import ClientError
import base64
import time
import http.client
import traceback
import re

error = "The system encountered an unexpected error during processing. Try your request again."
wait_error = "Too many requests, please wait before trying again. You have sent too many requests.  Wait before trying again."


def invoke_claude_3(prompt):

    # Initialize the Amazon Bedrock runtime client
    client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    # Invoke Claude 3 with the text prompt
    # model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    # model_id = "amazon.nova-pro-v1:0"
    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "user", "content": [{"type": "text", "text": prompt}]}
                    ],
                }
            ),
        )
        # Process and print the response
        result = json.loads(response.get("body").read())

        return result
    except ClientError as err:
        print(
            "Couldn't invoke Claude 3 Sonnet. Here's why: %s: %s",
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        return err.response["Error"]["Message"]


def invoke(prompt):
    result = invoke_claude_3(prompt)
    if error in result or wait_error in result:
        raise Exception(result)
    output = result.get("content", [])[0]["text"]
    if "error message" in output.lower() or output == "":
        print("error")
        print(output)
        raise
    return output


def lambda_handler(event, context):
    # print(event)
    prompt = event["bedrock_response"]["Payload"]["body"]["prompt"]
    # print(prompt)

    response = invoke(prompt)

    print("***************")
    print(response.replace("\n", " "))
    print("***************")
    return {"statusCode": 200, "bedrock_cypher_query": response}
