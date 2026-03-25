# Epic: Webhook Trigger Node Development

---

# Epic Brief: Webhook Trigger Node

## Summary

MediaLake is a media asset management platform with a visual pipeline builder where users compose processing workflows from nodes. Today, pipelines can only be triggered by internal platform events (S3 ingest, EventBridge rules) or manually via the UI. There is no way for an external system — a CMS, a DAM, a third-party SaaS tool, or a custom application — to push data into a MediaLake pipeline over HTTP. This Epic adds a **Webhook Trigger Node** that gives pipeline authors a first-class, secured HTTP entry point for their pipelines, provisioned automatically when the pipeline is saved and cleaned up when it is deleted.

---

## Context & Problem

### Who is affected

Pipeline authors — typically media operations teams, developers, and integrators — who need to connect external systems to MediaLake workflows without writing custom glue code or polling for events.

### Where in the product

The pipeline builder UI, the pipeline creation/deletion backend, and the platform's API Gateway + CloudFront infrastructure layer.

### Current pain

- **No external trigger surface.** External systems cannot push events into a MediaLake pipeline. The only inbound path is S3 upload or a manual UI action.
- **Integration friction.** Teams that want to trigger pipelines from external tools (e.g., a CMS publishing event, a partner API callback, a scheduled job) must build and maintain custom Lambda functions or EventBridge integrations outside the platform — duplicating effort and bypassing the pipeline builder entirely.
- **No standardised security model for inbound HTTP.** Even if a team hacks together an external trigger, there is no platform-managed way to authenticate the caller or rotate credentials.

### Goals

1. Allow any external HTTP client to trigger a MediaLake pipeline by sending a `POST` request to a unique, per-pipeline webhook URL.
2. Give pipeline authors a choice of three authentication methods in v1 — API Key / Bearer Token, Basic Auth, or HMAC SHA-256 — configured directly in the node panel.
3. Provision the webhook endpoint and its credentials automatically when the pipeline is saved; clean everything up automatically when the pipeline is deleted.
4. Reuse the existing API Gateway and CloudFront distribution, adding a dedicated `/webhooks/*` path with its own security and caching policies — keeping webhook traffic isolated from platform API traffic.
5. Forward the raw incoming payload to the pipeline's existing EventBridge event bus, consistent with how all other trigger types work.

### Constraints

- Must not require a new API Gateway instance or CloudFront distribution.
- Allow only **one Webhook Trigger node per pipeline**; adding a second one must show a validation error.
- Webhook secrets stored exclusively in AWS Secrets Manager (one secret per pipeline).
- Authentication validated by a dedicated Lambda authorizer before payload acceptance.
- V1 supported webhook auth methods are API Key / Bearer, Basic Auth, and HMAC SHA-256.
- POST method only; no caching on the `/webhooks/*` CloudFront behavior.
- Webhook endpoint accepts only `application/json` with valid JSON payload.
- If a pipeline is inactive/paused, webhook requests are rejected with an error response.
- Webhook URL remains stable after activation; auth/credential edits take effect on next pipeline save.
- Stored secrets are never fully revealed after save; API key/token-style credentials may show only last 4 characters.
- Cleanup of secrets and DynamoDB records is automatic on pipeline deletion.

### Success Criteria

- A pipeline author can add a Webhook Trigger node, choose an auth method, save the pipeline, and immediately see a working webhook URL in the node config panel.
- If a user attempts to add a second Webhook Trigger node in the same pipeline, the product blocks save and shows a clear validation message.
- An external system can `POST` a valid `application/json` payload to that URL with correct credentials and the pipeline starts asynchronously.
- Webhook `200` response clearly means “authenticated and accepted for async processing,” not “pipeline completed.”
- When available, response metadata includes correlation identifiers (e.g., execution ID / state machine execution reference).
- Invalid payload/content type returns client error; invalid or missing credential returns `403 Forbidden`; inactive pipeline returns a deterministic rejection.
- Deleting the pipeline removes the Secrets Manager secret and all associated metadata with no manual steps.

&nbsp;
