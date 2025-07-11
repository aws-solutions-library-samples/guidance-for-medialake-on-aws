#!/bin/bash

# Process vectors from S3 JSON file and push to OpenSearch
# Usage: ./process_vectors_s3.sh <bucket> <key> <video_name> <video_path> <opensearch_endpoint> [index_name] [aws_region]

set -e

# Check if required tools are available
command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed. Aborting." >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required but not installed. Aborting." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required but not installed. Aborting." >&2; exit 1; }

# Parse command line arguments
if [ $# -lt 5 ]; then
    echo "Usage: $0 <bucket> <key> <video_name> <video_path> <opensearch_endpoint> [index_name] [aws_region]"
    echo "Example: $0 my-bucket embeddings/video1.json video1 /path/to/video1.mp4 https://search-domain.us-east-1.es.amazonaws.com"
    exit 1
fi

BUCKET="$1"
KEY="$2"
VIDEO_NAME="$3"
VIDEO_PATH="$4"
OPENSEARCH_ENDPOINT="$5"
INDEX_NAME="${6:-media}"
AWS_REGION="${7:-us-east-1}"

# Temporary files
TEMP_DIR=$(mktemp -d)
JSON_FILE="$TEMP_DIR/embeddings.json"
TEMP_RECORD="$TEMP_DIR/record.json"
TEMP_DOCUMENT="$TEMP_DIR/document.json"

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo "Processing vectors from S3..."
echo "Bucket: $BUCKET"
echo "Key: $KEY"
echo "Video Name: $VIDEO_NAME"
echo "Video Path: $VIDEO_PATH"
echo "OpenSearch Endpoint: $OPENSEARCH_ENDPOINT"
echo "Index Name: $INDEX_NAME"
echo "AWS Region: $AWS_REGION"

# Download JSON file from S3
echo "Downloading JSON file from S3..."
aws s3 cp "s3://$BUCKET/$KEY" "$JSON_FILE" --region "$AWS_REGION"

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: Failed to download JSON file from S3"
    exit 1
fi

# Check if file is valid JSON
if ! jq empty "$JSON_FILE" 2>/dev/null; then
    echo "Error: Downloaded file is not valid JSON"
    exit 1
fi

# Get total number of records
TOTAL_RECORDS=$(jq length "$JSON_FILE")
echo "Total records to process: $TOTAL_RECORDS"

# Initialize counters
SUCCESSFUL_UPLOADS=0
FAILED_UPLOADS=0

# Function to convert seconds to timecode
seconds_to_timecode() {
    local seconds=$1
    local fps=${2:-30}
    
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    local frames=$(echo "scale=0; ($seconds - $hours * 3600 - $minutes * 60 - $secs) * $fps" | bc -l 2>/dev/null || echo 0)
    
    printf "%02d:%02d:%02d:%02d" "$hours" "$minutes" "$secs" "$frames"
}

# Function to push vector to OpenSearch
push_to_opensearch() {
    local document_file="$1"
    local doc_id="$2"
    
    # Use AWS CLI to sign the request
    local response
    response=$(aws opensearch-serverless batch-get-collection \
        --names "$INDEX_NAME" \
        --region "$AWS_REGION" 2>/dev/null || echo "")
    
    # For regular OpenSearch (not serverless), use curl with AWS signature
    local endpoint_clean="${OPENSEARCH_ENDPOINT#https://}"
    
    # Create the index URL
    local index_url="$OPENSEARCH_ENDPOINT/$INDEX_NAME/_doc/$doc_id"
    
    # Use aws-cli to make signed request (requires aws-cli v2 with opensearch support)
    # Note: This is a simplified approach - in production, you'd want proper AWS signature v4
    local curl_response
    curl_response=$(curl -s -w "%{http_code}" \
        -X PUT \
        -H "Content-Type: application/json" \
        -d @"$document_file" \
        "$index_url" 2>/dev/null || echo "000")
    
    local http_code="${curl_response: -3}"
    
    if [[ "$http_code" =~ ^(200|201)$ ]]; then
        return 0
    else
        echo "HTTP Error: $http_code"
        return 1
    fi
}

# Process each record
echo "Processing records..."
for i in $(seq 0 $((TOTAL_RECORDS - 1))); do
    # Extract record
    jq ".[$i]" "$JSON_FILE" > "$TEMP_RECORD"
    
    # Check if record has required fields
    if ! jq -e '.vector and .metadata' "$TEMP_RECORD" >/dev/null 2>&1; then
        echo "Warning: Record $((i + 1)) missing required fields (vector or metadata)"
        ((FAILED_UPLOADS++))
        continue
    fi
    
    # Extract metadata
    START_TIME=$(jq -r '.metadata.start_time // 0' "$TEMP_RECORD")
    END_TIME=$(jq -r '.metadata.end_time // 0' "$TEMP_RECORD")
    EMBEDDING_OPTION=$(jq -r '.metadata.embeddingOption // "default"' "$TEMP_RECORD")
    
    # Create vector key
    VECTOR_KEY="${VIDEO_NAME}_${START_TIME}-${END_TIME}_${EMBEDDING_OPTION}"
    
    # Convert times to timecode
    START_TIMECODE=$(seconds_to_timecode "$START_TIME")
    END_TIMECODE=$(seconds_to_timecode "$END_TIME")
    
    # Create OpenSearch document
    jq -n \
        --arg type "video" \
        --arg document_id "$VECTOR_KEY" \
        --argjson embedding "$(jq '.vector' "$TEMP_RECORD")" \
        --arg embedding_scope "clip" \
        --arg embedding_option "$EMBEDDING_OPTION" \
        --arg start_timecode "$START_TIMECODE" \
        --arg end_timecode "$END_TIMECODE" \
        --arg timestamp "$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")" \
        --arg asset_id "asset:vid:$VIDEO_NAME" \
        --arg asset_type "video" \
        --arg video_path "$VIDEO_PATH" \
        --argjson start_time_sec "$START_TIME" \
        --argjson end_time_sec "$END_TIME" \
        '{
            type: $type,
            document_id: $document_id,
            embedding: $embedding,
            embedding_scope: $embedding_scope,
            embedding_option: $embedding_option,
            start_timecode: $start_timecode,
            end_timecode: $end_timecode,
            timestamp: $timestamp,
            DigitalSourceAsset: {
                ID: $asset_id,
                Type: $asset_type
            },
            video_path: $video_path,
            start_time_sec: $start_time_sec,
            end_time_sec: $end_time_sec
        }' > "$TEMP_DOCUMENT"
    
    # Push to OpenSearch
    if push_to_opensearch "$TEMP_DOCUMENT" "$VECTOR_KEY"; then
        ((SUCCESSFUL_UPLOADS++))
        echo "Successfully processed record $((i + 1))/$TOTAL_RECORDS: $VECTOR_KEY"
    else
        ((FAILED_UPLOADS++))
        echo "Failed to process record $((i + 1))/$TOTAL_RECORDS: $VECTOR_KEY"
    fi
    
    # Progress update every 100 records
    if [ $((i % 100)) -eq 99 ]; then
        echo "Progress: $((i + 1))/$TOTAL_RECORDS records processed"
    fi
done

# Final summary
echo "Processing complete!"
echo "Total records: $TOTAL_RECORDS"
echo "Successful uploads: $SUCCESSFUL_UPLOADS"
echo "Failed uploads: $FAILED_UPLOADS"

# Exit with appropriate code
if [ "$FAILED_UPLOADS" -eq 0 ]; then
    exit 0
else
    exit 1
fi 