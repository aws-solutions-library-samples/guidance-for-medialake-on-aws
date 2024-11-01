#!/bin/bash

# Variables
DYNAMODB_TABLE_NAME="medialake_connector_table_Connectors"
JSON_FOLDER_PATH="connectors"

# Iterate over each JSON file in the specified folder
for file in "$JSON_FOLDER_PATH"/*.json; do
  if [ -f "$file" ]; then
    echo "Processing $file..."
    
    # Use AWS CLI to put the item into DynamoDB
    aws --profile 881490120934 dynamodb put-item \
      --table-name "$DYNAMODB_TABLE_NAME" \
      --item file://"$file" \
      --return-consumed-capacity TOTAL
  else
    echo "No JSON files found in the directory."
  fi
done