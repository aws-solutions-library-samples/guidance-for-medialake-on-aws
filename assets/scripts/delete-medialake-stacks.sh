#!/bin/bash

while true; do
    echo "Searching for MediaLake stacks..."
    
    # Get all stacks raw output for debugging
    all_stacks=$(aws cloudformation list-stacks \
        --no-paginate \
        --query "StackSummaries[?StackStatus!='DELETE_COMPLETE'].StackName" \
        --output text)
    
    echo "All active stacks:"
    echo "$all_stacks"
    
    # Filter for MediaLake stacks using case-insensitive grep
    # Only include stacks with "medialake" in their name
    stacks=$(echo "$all_stacks" | grep -i "medialake")
    
    # Exclude CDKToolkit
    stacks=$(echo "$stacks" | grep -v "CDKToolkit")
    
    if [ -z "$stacks" ]; then
        echo "No MediaLake stacks found."
        exit 0
    fi
    
    echo "Found MediaLake stacks to delete:"
    echo "$stacks"
    
    # Ask for confirmation before deleting
    read -p "Are you sure you want to delete these stacks? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operation cancelled."
        exit 0
    fi
    
    # Delete stacks with confirmation
    for stack in $stacks; do
        echo "Initiating deletion: $stack"
        aws cloudformation delete-stack \
            --stack-name "$stack"
    done
    
    echo "Waiting 60 seconds before next check..."
    sleep 60
done
