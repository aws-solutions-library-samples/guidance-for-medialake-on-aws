import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class UserSyncService:
    def __init__(self, region: str, user_pool_id: str, user_table_name: str):
        self.cognito = boto3.client("cognito-idp", region_name=region)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.user_table = self.dynamodb.Table(user_table_name)
        self.user_pool_id = user_pool_id

    def _extract_user_attributes(
        self, attributes: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Extract user attributes from Cognito format into a flat dictionary."""
        result = {}

        for attr in attributes:
            name = attr["Name"]
            value = attr["Value"]

            if name == "email":
                result["email"] = value
            elif name == "given_name":
                result["first_name"] = value
            elif name == "family_name":
                result["last_name"] = value
            elif name == "phone_number":
                result["phone_number"] = value
            elif name == "email_verified":
                result["verified"] = value.lower() == "true"
            # Add any custom attributes with 'custom:' prefix
            elif name.startswith("custom:"):
                custom_key = name.replace("custom:", "")
                result[custom_key] = value

        return result

    def get_cognito_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user details from Cognito."""
        try:
            response = self.cognito.admin_get_user(
                UserPoolId=self.user_pool_id, Username=username
            )
            return {
                "username": response["Username"],
                "attributes": self._extract_user_attributes(response["UserAttributes"]),
                "status": response["UserStatus"],
                "created_at": int(response["UserCreateDate"].timestamp() * 1000),
                "updated_at": int(response["UserLastModifiedDate"].timestamp() * 1000),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "UserNotFoundException":
                return None
            raise

    async def handle_user_creation(self, event: Dict[str, Any]) -> None:
        """Handle user creation event from Cognito."""
        username = event["userName"]
        cognito_user = self.get_cognito_user(username)

        if not cognito_user:
            logger.error(f"User {username} not found in Cognito during creation sync")
            return

        user_record = {
            "user_id": username,
            "email": cognito_user["attributes"].get("email"),
            "first_name": cognito_user["attributes"].get("first_name"),
            "last_name": cognito_user["attributes"].get("last_name"),
            "phone_number": cognito_user["attributes"].get("phone_number"),
            "created_at": cognito_user["created_at"],
            "updated_at": int(time.time() * 1000),
            "status": cognito_user["status"],
            "verified": cognito_user["attributes"].get("verified", False),
        }

        try:
            # Use conditional write to prevent overwriting existing users
            self.user_table.put_item(
                Item=user_record, ConditionExpression="attribute_not_exists(user_id)"
            )
            logger.info(f"Created user record in DynamoDB for user {username}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"User {username} already exists in DynamoDB")
            else:
                logger.error(f"Error creating user record: {str(e)}")
                raise

    async def handle_user_authentication(self, event: Dict[str, Any]) -> None:
        """Handle user authentication event from Cognito."""
        username = event["userName"]
        cognito_user = self.get_cognito_user(username)

        if not cognito_user:
            logger.error(f"User {username} not found in Cognito during auth sync")
            return

        update_expr = ["SET updated_at = :updated_at, last_login = :last_login"]
        expr_values = {
            ":updated_at": int(time.time() * 1000),
            ":last_login": int(time.time() * 1000),
        }

        # Add any changed attributes to the update
        attrs = cognito_user["attributes"]
        if "first_name" in attrs:
            update_expr.append("first_name = :first_name")
            expr_values[":first_name"] = attrs["first_name"]
        if "last_name" in attrs:
            update_expr.append("last_name = :last_name")
            expr_values[":last_name"] = attrs["last_name"]
        if "phone_number" in attrs:
            update_expr.append("phone_number = :phone_number")
            expr_values[":phone_number"] = attrs["phone_number"]

        try:
            self.user_table.update_item(
                Key={"user_id": username},
                UpdateExpression=", ".join(update_expr),
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"Updated user record in DynamoDB for user {username}")
        except ClientError as e:
            logger.error(f"Error updating user record: {str(e)}")
            raise

    async def handle_user_deletion(self, event: Dict[str, Any]) -> None:
        """Handle user deletion event from Cognito."""
        username = event["userName"]

        try:
            self.user_table.delete_item(Key={"user_id": username})
            logger.info(f"Deleted user record from DynamoDB for user {username}")
        except ClientError as e:
            logger.error(f"Error deleting user record: {str(e)}")
            raise

    async def handle_cognito_event(self, event: Dict[str, Any]) -> None:
        """Main handler for Cognito events."""
        trigger_source = event.get("triggerSource")

        if trigger_source == "PostConfirmation_ConfirmSignUp":
            await self.handle_user_creation(event)
        elif trigger_source == "PostAuthentication_Authentication":
            await self.handle_user_authentication(event)
        elif trigger_source == "PostCustomMessage_AdminDeleteUser":
            await self.handle_user_deletion(event)
        else:
            logger.warning(f"Unhandled trigger source: {trigger_source}")

    async def reconcile_user(self, user_id: str) -> None:
        """Utility method to check and fix inconsistencies between Cognito and DynamoDB."""
        try:
            # Get user from both systems
            cognito_user = self.get_cognito_user(user_id)
            dynamo_user = self.user_table.get_item(Key={"user_id": user_id}).get("Item")

            # User exists in Cognito but not in DynamoDB
            if cognito_user and not dynamo_user:
                await self.handle_user_creation({"userName": user_id})
                return

            # User exists in DynamoDB but not in Cognito
            if not cognito_user and dynamo_user:
                await self.handle_user_deletion({"userName": user_id})
                return

            # User exists in both, update DynamoDB with latest Cognito data
            if cognito_user and dynamo_user:
                await self.handle_user_authentication({"userName": user_id})

        except Exception as e:
            logger.error(f"Error reconciling user {user_id}: {str(e)}")
            raise


# Lambda handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for Cognito triggers."""

    print(event)
    print(context)

    return {"statusCode": 200, "body": "Success"}

    # sync_service = UserSyncService(
    #     region=context.invoked_function_arn.split(":")[3],
    #     user_pool_id=event["userPoolId"],
    #     user_table_name=os.environ["USER_SETTINGS_TABLE"],
    # )

    # try:
    #     await sync_service.handle_cognito_event(event)
    #     return {"statusCode": 200, "body": "Success"}
    # except Exception as e:
    #     logger.error(f"Error handling Cognito event: {str(e)}")
    #     return {"statusCode": 500, "body": str(e)}
