#!/bin/bash
# Quick diagnostic to check OpenSearch embedding storage

echo "Checking for documents with asset_embeddings..."
echo ""
echo "Run this command to check your OpenSearch index:"
echo ""
echo "# Get a sample document to see structure"
echo 'aws opensearch search --profile mcs --index media --body '"'"'{"query": {"match_all": {}}, "size": 1}'"'"
echo ""
echo "# Count documents with asset_embeddings field"
echo 'aws opensearch search --profile mcs --index media --body '"'"'{"query": {"exists": {"field": "asset_embeddings"}}, "size": 0}'"'"
echo ""
echo "# Count documents with embedding_512_cosine in nested array"
echo 'aws opensearch search --profile mcs --index media --body '"'"'{"query": {"nested": {"path": "asset_embeddings", "query": {"exists": {"field": "asset_embeddings.embedding_512_cosine"}}}}, "size": 0}'"'"
