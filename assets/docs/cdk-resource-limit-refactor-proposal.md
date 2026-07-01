# Proposal: CDK Stack Refactor for the 500-Resource Limit, Data Preservation, and Iterative API Deploys

Status: Draft for review
Scope: `app.py`, `medialake_stacks/`, `medialake_constructs/`
Author: Engineering (drafted with Kiro)

---

## 1. Executive summary

The MediaLake CDK app packs most of the API surface into a single nested stack
(`ApiGatewayStack`) that is approaching CloudFormation's hard limit of **500 resources per
template**. The team has already felt this pain once and carved `PortalApiStack` out of the
API stack specifically "to stay under CloudFormation's 500-resource per-stack limit" (comment
in `app.py`). The next wave of endpoints will breach the limit in that stack.

Two structural choices make the situation worse than a simple "too many resources" problem:

1. **Hard cross-stack coupling via `Fn::ImportValue`.** The REST API id and root resource id
   are exported once and imported by ~9 and ~7 stacks respectively. CloudFormation refuses to
   change or delete an exported value while anything imports it, so the API **cannot be
   reprovisioned** without first tearing down every consumer.
2. **A single global API deployment that depends on everything.** `ApiGatewayDeploymentStack`
   depends on the entire collected set of API resources and force-creates a new deployment on
   every run, so every deploy touches the whole API.

This proposal recommends a tiered refactor that:

- **Splits the heavy API stack** so no single template approaches 500 resources, with explicit
  per-stack budgets and headroom.
- **Permanently separates stateful "data" resources from stateless "API/compute" resources**,
  pins data resources to `RemovalPolicy.RETAIN`, and guarantees they are never moved or
  reprovisioned.
- **Replaces brittle `Fn::ImportValue` coupling with SSM Parameter Store reads** (the pattern
  already used for the API stage name), so the API tier can be fully reprovisioned and
  redeployed iteratively on top of any of the last several commits without export locks.

The work is phased so that **Phase 1 buys immediate headroom with low risk** and later phases
deliver durable independence. No phase requires moving or recreating a data store.

---

## 2. How the app is built today (as-observed)

### 2.1 Stack topology

There are three groups of stacks.

**Top-level stacks** (`cdk.Stack`), deployed independently:

| Stack                       | Region    | Role                                                          | State                     |
| --------------------------- | --------- | ------------------------------------------------------------- | ------------------------- |
| `CloudFrontWafStack`        | us-east-1 | CloudFront WAF WebACL                                         | stateless                 |
| `EdgeLambdaStack`           | us-east-1 | Lambda@Edge                                                   | stateless                 |
| `BaseInfrastructureStack`   | primary   | VPC, OpenSearch, S3 Vectors, S3 buckets, DynamoDB, EventBuses | **stateful**              |
| `CognitoStack`              | primary   | User pool, identity pool, client                              | **stateful**              |
| `ApiGatewayCoreStack`       | primary   | The shared `RestApi`, WAF ACL, X-Origin secret                | stateless                 |
| `AuthorizationStack`        | primary   | AVP policy store, auth table                                  | **stateful** (auth table) |
| `MediaLakeStack`            | primary   | Umbrella parent for ~14 nested stacks                         | mixed                     |
| `ApiGatewayDeploymentStack` | primary   | The `Deployment` + `Stage` + WAF association                  | stateless                 |
| `UserInterfaceStack`        | primary   | CloudFront + S3 site + config                                 | stateless                 |
| `CognitoUpdateStack`        | primary   | Post-deploy Cognito wiring                                    | stateless                 |
| `CleanupStack`              | primary   | Teardown helpers                                              | stateless                 |

**Nested stacks** (`cdk.NestedStack`), all children of `MediaLakeStack`:

`NodesStack`, `AssetSyncStack`, `SettingsStack`, `StorageConnectorsStack`, `ApiGatewayStack`,
`PortalApiStack`, `UsersGroupsStack`, `CollectionsStack`, `DashboardStack`,
`CollectionTypesStack`, `GroupsStack`, `IntegrationsEnvironmentStack`, `PipelineStack`,
`UpdatesApiStack`.

**Unused / legacy stack files** present in `medialake_stacks/` but not instantiated in
`app.py`: `monitoring_stack`, `lambda_warmer_stack`, `permissions_stack`,
`pipelines_executions_stack`, `post_deploy_config_stack`, `pre_deploy_cleanup_stack`,
`settings_api_stack` (deprecated), `shared_assets_stack`, `shared_vpc_stack`,
`shared_api_stack` (empty), `shared_services_stack` (empty).

### 2.2 The shared REST API pattern

`ApiGatewayCoreStack` creates one `RestApi` and exports its id, root-resource id, the WAF ACL
ARN, and the X-Origin verify secret ARN as CloudFormation outputs. Every feature stack then
imports the id/root via `Fn.import_value(...)` and re-hydrates the API with
`RestApi.from_rest_api_attributes(...)` before attaching its own resources and methods. The
single `Deployment`/`Stage` is created last, in `ApiGatewayDeploymentStack`.

### 2.3 Why the limit is per nested stack — and which one is hot

Each `cdk.NestedStack` synthesizes to its **own** CloudFormation template, so it has its own
independent 500-resource budget; in the parent template the nested stack counts as a single
`AWS::CloudFormation::Stack` resource. The parent `MediaLakeStack` (~14 nested stacks plus a
little cross-wiring) is nowhere near the limit. **The limit pressure is inside one nested
stack: `ApiGatewayStack`.**

---

## 3. Quantitative findings

These are static-analysis counts from the source (call-site counts of `add_method`,
`add_resource`, and Lambda constructors). They are **estimates**, not a synth count — see
§9 for why a local `cdk synth` could not be run and how to get the authoritative number.

**API surface, total across the app:** ~166 `add_method` and ~171 `add_resource` calls, all
attached to the single shared `RestApi`.

**Per-stack API surface (where each construct lives):**

| Nested stack                   | API construct(s)                                                      | ~methods | ~resources | ~Lambda ctors |
| ------------------------------ | --------------------------------------------------------------------- | -------- | ---------- | ------------- |
| **`ApiGatewayStack`**          | Assets + Connectors + Search + Nodes (+ webhooks, health, authorizer) | ~41      | ~44        | **~47**       |
| `CollectionTypesStack`         | settings                                                              | 17       | 22         | ~1            |
| `UsersGroupsStack`             | users                                                                 | 15       | 13         | ~1            |
| `PipelineStack`                | pipelines                                                             | 11       | 11         | ~8            |
| `CollectionsStack`             | collections                                                           | 8        | 8          | ~4            |
| `DashboardStack`               | dashboard                                                             | 6        | 7          | ~1            |
| `IntegrationsEnvironmentStack` | integrations + environments                                           | 6        | —          | ~5            |
| `UpdatesApiStack`              | updates                                                               | 2        | —          | ~0–1          |
| `PortalApiStack`               | portal (already split out)                                            | —        | —          | ~6            |

The single heaviest construct is `AssetsConstruct` (`api_gateway_assets.py`): ~29 Lambda
constructors, 19 methods, 19 resources — and it sits inside `ApiGatewayStack`.

**Resource math for `ApiGatewayStack`.** Each `Lambda` construct
(`shared_constructs/lambda_base.py`) emits roughly a function + execution role + an inline
policy + a log group + one or more `Lambda::Permission`s — call it ~4–6 CloudFormation
resources each (layers are shared per-stack singletons, so they don't multiply). With ~47
Lambdas that is ~200–280 resources, plus ~85 `ApiGateway::Resource` / `ApiGateway::Method`
nodes, plus per-method integration permissions, two `RequestAuthorizer`s, EventBridge warmer
rules, and secrets policies. That lands `ApiGatewayStack` in the **~350–480 resource** range:
close enough to 500 that ordinary feature growth will breach it.

**Recent growth (last 5 commits):** mostly application/runtime changes (portal and collection
node fixes, `pyvips`-based image proxy/thumbnail, vendored layer payloads under
`.preserve_layers/`), not large blocks of new CloudFormation resources. This matches the user's
observation. The limit problem is the **accumulated** size of `ApiGatewayStack`, not a single
recent spike — which is good news for "deploy on top of a recent commit": the recent commits do
not themselves push any stack over the edge.

---

## 4. Root-cause analysis

**RC-1 — One overloaded nested stack.** `ApiGatewayStack` bundles four heavy feature domains
(assets, connectors, search, nodes) plus the shared authorizer and webhook plumbing into a
single template. This is the proximate cause of the 500-resource pressure.

**RC-2 — `Fn::ImportValue` hard-locks the API core.** `MediaLakeApiGatewayCore-ApiGatewayId`
(imported ~9×) and `-RootResourceId` (imported ~7×), plus `XOriginVerifySecretArn`,
`ApiGatwayWAFACLARN`, the `MediaLakeCognito-*` exports, and `MediaLakeBaseInfrastructure`
bucket ARNs, are consumed with `Fn::ImportValue`. CloudFormation will not let you modify or
delete an export while another stack imports it. **This is the single biggest blocker to
"fully reprovision the API."**

**RC-3 — A single global deployment depending on everything.**
`ApiGatewayDeploymentStack` takes `api_resource_collector.get_resources()` (every API nested
stack) as dependencies and runs a custom-resource Lambda that force-creates a new deployment
every run (`Timestamp=int(time.time())`). Every deploy therefore re-touches the entire API and
is sensitive to ordering across all the API stacks.

**RC-4 — Stateful resources are set to DESTROY and are interleaved with compute.** Data stores
in `BaseInfrastructureStack` use `RemovalPolicy.DESTROY` / `destroy_on_delete=True`
(DynamoDB asset/pipeline/upload-directives tables, S3 buckets), and additional application data
tables live inside feature nested stacks (`NodesStack` nodes table, `SettingsStack`
system-settings + api-keys, `CollectionsStack` collections table,
`IntegrationsEnvironmentStack` integrations table, `AssetSyncStack` job table + results
bucket). Any stack split that _moves_ one of these resources to a new stack/logical id would
**delete and recreate it** — data loss. The DESTROY policy makes that failure mode silent.

**RC-5 — The umbrella couples lifecycles.** Because ~14 nested stacks live under one parent
`MediaLakeStack`, they deploy as one CloudFormation transaction and are wired to each other
inside the parent (e.g., the users Lambda is granted access to the collections table across
nested-stack boundaries). Nesting _does_ solve the per-template limit, but it does not give the
API tier an independent lifecycle from data-bearing nested stacks.

---

## 5. Requirements (restated)

1. **R1 — Stay under 500 resources per template**, with headroom for growth.
2. **R2 — Preserve all data stores and their data.** They must never be reprovisioned, moved
   to a new stack, or have their logical id changed.
3. **R3 — The API may be fully reprovisioned** (torn down and rebuilt) without touching data.
4. **R4 — Iterative deploys.** A `cdk deploy` must succeed on top of any of the last ~5
   commits/deploys, without export-lock failures or resource-limit breaches.

---

## 6. Target architecture

Two tiers with a hard, one-directional dependency (API depends on Data; never the reverse), and
loose coupling between them through SSM Parameter Store rather than CloudFormation exports.

```
                 ┌──────────────────────────────────────────────────────────┐
   DATA TIER     │  (stateful, RETAIN, deploy rarely, never reprovisioned)    │
   (persistent)  │                                                            │
                 │  BaseInfrastructureStack   CognitoStack   AuthZ data       │
                 │   - VPC / SG               - user pool    - auth table     │
                 │   - OpenSearch             - identity pool                 │
                 │   - S3 Vectors            ApplicationDataStack (new)       │
                 │   - S3 buckets             - nodes table                   │
                 │   - DynamoDB tables        - settings + api-keys tables    │
                 │   - EventBuses             - collections table             │
                 │                            - integrations table           │
                 │                            - asset-sync table + bucket     │
                 └───────────────┬───────────── writes ids/arns ─────────────┘
                                 │  SSM Parameter Store (soft references)
                                 │  /medialake/<env>/...   (no export locks)
                 ┌───────────────▼──────────────────────────────────────────┐
   API TIER      │  (stateless, fully reprovisionable, independent lifecycle)│
   (disposable)  │                                                           │
                 │  ApiCoreStack: RestApi + WAF + X-Origin secret + shared   │
                 │                authorizer                                  │
                 │  Feature API stacks (each well under 500, balanced):      │
                 │   - AssetsApiStack        - ConnectorsApiStack            │
                 │   - SearchApiStack        - NodesApiStack                 │
                 │   - PipelinesApiStack     - CollectionsApiStack           │
                 │   - UsersApiStack         - SettingsApiStack              │
                 │   - DashboardApiStack     - IntegrationsApiStack          │
                 │   - PortalApiStack        - UpdatesApiStack               │
                 │  ApiDeploymentStack: Deployment + Stage + WAF association  │
                 └───────────────────────────────────────────────────────────┘
```

Key properties:

- **Data tier is sacred.** Every resource is `RemovalPolicy.RETAIN`, lives in a fixed stack with
  a fixed logical id, and exposes its identifiers through SSM parameters. It is deployed on its
  own and rarely.
- **API tier reads only SSM** for everything it needs from the data tier (REST API id, root id,
  secret ARN, WAF ARN, Cognito ids, bucket names/ARNs, table names). No `Fn::ImportValue`
  across the tier boundary. This is what makes R3 and R4 possible.
- **Feature API stacks are balanced** so each has a comfortable margin below 500. Splitting the
  current `ApiGatewayStack` into `AssetsApiStack` + `ConnectorsApiStack` + `SearchApiStack` +
  `NodesApiStack` immediately removes the hotspot.

### 6.1 Shared REST API vs. multiple REST APIs

There are two viable shapes for the API tier. The phased plan starts with (A) because it is
low-risk, and offers (B) as the durable end state.

**(A) Keep one shared `RestApi`, balance methods across more stacks (recommended first).**
Minimal change to today's model. Each feature stack still imports the REST API id/root, but via
**SSM** instead of `Fn::ImportValue`. Pros: smallest diff, no frontend URL changes, no custom
domain needed. Cons: all feature stacks still share one API id, so a _full_ reprovision of the
API core still implies redeploying every feature stack together (acceptable — they are
stateless and deployed as one tier).

**(B) One `RestApi` per feature domain behind a single hostname (durable end state).**
Each feature API is fully self-contained (its own `RestApi` + methods + deployment + stage) and
is exposed under one hostname via either CloudFront path-based origins (the app already serves
the UI through CloudFront) or API Gateway custom-domain base-path mappings
(`/assets/* → AssetsApi`, `/pipelines/* → PipelinesApi`, ...). Pros: each API has its **own**
500 budget (the limit effectively disappears), and any single API can be reprovisioned in
isolation with zero shared-id coupling. Cons: requires a routing layer (CloudFront behaviors or
a custom domain) and a frontend change to how API URLs are constructed; per-API stages to
manage. This is the right long-term target if the API keeps growing.

---

## 7. Phased migration plan

Each phase is independently shippable and ordered by risk/value. No phase moves a data store.

### Phase 0 — Safety net and baseline (no behavior change)

- **Flip stateful resources to `RemovalPolicy.RETAIN`** (DynamoDB tables, S3 buckets, OpenSearch,
  S3 Vectors, Cognito user pool, auth table). This is a property-only change — it does not
  replace the resource — and it makes every later step safe by default. Update
  `s3bucket`/`DynamoDB` shared constructs and `base_infrastructure.py` accordingly. (Teardown
  helpers in `CleanupStack` can keep an explicit, opt-in destroy path for true environment
  teardown.)
- **Capture an authoritative resource count.** Run `cdk synth` on a machine with Docker
  available (see §9) and record per-stack resource counts as the real baseline and budget.
- **Add a CI guard** that fails when any template exceeds a budget (e.g., 450) so the team gets
  early warning well before 500.

Risk: minimal (property changes + tooling). Rollback: revert the property change.

### Phase 1 — Split the hot stack (immediate headroom, R1)

Carve `ApiGatewayStack` into feature stacks, exactly as `PortalApiStack` was carved out:

- `AssetsApiStack` (the big one — ~29 Lambdas / 19 methods)
- `ConnectorsApiStack`
- `SearchApiStack`
- `NodesApiStack`
- Leave the shared authorizer + webhook plumbing + health in a slim `ApiCommonStack` (or keep in
  `ApiGatewayStack` if it stays small), and expose the authorizer to the feature stacks the same
  way `api_gateway_stack` already shares it today.

Notes and gotchas:

- These constructs already take their dependencies via props, so the move is largely mechanical
  (instantiate the construct in a new `cdk.NestedStack` and thread the same props).
- Moving an `ApiGateway::Method`/`Resource` to a new stack changes its logical id, so those
  methods are recreated. That is acceptable because the API is reprovisionable, but it means a
  fresh `Deployment` must follow (already handled by `ApiGatewayDeploymentStack`'s force-redeploy).
- **Lambda log group names** are derived from the function name
  (`/aws/lambda/<name>`), not the logical id. If a function name is unchanged but the function
  moves stacks, a pre-existing log group can collide on create. Plan to either keep names stable
  and import the log groups, or allow CDK-managed log retention to adopt them. Validate in a
  scratch environment.
- Keep the shared authorizer Lambda in exactly one stack and pass it by reference; do not
  duplicate it.

Risk: medium (logical-id churn on stateless API resources). Rollback: redeploy the prior commit
(the API tier is disposable). No data impact.

### Phase 2 — Decouple the tier boundary (R3, R4)

Replace cross-tier `Fn::ImportValue` with SSM reads. The app already does this for the API
stage name (`ApiGatewayDeploymentStack` writes `api-gateway-stage-name`; `UserInterfaceStack`
reads it), for `media-assets-bucket-name`, and for `cloudfront-distribution-domain` — so the
pattern and helpers (`config.ssm_param(...)`) are in place.

- **Producers (data tier)** write their identifiers to SSM:
  REST API id + root id (from `ApiGatewayCoreStack`), X-Origin secret ARN, WAF ACL ARN,
  Cognito user-pool / client / identity-pool ids, bucket names/ARNs, table names.
- **Consumers (API tier)** read via `ssm.StringParameter.from_string_parameter_name(...)` /
  `value_for_string_parameter(...)` instead of `Fn.import_value(...)`.
- **Remove the now-unused `CfnOutput(export_name=...)` exports** once no stack imports them.
  Do this last and one at a time — you cannot delete an export until its importers are gone.

Why this satisfies R3/R4: SSM reads resolve a value at deploy time but create **no
CloudFormation dependency edge and no export lock**. The data tier can change, and the API tier
can be destroyed and recreated, without CloudFormation blocking on "export X is in use by stack
Y." That is precisely what allows `cdk deploy` to succeed on top of any recent commit.

Risk: medium (must sequence export removal after importer cutover). Rollback: SSM reads and
exports can coexist during transition; revert consumers to imports if needed.

### Phase 3 — Give the API tier an independent lifecycle (R3, R4)

- Promote the API feature stacks out from under the `MediaLakeStack` umbrella into their own
  top-level stacks (or a dedicated parent), so the **API tier deploys as its own unit**,
  separate from data-bearing nested stacks. With Phase 2 in place there is no `Fn::ImportValue`
  edge forcing them together.
- Keep a single `ApiDeploymentStack`, but make its dependency list explicit and stable rather
  than "every collected resource." Each feature stack can publish a small marker (e.g., an SSM
  parameter or a CfnOutput consumed only inside the API tier) that the deployment depends on,
  so the deployment waits for methods to exist without importing the entire world.

Risk: medium. This is the step that makes "tear down and rebuild just the API" a one-command
operation.

### Phase 4 — (Optional, durable) one REST API per domain behind one hostname

If the API keeps growing, adopt shape (B) from §6.1: a `RestApi` per feature domain, routed
under a single hostname via CloudFront behaviors or custom-domain base-path mappings. Each API
then has its own 500 budget and fully independent reprovisioning. This is the only option that
removes the 500 ceiling permanently rather than deferring it.

Risk: higher (routing + frontend URL construction changes). Do only if growth justifies it.

---

## 8. How this delivers each requirement

| Req                                      | Delivered by                       | Mechanism                                                                                                               |
| ---------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| R1 (under 500)                           | Phase 1 (+ Phase 4 for permanence) | Split `ApiGatewayStack`; per-template budgets + CI guard                                                                |
| R2 (preserve data)                       | Phase 0                            | `RETAIN` on all stateful resources; data resources never change stack or logical id                                     |
| R3 (reprovision API)                     | Phases 2–3                         | SSM-based soft coupling removes export locks; API tier is its own deploy unit                                           |
| R4 (iterative deploys on recent commits) | Phases 2–3                         | No export locks + balanced stacks ⇒ a `cdk deploy` of an older API-tier commit succeeds against the unchanged data tier |

### 8.1 The "deploy on top of the last 5 commits" workflow (target state)

Once Phases 0–3 land:

1. The **data tier** is deployed and stable; its identifiers are in SSM. It is not part of the
   day-to-day deploy loop.
2. To roll the API to any recent commit: check out that commit and
   `cdk deploy <api-tier stacks>`. The API stacks read data-tier ids from SSM, recreate their
   own (stateless) resources, and the deployment stack publishes a fresh stage. Because there
   are no export locks and no stack exceeds 500, the deploy is not blocked by older/newer
   resource shapes.
3. Rollback is the same operation against an earlier commit.

Pre-conditions worth pinning so old commits synth identically: a fixed CDK bootstrap/synthesizer
(`deployment_options.use_cli_credentials`), stable asset hashing, and unchanged data-tier SSM
parameter names across the commit range.

---

## 9. Validating resource counts (authoritative count)

A local `cdk synth` for exact counts was **not** possible in this environment: the
`CommonLibrariesLayer` (`shared_constructs/lambda_layers.py`) bundles via Docker
unconditionally (no CI/pre-built escape hatch) and the Docker daemon is unavailable here.
`container_nodes_enabled` defaults to `False`, so there are no `DockerImageAsset`s by default,
and there are no `from_lookup` context calls — so on a machine **with Docker running**, a normal
`cdk synth` will succeed. To get the authoritative per-stack counts:

```bash
# On a machine with Docker running:
cdk synth --output cdk.out

# Count resources per synthesized template (top-level and nested):
for f in cdk.out/*.template.json; do
  printf '%6s  %s\n' "$(jq '.Resources | length' "$f")" "$(basename "$f")"
done | sort -rn
```

Use these numbers to (a) confirm which template is closest to 500, (b) set the CI budget, and
(c) verify after each phase that no template regressed.

> Note: a temporary `cdk.json` edit (`aws:cdk:bundling-stacks: []`) was tried during analysis to
> bypass bundling; it did not stop the layer bundling and has been **reverted**. The repository
> is unchanged by this analysis.

---

## 10. Risk register

| #   | Risk                                                        | Likelihood | Impact   | Mitigation                                                                                                                                                       |
| --- | ----------------------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Moving a stateful resource recreates it (data loss)         | —          | Critical | Phase 0 `RETAIN` first; never move data resources; if a move is ever required, use CloudFormation **resource import** (`cdk import`) to adopt without recreation |
| 2   | Lambda log-group name collisions when functions move stacks | Medium     | Medium   | Keep function names stable and import existing log groups, or let CDK log-retention adopt them; validate in a scratch env                                        |
| 3   | Deleting a CFN export still in use blocks deploy            | Medium     | Medium   | Cut consumers over to SSM first; remove exports last, one at a time                                                                                              |
| 4   | API method logical-id churn causes brief 4xx during deploy  | Medium     | Low      | Acceptable for a stateless tier; rely on the existing force-redeploy of the stage; schedule in a low-traffic window                                              |
| 5   | Two sources of truth (export + SSM) during transition       | Medium     | Low      | Time-box the transition; CI check that new code reads SSM, not imports                                                                                           |
| 6   | `RETAIN` leaves orphaned resources on intentional teardown  | Low        | Low      | Keep an explicit destroy path in `CleanupStack` for real environment teardown                                                                                    |

---

## 11. Recommended first steps

1. Approve the **two-tier target** (§6) and the **shared-RestApi-first** approach (§6.1-A).
2. Land **Phase 0** (RETAIN + CI budget guard + authoritative synth count) — low risk, high
   safety value, and unblocks everything else.
3. Land **Phase 1** split of `ApiGatewayStack` in a scratch environment, validate log-group and
   deployment behavior, then promote.
4. Land **Phase 2** SSM decoupling, then remove dead exports.
5. Decide whether growth justifies **Phase 4** (per-domain REST APIs).

---

## Appendix A — Key source references

- `app.py` — stack wiring, the `MediaLakeStack` umbrella, `ApiResourceCollector`,
  `ResourceImporter` (the `Fn::ImportValue` helpers), the `PortalApiStack` split comment.
- `medialake_stacks/api_gateway_core_stack.py` — creates the shared `RestApi`; exports id / root
  / WAF ARN / X-Origin secret ARN.
- `medialake_stacks/api_gateway_stack.py` — the overloaded nested stack (Assets, Connectors,
  Search, Nodes + authorizer + webhooks + health).
- `medialake_stacks/api_gateway_deployment_stack.py` +
  `medialake_constructs/api_gateway/api_gateway_deployment_construct.py` — the single global
  deployment, force-redeploy custom resource, stage-name-to-SSM pattern.
- `medialake_stacks/base_infrastructure.py` — the data stores and their current
  `RemovalPolicy.DESTROY` settings.
- `medialake_stacks/user_interface_stack.py` — the existing SSM read pattern for the API stage
  name (the model to generalize in Phase 2).
- `config.py` — `stack_name`, `cfn_export`, `ssm_param`, `ssm_param_global`,
  `deployment_options.use_cli_credentials`, `use_prefixed_names`.

## Appendix B — The 500-resource limit (reference)

CloudFormation enforces a maximum of **500 resources per stack/template**, and this count
includes the supporting resources CDK generates automatically. Nested stacks are AWS's
recommended way to exceed it: each nested stack is its own template with its own 500 budget and
appears as a single resource in its parent. See AWS:
[Understand CloudFormation quotas](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html)
and [Keep an AWS CDK app within CloudFormation resource quotas](https://repost.aws/knowledge-center/cdk-application-cloudformation-quota).

_Content from external sources was rephrased for compliance with licensing restrictions._
