sadfsdf

# """Lambda function to get all connectors from DynamoDB."""
# import os
# from typing import Dict

# from aws_lambda_powertools import Logger, Tracer
# from aws_lambda_powertools.event_handler import (
#     APIGatewayRestResolver,
#     Response,
#     content_types,
# )
# from aws_lambda_powertools.logging import correlation_paths
# from aws_lambda_powertools.utilities.typing import LambdaContext
# from pynamodb.attributes import MapAttribute, UnicodeAttribute
# from pynamodb.models import Model


# tracer = Tracer()
# logger = Logger()
# app = APIGatewayRestResolver(enable_validation=True)


# class ConnectorModel(Model):
#     """DynamoDB model for storing connector information."""

#     class Meta:
#         """Model metadata."""
#         table_name = os.environ.get('CONNECTORS_TABLE')
#         region = os.environ.get('AWS_REGION')

#     id = UnicodeAttribute(hash_key=True)
#     name = UnicodeAttribute()
#     type = UnicodeAttribute()
#     created_at = UnicodeAttribute()
#     updated_at = UnicodeAttribute()
#     config = MapAttribute(null=True)


# @app.get("/connectors")
# def get_connector() -> Dict:
#     """Get all connectors from DynamoDB.

#     Returns:
#         Dict: Response containing list of connectors or error message
#     """
#     try:
#         connectors = []
#         for connector in ConnectorModel.scan():
#             connectors.append({
#                 'id': connector.id,
#                 'name': connector.name,
#                 'type': connector.type,
#                 'created_at': connector.created_at,
#                 'updated_at': connector.updated_at,
#                 'config': connector.config
#             })

#         return {
#             "data": {
#                 "connectors": connectors
#             }
#         }
#     except Exception as error:
#         logger.error(f"Error getting connectors: {str(error)}")
#         return Response(
#             status_code=500,
#             content_type=content_types.APPLICATION_JSON,
#             body={"message": "Internal server error"}
#         )


# @logger.inject_lambda_context(
#     correlation_id_path=correlation_paths.API_GATEWAY_HTTP
# )
# @tracer.capture_lambda_handler
# def lambda_handler(event: dict, context: LambdaContext) -> dict:
#     """AWS Lambda handler function.

#     Args:
#         event (dict): Lambda function invocation event
#         context (LambdaContext): Lambda function context

#     Returns:
#         dict: Response from API Gateway
#     """
#     return app.resolve(event, context)
