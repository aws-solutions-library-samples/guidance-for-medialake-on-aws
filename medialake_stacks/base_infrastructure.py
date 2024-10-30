from aws_cdk import (
    Stack,
    Environment,
    aws_events as events
)
from constructs import Construct
from medialake_constructs.shared_constructs.s3bucket import S3Bucket, S3Config
from config import config
from medialake_constructs.shared_constructs.eventbridge import EventBus, EventBusConfig

class BaseInfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        env = kwargs.get('env')
        region = env.region if isinstance(env, Environment) else config.primary_region

        # Create media assets bucket with explicit name including region
        media_assets_bucket_config = S3Config(
            bucket_name=f"medialake-media-assets-{region}-{config.small_uid}"
        )
        self.media_assets_bucket = S3Bucket(
            self,
            "MediaAssets",
            s3_config=media_assets_bucket_config
        )
        
        ingest_event_bus_config = EventBusConfig(
            bus_name=f"medialake-ingest-{region}-{config.small_uid}",
            description="event bus"
        )
        self._ingest_event_bus = EventBus(
            self,
            "IngestEventBus",
            props=ingest_event_bus_config
        )
    
    @property
    def ingest_event_bus(self) -> events.EventBus:
        return self._ingest_event_bus.event_bus
    
    @property
    def ingest_event_bus_name(self) -> str:
        return self._ingest_event_bus.event_bus_name
