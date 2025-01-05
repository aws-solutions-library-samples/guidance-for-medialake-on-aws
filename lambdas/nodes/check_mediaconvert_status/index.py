import boto3


def lambda_handler(event, context):
    job_id = event["JobId"]

    mediaconvert = boto3.client("mediaconvert", region_name="us-east-1")

    response = mediaconvert.get_job(Id=job_id)
    status = response["Job"]["Status"]  # e.g. SUBMITTED, PROGRESSING, COMPLETE, ERROR

    return {"status": status}
