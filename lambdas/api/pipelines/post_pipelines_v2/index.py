from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.logging import correlation_paths
from typing import Dict, Any
from botocore.exceptions import ClientError
import json
import os

# Initialize PowerTools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure CORS
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])

# Initialize API Gateway resolver
app = APIGatewayRestResolver(cors=cors_config)


@app.post("/pipelines")
@tracer.capture_method
def create_pipeline():
    ## TODO: Read pipeline definition

    ## Get Integrations
    ## Get Env?

    ## For node:
    ##  build auth from nodeTemplate that we got from get_node
    ##      authConfiguration - api-key in the header x-api-key and then value
    ##      customheadercofiguration
    ## input/output schema passed in to this lambda in the node data
    ## anything static or custom for payload passed in to this lambda in the node data
    pass


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    return app.resolve(event, context)
