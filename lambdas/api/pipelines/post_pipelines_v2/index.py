from typing import Dict, Any, List, Optional

import json
from pydantic import BaseModel, Field

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure CORS
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])

# Initialize API Gateway resolver
app = APIGatewayRestResolver(cors=cors_config)


# ---------------------
# Data Models (Pydantic)
# ---------------------
class NodeData(BaseModel):
    id: str
    type: str
    label: str
    icon: Dict[str, Any]
    inputTypes: List[str] = Field(default_factory=list)
    outputTypes: List[str] = Field(default_factory=list)
    configuration: Dict[str, Any]


class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, Any]
    width: str
    height: str
    data: NodeData


class Edge(BaseModel):
    source: str
    sourceHandle: Optional[str]
    target: str
    targetHandle: Optional[str]
    id: str
    type: str
    data: Dict[str, Any]


class Settings(BaseModel):
    autoStart: bool
    retryAttempts: int
    timeout: int


class Configuration(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    settings: Settings


class PipelineDefinition(BaseModel):
    name: str
    description: str
    configuration: Configuration


# ---------------------
# Route Handlers
# ---------------------
@app.post("/pipelines")
@tracer.capture_method
def create_pipeline(pipeline: PipelineDefinition) -> Dict[str, Any]:
    """
    Create a new pipeline based on the provided configuration.

    :param pipeline: Parsed PipelineDefinition data from the request body
    :return: JSON response indicating success or failure
    """
    try:
        name = pipeline.name
        description = pipeline.description
        nodes = pipeline.configuration.nodes
        edges = pipeline.configuration.edges
        settings = pipeline.configuration.settings

        logger.info(f"Creating pipeline: {name} - {description}")

        # Process nodes
        for node in nodes:
            logger.debug(f"Processing node: {node.id}")
            # Node processing logic here

        # Process edges
        for edge in edges:
            logger.debug(f"Processing edge: {edge.id}")
            # Edge processing logic here

        # Log settings
        logger.info(
            f"Pipeline settings -> AutoStart: {settings.autoStart}, "
            f"RetryAttempts: {settings.retryAttempts}, "
            f"Timeout: {settings.timeout}"
        )

        # Put your pipeline creation logic here...

        return {"message": "Pipeline created successfully", "name": name}

    except Exception as e:
        logger.exception("Error creating pipeline")
        return {"error": "Failed to create pipeline"}


# ---------------------
# Lambda Handler
# ---------------------
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.

    :param event: Event payload
    :param context: Lambda execution context
    :return: Response as a dictionary (handled by APIGatewayRestResolver)
    """
    # Log the incoming event at debug level
    logger.debug("Received event", extra={"event": event})
    return app.resolve(event, context)
