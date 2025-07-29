from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class NodeData(BaseModel):
    id: str
    type: str
    label: str
    description: str
    icon: Dict[str, Any]
    inputTypes: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    outputTypes: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
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
    active: bool = True  # Default to active
