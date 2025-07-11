#!/usr/bin/env python3
"""
Process vectors from S3 JSON file and push to OpenSearch vector storage.

This script downloads a JSON file from S3, iterates over embedding data,
and pushes each vector to OpenSearch for semantic search capabilities.
"""

import json
import os
import sys
import boto3
from datetime import datetime
from typing import Dict, List, Any, Optional
from opensearchpy import OpenSearch, AWSV4SignerAuth, RequestsHttpConnection
from aws_lambda_powertools import Logger
import argparse

# Configure logging
logger = Logger()

class VectorProcessor:
    """Process vectors from S3 JSON file and push to OpenSearch."""
    
    def __init__(self, opensearch_endpoint: str, index_name: str = "media", aws_region: str = "us-east-1"):
        """Initialize the vector processor."""
        self.opensearch_endpoint = opensearch_endpoint
        self.index_name = index_name
        self.aws_region = aws_region
        
        # Initialize AWS clients
        self.s3_client = boto3.client('s3', region_name=aws_region)
        
        # Initialize OpenSearch client
        session = boto3.Session()
        credentials = session.get_credentials()
        auth = AWSV4SignerAuth(credentials, aws_region, "es")
        
        self.opensearch_client = OpenSearch(
            hosts=[{"host": opensearch_endpoint.replace("https://", ""), "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )
        
        logger.info(f"Initialized VectorProcessor with endpoint: {opensearch_endpoint}")
    
    def download_json_from_s3(self, bucket: str, key: str) -> Dict[str, Any]:
        """Download and parse JSON file from S3."""
        try:
            logger.info(f"Downloading JSON file from s3://{bucket}/{key}")
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            logger.info(f"Successfully downloaded and parsed JSON file with {len(data)} records")
            return data
        except Exception as e:
            logger.error(f"Failed to download JSON from S3: {str(e)}")
            raise
    
    def create_vector_document(self, record: Dict[str, Any], video_name: str, video_path: str) -> Dict[str, Any]:
        """Create a vector document for OpenSearch from the record data."""
        # Extract embedding data
        embedding_vector = record.get("vector", [])
        if not embedding_vector:
            raise ValueError("No embedding vector found in record")
        
        metadata = record.get("metadata", {})
        
        # Create vector key similar to the provided format
        start_time = metadata.get("start_time", 0)
        end_time = metadata.get("end_time", 0)
        embedding_option = metadata.get("embeddingOption", "default")
        
        vector_key = f"{video_name}_{start_time}-{end_time}_{embedding_option}"
        
        # Create OpenSearch document following the MediaLake schema
        document = {
            "type": "video",
            "document_id": vector_key,
            "embedding": embedding_vector,
            "embedding_scope": "clip",
            "embedding_option": embedding_option,
            "start_timecode": self._seconds_to_timecode(start_time),
            "end_timecode": self._seconds_to_timecode(end_time),
            "timestamp": datetime.utcnow().isoformat(),
            "DigitalSourceAsset": {
                "ID": f"asset:vid:{video_name}",
                "Type": "video"
            },
            "video_path": video_path,
            "start_time_sec": start_time,
            "end_time_sec": end_time
        }
        
        return document
    
    def _seconds_to_timecode(self, seconds: float, fps: int = 30) -> str:
        """Convert seconds to SMPTE timecode format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"
    
    def push_vector_to_opensearch(self, document: Dict[str, Any]) -> bool:
        """Push a single vector document to OpenSearch."""
        try:
            # Index the document
            response = self.opensearch_client.index(
                index=self.index_name,
                body=document,
                id=document.get("document_id")
            )
            
            if response.get("result") in ["created", "updated"]:
                logger.info(f"Successfully indexed document: {document.get('document_id')}")
                return True
            else:
                logger.error(f"Failed to index document: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error indexing document {document.get('document_id')}: {str(e)}")
            return False
    
    def process_json_file(self, bucket: str, key: str, video_name: str, video_path: str) -> Dict[str, int]:
        """Process the entire JSON file and push vectors to OpenSearch."""
        try:
            # Download and parse JSON
            data = self.download_json_from_s3(bucket, key)
            
            # Initialize counters
            total_records = len(data)
            successful_uploads = 0
            failed_uploads = 0
            
            logger.info(f"Processing {total_records} records from {bucket}/{key}")
            
            # Process each record
            for i, record in enumerate(data, 1):
                try:
                    # Skip if record is not a dictionary
                    if not isinstance(record, dict):
                        logger.warning(f"Skipping record {i}: not a dictionary")
                        failed_uploads += 1
                        continue
                    
                    # Create vector document
                    document = self.create_vector_document(record, video_name, video_path)
                    
                    # Push to OpenSearch
                    if self.push_vector_to_opensearch(document):
                        successful_uploads += 1
                    else:
                        failed_uploads += 1
                        
                    # Log progress every 100 records
                    if i % 100 == 0:
                        logger.info(f"Processed {i}/{total_records} records")
                        
                except Exception as e:
                    logger.error(f"Error processing record {i}: {str(e)}")
                    failed_uploads += 1
                    continue
            
            # Final summary
            results = {
                "total_records": total_records,
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads
            }
            
            logger.info(f"Processing complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error processing JSON file: {str(e)}")
            raise


def main():
    """Main function to run the vector processor."""
    parser = argparse.ArgumentParser(description="Process vectors from S3 JSON file and push to OpenSearch")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--key", required=True, help="S3 object key (JSON file path)")
    parser.add_argument("--video-name", required=True, help="Video name for vector key generation")
    parser.add_argument("--video-path", required=True, help="Path to original video")
    parser.add_argument("--opensearch-endpoint", required=True, help="OpenSearch endpoint URL")
    parser.add_argument("--index-name", default="media", help="OpenSearch index name (default: media)")
    parser.add_argument("--aws-region", default="us-east-1", help="AWS region (default: us-east-1)")
    
    args = parser.parse_args()
    
    try:
        # Initialize processor
        processor = VectorProcessor(
            opensearch_endpoint=args.opensearch_endpoint,
            index_name=args.index_name,
            aws_region=args.aws_region
        )
        
        # Process the JSON file
        results = processor.process_json_file(
            bucket=args.bucket,
            key=args.key,
            video_name=args.video_name,
            video_path=args.video_path
        )
        
        # Print results
        print(f"Processing completed successfully!")
        print(f"Total records: {results['total_records']}")
        print(f"Successful uploads: {results['successful_uploads']}")
        print(f"Failed uploads: {results['failed_uploads']}")
        
        # Exit with appropriate code
        sys.exit(0 if results['failed_uploads'] == 0 else 1)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 