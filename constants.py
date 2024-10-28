import uuid
import os


def generate_small_uid():
    return str(uuid.uuid4())[:16]


SMALL_UID = os.environ.get("SMALL_UID", generate_small_uid())

API_TEMPLATES_BUCKET_NAME = "mne-mscdemo-api-templates"
DEMO_MEDIA_ASSETS_KMS_ALIAS_NAME = "alias/mne-mscdemo-media-assets-bucket"
API_TEMPLATES_KMS_ALIAS_NAME = "alias/mne-mscdemo-api-templates-bucket"
WORKFLOW_PAYLOAD_TEMP_BUCKET = "mne-mscdemo-workflow-payload-temp-data"
ACCESS_LOGS_BUCKET = f"medialake-access-logs-{SMALL_UID}"
