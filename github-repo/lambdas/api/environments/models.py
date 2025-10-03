from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, constr


class EnvironmentBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    region: constr(min_length=1, max_length=50)
    tags: Dict[str, str] = Field(
        default_factory=dict, example={"cost-center": "dept-123", "team": "platform"}
    )


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    status: Optional[Literal["active", "disabled"]] = None
    region: Optional[constr(min_length=1, max_length=50)] = None
    tags: Optional[Dict[str, str]] = None


class Environment(EnvironmentBase):
    environment_id: str
    status: Literal["active", "disabled"] = "active"
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
