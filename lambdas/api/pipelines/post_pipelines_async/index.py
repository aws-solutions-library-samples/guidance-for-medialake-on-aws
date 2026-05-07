"""
AWS Lambda function for asynchronously creating and updating pipelines.
This is the front-end Lambda that starts a Step Function execution.
"""

# Import the Lambda handler from handlers module
from handlers import lambda_handler

# Re-export the lambda_handler function
__all__ = ["lambda_handler"]
