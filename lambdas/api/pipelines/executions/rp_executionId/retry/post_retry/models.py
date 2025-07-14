from pynamodb.attributes import NumberAttribute, UnicodeAttribute
from pynamodb.models import Model


class PipelineExecution(Model):
    class Meta:
        table_name = "pipelines_executions_dev"  # Will be overridden by env var
        region = "us-east-1"  # Will be overridden by env var

    execution_id = UnicodeAttribute(hash_key=True)
    start_time = NumberAttribute(range_key=True)
    start_time_iso = UnicodeAttribute()
    pipeline_name = UnicodeAttribute()
    status = UnicodeAttribute()
    state_machine_arn = UnicodeAttribute()
    execution_arn = UnicodeAttribute()
    last_updated = UnicodeAttribute()  # Store as ISO string instead of UTCDateTime
    ttl = NumberAttribute()
    end_time = NumberAttribute(null=True)
    end_time_iso = UnicodeAttribute(null=True)
