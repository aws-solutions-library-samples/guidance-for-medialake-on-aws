import os
import json
import boto3
import urllib.request
import urllib.error
import urllib.parse
import logging
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

# Configuration variables
STUDIO_ID = "67dad188446b8490f9622aa9"  # Studio ID to fetch recordings from
API_KEY = os.environ["RIVERSIDE_API_KEY"]  # Store API key in environment variable
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
RIVERSIDE_API_BASE_URL = "https://platform.riverside.fm/api"

# Initialize AWS PowerTools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

class RiversideClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"BEARER {self.api_key}",
            "User-Agent": "Python-Lambda/1.0",
            "Accept": "application/json"
        }
    
    def list_studio_recordings(self, studio_id, page=0):
        """List all recordings for a specific studio"""
        url = f"{RIVERSIDE_API_BASE_URL}/v2/recordings?studioId={studio_id}&page={page}"
        
        req = urllib.request.Request(url)
        for key, value in self.headers.items():
            req.add_header(key, value)
        
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read().decode('utf-8')
                logger.debug(f"Studio recordings response (first 200 chars): {data[:200]}...")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error: {e.code} - {e.reason}")
            if hasattr(e, 'read'):
                logger.error(f"Response body: {e.read().decode('utf-8')}")
            raise
    
    def get_all_studio_recordings(self, studio_id):
        """Get all recordings for a studio by handling pagination"""
        all_recordings = []
        page = 0
        more_pages = True
        
        while more_pages:
            response = self.list_studio_recordings(studio_id, page)
            
            # Add recordings from current page
            if "data" in response and isinstance(response["data"], list):
                all_recordings.extend(response["data"])
                logger.info(f"Retrieved {len(response['data'])} recordings from page {page}")
            
            # Check if there are more pages
            if "next_page_url" in response and response["next_page_url"]:
                page += 1
            else:
                more_pages = False
                logger.info(f"No more pages available after page {page}")
        
        logger.info(f"Retrieved a total of {len(all_recordings)} recordings")
        return all_recordings
    
    def get_recording_details(self, recording_id):
        """Get detailed information about a specific recording"""
        url = f"{RIVERSIDE_API_BASE_URL}/v1/recordings/{recording_id}"
        
        req = urllib.request.Request(url)
        for key, value in self.headers.items():
            req.add_header(key, value)
        
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error: {e.code} - {e.reason} when fetching recording {recording_id}")
            if hasattr(e, 'read'):
                logger.error(f"Response body: {e.read().decode('utf-8')}")
            raise
    
    def download_file(self, file_id, destination_path):
        """Download a specific file from Riverside"""
        url = f"{RIVERSIDE_API_BASE_URL}/v1/download/file/{file_id}"
        
        req = urllib.request.Request(url)
        for key, value in self.headers.items():
            req.add_header(key, value)
        
        try:
            with urllib.request.urlopen(req) as response, open(destination_path, 'wb') as out_file:
                block_size = 8192
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    out_file.write(buffer)
            return destination_path
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error: {e.code} - {e.reason} when downloading file {file_id}")
            if hasattr(e, 'read'):
                logger.error(f"Response body: {e.read().decode('utf-8')}")
            raise

def filter_recent_recordings(recordings, hours=24):
    """Filter recordings from the past specified hours"""
    recent_recordings = []
    # Create timezone-aware cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    logger.info(f"Filtering recordings created after {cutoff_time.isoformat()}")
    
    for recording in recordings:
        created_date = recording.get("created_date")
        if not created_date:
            logger.warning(f"Recording missing created_date: {recording.get('recording_id', 'unknown')}")
            continue
        
        # Try to parse the date
        try:
            # Parse date with timezone consideration
            if 'Z' in created_date:
                created_date = created_date.replace('Z', '+00:00')
                
            # Make sure we have a timezone-aware datetime
            recording_date = datetime.fromisoformat(created_date)
            if recording_date.tzinfo is None:
                # If the datetime is naive, assume it's UTC
                recording_date = recording_date.replace(tzinfo=timezone.utc)
            
            logger.debug(f"Recording date: {recording_date.isoformat()}, cutoff: {cutoff_time.isoformat()}")
            
            if recording_date >= cutoff_time:
                logger.info(f"Found recent recording: {recording.get('name')} from {created_date}")
                recent_recordings.append(recording)
            else:
                logger.debug(f"Recording too old: {recording.get('name')} from {created_date}")
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing date {created_date}: {str(e)}")
    
    return recent_recordings

def check_and_download_recording(riverside_client, recording):
    """Check if recording needs to be downloaded and process it if needed"""
    recording_id = recording.get("recording_id")
    
    if not recording_id:
        logger.error("Recording object missing recording_id")
        return False
    
    # First check if we've already processed this recording
    try:
        response = table.get_item(Key={"recording_id": recording_id})
        if "Item" in response:
            logger.info(f"Recording {recording_id} already processed")
            return False
    except ClientError as e:
        logger.error(f"Error checking DynamoDB: {str(e)}")
        raise
    
    # Check if recording status is ready for download
    # From API sample, we see that Riverside uses "stopped" for completed recordings
    if recording.get("status") != "stopped":
        logger.info(f"Recording {recording_id} is not ready yet. Status: {recording.get('status')}")
        return False
    
    # Check if all tracks have a "done" status before proceeding
    all_tracks_done = True
    for track in recording.get("tracks", []):
        if track.get("status") != "done":
            all_tracks_done = False
            logger.info(f"Track {track.get('id')} in recording {recording_id} is not done. Status: {track.get('status')}")
            break
    
    if not all_tracks_done:
        return False
    
    # Download media files (mp3 and video) from each track
    s3_file_paths = []
    creation_date = recording.get("created_date")
    recording_name = recording.get("name") or f"Recording-{recording_id}"  # Handle empty names
    
    # Log the structure of the recording to help debug
    logger.debug(f"Processing recording: {recording_name} with {len(recording.get('tracks', []))} tracks")
    
    for track in recording.get("tracks", []):
        track_id = track.get("id", "unknown-track")
        track_type = track.get("type", "unknown-type")
        logger.debug(f"Processing track: {track_id} of type {track_type}")
        
        for file in track.get("files", []):
            file_type = file.get("type")
            
            # Download all audio and video types
            # Audio types: compressed_audio, raw_audio
            # Video types: raw_video, aligned_video, cloud_recording
            if file_type in ["compressed_audio", "raw_audio", "raw_video", "aligned_video", "cloud_recording"]:
                download_url = file.get("download_url", "")
                if not download_url:
                    logger.warning(f"Missing download URL for file in recording {recording_id}")
                    continue
                    
                file_id = download_url.split("/")[-1]
                
                # Determine the file extension based on file type
                file_extension = "mp3"  # Default
                if file_type == "raw_audio":
                    file_extension = "wav"
                elif file_type in ["raw_video", "aligned_video", "cloud_recording"]:
                    file_extension = "mp4"
                
                # Generate a file name using recording and track info
                safe_name = recording_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                file_name = f"{safe_name}_{track_type}_{file_type}.{file_extension}"
                
                try:
                    # Download to /tmp (Lambda's writable directory)
                    local_path = f"/tmp/{file_name}"
                    logger.info(f"Downloading {file_type} for track {track_id} to {local_path}")
                    riverside_client.download_file(file_id, local_path)
                    
                    # Upload to S3
                    s3_key = f"{recording_id}/{file_name}"
                    logger.info(f"Uploading to S3: {s3_key}")
                    s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
                    
                    # Clean up local file
                    os.remove(local_path)
                    
                    s3_file_paths.append(f"s3://{S3_BUCKET_NAME}/{s3_key}")
                    logger.info(f"Successfully processed file {file_type} for track {track_id}")
                except Exception as e:
                    logger.error(f"Error processing file {file_type} for track {track_id}: {str(e)}")
                    # Continue with other files
    
    # Record in DynamoDB
    item = {
        "recording_id": recording_id,
        "name": recording_name,
        "status": "downloaded",
        "created_date": creation_date,
        "processed_date": datetime.now(timezone.utc).isoformat(),
        "s3_paths": s3_file_paths,
        "studio_id": STUDIO_ID,
        "project_id": recording.get("project_id"),
        "project_name": recording.get("project_name")
    }
    
    table.put_item(Item=item)
    logger.info(f"Successfully processed recording {recording_id}")
    
    return True

@logger.inject_lambda_context
@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    riverside_client = RiversideClient(API_KEY)
    
    try:
        # Get all recordings for the specified studio
        logger.info(f"Fetching all recordings for studio {STUDIO_ID}")
        all_recordings = riverside_client.get_all_studio_recordings(STUDIO_ID)
        
        # Filter recent recordings - using 24 hours for wider testing window
        recent_recordings = filter_recent_recordings(all_recordings, hours=24)
        logger.info(f"Found {len(recent_recordings)} recordings from the past 24 hours")
        
        # Process each recording
        processed_count = 0
        for recording in recent_recordings:
            try:
                if check_and_download_recording(riverside_client, recording):
                    processed_count += 1
            except Exception as e:
                logger.error(f"Error processing recording {recording.get('recording_id')}: {str(e)}")
                # Continue with other recordings instead of failing the entire function
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully processed {processed_count} recordings",
                "totalRecordings": len(all_recordings),
                "recentRecordings": len(recent_recordings)
            })
        }
    except Exception as e:
        logger.exception("Error processing Riverside recordings")
        raise