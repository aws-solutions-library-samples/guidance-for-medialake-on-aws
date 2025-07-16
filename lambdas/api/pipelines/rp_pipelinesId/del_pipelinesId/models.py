from typing import Optional

from pydantic import BaseModel


class DeletePipelineRequest(BaseModel):
    """
    Model for pipeline deletion request.
    """

    pipeline_id: Optional[str] = None
    pipeline_name: Optional[str] = None

    def validate_request(self) -> bool:
        """
        Validate that at least one identifier is provided.

        Returns:
            bool: True if the request is valid, False otherwise
        """
        return bool(self.pipeline_id or self.pipeline_name)
