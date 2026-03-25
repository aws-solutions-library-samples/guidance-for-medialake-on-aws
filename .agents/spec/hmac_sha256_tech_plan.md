# Tech Plan: HMAC SHA-256 Webhook Authentication

## Overview

Add `hmac_sha256` as a third webhook authentication method alongside the existing `api_key` and `basic_auth` options. HMAC signing is the industry standard used by GitHub, Stripe, Slack, and most webhook providers — callers sign the request body with a shared secret and send the signature in a header.

## Architectural Constraint

API Gateway REQUEST-type authorizers do not receive the request body. HMAC verification requires the raw body to recompute the hash. Rather than introducing a second API Gateway, the solution splits responsibility:

- **Webhook Authorizer Lambda**: validates pipeline exists, is active, and is deployed. For `hmac_sha256` pipelines, returns Allow with `authMethod` in the authorizer context — no credential check.
- **Webhook Ingress Lambda**: for `hmac_sha256` pipelines, fetches the secret, computes `HMAC-SHA256(secret, raw_body)`, and compares against the signature header. Rejects with 401 on mismatch.

This mirrors how GitHub, Stripe, and Slack SDKs verify signatures — in the handler, not at the gateway layer.

## Authorizer Context Passthrough

The authorizer's Allow policy includes a `context` field that API Gateway forwards to the integration Lambda via `event.requestContext.authorizer`. The webhook authorizer will populate:

```json
{
  "authMethod": "hmac_sha256",
  "webhookSecretArn": "arn:aws:secretsmanager:..."
}
```

This lets the ingress Lambda skip a redundant DynamoDB read for HMAC pipelines.

For `api_key` and `basic_auth`, the context carries `authMethod` only (credential check already done in authorizer).

## Secret Structure

Extends the existing Secrets Manager secret with HMAC fields:

```json
{
  "authMethod": "hmac_sha256",
  "current": {
    "hmacSecret": "<shared-secret>",
    "signatureHeader": "X-Hub-Signature-256"
  },
  "previous": {
    "hmacSecret": "<old-secret>",
    "signatureHeader": "X-Hub-Signature-256"
  },
  "graceUntil": "ISO-8601 timestamp"
}
```

The `signatureHeader` field is configurable per-pipeline so callers can match their provider's convention (e.g. `X-Hub-Signature-256` for GitHub, `Stripe-Signature` for Stripe). Defaults to `X-Hub-Signature-256`.

## Signature Format

The ingress Lambda accepts two common formats in the signature header value:

1. `sha256=<hex-digest>` (GitHub-style prefix)
2. Raw hex digest (no prefix)

Comparison uses `hmac.compare_digest` for constant-time safety.

## Changes by Component

### 1. Node Template (`s3_bucket_assets/pipeline_nodes/node_templates/trigger/trigger_webhook.yaml`)

- Add `HMAC SHA-256` option (value: `hmac_sha256`) to the `authMethod` select
- Add `secret` password field shown when `authMethod == hmac_sha256`
- Add optional `signatureHeader` string field (default: `X-Hub-Signature-256`) shown when `authMethod == hmac_sha256`

### 2. Webhook Authorizer (`lambdas/auth/webhook_authorizer/index.py`)

- Add `elif auth_method == "hmac_sha256":` branch that returns Allow with context containing `authMethod` and `webhookSecretArn`
- Refactor `_allow()` to accept optional context dict
- Existing `api_key` and `basic_auth` branches also pass `authMethod` in context (non-breaking addition)

### 3. Webhook Ingress (`lambdas/nodes/webhook_ingress/index.py`)

- After JSON parse (step 3) and before payload size cap (step 4), check `event.requestContext.authorizer.authMethod`
- If `hmac_sha256`:
  - Read `webhookSecretArn` from authorizer context
  - Fetch secret from Secrets Manager
  - Extract signature from the configured header
  - Compute `HMAC-SHA256(secret, raw_body)` using the raw body string (before JSON parse)
  - Compare with `hmac.compare_digest`, supporting `sha256=` prefix stripping
  - Apply current/previous grace window logic
  - Return 401 on mismatch

### 4. Pipeline Creation (`lambdas/api/pipelines/post_pipelines/handlers.py`)

- Add `elif auth_method == "hmac_sha256":` branch in the webhook provisioning block
- Populate `hmacSecret` and `signatureHeader` in `secret_payload["current"]`
- Generate credential hint: last 4 chars of the secret

### 5. CDK Infrastructure (`medialake_stacks/api_gateway_stack.py`)

- Grant `secretsmanager:GetSecretValue` to the webhook ingress Lambda on the webhook secrets prefix
- No API Gateway changes needed

### 6. CORS OPTIONS (`medialake_stacks/api_gateway_stack.py`)

- Add the default signature header `X-Hub-Signature-256` to the `Access-Control-Allow-Headers` list in the OPTIONS mock integration

## IAM Changes

| Lambda          | New Permission                                                    |
| --------------- | ----------------------------------------------------------------- |
| Webhook Ingress | `secretsmanager:GetSecretValue` on `{resource_prefix}/webhooks/*` |

All other Lambdas retain existing permissions unchanged.

## Performance Impact

For `hmac_sha256` pipelines only, the ingress Lambda makes one additional Secrets Manager call (~30-50ms). This is acceptable for async webhook processing where the response is an acceptance acknowledgment, not a synchronous result.

## What Does NOT Change

- API Gateway structure (single API Gateway, same endpoints)
- CloudFront configuration
- Authorizer TTL (remains 0)
- Idempotency logic
- EventBridge publish path
- Secret rotation/grace window pattern (reused as-is)
- `api_key` and `basic_auth` behavior (fully backward compatible)
