import os

def get_state_machine_definition(
    image_metadata_extractor_arn: str,
    image_proxy_lambda_arn: str,
    pipeline_name: str,
    asset_table_name: str
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
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)"
                        }
                    }
                },
                "ResultPath": "$.metadataResult",
                "Next": "StoreMetadata"
            },
            "StoreMetadata": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET metadata = :metadata",
                    "ExpressionAttributeValues": {
                        ":metadata": {"M.$": "$.metadataResult.Payload.body.metadata"}
                    }
                },
                "ResultPath": null,
                "Next": "CreateProxy"
            },
            # Rest of the states remain the same
            "CreateProxy": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "metadata.$": "$.metadataResult.Payload.body.metadata",  # Updated path
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)",
                            "mode": "proxy",
                            "output_bucket": "YOUR_OUTPUT_BUCKET"
                        }
                    }
                },
                "ResultPath": "$.proxyResult",
                "Next": "StoreProxy"
            },
            "StoreProxy": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET proxyLocation = :proxyLocation",
                    "ExpressionAttributeValues": {
                        ":proxyLocation": {
                            "M": {
                                "bucket": {"S.$": "$.proxyResult.Payload.body.bucket"},
                                "key": {"S.$": "$.proxyResult.Payload.body.key"},
                                "type": {"S": "S3"}
                            }
                        }
                    }
                },
                "Next": "CreateThumbnail"
            },
            "CreateThumbnail": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "metadata.$": "$.metadataResult.Payload.body.metadata",  # Updated path
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)",
                            "mode": "thumbnail",
                            "output_bucket": "YOUR_OUTPUT_BUCKET",
                            "thumbnail": {
                                "width": 345,
                                "height": 194
                            }
                        }
                    }
                },
                "ResultPath": "$.thumbnailResult",
                "Next": "StoreThumbnail"
            },
            "StoreThumbnail": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET thumbnailLocation = :thumbnailLocation",
                    "ExpressionAttributeValues": {
                        ":thumbnailLocation": {
                            "M": {
                                "bucket": {"S.$": "$.thumbnailResult.Payload.body.bucket"},
                                "key": {"S.$": "$.thumbnailResult.Payload.body.key"},
                                "type": {"S": "S3"}
                            }
                        }
                    }
                },
                "End": True
            }
        }
    }

    """Returns the state machine definition with the provided ARNs"""
    return {
        "Comment": f"Pipeline {pipeline_name}",
        "StartAt": "ExtractMetadata",
        "States": {
            "ExtractMetadata": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_metadata_extractor_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)"
                        }
                    }
                },
                "ResultPath": "$.metadataResult",
                "Next": "StoreMetadata"
            },
            "StoreMetadata": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET metadata = :metadata",
                    "ExpressionAttributeValues": {
                        ":metadata": {"M.$": "$.metadataResult.body"}
                    }
                },
                "ResultPath": null
                "Next": "CreateProxy"
            },
            "CreateProxy": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "metadata.$": "$.metadataResult.body",
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)",
                            "mode": "proxy",
                            "output_bucket": "YOUR_OUTPUT_BUCKET"
                        }
                    }
                },
                "ResultPath": "$.proxyResult",
                "Next": "StoreProxy"
            },
            "StoreProxy": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET proxyLocation = :proxyLocation",
                    "ExpressionAttributeValues": {
                        ":proxyLocation": {
                            "M": {
                                "bucket": {"S.$": "$.proxyResult.body.bucket"},
                                "key": {"S.$": "$.proxyResult.body.key"},
                                "type": {"S": "S3"}
                            }
                        }
                    }
                },
                "Next": "CreateThumbnail"
            },
            "CreateThumbnail": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": image_proxy_lambda_arn,
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "metadata.$": "$.metadataResult.body",
                        "parameters": {
                            "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)",
                            "mode": "thumbnail",
                            "output_bucket": "YOUR_OUTPUT_BUCKET",
                            "thumbnail": {
                                "width": 345,
                                "height": 194
                            }
                        }
                    }
                },
                "ResultPath": "$.thumbnailResult",
                "Next": "StoreThumbnail"
            },
            "StoreThumbnail": {
                "Type": "Task",
                "Resource": "arn:aws:states:::dynamodb:updateItem",
                "Parameters": {
                    "TableName": asset_table_name,
                    "Key": {
                        "id": {"S.$": "$.input.id"}
                    },
                    "UpdateExpression": "SET thumbnailLocation = :thumbnailLocation",
                    "ExpressionAttributeValues": {
                        ":thumbnailLocation": {
                            "M": {
                                "bucket": {"S.$": "$.thumbnailResult.body.bucket"},
                                "key": {"S.$": "$.thumbnailResult.body.key"},
                                "type": {"S": "S3"}
                            }
                        }
                    }
                },
                "End": True
            }
        }
    }

def create_metadata_extractor_lambda(
    lambda_client,
    function_name: str,
    role_arn: str,
    deployment_bucket: str,
    deployment_zip: str,
    exiftool_layer_arn: str, 
    tags: dict
) -> dict:
    """Creates the metadata extractor lambda function"""
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.12',
        Role=role_arn,
        Timeout=900,
        Handler='index.lambda_handler',
        Code={
            'S3Bucket': deployment_bucket,
            'S3Key': deployment_zip
        },
        Layers=[exiftool_layer_arn],
        Tags=tags
    )

def create_image_proxy_lambda(
    lambda_client,
    function_name: str,
    role_arn: str,
    deployment_bucket: str,
    deployment_zip: str,
    tags: dict
) -> dict:
    """Creates the image proxy lambda function"""
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.12',
        Role=role_arn,
        Timeout=900,
        MemorySize=128,
        Handler='index.lambda_handler',
        Code={
            'S3Bucket': deployment_bucket,
            'S3Key': deployment_zip
        },
        Tags=tags
    )
