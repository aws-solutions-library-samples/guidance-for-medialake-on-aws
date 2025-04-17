#!/bin/bash

# Script to delete all entries in a DynamoDB table
# Usage: ./delete_dynamodb_entries.sh <aws-profile> <table-name> [region]

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <aws-profile> <table-name> [region]"
    echo "Example: $0 dev-profile my-table us-east-1"
    exit 1
fi

AWS_PROFILE=$1
TABLE_NAME=$2
REGION=${3:-"us-east-1"}  # Default to us-east-1 if region not provided

echo "WARNING: This will delete ALL items from the table '$TABLE_NAME' using profile '$AWS_PROFILE'"
echo "Are you sure you want to continue? (y/n)"
read -r confirmation

if [[ ! "$confirmation" =~ ^[yY]$ ]]; then
    echo "Operation cancelled"
    exit 0
fi

# Get the primary key information
echo "Retrieving table information..."
KEY_SCHEMA=$(aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --profile "$AWS_PROFILE" \
    --region "$REGION" \
    --query "Table.KeySchema" \
    --output json)

# Extract the hash key and range key (if exists)
HASH_KEY=$(echo "$KEY_SCHEMA" | jq -r '.[] | select(.KeyType == "HASH") | .AttributeName')
RANGE_KEY=$(echo "$KEY_SCHEMA" | jq -r '.[] | select(.KeyType == "RANGE") | .AttributeName')

echo "Hash key: $HASH_KEY"
if [ -n "$RANGE_KEY" ]; then
    echo "Range key: $RANGE_KEY"
fi

# Scan for all items and delete them in batches
echo "Scanning items..."
ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --attributes-to-get "$HASH_KEY" ${RANGE_KEY:+"$RANGE_KEY"} \
    --profile "$AWS_PROFILE" \
    --region "$REGION" \
    --query "Items" \
    --output json)

ITEM_COUNT=$(echo "$ITEMS" | jq 'length')
echo "Found $ITEM_COUNT items to delete"

if [ "$ITEM_COUNT" -eq 0 ]; then
    echo "No items to delete"
    exit 0
fi

echo "Starting deletion process..."
COUNTER=0
echo "$ITEMS" | jq -c '.[]' | while read -r item; do
    DELETE_REQUEST="{\"DeleteRequest\": {\"Key\": $item}}"
    
    BATCH_FILE=$(mktemp)
    echo "{\"$TABLE_NAME\": [$DELETE_REQUEST]}" > "$BATCH_FILE"
    
    aws dynamodb batch-write-item \
        --request-items file://"$BATCH_FILE" \
        --profile "$AWS_PROFILE" \
        --region "$REGION" > /dev/null
    
    rm "$BATCH_FILE"
    
    COUNTER=$((COUNTER + 1))
    if [ $((COUNTER % 10)) -eq 0 ]; then
        echo "Deleted $COUNTER items..."
    fi
done

echo "Successfully deleted all $ITEM_COUNT items from table '$TABLE_NAME'" 