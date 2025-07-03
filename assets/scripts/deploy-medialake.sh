#!/bin/bash

# Default values
AWS_PROFILE=""
AWS_REGION=""
STACK_PREFIX="medialake"
STACK_NAME="medialake-cf"  # Fixed stack name for creation
S3_PRESIGNED_URL=""
DEPLOY_TEMPLATE=false
REDEPLOY=false
DELETE_ONLY=false
S3_UPLOAD_PROFILE="medialake-demo"
S3_BUCKET="medialake-releases"
CURRENT_DATE_TIME=$(date "+%m-%d-%y-%H%M")
USERNAME=$(whoami)
REPO_DIR=""  # Will be set dynamically in generate_s3_key()
GIT_BRANCH="main"
SLACK_WEBHOOK_URL="https://hooks.slack.com/triggers/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"

# MediaLake specific parameters
INITIAL_USER_EMAIL="mne-medialake@amazon.com"
INITIAL_USER_FIRST_NAME="Media"
INITIAL_USER_LAST_NAME="Lake"
MEDIALAKE_ENVIRONMENT_NAME="dev"
OPENSEARCH_DEPLOYMENT_SIZE="small"

# Function to send Slack notification
send_slack_notification() {
    local username="$1"
    local action="$2"
    local branch="$3"
    local region="$4"
    local status="$5"
    local environment="$6"
    
    local payload=$(cat <<EOF
{
  "username": "$username",
  "action": "$action", 
  "branch": "$branch",
  "region": "$region",
  "status": "$status",
  "environment": "$environment"
}
EOF
)
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$SLACK_WEBHOOK_URL" \
        --silent --show-error
    
    if [ $? -eq 0 ]; then
        echo "Slack notification sent: $action - $status"
    else
        echo "Warning: Failed to send Slack notification"
    fi
}

# Function to sanitize string for S3 naming conventions
sanitize_for_s3() {
    local input="$1"
    # Convert to lowercase, replace invalid characters with hyphens, remove consecutive hyphens
    echo "$input" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g'
}

# Generate S3 key and unique repo directory after GIT_BRANCH is potentially updated by command line args
generate_s3_key() {
    local sanitized_username=$(sanitize_for_s3 "$USERNAME")
    local sanitized_branch=$(sanitize_for_s3 "$GIT_BRANCH")
    local sanitized_date=$(sanitize_for_s3 "$CURRENT_DATE_TIME")
    S3_KEY="ml-${sanitized_username}-${sanitized_branch}-${sanitized_date}.zip"
    # Create unique repo directory to avoid conflicts with concurrent deployments
    REPO_DIR="media-lake-v2-${sanitized_username}-${sanitized_branch}-${sanitized_date}-$$"
}

# Function to clean up temporary files and directories
cleanup_temp_files() {
    echo "Performing cleanup of temporary files and directories..."
    
    # Clean up the unique repo directory if it exists
    if [ -n "$REPO_DIR" ] && [ -d "$REPO_DIR" ]; then
        echo "Removing repository directory: $REPO_DIR"
        rm -rf "$REPO_DIR"
    fi
    
    # Clean up the zip file if it exists
    if [ -n "$S3_KEY" ] && [ -f "$S3_KEY" ]; then
        echo "Removing zip file: $S3_KEY"
        rm -f "$S3_KEY"
    fi
    
    # Clean up any old static directory from previous runs
    if [ -d "media-lake-v2" ]; then
        echo "Removing old static repository directory: media-lake-v2"
        rm -rf "media-lake-v2"
    fi
    
    # Clean up any leftover zip files from this session
    if [ -n "$USERNAME" ] && [ -n "$GIT_BRANCH" ]; then
        local sanitized_username=$(sanitize_for_s3 "$USERNAME")
        local sanitized_branch=$(sanitize_for_s3 "$GIT_BRANCH")
        local pattern="ml-${sanitized_username}-${sanitized_branch}-*.zip"
        
        # Find and remove any matching zip files
        local zip_files=$(find . -maxdepth 1 -name "$pattern" 2>/dev/null)
        if [ -n "$zip_files" ]; then
            echo "Removing leftover zip files matching pattern: $pattern"
            find . -maxdepth 1 -name "$pattern" -delete 2>/dev/null
        fi
        
        # Find and remove any matching repo directories
        local repo_pattern="media-lake-v2-${sanitized_username}-${sanitized_branch}-*"
        local repo_dirs=$(find . -maxdepth 1 -type d -name "$repo_pattern" 2>/dev/null)
        if [ -n "$repo_dirs" ]; then
            echo "Removing leftover repository directories matching pattern: $repo_pattern"
            find . -maxdepth 1 -type d -name "$repo_pattern" -exec rm -rf {} \; 2>/dev/null
        fi
    fi
    
    echo "Cleanup completed."
}

# Set up trap to ensure cleanup on script exit or interruption
trap cleanup_temp_files EXIT INT TERM

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      AWS_PROFILE="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --stack-name)
      STACK_PREFIX="$2"
      # Keep STACK_NAME fixed as "medialake-cf"
      shift 2
      ;;
    --presigned-url)
      S3_PRESIGNED_URL="$2"
      DEPLOY_TEMPLATE=true
      shift 2
      ;;
    --deploy)
      DEPLOY_TEMPLATE=true
      shift
      ;;
    --redeploy)
      REDEPLOY=true
      DEPLOY_TEMPLATE=true
      shift
      ;;
    --delete)
      DELETE_ONLY=true
      shift
      ;;
    --branch)
      GIT_BRANCH="$2"
      shift 2
      ;;
    --user-email)
      INITIAL_USER_EMAIL="$2"
      shift 2
      ;;
    --user-first-name)
      INITIAL_USER_FIRST_NAME="$2"
      shift 2
      ;;
    --user-last-name)
      INITIAL_USER_LAST_NAME="$2"
      shift 2
      ;;
    --environment)
      MEDIALAKE_ENVIRONMENT_NAME="$2"
      shift 2
      ;;
    --opensearch-size)
      OPENSEARCH_DEPLOYMENT_SIZE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 --profile <aws-profile> --region <aws-region> [--stack-name <stack-prefix>] [--presigned-url <s3-url>] [--deploy] [--redeploy] [--delete] [--branch <git-branch>] [--user-email <email>] [--user-first-name <name>] [--user-last-name <name>] [--environment <env>] [--opensearch-size <small|medium|large>]"
      exit 1
      ;;
  esac
done

# Validate required parameters
if [ -z "$AWS_PROFILE" ] || [ -z "$AWS_REGION" ]; then
    echo "Error: AWS profile and region are required"
    echo "Usage: $0 --profile <aws-profile> --region <aws-region> [--stack-name <stack-prefix>] [--presigned-url <s3-url>] [--deploy] [--redeploy] [--delete] [--branch <git-branch>] [--user-email <email>] [--user-first-name <name>] [--user-last-name <name>] [--environment <env>] [--opensearch-size <small|medium|large>]"
    exit 1
fi

# Validate OpenSearch deployment size
if [[ ! "$OPENSEARCH_DEPLOYMENT_SIZE" =~ ^(small|medium|large)$ ]]; then
    echo "Error: OpenSearch deployment size must be one of: small, medium, large"
    echo "Current value: $OPENSEARCH_DEPLOYMENT_SIZE"
    exit 1
fi

# Validate MediaLake environment name (alphanumeric only, max 10 chars)
if [[ ! "$MEDIALAKE_ENVIRONMENT_NAME" =~ ^[a-zA-Z0-9]{1,10}$ ]]; then
    echo "Error: MediaLake environment name must be alphanumeric and 1-10 characters long"
    echo "Current value: $MEDIALAKE_ENVIRONMENT_NAME"
    exit 1
fi

# Validate email format
if [[ ! "$INITIAL_USER_EMAIL" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; then
    echo "Error: Initial user email must be a valid email address"
    echo "Current value: $INITIAL_USER_EMAIL"
    exit 1
fi

# Generate S3 key now that all parameters are parsed
generate_s3_key
echo "Using S3 key: $S3_KEY"

# Display configuration summary
echo "=== MediaLake Deployment Configuration ==="
echo "AWS Profile: $AWS_PROFILE"
echo "AWS Region: $AWS_REGION"
echo "Stack Prefix: $STACK_PREFIX"
echo "Git Branch: $GIT_BRANCH"
echo "Initial User Email: $INITIAL_USER_EMAIL"
echo "Initial User Name: $INITIAL_USER_FIRST_NAME $INITIAL_USER_LAST_NAME"
echo "Environment Name: $MEDIALAKE_ENVIRONMENT_NAME"
echo "OpenSearch Size: $OPENSEARCH_DEPLOYMENT_SIZE"
echo "=========================================="

# Clean up any leftover files from previous runs at the start
cleanup_temp_files

# Determine the action for notifications
ACTION=""
if [ "$DELETE_ONLY" = true ]; then
    ACTION="delete"
elif [ "$REDEPLOY" = true ]; then
    ACTION="redeploy"
elif [ "$DEPLOY_TEMPLATE" = true ]; then
    ACTION="deploy"
fi

# Function to list all matching stacks using grep for case-insensitive matching
list_stacks() {
    local region=$1
    # Get all stacks excluding DELETE_COMPLETE and filter case-insensitively for the prefix
    aws cloudformation list-stacks \
        --profile $AWS_PROFILE \
        --region $region \
        --stack-status-filter CREATE_COMPLETE CREATE_FAILED CREATE_IN_PROGRESS REVIEW_IN_PROGRESS ROLLBACK_COMPLETE ROLLBACK_FAILED ROLLBACK_IN_PROGRESS UPDATE_COMPLETE UPDATE_COMPLETE_CLEANUP_IN_PROGRESS UPDATE_IN_PROGRESS UPDATE_ROLLBACK_COMPLETE UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS UPDATE_ROLLBACK_FAILED UPDATE_ROLLBACK_IN_PROGRESS DELETE_FAILED \
        --query "StackSummaries[].StackName" \
        --output text | tr '\t' '\n' | grep -i "$STACK_PREFIX"
}

# Function to check if any matching stacks are being deleted
any_deleting() {
    local region=$1
    local deleting_stacks=$(aws cloudformation list-stacks \
        --profile $AWS_PROFILE \
        --region $region \
        --stack-status-filter DELETE_IN_PROGRESS \
        --query "StackSummaries[].StackName" \
        --output text | tr '\t' '\n' | grep -i "$STACK_PREFIX")
    
    if [ -z "$deleting_stacks" ]; then
        return 1
    else
        echo "Stacks currently being deleted in $region: $deleting_stacks"
        return 0
    fi
}

# Function to delete stacks in a specific region
delete_stacks_in_region() {
    local region=$1
    echo "Starting stack destruction in region $region using profile $AWS_PROFILE"
    echo "Will delete all stacks containing (case-insensitive): '$STACK_PREFIX'"
    
    # Main loop to delete stacks
    while true; do
        stacks=$(list_stacks "$region")
        
        if [ -z "$stacks" ]; then
            echo "No more stacks containing '$STACK_PREFIX' found in region $region. Destruction complete!"
            break
        fi
        
        echo "Found stacks in $region: $stacks"
        
        # Check if any stack is already being deleted
        if any_deleting "$region"; then
            echo "Waiting for in-progress deletions to complete in $region..."
        else
            # Attempt to delete each stack
            for stack in $stacks; do
                echo "Attempting to delete stack: $stack in region $region"
                
                # Check if stack is in DELETE_FAILED state and try with retain resources
                stack_status=$(aws cloudformation describe-stacks --stack-name "$stack" --region "$region" --profile "$AWS_PROFILE" --query "Stacks[0].StackStatus" --output text 2>/dev/null)
                
                if [ "$stack_status" == "DELETE_FAILED" ]; then
                    echo "Stack $stack is in DELETE_FAILED state. Attempting to get resources that failed to delete..."
                    
                    # Get resources that might have failed to delete
                    resources=$(aws cloudformation list-stack-resources --stack-name "$stack" --region "$region" --profile "$AWS_PROFILE" --query "StackResourceSummaries[?ResourceStatus=='DELETE_FAILED'].LogicalResourceId" --output text)
                    
                    if [ -n "$resources" ]; then
                        echo "Found resources that failed to delete: $resources"
                        echo "Attempting to delete stack with --retain-resources option"
                        aws cloudformation delete-stack \
                            --profile $AWS_PROFILE \
                            --region $region \
                            --stack-name $stack \
                            --retain-resources $resources
                    else
                        # Standard delete attempt
                        aws cloudformation delete-stack \
                            --profile $AWS_PROFILE \
                            --region $region \
                            --stack-name $stack
                    fi
                else
                    # Standard delete attempt
                    aws cloudformation delete-stack \
                        --profile $AWS_PROFILE \
                        --region $region \
                        --stack-name $stack
                fi
                
                # Break after initiating one deletion to handle dependencies
                break
            done
        fi
        
        echo "Waiting 60 seconds before checking again in $region..."
        sleep 60
    done
}

# Function to create and upload zip file to S3 and return presigned URL
create_and_upload_zip() {
    # Store current directory
    local current_dir=$(pwd)
    
    # Clean up any existing files from previous runs
    cleanup_temp_files
    
    echo "Cloning repository (branch: $GIT_BRANCH)..."
    git clone -b "$GIT_BRANCH" git@ssh.gitlab.aws.dev:aws-mne-msc/media-lake-v2.git "$REPO_DIR"
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to clone repository on branch $GIT_BRANCH"
        return 1
    fi
    
    # Navigate to the repository directory
    cd "$REPO_DIR"
    
    echo "Creating zip archive..."
    zip -r9 "../$S3_KEY" ./ -x ./.envrc -x ./.git/\* -x ./.venv/\* -x ./__pycache__/\* -x ./cdk.out/\* -x ./dist/\* -x ./node_modules/\* -x ./medialake_user_interface/dist/\* -x ./medialake_user_interface/node_modules/\* -x ./config.json -x ./cdk.context.json -x ./package-lock.json -x ./lambdas/nodes/image_metadata_extractor/node_modules/\*
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create zip archive"
        cd "$current_dir"
        cleanup_temp_files
        return 1
    fi
    
    # Return to original directory
    cd "$current_dir"
    
    echo "Uploading zip to S3..."
    aws s3 cp "$S3_KEY" s3://$S3_BUCKET/$S3_KEY --profile $S3_UPLOAD_PROFILE
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to upload zip to S3"
        cleanup_temp_files
        return 1
    fi
    
    echo "Generating presigned URL..."
    S3_PRESIGNED_URL=$(aws s3 presign s3://$S3_BUCKET/$S3_KEY --expires-in 86400 --profile $S3_UPLOAD_PROFILE)
    
    if [ $? -ne 0 ] || [ -z "$S3_PRESIGNED_URL" ]; then
        echo "Error: Failed to generate presigned URL"
        cleanup_temp_files
        return 1
    fi
    
    echo "Cleaning up temporary files after successful upload..."
    cleanup_temp_files
    
    echo "Presigned URL generated successfully"
    return 0
}

# Function to monitor CodePipeline status
monitor_pipeline() {
    local pipeline_name="${1:-MediaLakeCDKPipeline}"  # Accept pipeline name as parameter, default to MediaLakeCDKPipeline
    local max_wait_time=7200  # 2 hour max wait time
    local elapsed_time=0
    
    echo "Monitoring CodePipeline: $pipeline_name"
    echo "This may take several minutes to complete..."
    
    while [ $elapsed_time -lt $max_wait_time ]; do
        # Get pipeline execution status
        local execution_status=$(aws codepipeline list-pipeline-executions \
            --pipeline-name "$pipeline_name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --max-items 1 \
            --query "pipelineExecutionSummaries[0].status" \
            --output text 2>/dev/null | tr -d '\n\r' | sed 's/None//g' | xargs)
        
        if [ $? -ne 0 ] || [ "$execution_status" == "None" ] || [ -z "$execution_status" ] || [ "$execution_status" == "null" ]; then
            echo "Pipeline $pipeline_name not found or no executions yet. Waiting..."
        else
            echo "Pipeline Status: $execution_status ($(date '+%H:%M:%S'))"
            
            case "$execution_status" in
                "Succeeded")
                    echo "✅ Pipeline completed successfully!"
                    if [ "$REDEPLOY" = true ]; then
                        send_slack_notification "$USERNAME" "redeploy" "$GIT_BRANCH" "$AWS_REGION" "pipeline-completed" "$AWS_PROFILE"
                    else
                        send_slack_notification "$USERNAME" "deploy" "$GIT_BRANCH" "$AWS_REGION" "pipeline-completed" "$AWS_PROFILE"
                    fi
                    return 0
                    ;;
                "Failed")
                    echo "❌ Pipeline failed!"
                    echo "Deployment has failed. Exiting..."
                    send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "pipeline-failed" "$AWS_PROFILE"
                    return 1
                    ;;
                "Stopped")
                    echo "⏹️ Pipeline was stopped!"
                    echo "Pipeline execution was stopped. Exiting..."
                    send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "pipeline-stopped" "$AWS_PROFILE"
                    return 1
                    ;;
                "Stopping")
                    echo "⏸️ Pipeline is stopping..."
                    echo "Pipeline is in the process of stopping. Will exit when stopped."
                    ;;
                "InProgress"|"IN_PROGRESS"|"In_Progress")
                    echo "🔄 Pipeline is running..."
                    ;;
                "Superseded")
                    echo "🔄 Pipeline was superseded by a newer execution..."
                    echo "Pipeline execution was superseded. Exiting..."
                    send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "pipeline-superseded" "$AWS_PROFILE"
                    return 1
                    ;;
                *)
                    # Check if it's any variation of failure status
                    if [[ "$execution_status" == *"FAILED"* ]] || [[ "$execution_status" == *"Failed"* ]] || [[ "$execution_status" == *"failed"* ]]; then
                        echo "❌ Pipeline appears to have failed (status: $execution_status)"
                        echo "Deployment has failed. Exiting..."
                        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "pipeline-failed" "$AWS_PROFILE"
                        return 1
                    # Check if it's any variation of in-progress status
                    elif [[ "$execution_status" == *"PROGRESS"* ]] || [[ "$execution_status" == *"Progress"* ]] || [[ "$execution_status" == *"progress"* ]] || [[ "$execution_status" == *"RUNNING"* ]] || [[ "$execution_status" == *"Running"* ]] || [[ "$execution_status" == *"InProgress"* ]]; then
                        echo "🔄 Pipeline appears to be running (status: $execution_status)"
                    else
                        echo "⚠️ Unknown pipeline status: $execution_status"
                    fi
                    ;;
            esac
        fi
        
        sleep 60
        elapsed_time=$((elapsed_time + 60))
    done
    
    echo "⏰ Pipeline monitoring timed out after 2 hours"
    echo "Deployment monitoring timed out. Exiting..."
    send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "pipeline-timeout" "$AWS_PROFILE"
    return 1
}

# Function to check if CodePipeline exists and return the found pipeline name
check_pipeline_exists() {
    local pipeline_names=("MediaLakeCDKPipeline" "CDKDeploymentPipeline")
    
    for pipeline_name in "${pipeline_names[@]}"; do
        if aws codepipeline get-pipeline \
            --name "$pipeline_name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query "pipeline.name" \
            --output text >/dev/null 2>&1; then
            echo "$pipeline_name"
            return 0
        fi
    done
    
    return 1
}

# Function to check if CodeBuild project exists and return the found project name
check_codebuild_exists() {
    local pipeline_name="${1:-MediaLakeCDKPipeline}"  # Accept pipeline name as parameter
    local project_names=("${pipeline_name}-DownloadSource")
    
    # If no specific pipeline provided, check both possible names
    if [ -z "$1" ]; then
        project_names=("MediaLakeCDKPipeline-DownloadSource" "CDKDeploymentPipeline-DownloadSource")
    fi
    
    for project_name in "${project_names[@]}"; do
        if aws codebuild batch-get-projects \
            --names "$project_name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query "projects[0].name" \
            --output text >/dev/null 2>&1; then
            echo "$project_name"
            return 0
        fi
    done
    
    return 1
}

# Function to update CodeBuild project with new pre-signed URL
update_codebuild_project() {
    local project_name="$1"
    local new_presigned_url="$2"
    
    echo "Updating CodeBuild project: $project_name"
    echo "New pre-signed URL: $new_presigned_url"
    
    # Get current project configuration
    local project_json=$(aws codebuild batch-get-projects \
        --names "$project_name" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "projects[0]" \
        --output json)
    
    if [ $? -ne 0 ] || [ -z "$project_json" ] || [ "$project_json" == "null" ]; then
        echo "Error: Failed to get CodeBuild project configuration"
        return 1
    fi
    
    # Extract current buildspec and update the curl command
    local current_buildspec=$(echo "$project_json" | jq -r .source.buildspec)
    
    if [ "$current_buildspec" == "null" ] || [ -z "$current_buildspec" ]; then
        echo "Error: No buildspec found in CodeBuild project"
        return 1
    fi
    
    echo "Current buildspec (first 200 chars):"
    echo "$current_buildspec" | head -c 200
    echo "..."
    
    # Write buildspec to temporary file to avoid string literal issues
    local temp_buildspec_file="/tmp/current_buildspec.txt"
    echo "$current_buildspec" > "$temp_buildspec_file"
    
    # Use Python to safely replace the entire curl command line in the buildspec
    local updated_buildspec=$(python3 -c "
import sys
import re

# Read buildspec from file
with open('$temp_buildspec_file', 'r') as f:
    buildspec = f.read()

new_url = '''$new_presigned_url'''

# Clean curl command to replace with
clean_curl_command = f'curl -L \"{new_url}\" -o source-code.zip'

# First, try to find a clean curl pattern and replace it
pattern1 = r'curl -L \"[^\"]*\" -o source-code\.zip'
if re.search(pattern1, buildspec):
    updated_buildspec = re.sub(pattern1, clean_curl_command, buildspec, count=1)
else:
    # If the buildspec is corrupted, look for any line starting with curl and containing URLs
    # This handles corrupted buildspecs with concatenated curl commands
    lines = buildspec.split('\n')
    updated_lines = []
    curl_replaced = False
    
    for line in lines:
        # Look for lines that start with spaces and contain 'curl -L'
        if re.match(r'\s*-\s*curl -L', line.strip()) or (re.match(r'\s+curl -L', line) and not curl_replaced):
            # Replace the entire corrupted curl line with a clean one
            # Preserve the indentation
            indent_match = re.match(r'(\s*)', line)
            indent = indent_match.group(1) if indent_match else '      '
            if line.strip().startswith('-'):
                updated_lines.append(f'{indent}- {clean_curl_command}')
            else:
                updated_lines.append(f'{indent}{clean_curl_command}')
            curl_replaced = True
        else:
            updated_lines.append(line)
    
    updated_buildspec = '\n'.join(updated_lines)

print(updated_buildspec, end='')
")
    
    # Clean up temporary file
    rm -f "$temp_buildspec_file"
    
    if [ $? -ne 0 ] || [ -z "$updated_buildspec" ]; then
        echo "Error: Failed to update buildspec using Python"
        return 1
    fi
    
    echo "Updated buildspec (first 200 chars):"
    echo "$updated_buildspec" | head -c 200
    echo "..."
    
    # Create updated project configuration with only allowed fields for update-project
    local updated_project=$(echo "$project_json" | jq --arg buildspec "$updated_buildspec" '
    {
        name: .name,
        description: .description,
        source: (.source | .buildspec = $buildspec),
        secondarySources: .secondarySources,
        sourceVersion: .sourceVersion,
        secondarySourceVersions: .secondarySourceVersions,
        artifacts: .artifacts,
        secondaryArtifacts: .secondaryArtifacts,
        cache: .cache,
        environment: .environment,
        serviceRole: .serviceRole,
        timeoutInMinutes: .timeoutInMinutes,
        queuedTimeoutInMinutes: .queuedTimeoutInMinutes,
        encryptionKey: .encryptionKey,
        tags: .tags,
        vpcConfig: .vpcConfig,
        badgeEnabled: .badgeEnabled,
        logsConfig: .logsConfig,
        fileSystemLocations: .fileSystemLocations,
        buildBatchConfig: .buildBatchConfig,
        concurrentBuildLimit: .concurrentBuildLimit,
        autoRetryLimit: .autoRetryLimit
    }
    | with_entries(select(.value != null))
    ')
    
    # Update the project
    aws codebuild update-project \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --cli-input-json "$updated_project" >/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ CodeBuild project updated successfully"
        return 0
    else
        echo "❌ Failed to update CodeBuild project"
        echo "Debug: Attempting to write updated project JSON to file for inspection..."
        echo "$updated_project" > /tmp/codebuild_update.json
        echo "Updated project JSON written to /tmp/codebuild_update.json"
        return 1
    fi
}

# Function to start pipeline execution
start_pipeline_execution() {
    local pipeline_name="${1:-MediaLakeCDKPipeline}"  # Accept pipeline name as parameter, default to MediaLakeCDKPipeline
    
    echo "Starting pipeline execution: $pipeline_name"
    
    local execution_id=$(aws codepipeline start-pipeline-execution \
        --name "$pipeline_name" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "pipelineExecutionId" \
        --output text)
    
    if [ $? -eq 0 ] && [ -n "$execution_id" ]; then
        echo "✅ Pipeline execution started successfully"
        echo "Execution ID: $execution_id"
        return 0
    else
        echo "❌ Failed to start pipeline execution"
        return 1
    fi
}

# Function to deploy using existing infrastructure
deploy_with_existing_pipeline() {
    local pipeline_name="$1"  # Accept pipeline name as parameter
    
    echo "🔄 Using existing CodePipeline infrastructure for deployment"
    echo "Found pipeline: $pipeline_name"
    
    # Check if CodeBuild project exists
    codebuild_project=$(check_codebuild_exists "$pipeline_name")
    if [ $? -ne 0 ]; then
        echo "❌ CodeBuild project '${pipeline_name}-DownloadSource' not found"
        echo "Cannot update existing pipeline. Please use --redeploy to recreate infrastructure."
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        return 1
    fi
    
    echo "Found CodeBuild project: $codebuild_project"

    # Update CodeBuild project with new pre-signed URL
    if ! update_codebuild_project "$codebuild_project" "$S3_PRESIGNED_URL"; then
        echo "❌ Failed to update CodeBuild project"
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        return 1
    fi
    
    # Start pipeline execution
    if ! start_pipeline_execution "$pipeline_name"; then
        echo "❌ Failed to start pipeline execution"
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        return 1
    fi
    
    # Monitor the pipeline
    if monitor_pipeline "$pipeline_name"; then
        echo "✅ Deployment completed successfully using existing pipeline!"
        if [ "$REDEPLOY" = true ]; then
            send_slack_notification "$USERNAME" "redeploy" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
        else
            send_slack_notification "$USERNAME" "deploy" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
        fi
        return 0
    else
        echo "❌ Pipeline execution failed or timed out"
        return 1
    fi
}

# Function to deploy using new CloudFormation stack
deploy_with_new_stack() {
    echo "🚀 Creating new CloudFormation stack for deployment"
    
    # Check if we need to clone the repo to get the template
    if [ ! -d "$REPO_DIR" ]; then
        echo "Cloning repository to get the CloudFormation template (branch: $GIT_BRANCH)..."
        git clone -b "$GIT_BRANCH" git@ssh.gitlab.aws.dev:aws-mne-msc/media-lake-v2.git "$REPO_DIR"
        
        if [ $? -ne 0 ]; then
            echo "Error: Failed to clone repository for template on branch $GIT_BRANCH"
            send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
            return 1
        fi
    fi
    
    # Find the template file - check multiple possible names
    TEMPLATE_PATH=""
    for template_name in "medialake.template" "medialake.yaml" "medialake.yml" "template.yaml" "template.yml"; do
        if [ -f "$REPO_DIR/$template_name" ]; then
            TEMPLATE_PATH="$REPO_DIR/$template_name"
            break
        fi
    done
    
    if [ -z "$TEMPLATE_PATH" ]; then
        echo "Error: CloudFormation template file not found in $REPO_DIR"
        echo "Looked for: medialake.template, medialake.yaml, medialake.yml, template.yaml, template.yml"
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        return 1
    fi
    
    echo "Deploying CloudFormation template from $TEMPLATE_PATH..."
    
    # Create new stack with provided parameters
    aws cloudformation create-stack \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --stack-name "$STACK_NAME" \
        --template-body file://$TEMPLATE_PATH \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
        --parameters \
            ParameterKey=SourceType,ParameterValue=S3PresignedURL \
            ParameterKey=S3PresignedURL,ParameterValue="$S3_PRESIGNED_URL" \
            ParameterKey=InitialUserEmail,ParameterValue="$INITIAL_USER_EMAIL" \
            ParameterKey=InitialUserFirstName,ParameterValue="$INITIAL_USER_FIRST_NAME" \
            ParameterKey=InitialUserLastName,ParameterValue="$INITIAL_USER_LAST_NAME" \
            ParameterKey=MediaLakeEnvironmentName,ParameterValue="$MEDIALAKE_ENVIRONMENT_NAME" \
            ParameterKey=OpenSearchDeploymentSize,ParameterValue="$OPENSEARCH_DEPLOYMENT_SIZE"
    
    # Check if deployment was successful
    if [ $? -eq 0 ]; then
        echo "CloudFormation stack deployment initiated successfully"
        echo "Stack name: $STACK_NAME"
        echo "Waiting for CloudFormation stack to create CodePipeline..."
        
        # Wait a bit for the stack to create the pipeline
        sleep 120
        
        # Monitor the CodePipeline - check which one was created
        created_pipeline=$(check_pipeline_exists)
        if [ $? -eq 0 ]; then
            echo "Found created pipeline: $created_pipeline"
            if monitor_pipeline "$created_pipeline"; then
                echo "✅ Deployment completed successfully!"
                if [ "$REDEPLOY" = true ]; then
                    send_slack_notification "$USERNAME" "redeploy" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
                else
                    send_slack_notification "$USERNAME" "deploy" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
                fi
                # Cleanup will be handled by the trap
                return 0
            else
                echo "❌ Pipeline monitoring failed or timed out"
                # Cleanup will be handled by the trap
                return 1
            fi
        else
            echo "❌ No pipeline found after stack creation"
            # Cleanup will be handled by the trap
            return 1
        fi
    else
        echo "CloudFormation stack deployment failed"
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        # Cleanup will be handled by the trap
        return 1
    fi
}

# Destroy stacks if needed
if [ "$REDEPLOY" = true ] || [ "$DELETE_ONLY" = true ]; then
    if [ "$DELETE_ONLY" = true ]; then
        echo "Starting stack deletion process (without redeployment)..."
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "started" "$AWS_PROFILE"
    else
        echo "Starting destruction process in both target region and us-east-1 for WAF rules..."
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "started" "$AWS_PROFILE"
    fi
    
    # First, destroy stacks in the target region
    delete_stacks_in_region "$AWS_REGION"
    
    # Then destroy stacks in us-east-1 if it's not already the target region
    if [ "$AWS_REGION" != "us-east-1" ]; then
        echo "Checking for WAF rules and other global resources in us-east-1..."
        delete_stacks_in_region "us-east-1"
    fi
    
    # Send completion notification for deletion
    if [ "$DELETE_ONLY" = true ]; then
        echo "Stack deletion completed. Exiting as requested."
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
        exit 0
    else
        echo "Stack deletion completed. Proceeding with deployment..."
        send_slack_notification "$USERNAME" "delete" "$GIT_BRANCH" "$AWS_REGION" "completed" "$AWS_PROFILE"
    fi
fi

# Generate presigned URL if needed for deployment
if [ "$DEPLOY_TEMPLATE" = true ] && [ -z "$S3_PRESIGNED_URL" ]; then
    echo "Creating and uploading code to generate presigned URL..."
    create_and_upload_zip
    
    if [ $? -ne 0 ]; then
        echo "Failed to prepare deployment package"
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "failed" "$AWS_PROFILE"
        exit 1
    fi
fi

# Deploy CloudFormation template if requested
if [ "$DEPLOY_TEMPLATE" = true ]; then
    # Send started notification for deployment (if not already sent for redeploy)
    if [ "$REDEPLOY" != true ]; then
        send_slack_notification "$USERNAME" "$ACTION" "$GIT_BRANCH" "$AWS_REGION" "started" "$AWS_PROFILE"
    else
        send_slack_notification "$USERNAME" "deploy" "$GIT_BRANCH" "$AWS_REGION" "started" "$AWS_PROFILE"
    fi
    
    # Check if CodePipeline already exists
    existing_pipeline=$(check_pipeline_exists)
    if [ $? -eq 0 ] && [ "$REDEPLOY" != true ]; then
        echo "📋 Found existing CodePipeline infrastructure"
        if ! deploy_with_existing_pipeline "$existing_pipeline"; then
            exit 1
        fi
    else
        if [ "$REDEPLOY" = true ]; then
            echo "🔄 Redeploy requested - will create new infrastructure"
        else
            echo "🆕 No existing CodePipeline found - creating new infrastructure"
        fi
        
        if ! deploy_with_new_stack; then
            exit 1
        fi
    fi
fi

# Final cleanup before successful exit
cleanup_temp_files

exit 0