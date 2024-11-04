import boto3
import cfnresponse


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
        except Exception as e:
            print(e)
            cfnresponse.send(event, context, cfnresponse.FAILED, {})
    else:
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
