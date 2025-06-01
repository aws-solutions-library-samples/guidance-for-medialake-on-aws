"""
AWS Lambda function for deleting pipelines.
This is the main entry point that imports from the modular components.
"""

from typing import Dict, Any

from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the Lambda handler from handlers module
from handlers import lambda_handler

# Re-export the lambda_handler function
__all__ = ["lambda_handler"]
