# Bedrock Prompt Selection UX Redesign

## Problem Statement

The current implementation has 4 independent optional fields for prompt selection, making it unclear to users which combination they should use. Users may wonder: "Do I need all three prompt fields?" or "What happens if I fill in both default and custom?"

## Solution: Three-Decision Flow with Conditional Fields

### Decision Hierarchy

1. **Which model?** (required)
2. **What is the content source?** (required)
3. **Where does the prompt come from?** (choose exactly one)
   - Use default prompt (system-defined)
   - Choose from saved prompts (pre-configured library)
   - Write a custom prompt (user-defined)

## New Schema Design

### YAML Configuration Structure

```yaml
parameters:
  - in: body
    name: model_id
    label: Bedrock Model
    required: true
    schema:
      type: select
      options: [...] # Model list with label/value pairs

  - in: body
    name: content_source
    label: Content Source
    required: true
    schema:
      type: select
      options: ["transcript", "proxy"]

  - in: body
    name: prompt_source
    label: Prompt Source
    required: true
    schema:
      type: radio
      options:
        - label: Use default prompt
          value: default
          help_text: "Recommended summary for most transcripts"
        - label: Choose from saved prompts
          value: saved
          help_text: "Use a prompt your team has already defined"
        - label: Write a custom prompt
          value: custom
          help_text: "Create new instructions for this node"
      default: default

  # Conditional field - only shown when prompt_source = "saved"
  - in: body
    name: saved_prompt_name
    label: Select Saved Prompt
    required: false
    schema:
      type: select
      options:
        - label: "Summary (100 words)"
          value: "summary_100"
        - label: "Describe Image"
          value: "describe_image"
        - label: "Extract Key Points"
          value: "extract_key_points"
        - label: "Analyze Sentiment"
          value: "analyze_sentiment"
    condition:
      field: prompt_source
      value: saved

  # Conditional fields - only shown when prompt_source = "custom"
  - in: body
    name: custom_prompt_label
    label: Prompt Label
    placeholder: "Name this prompt (e.g., 'Technical Documentation Summary')"
    required: false
    schema:
      type: text
    condition:
      field: prompt_source
      value: custom

  - in: body
    name: custom_prompt_text
    label: Prompt Text
    placeholder: "Enter instructions for the model..."
    required: false
    schema:
      type: textarea
      rows: 8
    condition:
      field: prompt_source
      value: custom
```

## Frontend Implementation

### Form State Management

```typescript
interface BedrockNodeConfig {
  // Configuration section
  model_id: string; // Required
  content_source: string; // Required

  // Prompt section
  prompt_source: "default" | "saved" | "custom"; // Required

  // Conditional fields
  saved_prompt_name?: string; // Only when prompt_source = 'saved'
  custom_prompt_label?: string; // Only when prompt_source = 'custom'
  custom_prompt_text?: string; // Only when prompt_source = 'custom'
}
```

### Validation Logic

```typescript
function validateBedrockConfig(config: BedrockNodeConfig): ValidationResult {
  const errors: string[] = [];

  // Required fields
  if (!config.model_id) errors.push("Bedrock Model is required");
  if (!config.content_source) errors.push("Content Source is required");
  if (!config.prompt_source) errors.push("Prompt Source is required");

  // Conditional validation based on prompt_source
  switch (config.prompt_source) {
    case "saved":
      if (!config.saved_prompt_name) {
        errors.push("Please select a saved prompt");
      }
      break;

    case "custom":
      if (!config.custom_prompt_label?.trim()) {
        errors.push("Prompt Label is required for custom prompts");
      }
      if (!config.custom_prompt_text?.trim()) {
        errors.push("Prompt Text is required for custom prompts");
      }
      break;

    case "default":
      // No additional validation needed
      break;
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
```

### UI Component Structure

```typescript
function BedrockNodeForm({ config, onChange }: Props) {
  return (
    <form>
      {/* Configuration Section */}
      <section>
        <h3>Configuration</h3>
        <FormSelect
          label="Bedrock Model *"
          name="model_id"
          value={config.model_id}
          options={bedrockModels}
          required
        />
        <FormSelect
          label="Content Source *"
          name="content_source"
          value={config.content_source}
          options={contentSources}
          required
        />
      </section>

      {/* Prompt Section */}
      <section>
        <h3>Prompt</h3>
        <FormRadioGroup
          label="Prompt Source *"
          name="prompt_source"
          value={config.prompt_source}
          options={[
            {
              value: 'default',
              label: 'Use default prompt',
              helpText: 'Recommended summary for most transcripts',
              preview: 'summary_100'
            },
            {
              value: 'saved',
              label: 'Choose from saved prompts',
              helpText: 'Use a prompt your team has already defined'
            },
            {
              value: 'custom',
              label: 'Write a custom prompt',
              helpText: 'Create new instructions for this node'
            }
          ]}
        />

        {/* Conditional: Saved Prompt Dropdown */}
        {config.prompt_source === 'saved' && (
          <FormSelect
            label="Select Saved Prompt *"
            name="saved_prompt_name"
            value={config.saved_prompt_name}
            options={savedPrompts}
            required
          />
        )}

        {/* Conditional: Custom Prompt Fields */}
        {config.prompt_source === 'custom' && (
          <>
            <FormInput
              label="Prompt Label *"
              name="custom_prompt_label"
              placeholder="Name this prompt (e.g., 'Technical Documentation Summary')"
              value={config.custom_prompt_label}
              required
            />
            <FormTextarea
              label="Prompt Text *"
              name="custom_prompt_text"
              placeholder="Enter instructions for the model..."
              value={config.custom_prompt_text}
              rows={8}
              required
            />
          </>
        )}
      </section>
    </form>
  );
}
```

## Lambda Handler Logic

### Parameter Extraction

```python
def extract_prompt_configuration(env_vars: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract and resolve prompt configuration based on prompt_source.

    Returns:
        {
            'prompt_text': str,      # The actual prompt to use
            'prompt_source': str,    # 'default', 'saved', or 'custom'
            'prompt_label': str,     # Label for DynamoDB storage
        }
    """
    prompt_source = env_vars.get("PROMPT_SOURCE", "default")

    if prompt_source == "default":
        return {
            'prompt_text': DEFAULT_PROMPTS["summary_100"],
            'prompt_source': 'default',
            'prompt_label': 'Summary100'  # For DynamoDB key
        }

    elif prompt_source == "saved":
        saved_prompt_name = env_vars.get("SAVED_PROMPT_NAME")
        if not saved_prompt_name:
            raise ValueError("SAVED_PROMPT_NAME required when PROMPT_SOURCE is 'saved'")

        if saved_prompt_name not in DEFAULT_PROMPTS:
            raise ValueError(f"Unknown saved prompt: {saved_prompt_name}")

        return {
            'prompt_text': DEFAULT_PROMPTS[saved_prompt_name],
            'prompt_source': 'saved',
            'prompt_label': _format_prompt_name_for_dynamo(saved_prompt_name)
        }

    elif prompt_source == "custom":
        custom_prompt_text = env_vars.get("CUSTOM_PROMPT_TEXT")
        custom_prompt_label = env_vars.get("CUSTOM_PROMPT_LABEL")

        if not custom_prompt_text or not custom_prompt_label:
            raise ValueError(
                "CUSTOM_PROMPT_TEXT and CUSTOM_PROMPT_LABEL required when PROMPT_SOURCE is 'custom'"
            )

        # Validate custom prompt
        sanitized_label = sanitize_prompt_label(custom_prompt_label)
        if not sanitized_label:
            raise ValueError(f"Invalid custom_prompt_label: '{custom_prompt_label}'")

        return {
            'prompt_text': custom_prompt_text.strip(),
            'prompt_source': 'custom',
            'prompt_label': sanitized_label
        }

    else:
        raise ValueError(f"Invalid PROMPT_SOURCE: {prompt_source}")
```

### Updated Handler Flow

```python
@lambda_handler
def lambda_handler(event, context):
    try:
        # Extract configuration
        model_id = os.getenv("MODEL_ID")
        content_src = os.getenv("CONTENT_SOURCE", "proxy")

        # Required validations
        if not model_id:
            raise ValueError("MODEL_ID environment variable is required")

        # Extract and resolve prompt configuration
        prompt_config = extract_prompt_configuration(os.environ)
        instr = prompt_config['prompt_text']
        prompt_label = prompt_config['prompt_label']

        logger.info(f"Using prompt source: {prompt_config['prompt_source']}")
        logger.info(f"Prompt label for DynamoDB: {prompt_label}")

        # ... rest of processing logic ...

        # Store result in DynamoDB with appropriate key
        dynamo_key = f"{prompt_label}Result"
        table.update_item(
            Key={"InventoryID": asset_id},
            UpdateExpression="SET #k = :v",
            ExpressionAttributeNames={"#k": dynamo_key},
            ExpressionAttributeValues={":v": result},
        )

        return {
            "statusCode": 200,
            "body": {
                "result": result,
                "prompt_source": prompt_config['prompt_source'],
                "prompt_label": prompt_label,
                # ... other fields ...
            }
        }

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
```

## Visual Layout

```
┌─────────────────────────────────────────────────────────┐
│ Configure Node – Bedrock Content Processor              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Configuration                                           │
│ ──────────────────────────────────────────────────     │
│                                                         │
│ Bedrock Model *                                         │
│ ┌────────────────────────────────────────────┐         │
│ │ Amazon Nova Pro v1 (us-east-1, us-west-2) ▼│         │
│ └────────────────────────────────────────────┘         │
│                                                         │
│ Content Source *                                        │
│ ┌────────────────────────────────────────────┐         │
│ │ transcript                                 ▼│         │
│ └────────────────────────────────────────────┘         │
│                                                         │
│ Prompt                                                  │
│ ──────────────────────────────────────────────────     │
│                                                         │
│ Prompt Source *                                         │
│                                                         │
│ ◉ Use default prompt                                   │
│   Recommended summary for most transcripts              │
│   └─ summary_100                                        │
│                                                         │
│ ○ Choose from saved prompts                             │
│   Use a prompt your team has already defined            │
│                                                         │
│ ○ Write a custom prompt                                 │
│   Create new instructions for this node                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                    [ Cancel ]  [ Save ] │
└─────────────────────────────────────────────────────────┘
```

### When "Choose from saved prompts" selected:

```
│ ◯ Use default prompt                                   │
│                                                         │
│ ◉ Choose from saved prompts                             │
│   Use a prompt your team has already defined            │
│   ┌────────────────────────────────────────────┐       │
│   │ Summary (100 words)                       ▼│       │
│   └────────────────────────────────────────────┘       │
│                                                         │
│ ○ Write a custom prompt                                 │
```

### When "Write a custom prompt" selected:

```
│ ◯ Use default prompt                                   │
│ ◯ Choose from saved prompts                             │
│                                                         │
│ ◉ Write a custom prompt                                 │
│   Create new instructions for this node                 │
│                                                         │
│   Prompt Label *                                        │
│   ┌────────────────────────────────────────────┐       │
│   │ Technical Documentation Summary            │       │
│   └────────────────────────────────────────────┘       │
│                                                         │
│   Prompt Text *                                         │
│   ┌────────────────────────────────────────────┐       │
│   │ You are a technical documentation          │       │
│   │ specialist. Summarize this content         │       │
│   │ focusing on:                                │       │
│   │ - Key technical concepts                    │       │
│   │ - Implementation details                    │       │
│   │ - Code examples and APIs                    │       │
│   └────────────────────────────────────────────┘       │
```

## Migration Strategy

### Phase 1: Backend Support (Non-Breaking)

1. Update Lambda to support both old and new parameter structures
2. Add `extract_prompt_configuration()` function with backward compatibility
3. Keep existing environment variable names working

### Phase 2: YAML Update

1. Add new `prompt_source` radio parameter
2. Add conditional rendering support to YAML schema
3. Mark old fields as deprecated but still functional

### Phase 3: Frontend Implementation

1. Implement radio group component with conditional fields
2. Add form state management for prompt_source
3. Update validation logic

### Phase 4: Migration Complete

1. Remove deprecated parameters from YAML
2. Remove backward compatibility code from Lambda
3. Update documentation

## Benefits

### User Experience

- **Clearer mental model**: One decision, not four independent fields
- **Reduced confusion**: Conditional visibility prevents "do I need all of these?"
- **Better guidance**: Help text explains each option
- **Validation feedback**: Clear error messages for missing required fields

### Technical

- **Explicit state**: No ambiguity about which prompt to use
- **Easier validation**: Single decision point with clear requirements
- **Better error handling**: Can validate based on prompt_source
- **Maintainable**: Adding new prompt types is straightforward

### Future Extensibility

- Easy to add new prompt sources (e.g., "Load from URL", "Use from template library")
- Can add preview/test functionality per source type
- Can add prompt versioning for saved prompts
- Can implement prompt sharing across team

## Implementation Checklist

- [ ] Update YAML with new parameter structure
- [ ] Add radio button support to form schema parser
- [ ] Implement conditional field rendering in DynamicForm
- [ ] Add `extract_prompt_configuration()` to Lambda
- [ ] Update validation logic in Lambda
- [ ] Add help text and microcopy
- [ ] Test all three prompt source flows
- [ ] Update user documentation
- [ ] Remove deprecated parameters
