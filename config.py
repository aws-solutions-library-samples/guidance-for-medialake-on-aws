import json
import os
import uuid
from typing import List, Optional
from pydantic import BaseModel
import hashlib


def generate_small_uid() -> str:
    return str(uuid.uuid4())[:16]

GLOBAL_PREFIX = "medialake"
class CDKConfig(BaseModel):
    """Configuration for CDK Application"""
    enable_ha: bool = False
    primary_region: str = "us-east-1"
    secondary_region: Optional[str] = None
    small_uid: str = ""


    @property
    def regions(self) -> List[str]:
        regions = [self.primary_region]
        if self.enable_ha and self.secondary_region:
            regions.append(self.secondary_region)
        return regions

    @property
    def access_logs_bucket(self) -> str:
        return "medialake-access-logs"

    @classmethod
    def load_from_file(cls, filename="cdk_config.json"):
        try:
            with open(filename, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            return cls()
        
def generate_short_uid(construct, length=8):
    # Generate a hash based on the construct's path
    construct_path = construct.node.path
    hash_object = hashlib.md5(construct_path.encode())
    full_hash = hash_object.hexdigest()
    return full_hash[:length]

config = CDKConfig.load_from_file()
