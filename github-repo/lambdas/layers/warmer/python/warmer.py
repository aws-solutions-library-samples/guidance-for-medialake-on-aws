import json
import os
import time
import urllib.request
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


class WarmerExtension:
    def __init__(self):
        self.extension_id = os.environ.get("_HANDLER")
        self.table_name = os.environ.get("WARMER_TABLE")
        self.ttl = int(os.environ.get("EXTENSION_TTL", "300"))
        self.enabled = os.environ.get("WARMER_ENABLED", "false").lower() == "true"
        self.max_retries = 3
        self.retry_delay = 1
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def register(self) -> str:
        """Register the extension with Lambda Runtime."""
        request = urllib.request.Request(
            f"http://{os.environ['AWS_LAMBDA_RUNTIME_API']}/2020-01-01/extension/register",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Lambda-Extension-Name": "warmer",
            },
            data=json.dumps({"events": ["INVOKE", "SHUTDOWN"]}).encode(),
        )

        try:
            with urllib.request.urlopen(request) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to register extension: {response.read().decode()}"
                    )
                return json.loads(response.read())["extensionId"]
        except Exception as e:
            raise Exception(f"Extension registration failed: {str(e)}")

    def process_events(self) -> None:
        """Process Lambda extension events."""
        while True:
            request = urllib.request.Request(
                f"http://{os.environ['AWS_LAMBDA_RUNTIME_API']}/2020-01-01/extension/event/next",
                method="GET",
                headers={
                    "Content-Type": "application/json",
                    "Lambda-Extension-Identifier": self.extension_id,
                },
            )

            try:
                with urllib.request.urlopen(request) as response:
                    if response.status != 200:
                        print(f"Failed to get next event: {response.read().decode()}")
                        continue

                    event = json.loads(response.read())

                    if event["eventType"] == "INVOKE":
                        self.handle_invoke()
                    elif event["eventType"] == "SHUTDOWN":
                        self.handle_shutdown()
                        break
            except Exception as e:
                print(f"Error processing events: {str(e)}")
                time.sleep(1)

    def handle_invoke(self) -> None:
        """Handle Lambda invoke event."""
        if not self.enabled:
            return

        try:
            self.update_state()
        except Exception as e:
            print(f"Failed to handle invoke: {str(e)}")

    def handle_shutdown(self) -> None:
        """Handle Lambda shutdown event."""
        if not self.enabled:
            return

        try:
            self.cleanup_state()
        except Exception as e:
            print(f"Failed to handle shutdown: {str(e)}")

    def update_state(self) -> None:
        """Update extension state in DynamoDB."""
        now = int(time.time())
        item = {
            "extensionId": self.extension_id,
            "ttl": now + self.ttl,
            "lastUpdated": now,
        }

        for attempt in range(self.max_retries):
            try:
                self.table.put_item(Item=item)
                return
            except ClientError as e:
                if attempt == self.max_retries - 1:
                    raise e
                time.sleep(self.retry_delay * (2**attempt))

    def cleanup_state(self) -> None:
        """Clean up extension state from DynamoDB."""
        try:
            self.table.delete_item(Key={"extensionId": self.extension_id})
        except Exception as e:
            print(f"Failed to cleanup state: {str(e)}")


def create_handler_wrapper(original_handler):
    """Create a wrapper for the Lambda handler that supports warming."""

    def wrapper(event: Dict[str, Any], context: Any) -> Any:
        if event.get("warmer"):
            return {"warmed": True, "function": context.function_name}
        return original_handler(event, context)

    return wrapper
