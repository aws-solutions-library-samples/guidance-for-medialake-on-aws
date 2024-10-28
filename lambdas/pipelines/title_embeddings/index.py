from opensearch.client import OpenSearchClient
import boto3
import json


def lambda_handler(event, context):
    try:
        print(event)
        title = transform_event(event)
        embeddings = create_embeddings(title)
        title["embedding"] = embeddings
        opensearch = OpenSearchClient()
        opensearch.put_document(
            index="titles",
            document=title,
            lookup_field="titleId",
            lookup_value=title["titleId"]
        )
        return {'statusCode': 200, 'body': 'Success'}
    except Exception as e:
        return {'statusCode': 500, 'body': str(e)}


def transform_event(event):
    meta = event["detail"]["meta"]
    data = event["detail"]["data"]

    title = {
        "titleId": meta["id"],
        "name": data["name"]
    }

    return title


def create_embeddings(title):
    try:
        bedrock_runtime = boto3.client("bedrock-runtime")
        model_name = "amazon.titan-embed-text-v2:0"

        response = bedrock_runtime.invoke_model(
            modelId=model_name,
            body=json.dumps({
                "inputText": title["name"],
                "dimensions": 1024,
                "normalize": True
            }),
            contentType="application/json",
            accept="application/json"
        )
        embeddings = json.loads(response.get('body').read())
        return embeddings['embedding']
    except Exception as e:
        print(f"Error creating embeddings: {str(e)}")
        return None
