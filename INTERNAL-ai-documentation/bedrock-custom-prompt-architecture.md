# Bedrock Content Processor: Custom Prompt Architecture

## Overview

Enhancement to the Bedrock Content Processor node to support user-defined custom prompts that override pre-canned prompt templates.

## Current Architecture

### Prompt Resolution Flow

```
Environment Variables → Prompt Selection Logic
         ↓
    PROMPT_NAME env var
         ↓
    DEFAULT_PROMPTS lookup → Bedrock API
         ↓ (fallback)
    PROMPT env var or default
```

### Limitations

- Only supports pre-defined prompts via dropdown selection
- No user-customizable prompt input
- Custom prompts require environment variable manipulation

## Proposed Architecture

### Enhanced Prompt Resolution Hierarchy

```
User Input (YAML Config)
    ↓
Environment Variables (CUSTOM_PROMPT, PROMPT_NAME, PROMPT)
    ↓
┌──────────────────────────────────────────────────────┐
│         Prompt Resolution Logic                      │
│                                                       │
│  Priority Order:                                     │
│  1. CUSTOM_PROMPT (if provided) ← HIGHEST PRIORITY   │
│  2. PROMPT_NAME → DEFAULT_PROMPTS lookup             │
│  3. PROMPT env var (legacy)                          │
│  4. DEFAULT_PROMPTS["summary_100"] (hardcoded)       │
└──────────────────────────────────────────────────────┘
    ↓
Bedrock API Invocation
    ↓
DynamoDB Storage (customPromptResult key)
```

## Design Decisions

### Decision 1: Custom Prompt Takes Precedence

**Rationale**: User-provided custom prompts indicate specific requirements that should override any pre-selected templates.

**Implementation**: Check `CUSTOM_PROMPT` environment variable first before falling back to `prompt_name` logic.

**Impact**: Maintains backward compatibility while enabling advanced use cases.

### Decision 2: Textarea Input Type

**Rationale**:

- Prompts often require multi-line formatting
- Better UX for entering complex instructions
- Allows markdown-style formatting in prompts

**Implementation Strategy**: The form system already supports textarea through Material-UI's TextField component:

- [`FormFieldDefinition`](medialake_user_interface/src/forms/types.ts:22) includes `multiline` and `rows` properties
- [`FormField`](medialake_user_interface/src/forms/components/FormField.tsx:60) uses Material-UI TextField which supports `multiline` prop
- Properties are passed through via `...rest` spread operator

**Schema Configuration**: Use `type: string` with additional properties:

```yaml
schema:
  type: string
  multiline: true
  rows: 6
```

### Decision 3: Both Parameters Remain Optional

**Rationale**:

- Maintains backward compatibility
- Provides sensible defaults
- Allows gradual adoption

**Default Behavior**: Falls back to `summary_100` if neither custom nor pre-canned prompt is provided.

### Decision 4: DynamoDB Storage Strategy

**Current Logic** (lines 775-782 in [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:775)):

```python
formatted_prompt_name = _format_prompt_name_for_dynamo(prompt_name) if prompt_name else None
dynamo_key = f"{formatted_prompt_name}Result" if formatted_prompt_name else "customPromptResult"
```

**Behavior with Custom Prompt**:

- When `custom_prompt` is used, `prompt_name` will be `None`
- Result stored in DynamoDB field: `"customPromptResult"`
- This is appropriate as custom prompts are user-defined

**No Changes Required**: Existing logic already handles custom prompts correctly.

## Component Changes

### 1. YAML Configuration Schema

**File**: [`bedrock_content_processor.yaml`](s3_bucket_assets/pipeline_nodes/node_templates/utility/bedrock_content_processor.yaml:100)

**Change**: Uncomment and configure custom_prompt parameter (lines 100-105)

```yaml
- in: body
  name: custom_prompt
  label: Custom Prompt (Optional - Overrides Default Prompts)
  required: false
  schema:
    type: string
    multiline: true
    rows: 6
```

**Placement**: Insert between `prompt_name` (line 88) and `content_source` (line 107)

**UI Rendering Flow**:

1. YAML `schema.type: string` → [`mapParameterTypeToFormType()`](medialake_user_interface/src/features/pipelines/components/PipelineEditor/NodeConfigurationForm.tsx:21) → `type: "text"`
2. `schema.multiline: true` and `schema.rows: 6` → Passed through to [`FormField`](medialake_user_interface/src/forms/components/FormField.tsx:60)
3. Material-UI [`TextField`](medialake_user_interface/src/forms/components/FormField.tsx:60) component receives `multiline={true}` and `rows={6}`
4. Result: Multi-line textarea with 6 rows

### 2. Lambda Handler Logic

**File**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:609)

**Current Logic** (lines 609-619):

```python
content_src = os.getenv("CONTENT_SOURCE", "proxy")
prompt_name = os.getenv("PROMPT_NAME")
model_id = os.getenv("MODEL_ID")

if not model_id:
    raise KeyError("MODEL_ID environment variable is required")

# Get instruction/prompt
instr = DEFAULT_PROMPTS.get(prompt_name) or os.getenv(
    "PROMPT", DEFAULT_PROMPTS["summary_100"]
)
```

**Proposed Logic**:

```python
content_src = os.getenv("CONTENT_SOURCE", "proxy")
prompt_name = os.getenv("PROMPT_NAME")
custom_prompt = os.getenv("CUSTOM_PROMPT")
model_id = os.getenv("MODEL_ID")

if not model_id:
    raise KeyError("MODEL_ID environment variable is required")

# Prompt resolution with priority hierarchy
if custom_prompt:
    instr = custom_prompt.strip()
    logger.info("Using custom prompt override")
elif prompt_name and prompt_name in DEFAULT_PROMPTS:
    instr = DEFAULT_PROMPTS[prompt_name]
    logger.info(f"Using pre-canned prompt: {prompt_name}")
else:
    instr = os.getenv("PROMPT", DEFAULT_PROMPTS["summary_100"])
    logger.info("Using default prompt: summary_100")
```

## UI Form System Integration

### Form Field Type Mapping

The UI uses [`NodeConfigurationForm`](medialake_user_interface/src/features/pipelines/components/PipelineEditor/NodeConfigurationForm.tsx:21) to render node parameters. The type mapping function handles schema types:

```typescript
const mapParameterTypeToFormType = (
  type: string,
): FormFieldDefinition["type"] => {
  switch (type) {
    case "boolean":
      return "switch";
    case "number":
    case "integer":
      return "number";
    case "select":
      return "select";
    default:
      return "text"; // ← "string" type maps to "text"
  }
};
```

### Textarea Support

The form system supports textarea through **additional properties** on the schema:

**From YAML Schema** → **To Form Field**:

```typescript
{
  name: "custom_prompt",
  schema: {
    type: "string",      // Maps to FormField type="text"
    multiline: true,     // Passed to TextField multiline prop
    rows: 6              // Passed to TextField rows prop
  }
}
```

**Field Definition** (line 378-384):

```typescript
const field: FormFieldDefinition = {
  name: `parameters.${param.name}`,
  type: mapParameterTypeToFormType(param.schema?.type || "string"),
  label: param.label || param.name,
  required: param.required,
  tooltip: param.description,
};
```

**Additional Properties**: The `multiline` and `rows` properties from the schema are preserved and passed through to the Material-UI TextField component via the spread operator in [`FormField`](medialake_user_interface/src/forms/components/FormField.tsx:62):

```typescript
<TextField
  {...field}
  {...rest}  // ← multiline and rows pass through here
  type={type}
  label={fieldLabel}
  // ...
/>
```

### Type Definition Support

The [`FormFieldDefinition`](medialake_user_interface/src/forms/types.ts:22) interface already includes:

```typescript
export interface FormFieldDefinition {
  name: string;
  type:
    | "text"
    | "email"
    | "select"
    | "multiselect"
    | "switch"
    | "number"
    | "password";
  label: string;
  tooltip?: string;
  required?: boolean;
  multiline?: boolean; // ← Textarea support
  rows?: number; // ← Row count for textarea
  // ...
}
```

### Processing Flow

```
YAML Node Template (custom_prompt parameter)
    ↓
Lambda Environment (CUSTOM_PROMPT env var)
    ↓
Backend API Response (parameter schema with multiline: true)
    ↓
NodeConfigurationForm effectiveParameters
    ↓
mapParameterTypeToFormType("string") → "text"
    ↓
FormField with multiline={true} rows={6}
    ↓
Material-UI TextField (textarea rendered)
    ↓
User Input → Form Submission
    ↓
configuration.parameters.custom_prompt
    ↓
Lambda Handler (os.getenv("CUSTOM_PROMPT"))
```

## Data Flow Diagram

```
┌─────────────────┐
│  User Interface │
│   (Pipeline UI) │
└────────┬────────┘
         │
         ├─→ model_id (required)
         ├─→ custom_prompt (optional) ← NEW
         ├─→ prompt_name (optional)
         └─→ content_source (required)
         │
         ↓
┌────────────────────────────────────┐
│  Lambda Environment Variables      │
│  - MODEL_ID                        │
│  - CUSTOM_PROMPT ← NEW             │
│  - PROMPT_NAME                     │
│  - CONTENT_SOURCE                  │
└────────┬───────────────────────────┘
         │
         ↓
┌────────────────────────────────────┐
│  Prompt Resolution                 │
│  if CUSTOM_PROMPT: use it          │
│  elif PROMPT_NAME: lookup default  │
│  else: use fallback                │
└────────┬───────────────────────────┘
         │
         ↓
┌────────────────────────────────────┐
│  Build Bedrock Request Body        │
│  - model_id                        │
│  - instr (resolved prompt)         │
│  - content (from source)           │
└────────┬───────────────────────────┘
         │
         ↓
┌────────────────────────────────────┐
│  Invoke Bedrock API                │
│  - With retry logic                │
│  - Handle chunking if needed       │
└────────┬───────────────────────────┘
         │
         ↓
┌────────────────────────────────────┐
│  Store Result in DynamoDB          │
│  Key: customPromptResult (if       │
│       custom_prompt used)          │
│  Key: {PromptName}Result (if       │
│       pre-canned used)             │
└────────────────────────────────────┘
```

## Interface Contract

### Input Parameters

| Parameter        | Type     | Required | Description                                   |
| ---------------- | -------- | -------- | --------------------------------------------- |
| `model_id`       | select   | Yes      | Bedrock model to use                          |
| `custom_prompt`  | textarea | No       | User-defined prompt (overrides `prompt_name`) |
| `prompt_name`    | select   | No       | Pre-canned prompt selection                   |
| `content_source` | select   | Yes      | Source of content (transcript/proxy)          |

### Prompt Resolution Logic

```python
def resolve_prompt(custom_prompt: str, prompt_name: str) -> str:
    """
    Resolve the prompt to use for Bedrock invocation.

    Priority:
    1. custom_prompt (user-defined)
    2. prompt_name (pre-canned)
    3. default (summary_100)
    """
    if custom_prompt:
        return custom_prompt.strip()

    if prompt_name and prompt_name in DEFAULT_PROMPTS:
        return DEFAULT_PROMPTS[prompt_name]

    return DEFAULT_PROMPTS["summary_100"]
```

## Migration Strategy

### Backward Compatibility

- ✅ Existing pipelines using `prompt_name` continue to work
- ✅ No breaking changes to API contract
- ✅ Default behavior unchanged when neither parameter provided

### User Migration Path

1. **Phase 1**: Deploy updated YAML and Lambda
2. **Phase 2**: Users can optionally add `custom_prompt` to pipeline nodes
3. **Phase 3**: System operates with both mechanisms simultaneously

## Testing Scenarios

### Test Case 1: Custom Prompt Override

**Input**:

- `custom_prompt`: "Analyze this content for security vulnerabilities"
- `prompt_name`: "summary_100"

**Expected**: Uses custom prompt, ignores prompt_name

### Test Case 2: Pre-canned Prompt Only

**Input**:

- `custom_prompt`: (empty)
- `prompt_name`: "analyze_sentiment"

**Expected**: Uses pre-canned "analyze_sentiment" prompt

### Test Case 3: Neither Provided

**Input**:

- `custom_prompt`: (empty)
- `prompt_name`: (empty)

**Expected**: Uses default "summary_100" prompt

### Test Case 4: Invalid Prompt Name

**Input**:

- `custom_prompt`: (empty)
- `prompt_name`: "invalid_prompt"

**Expected**: Falls back to "summary_100" with warning log

## Security Considerations

### Prompt Injection

**Risk**: Users could craft malicious prompts to extract sensitive information or manipulate model behavior.

**Mitigation**:

- Lambda operates in isolated environment
- Bedrock models have built-in safety guardrails
- Results stored per-asset, scoped by user permissions

### Input Validation

**Implementation**: Add basic validation to reject excessively large prompts:

```python
MAX_CUSTOM_PROMPT_LENGTH = 10000  # characters

if custom_prompt and len(custom_prompt) > MAX_CUSTOM_PROMPT_LENGTH:
    raise ValueError(
        f"Custom prompt too large: {len(custom_prompt)} chars "
        f"(max: {MAX_CUSTOM_PROMPT_LENGTH})"
    )
```

## Monitoring & Observability

### New Log Entries

```python
logger.info("Using custom prompt override")
logger.info(f"Using pre-canned prompt: {prompt_name}")
logger.info("Using default prompt: summary_100")
```

### Metrics to Track

- Custom prompt usage rate
- Custom prompt length distribution
- Error rates by prompt type
- DynamoDB write patterns (customPromptResult field)

## Future Enhancements

### Phase 2: Prompt Library

- Allow users to save custom prompts for reuse
- Create organizational prompt templates
- Version control for prompts

### Phase 3: Prompt Validation

- Syntax checking for prompt structure
- Variable substitution support
- Template-based custom prompts

### Phase 4: A/B Testing

- Compare custom vs pre-canned prompt results
- Quality metrics for different prompt strategies
- Automated prompt optimization

## References

- **YAML Config**: [`bedrock_content_processor.yaml`](s3_bucket_assets/pipeline_nodes/node_templates/utility/bedrock_content_processor.yaml:1)
- **Lambda Handler**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:604)
- **DEFAULT_PROMPTS**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:32)
- **DynamoDB Storage**: [`index.py`](lambdas/nodes/bedrock_content_processor/index.py:775)
