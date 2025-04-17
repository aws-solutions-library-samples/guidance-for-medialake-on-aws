import boto3
import cfnresponse
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    if event["RequestType"] == "Create":
        client = boto3.client("cognito-idp")
        try:
            client.admin_create_user(
                UserPoolId=event["ResourceProperties"]["UserPoolId"],
                Username="raverrr@amazon.com.com",
                UserAttributes=[
                    {"Name": "email", "Value": "admin@example.com"},
                    {"Name": "email_verified", "Value": "true"},
                ],
                DesiredDeliveryMediums=["EMAIL"],
            )
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "UsernameExistsException":
                print("User already exists, treating as success")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            else:
                print(f"Error: {error_code} - {e}")
                cfnresponse.send(event, context, cfnresponse.FAILED, {})
        except Exception as e:
            print(e)
            cfnresponse.send(event, context, cfnresponse.FAILED, {})
    else:
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
