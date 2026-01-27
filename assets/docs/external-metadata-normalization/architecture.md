# Metadata Normalizer Architecture

This document describes the architecture of MediaLake's metadata normalization system, which transforms source-specific metadata into MovieLabs MEC (Media Entertainment Core) v2.25 compliant format.

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Validation Layer](#validation-layer)
- [Adding a New Normalizer](#adding-a-new-normalizer)
- [Reusing Field Mappers](#reusing-field-mappers)
- [Testing Requirements for New Normalizers](#testing-requirements-for-new-normalizers)
- [Configuration Loading](#configuration-loading)
- [Performance Considerations](#performance-considerations)
- [Error Handling](#error-handling)
- [Related Documentation](#related-documentation)
- [Known Limitations](#known-limitations)

## Overview

The normalizer architecture is designed around three core principles:

1. **Pluggable Design**: Support multiple source formats through a common interface
2. **Configuration-Driven**: All customer-specific field names and mappings are defined in configuration, not code
3. **MEC Compliance**: Output follows MovieLabs MEC v2.25 schema structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    External_Metadata_Fetch_Node                      │
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │   Adapter    │───▶│  Normalizer      │───▶│  DynamoDB        │  │
│  │  (fetch)     │    │  Factory         │    │  Operations      │  │
│  └──────────────┘    └────────┬─────────┘    └──────────────────┘  │
│                               │                                      │
│                    ┌──────────▼─────────┐                           │
│                    │  Source Normalizer │                           │
│                    │  (pluggable)       │                           │
│                    └──────────┬─────────┘                           │
│                               │                                      │
│         ┌─────────────────────┼─────────────────────┐               │
│         ▼                     ▼                     ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ Generic XML  │    │ Future       │    │ Future       │          │
│  │ Normalizer   │    │ Normalizer B │    │ Normalizer C │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. SourceNormalizer Interface

The `SourceNormalizer` abstract base class defines the contract all normalizers must implement:

```python
from normalizers import SourceNormalizer, ValidationResult, NormalizationResult

class SourceNormalizer(ABC):
    """Abstract base class for source-specific metadata normalizers."""

    def __init__(self, config: dict | None = None):
        """Initialize with customer-specific configuration."""
        self.config = config or {}

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type identifier (e.g., 'generic_xml')."""
        pass

    @abstractmethod
    def validate_input(self, raw_metadata: dict) -> ValidationResult:
        """Validate source metadata structure before normalization."""
        pass

    @abstractmethod
    def normalize(self, raw_metadata: dict) -> NormalizationResult:
        """Transform source metadata to MEC-compliant format."""
        pass
```

### 2. Normalizer Factory

The factory pattern selects and instantiates the appropriate normalizer:

```python
from normalizers import create_normalizer

# Create normalizer with customer-specific configuration
config = {
    "source_namespace_prefix": "CUSTOMER",
    "identifier_mappings": {...},
    "title_mappings": {...},
}
normalizer = create_normalizer("generic_xml", config)
result = normalizer.normalize(raw_metadata)
```

### 3. Field Mappers

Modular mapping functions handle each field category:

| Module                     | Purpose                               |
| -------------------------- | ------------------------------------- |
| `map_identifiers.py`       | AltIdentifier elements (external IDs) |
| `map_titles.py`            | LocalizedInfo (titles, descriptions)  |
| `map_classifications.py`   | WorkType, genres                      |
| `map_hierarchy.py`         | SequenceInfo, Parent relationships    |
| `map_people.py`            | People/Job elements (cast & crew)     |
| `map_ratings.py`           | RatingSet elements                    |
| `map_technical.py`         | Video/Audio/Subtitle attributes       |
| `extract_custom_fields.py` | Unmapped field preservation           |

### 4. MEC Schema Models

Dataclass models represent the MEC output structure:

- `BasicMetadata` - Core content information
- `LocalizedInfo` - Language-specific titles and descriptions
- `Job` / `PersonName` - Cast and crew
- `Rating` - Content ratings
- `SequenceInfo` / `Parent` - Hierarchy
- `AltIdentifier` - External identifiers
- `VideoAttributes` / `AudioAttributes` / `SubtitleAttributes` - Technical specs

## Data Flow

```
Source XML/JSON → Adapter → Raw Dict → Normalizer → MEC-compliant Dict → DynamoDB
                              │
                              ▼
                    ┌─────────────────┐
                    │ Field Mappers   │
                    │ (config-driven) │
                    └─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              MEC Elements        Custom Fields
              (standard)          (unmapped)
```

## Validation Layer

The normalizer performs two-stage validation:

### Input Validation

- Required field presence (using configured field names)
- Data format validation (dates, years, durations)
- Structural integrity checks

### Output Validation

- MEC schema compliance
- Required MEC elements populated
- Data type and format validation

```python
# Validation result structure
@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue]  # warnings and errors

@dataclass
class ValidationIssue:
    severity: ValidationSeverity  # WARNING or ERROR
    field_path: str               # e.g., "ratings.0.value"
    message: str
    source_value: Any | None
```

## Adding a New Normalizer

To add support for a new metadata source format:

### Step 1: Create the Normalizer Class

```python
# lambdas/nodes/external_metadata_fetch/normalizers/my_source.py

from normalizers.base import SourceNormalizer, NormalizationResult, ValidationResult
from normalizers.mec_schema import BasicMetadata, NormalizedMetadata

class MySourceNormalizer(SourceNormalizer):
    """Normalizer for MySource metadata format."""

    def get_source_type(self) -> str:
        return "my_source"

    def validate_input(self, raw_metadata: dict) -> ValidationResult:
        """Validate MySource-specific structure."""
        result = ValidationResult(is_valid=True)

        # Check required fields using config
        id_field = self.config.get("primary_id_field", "id")
        if not raw_metadata.get(id_field):
            result.add_error(id_field, "Primary identifier is required")

        return result

    def normalize(self, raw_metadata: dict) -> NormalizationResult:
        """Transform MySource metadata to MEC format."""
        # Validate first
        validation = self.validate_input(raw_metadata)
        if not validation.is_valid:
            return NormalizationResult(success=False, validation=validation)

        try:
            # Use field mappers with config
            from normalizers.field_mappers import (
                map_identifiers, map_titles, map_people
            )

            basic = BasicMetadata(
                content_id=self._generate_content_id(raw_metadata),
                work_type=self._determine_work_type(raw_metadata),
                alt_identifiers=map_identifiers.map_all_identifiers(
                    raw_metadata, self.config
                ),
                # ... other mappings
            )

            normalized = NormalizedMetadata(basic_metadata=basic)

            return NormalizationResult(
                success=True,
                normalized_metadata=normalized.to_dict(),
                validation=validation
            )
        except Exception as e:
            validation.add_error("normalization", f"Failed: {e}")
            return NormalizationResult(success=False, validation=validation)
```

### Step 2: Register the Normalizer

```python
# In normalizers/__init__.py or at runtime

from normalizers import register_normalizer
from normalizers.my_source import MySourceNormalizer

register_normalizer("my_source", MySourceNormalizer)
```

### Step 3: Create Configuration

```json
{
  "source_type": "my_source",
  "config": {
    "source_namespace_prefix": "MYSOURCE",
    "primary_id_field": "content_id",
    "identifier_mappings": {
      "content_id": "",
      "external_ref": "-REF"
    },
    "title_mappings": {
      "title_field": "name",
      "description_field": "synopsis"
    }
  }
}
```

### Step 4: Write Tests

```python
# tests/nodes/external_metadata_fetch/test_my_source_normalizer.py

import pytest
from normalizers import create_normalizer

def test_my_source_normalizer_basic():
    config = {
        "source_namespace_prefix": "TEST",
        "primary_id_field": "id",
    }
    normalizer = create_normalizer("my_source", config)

    raw = {"id": "123", "name": "Test Content"}
    result = normalizer.normalize(raw)

    assert result.success
    assert result.normalized_metadata["BasicMetadata"]["ContentId"] == "123"
```

## Reusing Field Mappers

Existing field mappers are designed to be reusable across normalizers. They all accept a `config` parameter for field name lookups:

```python
from normalizers.field_mappers import map_identifiers, map_people, map_ratings

# All mappers use config for field names - no hardcoded values
identifiers = map_identifiers.map_all_identifiers(raw_metadata, config)
people = map_people.map_all_people(raw_metadata, config)
ratings = map_ratings.map_ratings(raw_metadata, config)
```

### Available Field Mappers

| Module                  | Function                               | Purpose                               | Config Keys Used                                 |
| ----------------------- | -------------------------------------- | ------------------------------------- | ------------------------------------------------ |
| `map_identifiers`       | `map_all_identifiers(raw, config)`     | External IDs → AltIdentifier          | `identifier_mappings`, `source_namespace_prefix` |
| `map_titles`            | `map_localized_info(raw, config)`      | Titles/descriptions → LocalizedInfo   | `title_mappings`, `default_language`             |
| `map_classifications`   | `get_work_type(raw, config)`           | Content type → WorkType               | `classification_mappings`                        |
| `map_hierarchy`         | `map_sequence_info(raw, config)`       | Episode/season numbers → SequenceInfo | `hierarchy_mappings`                             |
| `map_hierarchy`         | `map_parents(raw, config)`             | Relationships → Parent                | `hierarchy_mappings`                             |
| `map_hierarchy`         | `extract_parent_metadata(raw, config)` | Denormalized parent info              | `parent_metadata_mappings`                       |
| `map_people`            | `map_all_people(raw, config)`          | Cast/crew → People/Job                | `people_field_mappings`                          |
| `map_ratings`           | `map_ratings(raw, config)`             | Ratings → RatingSet                   | `rating_system_mappings`                         |
| `map_technical`         | `map_video_attributes(raw, config)`    | Video specs → VideoAttributes         | `technical_mappings`                             |
| `map_technical`         | `map_audio_attributes(raw, config)`    | Audio specs → AudioAttributes         | `technical_mappings`                             |
| `extract_custom_fields` | `extract(raw, config)`                 | Unmapped fields → CustomFields        | `custom_field_categories`                        |

### Mapper Reuse Example

```python
# In your new normalizer, reuse existing mappers with your config

from normalizers.field_mappers import (
    map_identifiers,
    map_titles,
    map_classifications,
    map_hierarchy,
    map_people,
    map_ratings,
    map_technical,
    extract_custom_fields
)

class MySourceNormalizer(SourceNormalizer):
    def normalize(self, raw_metadata: dict) -> NormalizationResult:
        # Reuse all existing mappers - they adapt to your config
        basic = BasicMetadata(
            content_id=self._generate_content_id(raw_metadata),
            work_type=map_classifications.get_work_type(raw_metadata, self.config)[0],
            localized_info=map_titles.map_localized_info(raw_metadata, self.config),
            alt_identifiers=map_identifiers.map_all_identifiers(raw_metadata, self.config),
            people=map_people.map_all_people(raw_metadata, self.config),
            ratings=map_ratings.map_ratings(raw_metadata, self.config),
            sequence_info=map_hierarchy.map_sequence_info(raw_metadata, self.config),
            parents=map_hierarchy.map_parents(raw_metadata, self.config),
        )

        # Add technical attributes if your source has them
        video_attrs = map_technical.map_video_attributes(raw_metadata, self.config)
        if video_attrs:
            basic.video_attributes = video_attrs

        # Capture unmapped fields
        custom_fields = extract_custom_fields.extract(raw_metadata, self.config)

        return NormalizationResult(
            success=True,
            normalized_metadata=NormalizedMetadata(
                basic_metadata=basic,
                custom_fields=custom_fields
            ).to_dict()
        )
```

### Creating Custom Mappers

If your source format has unique fields not covered by existing mappers:

```python
# normalizers/field_mappers/map_my_custom_fields.py

def map_custom_field(raw_metadata: dict, config: dict) -> dict:
    """Map source-specific fields that don't fit existing mappers."""
    field_name = config.get("my_custom_field", "custom_data")
    value = raw_metadata.get(field_name)

    if not value:
        return {}

    # Transform as needed
    return {
        "MyCustomField": value
    }
```

## Testing Requirements for New Normalizers

### Required Test Categories

1. **Unit Tests** - Test individual mapper functions
2. **Integration Tests** - Test complete normalization flow
3. **Sample-Based Tests** - Test with real (anonymized) sample data
4. **Validation Tests** - Test input/output validation

### Minimum Test Coverage

```python
# tests/nodes/external_metadata_fetch/test_my_source_normalizer.py

import pytest
from normalizers import create_normalizer

class TestMySourceNormalizer:
    """Test suite for MySource normalizer."""

    @pytest.fixture
    def config(self):
        """Sample configuration for testing."""
        return {
            "source_namespace_prefix": "TEST",
            "primary_id_field": "id",
            "identifier_mappings": {"id": "", "ref": "-REF"},
            "title_mappings": {"title_field": "name"},
        }

    @pytest.fixture
    def normalizer(self, config):
        return create_normalizer("my_source", config)

    # 1. Basic normalization
    def test_normalize_basic_content(self, normalizer):
        """Test normalization of minimal valid content."""
        raw = {"id": "123", "name": "Test Content"}
        result = normalizer.normalize(raw)

        assert result.success
        assert result.normalized_metadata["BasicMetadata"]["ContentId"] == "123"

    # 2. Input validation
    def test_validate_missing_required_field(self, normalizer):
        """Test validation fails for missing required fields."""
        raw = {"name": "No ID"}  # Missing id
        result = normalizer.validate_input(raw)

        assert not result.is_valid
        assert len(result.errors) > 0

    # 3. Empty/null handling
    def test_normalize_with_empty_fields(self, normalizer):
        """Test normalization handles empty fields gracefully."""
        raw = {"id": "123", "name": "", "description": None}
        result = normalizer.normalize(raw)

        assert result.success
        # Empty fields should be omitted, not stored as empty

    # 4. All field categories
    def test_normalize_identifiers(self, normalizer):
        """Test identifier mapping."""
        raw = {"id": "123", "ref": "REF456"}
        result = normalizer.normalize(raw)

        alt_ids = result.normalized_metadata["BasicMetadata"]["AltIdentifiers"]
        assert len(alt_ids) == 2

    def test_normalize_people(self, normalizer):
        """Test people/credits mapping."""
        raw = {
            "id": "123",
            "actors": [{"name": "John Actor", "order": 1}]
        }
        result = normalizer.normalize(raw)

        people = result.normalized_metadata["BasicMetadata"].get("People", [])
        assert len(people) > 0

    # 5. Error handling
    def test_normalize_malformed_input(self, normalizer):
        """Test handling of malformed input."""
        raw = None
        result = normalizer.normalize(raw)

        assert not result.success
        assert len(result.validation.errors) > 0

    # 6. Configuration variations
    def test_normalize_with_different_config(self):
        """Test normalizer adapts to different configurations."""
        config = {
            "source_namespace_prefix": "OTHER",
            "primary_id_field": "content_id",  # Different field name
        }
        normalizer = create_normalizer("my_source", config)

        raw = {"content_id": "ABC"}
        result = normalizer.normalize(raw)

        assert result.success
        assert result.normalized_metadata["BasicMetadata"]["ContentId"] == "ABC"
```

### Sample-Based Testing

Create anonymized test fixtures based on real source data:

```python
# tests/nodes/external_metadata_fetch/fixtures/my_source/

# sample_episode.json - Full episode with all fields
# sample_trailer.json - Minimal trailer content
# sample_special.json - Special content (recap, documentary)
```

```python
# Test with fixtures
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "my_source"

def test_normalize_sample_episode(normalizer):
    """Test normalization of full episode sample."""
    with open(FIXTURES_DIR / "sample_episode.json") as f:
        raw = json.load(f)

    result = normalizer.normalize(raw)

    assert result.success
    # Verify all expected fields are mapped
    basic = result.normalized_metadata["BasicMetadata"]
    assert basic["ContentId"]
    assert basic["WorkType"]
    assert basic["LocalizedInfo"]
```

### Performance Testing

```python
import time

def test_normalization_performance(normalizer):
    """Test normalization completes within performance target."""
    raw = load_large_sample()  # ~1MB payload

    start = time.perf_counter()
    result = normalizer.normalize(raw)
    elapsed = time.perf_counter() - start

    assert result.success
    assert elapsed < 0.1  # < 100ms target
```

## Configuration Loading

Configurations can be loaded from:

1. **Inline** - Directly in node configuration
2. **S3** - Referenced by path, loaded at runtime

```python
from normalizers import resolve_normalizer_config

# Supports both inline and S3-based configs
node_config = {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/customer-config.json",
    "config": {"include_raw_source": True}  # Optional overrides
}
resolved_config = resolve_normalizer_config(node_config)
```

## Performance Considerations

- Single asset normalization target: < 100ms
- No external API calls during normalization
- S3 configurations are cached (LRU cache)
- Performance metrics logged for monitoring

## Error Handling

The normalizer uses a structured error handling approach:

- **Validation errors** block normalization and return detailed issues
- **Validation warnings** allow normalization to proceed but are reported
- **Runtime exceptions** are caught and converted to validation errors

```python
result = normalizer.normalize(raw_metadata)

if not result.success:
    for error in result.validation.errors:
        print(f"Error at {error.field_path}: {error.message}")
    for warning in result.validation.warnings:
        print(f"Warning at {warning.field_path}: {warning.message}")
```

## Related Documentation

- [Field Mapping Reference](./field-mappings.md) - Source to MEC field mappings
- [Configuration Options](./configuration.md) - Complete configuration schema
- [MovieLabs MEC v2.25](https://movielabs.com/md/) - Official MEC specification

---

## Known Limitations

This section documents limitations, edge cases, and workarounds discovered during implementation.

### Fields Without Direct MEC Mapping

The following source fields cannot be perfectly mapped to MEC elements and are stored in `CustomFields`:

| Field                                  | Reason                                          | Storage Location                          |
| -------------------------------------- | ----------------------------------------------- | ----------------------------------------- |
| Platform-specific genres               | MEC Genre doesn't support platform attribution  | `CustomFields.platform_genres.{platform}` |
| `ad_category`, `ad_content_id`         | Advertising metadata not in MEC scope           | `CustomFields.advertising`                |
| `cue_points`, `adopportunitiesmarkers` | Ad insertion points not in MEC scope            | `CustomFields.advertising`                |
| `timelines`, `segments`, `markers`     | Timing data belongs in MMC spec, not MEC        | `CustomFields.timing`                     |
| `AFD` (Active Format Description)      | Broadcast-specific, no MEC equivalent           | `CustomFields.technical`                  |
| `needs_watermark`, `semitextless`      | Workflow/production flags, not content metadata | `CustomFields.technical`                  |
| `conform_materials_list`               | Production metadata, not content metadata       | `CustomFields.technical`                  |
| `season_count`, `episode_count`        | Aggregate values - MEC uses relationships       | `CustomFields` or `ParentMetadata`        |
| `placement`                            | Complex placement data, no MEC equivalent       | `CustomFields.other`                      |

### Edge Cases Requiring Special Handling

#### 1. Special Content (Season Recaps, Documentaries)

- **Pattern:** `season_number=99` indicates special content, not a real season
- **Handling:** Normalizer preserves the value; downstream systems should interpret 99 as "special"
- **Example:** Season recap content uses `season_number=99` with empty `episode_number`

#### 2. Trailers and Interstitials

- **Pattern:** `content_type=Interstitial` with `episode_number=0`
- **Handling:** Maps to `WorkType=Promotion`
- **Note:** Trailers have minimal cast/crew data (often just lead actor)

#### 3. Empty vs. Missing Fields

- **Behavior:** Empty fields are omitted from output (not stored as null/empty)
- **Rationale:** MEC schema prefers omission over empty values
- **Impact:** Downstream systems should use `.get()` with defaults

#### 4. Frame Rate Conversion

- **Source format:** Integer × 100 (e.g., `2400` for 24.00 fps)
- **Output format:** String with decimal (e.g., `"24.00"`)
- **Edge case:** `2997` converts to `"29.97"` (drop-frame)

#### 5. Resolution Parsing

- **Source format:** String like `"1920x1080"` or empty
- **Output format:** Separate `WidthPixels` and `HeightPixels` integers
- **Edge case:** Empty resolution results in omitted video dimensions

#### 6. Rating Descriptors

- **Source format:** Single string with concatenated codes (e.g., `"LSV"`)
- **Output format:** Single `Reason` element with the full string
- **Note:** MEC allows multiple `Reason` elements, but source provides single concatenated value

### Performance Considerations

#### Large Payloads

- **Target:** < 100ms normalization time per asset
- **Tested:** Up to 1MB metadata payloads
- **Bottleneck:** XML parsing for very large source documents
- **Mitigation:** No external API calls during normalization; all processing is in-memory

#### S3 Configuration Loading

- **Behavior:** Configurations loaded from S3 are cached (LRU cache)
- **Cache scope:** Per Lambda invocation (warm starts reuse cache)
- **Impact:** First request may be slower due to S3 fetch

#### Memory Usage

- **Behavior:** Entire source document loaded into memory
- **Limit:** Lambda memory allocation (default 256MB)
- **Recommendation:** Increase Lambda memory for very large metadata payloads

### Workarounds and Compromises

#### 1. DisplayName Requirement

- **Issue:** MEC requires `DisplayName` in `PersonName`, but source may only have first/last name
- **Workaround:** Construct `DisplayName` from `FirstGivenName` + `FamilyName` if not provided
- **Fallback:** Use `"Unknown"` if no name data available

#### 2. Region Requirement in Ratings

- **Issue:** MEC requires `Region` with `country` child in every `Rating`
- **Workaround:** Derive region from rating system using `rating_system_mappings` config
- **Fallback:** Use `"US"` if rating system not in mapping

#### 3. Content ID Generation

- **Issue:** MEC requires `ContentId`, but source may have multiple identifiers
- **Workaround:** Use `primary_id_field` config to specify which field to use
- **Fallback:** Use `ref_id_field` if primary is empty, then `"unknown"`

#### 4. Platform-Specific Genres

- **Issue:** MEC `Genre` element doesn't support platform attribution
- **Workaround:** Store primary genre in `LocalizedInfo/Genres`, platform-specific in `CustomFields`
- **Trade-off:** Platform genres not in standard MEC structure but preserved for downstream use

### Unsupported Features

The following features are not currently supported:

1. **XML Export:** The normalizer produces JSON output only. No XML serialization to MEC XML format.
2. **Round-Trip Validation:** No validation that output can be converted back to source format.
3. **MMC (Media Manifest Core):** File references and timing data are stored in custom fields, not MMC structure.
4. **Multi-Language LocalizedInfo:** Currently produces single `LocalizedInfo` with configured default language.
5. **Avails/Rights:** Rights and availability data is stored in custom fields, not MEC Avails structure.

### Future Considerations

1. **Movie Content:** Current implementation tested with TV episodes and trailers. Movie-specific fields may need additional handling.
2. **Season/Series Level Metadata:** Current focus is episode-level. Season and series entities may need dedicated normalizers.
3. **Additional Rating Systems:** New rating systems can be added via `rating_system_mappings` config without code changes.
4. **New Source Formats:** Architecture supports adding new normalizers for different source formats (JSON, different XML schemas).
