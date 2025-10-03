# Decision Log

This file records architectural and implementation decisions using a list format.
2025-09-06 00:40:54 - Log of updates made.

## Decision

- Migrate from S3 presigned URLs to CloudFront URLs for content delivery

## Rationale

- CloudFront provides better performance, caching, and global distribution
- Reduces latency for end users accessing media assets
- Improves scalability and reduces S3 direct access load

## Implementation Details

- CloudFront URL generation functions already exist in search_utils.py
- Need to update index.py to use CloudFront functions instead of S3 presigned URL functions
- Three search paths need updating: regular text search, semantic search without clip logic, semantic search with clip logic
