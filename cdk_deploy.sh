#!/bin/bash

# CDK Deploy Script with Auto-Restart on Hang
# This script monitors CDK deployment and restarts if it hangs for more than 10 minutes

set -e

# Configuration
TIMEOUT_SECONDS=600  # 10 minutes
MAX_RETRIES=5
RETRY_COUNT=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to clean CDK cache and temporary files
clean_cdk_cache() {
    log_info "Cleaning CDK cache and temporary files..."

    # Remove cdk.out directory
    if [ -d "cdk.out" ]; then
        log_info "Removing cdk.out directory..."
        rm -rf cdk.out
    fi

    # Remove cdk-test-output directory if it exists
    if [ -d "cdk-test-output" ]; then
        log_info "Removing cdk-test-output directory..."
        rm -rf cdk-test-output
    fi

    # Remove synth.lock if it exists
    if [ -f "cdk-test-output/synth.lock" ]; then
        log_info "Removing synth.lock..."
        rm -f cdk-test-output/synth.lock
    fi

    # Clear npm cache (sometimes CDK issues are related to npm)
    log_info "Clearing npm cache..."
    npm cache clean --force 2>/dev/null || true

    log_success "Cache cleaned successfully"
}

# Function to kill all CDK-related processes
kill_cdk_processes() {
    log_warning "Killing CDK processes..."

    # Kill any running cdk processes
    pkill -f "cdk deploy" 2>/dev/null || true
    pkill -f "cdk synth" 2>/dev/null || true

    # Wait a moment for processes to die
    sleep 2

    log_info "CDK processes terminated"
}

# Function to run CDK deploy with timeout monitoring
run_cdk_deploy() {
    local temp_output=$(mktemp)
    local last_output_time=$(date +%s)
    local cdk_pid

    log_info "Starting CDK deployment (Attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."

    # Start CDK deploy in background and capture output
    cdk deploy --all --require-approval never 2>&1 | tee "$temp_output" &
    cdk_pid=$!

    log_info "CDK process started with PID: $cdk_pid"

    # Monitor the output
    local line_count=0
    local current_time
    local time_since_output

    while kill -0 $cdk_pid 2>/dev/null; do
        # Check if there's new output
        local new_line_count=$(wc -l < "$temp_output" 2>/dev/null || echo "0")

        if [ "$new_line_count" -gt "$line_count" ]; then
            # New output detected, update timestamp
            last_output_time=$(date +%s)
            line_count=$new_line_count
        fi

        # Check if we've exceeded timeout
        current_time=$(date +%s)
        time_since_output=$((current_time - last_output_time))

        if [ $time_since_output -gt $TIMEOUT_SECONDS ]; then
            log_error "No output for $TIMEOUT_SECONDS seconds. Deployment appears to be hung."

            # Kill the CDK process and all its children
            log_warning "Killing CDK process $cdk_pid and its children..."
            pkill -P $cdk_pid 2>/dev/null || true
            kill -9 $cdk_pid 2>/dev/null || true

            rm -f "$temp_output"
            return 1
        fi

        # Show progress indicator
        echo -ne "\r${BLUE}[MONITORING]${NC} Time since last output: ${time_since_output}s / ${TIMEOUT_SECONDS}s"

        sleep 5
    done

    # Clear progress line
    echo -ne "\r\033[K"

    # Check exit status
    wait $cdk_pid
    local exit_code=$?

    rm -f "$temp_output"

    if [ $exit_code -eq 0 ]; then
        log_success "CDK deployment completed successfully!"
        return 0
    else
        log_error "CDK deployment failed with exit code: $exit_code"
        return 1
    fi
}

# Main execution
main() {
    log_info "=== CDK Deployment Script Started ==="
    log_info "Timeout: ${TIMEOUT_SECONDS}s, Max Retries: ${MAX_RETRIES}"

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # Clean cache before each attempt
        clean_cdk_cache

        # Run CDK deploy
        if run_cdk_deploy; then
            log_success "=== CDK Deployment Successful ==="
            exit 0
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))

            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                log_warning "Deployment failed or hung. Retrying in 10 seconds..."
                log_warning "Retry attempt: $RETRY_COUNT / $MAX_RETRIES"

                # Kill any remaining processes
                kill_cdk_processes

                sleep 10
            else
                log_error "=== Maximum retry attempts reached ==="
                log_error "CDK deployment failed after $MAX_RETRIES attempts"
                exit 1
            fi
        fi
    done
}

# Trap to ensure cleanup on script exit
trap 'kill_cdk_processes; log_warning "Script interrupted. Cleaning up..."; exit 130' INT TERM

# Run main function
main
