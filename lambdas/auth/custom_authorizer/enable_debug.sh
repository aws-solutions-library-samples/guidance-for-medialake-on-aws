#!/bin/bash

# Script to enable debugging for MediaLake Custom Authorizer
# This script helps you set environment variables for enhanced logging

echo "🔧 MediaLake Custom Authorizer Debug Configuration"
echo "=================================================="
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed or not in PATH"
    echo "Please install AWS CLI first: https://aws.amazon.com/cli/"
    exit 1
fi

# Function to get Lambda function name
get_lambda_name() {
    local function_name=""

    # Try to get from environment or ask user
    if [ -n "$LAMBDA_FUNCTION_NAME" ]; then
        function_name=$LAMBDA_FUNCTION_NAME
    else
        echo "Enter your Lambda function name (or set LAMBDA_FUNCTION_NAME environment variable):"
        read -r function_name
    fi

    echo "$function_name"
}

# Function to get AWS region
get_aws_region() {
    local region=""

    # Try to get from environment or AWS config
    if [ -n "$AWS_DEFAULT_REGION" ]; then
        region=$AWS_DEFAULT_REGION
    elif [ -n "$AWS_REGION" ]; then
        region=$AWS_REGION
    else
        # Try to get from AWS config
        region=$(aws configure get region 2>/dev/null)
        if [ -z "$region" ]; then
            echo "Enter your AWS region (e.g., us-east-1):"
            read -r region
        fi
    fi

    echo "$region"
}

# Main script
echo "This script will help you enable debugging for your Custom Authorizer Lambda function."
echo ""

# Get Lambda function name
LAMBDA_NAME=$(get_lambda_name)
if [ -z "$LAMBDA_NAME" ]; then
    echo "❌ Lambda function name is required"
    exit 1
fi

# Get AWS region
AWS_REGION=$(get_aws_region)
if [ -z "$AWS_REGION" ]; then
    echo "❌ AWS region is required"
    exit 1
fi

echo ""
echo "📋 Configuration Summary:"
echo "   - Lambda Function: $LAMBDA_NAME"
echo "   - AWS Region: $AWS_REGION"
echo ""

# Check if Lambda function exists
echo "🔍 Checking if Lambda function exists..."
if ! aws lambda get-function --function-name "$LAMBDA_NAME" --region "$AWS_REGION" &>/dev/null; then
    echo "❌ Lambda function '$LAMBDA_NAME' not found in region '$AWS_REGION'"
    echo "Please check the function name and region"
    exit 1
fi

echo "✅ Lambda function found!"

# Get current configuration
echo ""
echo "📊 Current Lambda Configuration:"
aws lambda get-function-configuration --function-name "$LAMBDA_NAME" --region "$AWS_REGION" --query 'Environment.Variables' --output table

echo ""
echo "🔧 Enabling Debug Mode..."

# Update Lambda environment variables
aws lambda update-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --region "$AWS_REGION" \
    --environment "Variables={DEBUG_MODE=true,ENABLE_JWT_DEBUG=true,ENABLE_AVP_DEBUG=true,ENABLE_API_KEY_DEBUG=true,ENABLE_PERMISSION_DEBUG=true}" \
    --output table

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Debug mode enabled successfully!"
    echo ""
    echo "🔍 Debug Features Enabled:"
    echo "   - DEBUG_MODE=true: General debug logging"
    echo "   - ENABLE_JWT_DEBUG=true: JWT token validation logging"
    echo "   - ENABLE_AVP_DEBUG=true: Amazon Verified Permissions logging"
    echo "   - ENABLE_API_KEY_DEBUG=true: API key validation logging"
    echo "   - ENABLE_PERMISSION_DEBUG=true: Permission checking logging"
    echo ""
    echo "📝 Next Steps:"
    echo "1. Test your API endpoint that was failing"
    echo "2. Check CloudWatch logs for the Lambda function"
    echo "3. Look for detailed logging with 🔍, 🔐, ⚖️, and 📋 emojis"
    echo "4. The logs will show exactly where the authorization is failing"
    echo ""
    echo "🔄 To disable debug mode later, run:"
    echo "   aws lambda update-function-configuration \\"
    echo "       --function-name '$LAMBDA_NAME' \\"
    echo "       --region '$AWS_REGION' \\"
    echo "       --environment 'Variables={DEBUG_MODE=false}'"
else
    echo "❌ Failed to enable debug mode"
    exit 1
fi
