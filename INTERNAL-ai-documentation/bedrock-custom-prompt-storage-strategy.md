# Custom Prompt Storage Strategy: User-Friendly Labels with Data Protection

## Problem Statement

### Current Implementation Issues

1. **Data Loss**: All custom prompts write to same key `customPromptResult`
2. **No UI Display Names**: Keys like `exec-abc-123` are not user-friendly
3. **No Overwrite Protection**: Second execution overwrites first

### User Requirements

1. ✅ Friendly, meaningful names visible in UI
2. ✅ Prevent accidental data overwrites
3. ✅ Allow multiple custom prompt results per asset

---

## Recommended Solution: User-Defined Prompt Labels

### Architecture Overview

**Core Concept**: Users provide a meaningful label for each custom prompt execution. This label becomes both the storage key and the UI display name.

### User Experience Flow

```
1. User configures Bedrock node:
   ├─ Model: anthropic.claude-3-sonnet
   ├─ Custom Prompt: "Analyze this video for security vulnerabilities..."
   └─ Prompt Label: "Security Analysis" ← USER ENTERS THIS

2. System sanitizes label: "Security Analysis" → "SecurityAnalysis"

3. Creates DynamoDB key: "BedrockPrompt_SecurityAnalysis"

4. Before writing, checks if key exists:
   ├─ If exists → ERROR: "A result with label 'Security Analysis' already exists"
   └─ If not exists → Write result

5. UI displays result with friendly label: "Security Analysis"
```

---

## Implementation Design

### 1. YAML Configuration Changes

---

## Critical: Validation Order (Cost Optimization)

### Execution Flow: Validate BEFORE Expensive Operations

**IMPORTANT**: Label validation must happen **BEFORE** invoking Bedrock to avoid wasting money on API calls that will fail later.

```python
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: EARLY VALIDATION (Fast, No Cost)
        # ═══════════════════════════════════════════════════════════════════

        # 1.1 Extract parameters
        content_src = os.getenv("CONTENT_SOURCE", "proxy")
        prompt_name = os.getenv("PROMPT_NAME")
        custom_prompt = os.getenv("CUSTOM_PROMPT")
        prompt_label = os.getenv("PROMPT_LABEL")
        model_id = os.getenv("MODEL_ID")

        if not model_id:
            raise KeyError("MODEL_ID environment variable is required")

        # 1.2 Get asset ID early
        payload = event.get("payload", {})
        assets = payload.get("assets", [])
        if not assets:
            raise ValueError("No assets found in event.payload.assets")

        asset_id = assets[0].get("InventoryID")
        if not asset_id:
            raise ValueError("No InventoryID found in asset")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: LABEL VALIDATION (Fast DynamoDB Read, Minimal Cost)
        # Must happen BEFORE content processing and Bedrock invocation!
        # ═══════════════════════════════════════════════════════════════════

        dynamo_key = None

        if custom_prompt:
            # 2.1 Generate/validate label
            if not prompt_label:
                prompt_label = generate_default_label()
                logger.info(f"Generated default label: {prompt_label}")

            # 2.2 Sanitize label
            try:
                sanitized_label = sanitize_prompt_label(prompt_label)
            except ValueError as e:
                logger.error(f"Invalid label format: {e}")
                raise  # Fail fast - no need to proceed

            dynamo_key = f"BedrockPrompt_{sanitized_label}"

            # 2.3 CHECK IF KEY EXISTS (Critical validation point!)
            exists, existing_data = check_key_exists(table, asset_id, dynamo_key)

            if exists:
                # Fail fast with detailed error - BEFORE spending money on Bedrock
                pipeline_name = event.get("metadata", {}).get("execution", {}).get("Name", "Unknown")
                previous_pipeline = existing_data.get("pipeline_name", "Unknown")
                previous_timestamp = existing_data.get("timestamp", "Unknown")

                error_msg = (
                    f"❌ Label Conflict Detected - Operation Aborted\n\n"
                    f"A Bedrock result with label '{prompt_label}' already exists on this asset.\n\n"
                    f"Existing Result Details:\n"
                    f"  • Created by pipeline: {previous_pipeline}\n"
                    f"  • Timestamp: {previous_timestamp}\n"
                    f"  • Model: {existing_data.get('model_id', 'Unknown')}\n\n"
                    f"Current Pipeline: {pipeline_name}\n\n"
                    f"💡 Solutions:\n"
                    f"  1. Use a more specific label (e.g., '{prompt_label} - {pipeline_name}')\n"
                    f"  2. Delete the existing result if it should be replaced\n"
                    f"  3. Choose a different prompt label\n\n"
                    f"⚠️  This check prevented wasting costs on a Bedrock API call that would not be stored."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validation passed - safe to proceed
            instr = custom_prompt.strip()
            logger.info(f"✅ Label validation passed: '{prompt_label}' is available")

        elif prompt_name and prompt_name in DEFAULT_PROMPTS:
            # Pre-canned prompt - no label validation needed
            instr = DEFAULT_PROMPTS[prompt_name]
            formatted_prompt_name = _format_prompt_name_for_dynamo(prompt_name)
            dynamo_key = f"{formatted_prompt_name}Result"
            logger.info(f"Using pre-canned prompt: {prompt_name}")

        else:
            # Default fallback
            instr = os.getenv("PROMPT", DEFAULT_PROMPTS["summary_100"])
            dynamo_key = "Summary100Result"
            logger.info("Using default prompt: summary_100")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: CONTENT PROCESSING (Expensive - S3 reads, processing)
        # Only reached if validation passed!
        # ═══════════════════════════════════════════════════════════════════

        asset_detail = assets[0]

        # ... existing content loading logic ...
        # (content_src == "transcript" / "proxy" processing)

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 4: BEDROCK INVOCATION (Most Expensive - $$$)
        # Only reached if validation passed AND content loaded successfully!
        # ═══════════════════════════════════════════════════════════════════

        logger.info(f"Invoking Bedrock model: {model_id}")
        # ... bedrock invocation code ...

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 5: STORE RESULTS (Fast - DynamoDB write)
        # We know the key is valid because we checked in Phase 2
        # ═══════════════════════════════════════════════════════════════════

        result_data = {
            "result": result,
            "model_id": model_id,
            "timestamp": datetime.utcnow().isoformat(),
            "content_source": content_src,
        }

        if custom_prompt:
            result_data["prompt_type"] = "custom"
            result_data["prompt_label"] = prompt_label
            result_data["prompt_preview"] = custom_prompt[:200]
            result_data["pipeline_name"] = event.get("metadata", {}).get("execution", {}).get("Name")
        elif prompt_name:
            result_data["prompt_type"] = "pre_canned"
            result_data["prompt_name"] = prompt_name

        logger.info(f"Storing result with key: {dynamo_key}")
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET #k = :v",
            ExpressionAttributeNames={"#k": dynamo_key},
            ExpressionAttributeValues={":v": result_data}
        )

        # ... return response ...

    except ValueError as e:
        # Validation errors - no money wasted!
        logger.error(f"Validation failed: {e}")
        raise
    except Exception:
        logger.exception("Lambda failed")
        raise
```

### Cost Savings Diagram

```
Without Early Validation:
┌─────────────────┐
│ Start Lambda    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Load Content    │  ← Cost: S3 reads
│ from S3         │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Invoke Bedrock  │  ← Cost: $$$ (expensive!)
│ Process Content │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Try to store    │
│ with label      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ ❌ Label exists!│  ← Fail AFTER spending money
│ Throw error     │
└─────────────────┘

Total Waste: S3 read costs + Bedrock API costs + Lambda time


With Early Validation (Our Approach):
┌─────────────────┐
│ Start Lambda    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Extract params  │  ← Cost: Minimal (milliseconds)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Validate label  │  ← Cost: One DynamoDB read (~$0.0001)
│ Check exists?   │
└────────┬────────┘
         │
   ┌─────┴─────┐
   │           │
Exists      Available
   │           │
   ↓           ↓
┌──────┐  ┌─────────────────┐
│ Fail │  │ Load Content    │
│ Fast │  │ Invoke Bedrock  │
└──────┘  │ Store Result    │
          └─────────────────┘

Total Cost When Label Exists: ~$0.0001 (DynamoDB read only)
Savings: Avoided expensive Bedrock call + S3 reads
```

### Performance Impact

**DynamoDB Read Latency**: ~10-20ms
**Bedrock API Call**: 2-30 seconds + $$$ cost

**Result**: Early validation adds negligible latency but saves significant costs when labels conflict.

---

**File**: [`bedrock_content_processor.yaml`](s3_bucket_assets/pipeline_nodes/node_templates/utility/bedrock_content_processor.yaml:100)

```yaml
- in: body
  name: prompt_label
  label: Prompt Label (for custom prompts)
  description: A friendly name to identify this prompt result (e.g., "Marketing Summary")
  required: false
  schema:
    type: string
    maxLength: 50
  showWhen:
    field: custom_prompt
    hasValue: true

- in: body
  name: custom_prompt
  label: Custom Prompt (Optional - Overrides Default Prompts)
  required: false
  schema:
    type: string
    multiline: true
    rows: 6

- in: body
  name: prompt_name
  label: Default Prompt
  required: false
  schema:
    type: select
    options: [...]
```

**Conditional Display**: `prompt_label` only shows when `custom_prompt` has a value.

### 2. Label Sanitization Function

**File**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:298)

```python
import re

def sanitize_prompt_label(label: str) -> str:
    """
    Convert user-friendly label to DynamoDB-safe key.

    Examples:
        "Marketing Summary" → "MarketingSummary"
        "Security-Analysis_2024" → "SecurityAnalysis2024"
        "My Custom Prompt #1" → "MyCustomPrompt1"

    Rules:
        - Remove all non-alphanumeric characters except underscores
        - Remove leading/trailing whitespace
        - Capitalize first letter of each word
        - Max length: 50 characters
        - Must start with letter
    """
    if not label:
        raise ValueError("Prompt label cannot be empty")

    # Remove leading/trailing whitespace
    label = label.strip()

    # Replace spaces with nothing, capitalize words
    words = label.split()
    camel_case = ''.join(word.capitalize() for word in words)

    # Remove all non-alphanumeric characters except underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', camel_case)

    # Ensure starts with letter
    if not sanitized or not sanitized[0].isalpha():
        raise ValueError(f"Prompt label must start with a letter: '{label}'")

    # Truncate to max length
    sanitized = sanitized[:50]

    logger.info(f"Sanitized prompt label: '{label}' → '{sanitized}'")
    return sanitized


def generate_default_label() -> str:
    """
    Generate a default label when user doesn't provide one.
    Format: CustomPrompt_YYYYMMDD_HHMMSS
    """
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"CustomPrompt_{timestamp}"
```

### 3. Overwrite Protection Logic

```python
def check_key_exists(table, asset_id: str, key_name: str) -> tuple[bool, dict]:
    """
    Check if a DynamoDB key already exists for the asset.

    **IMPORTANT**: This check is ASSET-SCOPED, not pipeline-scoped.
    If ANY pipeline has already written a result with this label,
    it will be detected regardless of which pipeline is currently running.

    This is the CORRECT behavior because:
    1. Asset results should not have duplicate labels (confusing to users)
    2. Labels are meant to be meaningful identifiers, not pipeline-specific
    3. If different pipelines need different analyses, use different labels

---

## Cross-Pipeline Label Validation

### Design Decision: Asset-Scoped Labels

**IMPORTANT**: Label uniqueness is enforced at the **ASSET level**, NOT the pipeline level.

### How It Works

```

Asset: video-123

Pipeline A runs:
├─ Custom Prompt: "Create marketing summary"
├─ Prompt Label: "Marketing Summary"
└─ Result: Stored in BedrockPrompt_MarketingSummary ✅

Pipeline B tries to run:
├─ Custom Prompt: "Different marketing analysis"
├─ Prompt Label: "Marketing Summary" ← SAME LABEL
└─ Result: ❌ BLOCKED - Label already exists on this asset

```

### Rationale

**Why asset-scoped, not pipeline-scoped?**

1. **User Perspective**:
   - Users view results on ASSETS, not pipelines
   - Having multiple "Marketing Summary" results is confusing
   - Which one is the "real" marketing summary?

2. **Data Integrity**:
   - One label = One result per asset
   - Clear, unambiguous identification
   - No duplicate or conflicting analyses

3. **UI Clarity**:
   - Asset details show: "Marketing Summary", "Technical Review", "Security Analysis"
   - NOT: "Marketing Summary (Pipeline A)", "Marketing Summary (Pipeline B)"

### When Different Pipelines Need Similar Analyses

**Solution: Use Descriptive, Differentiated Labels**

**❌ Bad Approach** (causes conflicts):
```

Pipeline A: label = "Marketing Summary"
Pipeline B: label = "Marketing Summary" ← Conflict!

```

**✅ Good Approach** (descriptive labels):
```

Pipeline A: label = "Marketing Summary - Social Media"
Pipeline B: label = "Marketing Summary - Email Campaign"
Pipeline C: label = "Marketing Summary - Website"

```

**✅ Alternative Approach** (include pipeline name):
```

Pipeline A: label = "Social Media Analysis"
Pipeline B: label = "Email Campaign Analysis"

````

### Validation Flow with Enhanced Error Message

```python
def lambda_handler(event, context):
    # ... extract parameters ...

    if custom_prompt:
        sanitized_label = sanitize_prompt_label(prompt_label or generate_default_label())
        dynamo_key = f"BedrockPrompt_{sanitized_label}"

        # Check if label already exists on this asset
        exists, existing_data = check_key_exists(table, asset_id, dynamo_key)

        if exists:
            # Get pipeline information from event
            current_pipeline = event.get("metadata", {}).get("execution", {}).get("Name", "Unknown")
            previous_pipeline = existing_data.get("pipeline_name", "Unknown")
            previous_timestamp = existing_data.get("timestamp", "Unknown")

            raise ValueError(
                f"Label Conflict: A Bedrock result with label '{prompt_label}' already exists on this asset.\n\n"
                f"Existing result details:\n"
                f"  - Created by pipeline: {previous_pipeline}\n"
                f"  - Timestamp: {previous_timestamp}\n"
                f"  - Model used: {existing_data.get('model_id', 'Unknown')}\n\n"
                f"Current pipeline: {current_pipeline}\n\n"
                f"Solutions:\n"
                f"  1. Use a different, more specific label (e.g., '{prompt_label} - {current_pipeline}')\n"
                f"  2. Delete the existing result if it should be replaced\n"
                f"  3. Review if this pipeline should use a different prompt entirely\n\n"
                f"Note: Labels are unique per asset, regardless of which pipeline created them."
            )

        # Store with pipeline metadata
        result_data = {
            "result": result,
            "model_id": model_id,
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_type": "custom",
            "prompt_label": prompt_label,
            "prompt_preview": custom_prompt[:200],
            "pipeline_name": current_pipeline,  # Track which pipeline created this
            "pipeline_execution_id": event.get("metadata", {}).get("execution", {}).get("Id"),
            "content_source": content_src
        }
````

### Example Scenarios

#### Scenario 1: Intentional Duplicate (Should Fail)

```
Asset: product-demo.mp4

Week 1:
  Pipeline: "Content Analysis"
  Label: "Marketing Summary"
  Result: "Great for Q1 campaign..."
  ✅ Stored successfully

Week 2:
  Pipeline: "Monthly Review"
  Label: "Marketing Summary"  ← Trying to use same label
  Result: ❌ ERROR

Message: "Label 'Marketing Summary' already exists from pipeline
         'Content Analysis' created on 2024-01-15. Use a different
         label like 'Marketing Summary - Monthly Review'."
```

#### Scenario 2: Proper Differentiation (Should Succeed)

```
Asset: product-demo.mp4

Pipeline A: "Social Media Prep"
  Label: "Social Media Marketing"
  Result: ✅ Stored

Pipeline B: "Email Campaign Prep"
  Label: "Email Marketing"
  Result: ✅ Stored

Pipeline C: "Website Content"
  Label: "Web Marketing"
  Result: ✅ Stored
```

#### Scenario 3: Re-running Same Pipeline (Should Fail)

```
Asset: product-demo.mp4

Run 1:
  Pipeline: "Content Analysis"
  Label: "Marketing Summary"
  Result: ✅ Stored

Run 2: (re-run of same pipeline)
  Pipeline: "Content Analysis"
  Label: "Marketing Summary"
  Result: ❌ ERROR - Even same pipeline can't overwrite!

Message: "Label 'Marketing Summary' already exists from this pipeline
         created on 2024-01-15. If you want to update it, delete the
         existing result first, or use a versioned label like
         'Marketing Summary v2'."
```

### Override Mechanism (Advanced Feature)

**Optional Future Enhancement**: Add an `overwrite` flag for intentional updates:

```yaml
- in: body
  name: allow_overwrite
  label: Allow Overwrite (Advanced)
  description: If checked, will replace existing result with same label
  required: false
  schema:
    type: boolean
    default: false
```

```python
if custom_prompt:
    exists, existing_data = check_key_exists(table, asset_id, dynamo_key)
    allow_overwrite = os.getenv("ALLOW_OVERWRITE", "false").lower() == "true"

    if exists and not allow_overwrite:
        raise ValueError(f"Label '{prompt_label}' already exists...")

    if exists and allow_overwrite:
        logger.warning(f"OVERWRITING existing result with label '{prompt_label}'")
        # Archive old result before overwriting
        archive_previous_result(asset_id, dynamo_key, existing_data)
```

### Best Practices for Pipeline Authors

**1. Use Specific Labels**

```
✅ "Q1 Marketing Summary"
✅ "Technical Specs - API Review"
✅ "Security Analysis - PCI Compliance"

❌ "Summary"
❌ "Analysis"
❌ "Review"
```

**2. Include Context in Label**

```
✅ "Brand Guidelines Check - Logo Usage"
✅ "Content Moderation - Inappropriate Content"
✅ "Accessibility Review - WCAG 2.1"
```

**3. Version When Needed**

```
✅ "Marketing Summary v1"
✅ "Marketing Summary v2"
✅ "Marketing Summary - Updated Jan 2024"
```

**4. Document Pipeline Label Conventions**

```markdown
# Pipeline: Social Media Content Prep

## Bedrock Labels Used:

- "Social Media Summary" - Short-form summary
- "Hashtag Suggestions" - Recommended hashtags
- "Platform Recommendations" - Best platforms for content
```

### Monitoring & Alerts

**CloudWatch Metrics to Track:**

```python
# Track label conflicts
cloudwatch.put_metric_data(
    Namespace='MediaLake/Bedrock',
    MetricData=[
        {
            'MetricName': 'LabelConflicts',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'PipelineName', 'Value': pipeline_name},
                {'Name': 'Label', 'Value': prompt_label}
            ]
        }
    ]
)
```

**Alert on Repeated Conflicts:**

- If same pipeline repeatedly hits label conflicts
- May indicate pipeline misconfiguration
- May need label naming convention update

  Args:
  table: DynamoDB table resource
  asset_id: Asset InventoryID
  key_name: The field name to check

  Returns:
  tuple: (exists: bool, existing_data: dict or None) - exists: True if key exists and has a value - existing_data: The existing result data if found, None otherwise
  """
  try:
  response = table.get_item(
  Key={"InventoryID": asset_id},
  ProjectionExpression=key_name
  )
  item = response.get("Item", {})

        if key_name in item and item[key_name] is not None:
            existing_data = item[key_name]
            return True, existing_data
        return False, None

  except ClientError as e:
  if e.response["Error"]["Code"] == "ValidationException": # Key doesn't exist in schema
  return False, None
  raise

````

### 4. Updated Lambda Handler Logic

**File**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:609)

```python
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Event received", extra={"event": event})

        # Extract parameters
        content_src = os.getenv("CONTENT_SOURCE", "proxy")
        prompt_name = os.getenv("PROMPT_NAME")
        custom_prompt = os.getenv("CUSTOM_PROMPT")
        prompt_label = os.getenv("PROMPT_LABEL")
        model_id = os.getenv("MODEL_ID")

        if not model_id:
            raise KeyError("MODEL_ID environment variable is required")

        # Determine DynamoDB key and validate
        if custom_prompt:
            # Custom prompt requires a label
            if not prompt_label:
                prompt_label = generate_default_label()
                logger.info(f"Generated default prompt label: {prompt_label}")

            # Sanitize the label
            sanitized_label = sanitize_prompt_label(prompt_label)
            dynamo_key = f"BedrockPrompt_{sanitized_label}"

            # Check for existing key to prevent overwrite
            if check_key_exists(table, asset_id, dynamo_key):
                raise ValueError(
                    f"A Bedrock processing result with label '{prompt_label}' "
                    f"already exists for this asset. Please use a different label "
                    f"or delete the existing result first."
                )

            instr = custom_prompt.strip()
            logger.info(f"Using custom prompt with label: {prompt_label}")

        elif prompt_name and prompt_name in DEFAULT_PROMPTS:
            instr = DEFAULT_PROMPTS[prompt_name]
            formatted_prompt_name = _format_prompt_name_for_dynamo(prompt_name)
            dynamo_key = f"{formatted_prompt_name}Result"
            logger.info(f"Using pre-canned prompt: {prompt_name}")

        else:
            instr = os.getenv("PROMPT", DEFAULT_PROMPTS["summary_100"])
            dynamo_key = "Summary100Result"
            logger.info("Using default prompt: summary_100")

        # ... [rest of existing logic for content processing] ...

        # Store result with metadata
        result_data = {
            "result": result,
            "model_id": model_id,
            "timestamp": datetime.utcnow().isoformat(),
            "content_source": content_src
        }

        # Add prompt information
        if custom_prompt:
            result_data["prompt_type"] = "custom"
            result_data["prompt_label"] = prompt_label
            result_data["prompt_preview"] = custom_prompt[:200]
        elif prompt_name:
            result_data["prompt_type"] = "pre_canned"
            result_data["prompt_name"] = prompt_name

        logger.info(f"Storing result in DynamoDB key: {dynamo_key}")

        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET #k = :v",
            ExpressionAttributeNames={"#k": dynamo_key},
            ExpressionAttributeValues={":v": result_data}
        )

        # Return response
        updated = table.get_item(Key={"InventoryID": asset_id}).get("Item", {})
        return {
            "statusCode": 200,
            "body": {
                "result": result,
                "model_id": model_id,
                "prompt_label": prompt_label if custom_prompt else prompt_name,
                "dynamo_key": dynamo_key,
                "content_source": content_src,
                "asset_id": asset_id,
            },
            "updatedAsset": _strip_decimals(updated),
            "metadata": event.get("metadata", {}),
            "payload": event.get("payload", {}),
        }

    except ValueError as e:
        # Handle validation errors (duplicate labels, invalid formats)
        logger.error(f"Validation error: {e}")
        raise
    except Exception:
        logger.exception("Lambda failed – propagating error to Step Functions")
        raise
````

---

## DynamoDB Storage Structure

### Example Asset with Multiple Results

```json
{
  "InventoryID": "asset-123",
  "AssetType": "video",
  "Title": "Product Demo Video",

  // Pre-canned prompt results (backward compatible)
  "Summary100Result": {
    "result": "A 5-minute product demonstration...",
    "model_id": "amazon.nova-lite",
    "timestamp": "2024-01-15T10:00:00Z",
    "prompt_type": "pre_canned",
    "prompt_name": "summary_100"
  },

  "AnalyzeSentimentResult": {
    "result": "Overall sentiment: positive (85%)...",
    "model_id": "anthropic.claude-3-sonnet",
    "timestamp": "2024-01-15T10:05:00Z",
    "prompt_type": "pre_canned",
    "prompt_name": "analyze_sentiment"
  },

  // Custom prompt results with user-friendly labels
  "BedrockPrompt_MarketingSummary": {
    "result": "Perfect for social media! Key highlights include...",
    "model_id": "anthropic.claude-3-opus",
    "timestamp": "2024-01-15T11:30:00Z",
    "prompt_type": "custom",
    "prompt_label": "Marketing Summary",
    "prompt_preview": "Analyze this video and create a compelling marketing summary..."
  },

  "BedrockPrompt_TechnicalAnalysis": {
    "result": "Technical specifications demonstrated:\n1. API response time...",
    "model_id": "amazon.nova-pro",
    "timestamp": "2024-01-15T12:00:00Z",
    "prompt_type": "custom",
    "prompt_label": "Technical Analysis",
    "prompt_preview": "Extract all technical specifications and performance metrics..."
  },

  "BedrockPrompt_SecurityReview": {
    "result": "Security assessment:\n- No sensitive data exposed...",
    "model_id": "anthropic.claude-3-5-sonnet",
    "timestamp": "2024-01-15T14:30:00Z",
    "prompt_type": "custom",
    "prompt_label": "Security Review",
    "prompt_preview": "Review this video for any security concerns or sensitive information..."
  }
}
```

---

## UI Integration

### Display in Asset Details

```typescript
// Frontend code to display Bedrock results
interface BedrockResult {
  result: string;
  model_id: string;
  timestamp: string;
  prompt_type: "custom" | "pre_canned";
  prompt_label?: string;
  prompt_name?: string;
  prompt_preview?: string;
}

function getBedrockResults(asset: Asset): Array<{label: string, data: BedrockResult}> {
  const results = [];

  // Scan for all Bedrock result fields
  for (const [key, value] of Object.entries(asset)) {
    if (key.startsWith("BedrockPrompt_")) {
      // Custom prompt result
      const label = value.prompt_label || key.replace("BedrockPrompt_", "");
      results.push({ label, data: value as BedrockResult });
    } else if (key.endsWith("Result") && typeof value === "object" && value.prompt_type) {
      // Pre-canned prompt result
      const label = value.prompt_name || key.replace("Result", "");
      results.push({ label, data: value as BedrockResult });
    }
  }

  // Sort by timestamp (newest first)
  results.sort((a, b) =>
    new Date(b.data.timestamp).getTime() - new Date(a.data.timestamp).getTime()
  );

  return results;
}

// Example usage in UI component
function BedrockResultsPanel({ asset }: { asset: Asset }) {
  const results = getBedrockResults(asset);

  return (
    <div>
      <h3>Bedrock AI Analysis Results</h3>
      {results.map(({ label, data }) => (
        <div key={label} className="result-card">
          <h4>{label}</h4>
          <span className="metadata">
            Model: {data.model_id} |
            Time: {new Date(data.timestamp).toLocaleString()}
          </span>
          {data.prompt_preview && (
            <details>
              <summary>View Prompt</summary>
              <pre>{data.prompt_preview}</pre>
            </details>
          )}
          <div className="result-content">
            {data.result}
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## Label Validation Rules

### Valid Labels

```
✅ "Marketing Summary"      → BedrockPrompt_MarketingSummary
✅ "Security-Review"         → BedrockPrompt_SecurityReview
✅ "Q4_2024_Analysis"        → BedrockPrompt_Q42024Analysis
✅ "Technical Specs v2"      → BedrockPrompt_TechnicalSpecsV2
✅ "Brand Compliance Check"  → BedrockPrompt_BrandComplianceCheck
```

### Invalid Labels (Will Error)

```
❌ ""                       → Error: Empty label
❌ "123abc"                 → Error: Must start with letter
❌ "___test"                → Error: Must start with letter
❌ "A"*100                  → Error: Exceeds max length (50 chars)
❌ "!@#$%"                  → Error: No valid characters
```

---

## Overwrite Prevention Flow

```
┌─────────────────────────────────────────┐
│ User submits custom prompt with label   │
│ "Marketing Summary"                      │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│ Sanitize label                          │
│ "Marketing Summary" → "MarketingSummary"│
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│ Create DynamoDB key                     │
│ "BedrockPrompt_MarketingSummary"        │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│ Check if key exists in DynamoDB         │
└──────────────────┬──────────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    Key Exists          Key Not Exists
         │                   │
         ↓                   ↓
┌──────────────────┐  ┌──────────────────┐
│ Raise ValueError │  │ Process content  │
│ with clear msg   │  │ Store result     │
│                  │  │                  │
│ "A result with   │  │ Success! ✅      │
│ label 'Marketing │  │                  │
│ Summary' already │  │                  │
│ exists. Use      │  │                  │
│ different label."│  │                  │
└──────────────────┘  └──────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ User sees error in pipeline execution    │
│ Must choose different label or delete    │
│ existing result                          │
└──────────────────────────────────────────┘
```

---

## Error Messages

### User-Friendly Error Responses

```python
# Duplicate label error
raise ValueError(
    f"A Bedrock processing result with label '{prompt_label}' already exists "
    f"for this asset. Please use a different label or delete the existing result first.\n"
    f"Existing result key: {dynamo_key}"
)

# Invalid label format error
raise ValueError(
    f"Invalid prompt label format: '{prompt_label}'. "
    f"Labels must start with a letter and contain only letters, numbers, and underscores. "
    f"Examples: 'Marketing Summary', 'Technical Review', 'Q4 Analysis'"
)

# Empty label error
raise ValueError(
    "Prompt label is required when using custom prompts. "
    "Please provide a meaningful label like 'Marketing Summary' or 'Technical Analysis'."
)
```

---

## Testing Scenarios

### Test 1: Unique Labels Work

```python
# First execution
custom_prompt="Summarize for marketing"
prompt_label="Marketing Summary"
# Result: Stored in BedrockPrompt_MarketingSummary ✅

# Second execution (different label)
custom_prompt="Extract technical details"
prompt_label="Technical Analysis"
# Result: Stored in BedrockPrompt_TechnicalAnalysis ✅
```

### Test 2: Duplicate Labels Blocked

```python
# First execution
custom_prompt="Analysis v1"
prompt_label="Security Review"
# Result: Stored successfully ✅

# Second execution (same label)
custom_prompt="Analysis v2"
prompt_label="Security Review"
# Result: ValueError raised ❌
# Message: "A result with label 'Security Review' already exists..."
```

### Test 3: Auto-Generated Labels

```python
# No label provided
custom_prompt="Some analysis"
prompt_label=None
# System generates: "CustomPrompt_20240115_103045"
# Result: Stored in BedrockPrompt_CustomPrompt20240115103045 ✅
```

### Test 4: Label Sanitization

```python
# Various label formats
"Marketing Summary"    → BedrockPrompt_MarketingSummary
"Q4-2024 Analysis"     → BedrockPrompt_Q42024Analysis
"Security Review #1"   → BedrockPrompt_SecurityReview1
"My Custom Prompt!!!"  → BedrockPrompt_MyCustomPrompt
```

---

## Migration from Existing Implementation

### Step 1: Update YAML Configuration

- Add `prompt_label` parameter
- Make it conditional on `custom_prompt` presence

### Step 2: Update Lambda Handler

- Add label sanitization function
- Add overwrite check function
- Update storage logic

### Step 3: Handle Existing Data

```python
# Existing customPromptResult field is not affected
# New executions use labeled keys
# UI can display both old and new formats
```

---

## Advantages of This Approach

1. **✅ User-Friendly**: Labels like "Marketing Summary" are meaningful
2. **✅ No Data Loss**: Each label gets unique key, overwrite protection
3. **✅ UI-Ready**: Labels display directly without transformation
4. **✅ Backward Compatible**: Pre-canned prompts unchanged
5. **✅ Flexible**: Auto-generation available if user doesn't provide label
6. **✅ Queryable**: Easy to find specific results by label
7. **✅ Safe**: Validation prevents invalid or duplicate labels

---

## Summary

### Key Changes Required

1. **YAML**: Add `prompt_label` parameter (conditional on custom_prompt)
2. **Lambda**: Add 3 new functions (~60 lines of code)
   - `sanitize_prompt_label()`
   - `generate_default_label()`
   - `check_key_exists()`
3. **Storage**: Use pattern `BedrockPrompt_{SanitizedLabel}`
4. **UI**: Display `prompt_label` as-is from stored data

### User Experience

```
User configures:
├─ Custom Prompt: "Analyze for compliance issues..."
└─ Prompt Label: "Compliance Review"

System stores in: BedrockPrompt_ComplianceReview

UI displays: "Compliance Review" with timestamp and result
```

This design provides the best balance of usability, safety, and maintainability.
