import os


def get_state_machine_definition(
    image_metadata_extractor_arn: str,
    image_proxy_lambda_arn: str,
    pipeline_name: str,
    asset_table_name: str,
    output_bucket_name: str,
) -> dict:
    """Returns the state machine definition with the provided ARNs"""
    return {
        "Comment": f"Pipeline {pipeline_name}",
        "StartAt": "ExtractMetadata",
        "States": {
            "ExtractMetadata": {
                # This state remains the same
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_metadata_extractor_arn,
                    "Payload": {"pipeline_id.$": "$.pipeline_id", "input.$": "$.input"},
                },
                "ResultPath": "$.metadataResult",
                "Next": "CreateProxy",
            },
       
            "CreateProxy": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "output_bucket": output_bucket_name,
                        "mode": "proxy",
                    },
                },
                "ResultPath": "$.proxyResult",
                "Next": "CreateThumbnail",
            },
           
            "CreateThumbnail": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        # "metadata.$": "$.metadataResult.Payload.body.metadata",
                        "output_bucket": output_bucket_name,
                        "mode": "thumbnail",
                        "width": 345,
                    },  # This closing brace was missing
                },
                "ResultPath": None,
                "End": True,
            },
          
        },
    }


def create_metadata_extractor_lambda(
    lambda_client,
    function_name: str,
    role_arn: str,
    deployment_bucket: str,
    deployment_zip: str,
    exiftool_layer_arn: str,
    exempitool_layer_arn: str,
    environment_variables: dict,
    tags: dict,   
) -> dict:
    """Creates the metadata extractor lambda function"""
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Timeout=900,
        Handler="index.lambda_handler",
        Code={"S3Bucket": deployment_bucket, "S3Key": deployment_zip},
        Layers=[exiftool_layer_arn,exempitool_layer_arn],
        Environment={
            'Variables': environment_variables
        },
        Tags=tags,
    )


def create_image_proxy_lambda(
    lambda_client,
    function_name: str,
    role_arn: str,
    deployment_bucket: str,
    deployment_zip: str,
    environment_variables: dict,
    tags: dict,
) -> dict:
    """Creates the image proxy lambda function"""
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Timeout=900,
        MemorySize=10240,
        Handler="index.lambda_handler",
        Code={"S3Bucket": deployment_bucket, "S3Key": deployment_zip},
        Layers=["arn:aws:lambda:us-east-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:56"],
        Environment={
            'Variables': environment_variables
        },
        Tags=tags,
    )
