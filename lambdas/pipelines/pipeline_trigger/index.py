import os
import boto3

def lambda_handler(event, context):
    # Get the Step Function ARN from environment variables
    step_function_arn = os.environ['STEP_FUNCTION_ARN']
    
    # Initialize the Step Functions client
    client = boto3.client('stepfunctions')
    
    # Start execution of the Step Function
    try:
        response = client.start_execution(
            stateMachineArn=step_function_arn,
            input='{}'  # You can pass any input here as a JSON string
        )
        return {
            'statusCode': 200,
            'body': response
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }
