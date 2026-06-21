#!/bin/bash
# Read-only verification of the ml-dev4 deploy target.
OUT=/tmp/kiro_aws_verify.log
: > "$OUT"
{
  echo "=== identity ==="
  aws sts get-caller-identity --profile ml-dev4 --no-cli-pager --output json 2>&1
  echo ""
  echo "=== distribution E3VFETIU52O8JM ==="
  aws cloudfront get-distribution --id E3VFETIU52O8JM --profile ml-dev4 --no-cli-pager --output json \
    --query 'Distribution.{Domain:DomainName,Status:Status,Origins:DistributionConfig.Origins.Items[].DomainName}' 2>&1
  echo ""
  echo "=== UI bucket (top-level) ==="
  aws s3 ls s3://medialake-user-interface-438465153766-dev/ --profile ml-dev4 --no-cli-pager 2>&1 | head -30
  echo ""
  echo "===AWS_VERIFY_DONE==="
} >> "$OUT" 2>&1
