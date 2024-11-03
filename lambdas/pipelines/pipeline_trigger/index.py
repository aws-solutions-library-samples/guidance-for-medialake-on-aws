import os
import json
import boto3

def lambda_handler(event, context):
    # Get the Step Function ARN from environment variables
    step_function_arn = os.environ['STEP_FUNCTION_ARN']
    
    # Initialize the Step Functions client
    sfn_client = boto3.client('stepfunctions')
    
    try:
        # Process each record from SQS
        for record in event['Records']:
            # Parse the message body which contains the EventBridge event
            message_body = json.loads(record['body'])
            
            # Extract the assets array from the detail
            assets = message_body['detail']['assets']
            
            # Start execution of the Step Function for each asset
            for asset in assets:
                # Prepare the input for the Step Function
                step_function_input = {
                    "pipeline_id": asset['id'],  # Using asset ID as pipeline_id
                    "input": asset  # Pass the entire asset object
                }
                
                # Start the Step Function execution
                response = sfn_client.start_execution(
                    stateMachineArn=step_function_arn,
                    input=json.dumps(step_function_input)
                )
                
                print(f"Started execution for asset {asset['id']}: {response['executionArn']}")
        
        return {
            'statusCode': 200,
            'body': 'Successfully processed all assets'
        }
        
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return {
            'statusCode': 500,
            'body': str(e)
        }
