"""
AWS Lambda function for asynchronously creating and updating pipelines.
This is the front-end Lambda that starts a Step Function execution.
"""

from typing import Dict, Any

from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the Lambda handler from handlers module
from handlers import lambda_handler

# Re-export the lambda_handler function
__all__ = ["lambda_handler"]