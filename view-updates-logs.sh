#!/bin/bash
# Script to view CloudWatch logs for the Updates API Lambda

LOG_GROUP="/aws/lambda/medialake-updates-api-prd"
REGION="us-east-1"

echo "Viewing logs for: $LOG_GROUP"
echo "Region: $REGION"
echo "================================"
echo ""

# Tail the logs in real-time
aws logs tail "$LOG_GROUP" \
    --region "$REGION" \
    --follow \
    --format short \
    --filter-pattern "DEBUG|Authorization|Access"

# Alternative: View recent logs without following
# aws logs tail "$LOG_GROUP" --region "$REGION" --since 5m --format short
