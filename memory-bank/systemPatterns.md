# System Patterns

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-09-06 00:41:06 - Log of updates made.

## Coding Patterns

- Lambda function architecture for API endpoints
- Utility functions separated into dedicated modules (search_utils.py)
- URL generation functions following consistent naming patterns

## Architectural Patterns

- AWS Lambda + S3 + CloudFront content delivery architecture
- Batch processing for URL generation to optimize performance
- Three distinct search paths: regular text search, semantic search without clip logic, semantic search with clip logic

## Testing Patterns

- To be defined as testing is implemented
