import json
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, ConfigDict

# Initialize AWS clients and utilities
logger = Logger()
metrics = Metrics()

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


class BaseModelWithConfig(BaseModel):
    """Base model with JSON configuration"""

    model_config = ConfigDict(json_encoders={})


class FieldInfo(BaseModelWithConfig):
    """Model for field information"""

    name: str
    displayName: str
    description: str
    type: str
    isDefault: bool = False


class FieldsResponse(BaseModelWithConfig):
    """Model for fields response"""

    status: str
    message: str
    data: Dict[str, Any]


def get_search_fields() -> Dict[str, Any]:
    """
    Get all available search fields and default fields.

    Returns:
        Dict containing default fields and all available fields
    """
    # Define all available search fields
    all_fields = [
        FieldInfo(
            name="DigitalSourceAsset.Type",
            displayName="Asset Type",
            description="Type of the asset (image, video, audio, document)",
            type="string",
            isDefault=True,
        ),
        FieldInfo(
            name="DigitalSourceAsset.MainRepresentation.Format",
            displayName="File Format",
            description="Format/extension of the file",
            type="string",
            isDefault=True,
        ),
        FieldInfo(
            name="DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
            displayName="File Size",
            description="Size of the file in bytes",
            type="number",
            isDefault=True,
        ),
        FieldInfo(
            name="DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
            displayName="Created date",
            description="Date when the asset was created",
            type="date",
            isDefault=True,
        ),
        FieldInfo(
            name="DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
            displayName="File name",
            description="Name of the file",
            type="string",
            isDefault=True,
        ),
        FieldInfo(
            name="DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath",
            displayName="Full path",
            description="Full path to the file",
            type="string",
            isDefault=False,
        ),
        # FieldInfo(
        #     name="DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket",
        #     displayName="Storage location",
        #     description="Storage bucket where the asset is stored",
        #     type="string",
        #     isDefault=True
        # ),
    ]

    # Extract default fields
    default_fields = [field for field in all_fields if field.isDefault]

    return {
        "defaultFields": [field.model_dump(by_alias=True) for field in default_fields],
        "availableFields": [field.model_dump(by_alias=True) for field in all_fields],
    }


@app.get("/search/fields")
def handle_get_fields():
    """Handle request to get search fields"""
    try:
        fields_data = get_search_fields()
        return {"status": "200", "message": "ok", "data": fields_data}
    except Exception as e:
        logger.error(f"Error retrieving search fields: {str(e)}")
        return {
            "status": "500",
            "message": f"Error retrieving search fields: {str(e)}",
            "data": None,
        }


@metrics.log_metrics
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    return app.resolve(event, context)
