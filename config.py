import json
import os
import uuid
from typing import List, Optional
from pydantic import BaseModel


def generate_small_uid() -> str:
    return str(uuid.uuid4())[:16]


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""
    enable_ha: bool = False
    primary_region: str = "us-east-1"
    secondary_region: Optional[str] = None
    small_uid: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        self.small_uid = os.environ.get("SMALL_UID", generate_small_uid())
        
    @property
    def regions(self) -> List[str]:
        regions = [self.primary_region]
        if self.enable_ha and self.secondary_region:
            regions.append(self.secondary_region)
        return regions

    @property
    def access_logs_bucket(self) -> str:
        return f"medialake-access-logs-{self.small_uid}"

    @classmethod
    def load_from_file(cls, filename="cdk_config.json"):
        try:
            with open(filename, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            return cls()


config = CDKConfig.load_from_file()
