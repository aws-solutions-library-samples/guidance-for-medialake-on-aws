# Normalizer Configuration Reference

This document provides a complete reference for configuring the metadata normalizer, including all available options and example configurations.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Configuration Schema](#configuration-schema)
  - [Core Settings](#core-settings)
  - [Identifier Mappings](#identifier-mappings)
  - [Title Mappings](#title-mappings)
  - [Classification Mappings](#classification-mappings)
  - [Hierarchy Mappings](#hierarchy-mappings)
  - [Parent Metadata Mappings](#parent-metadata-mappings)
  - [People Field Mappings](#people-field-mappings)
  - [Rating System Mappings](#rating-system-mappings)
  - [Technical Mappings](#technical-mappings)
  - [Custom Field Categories](#custom-field-categories)
  - [Temporal Field Mappings](#temporal-field-mappings)
  - [Geographic/Linguistic Mappings](#geographiclinguistic-mappings)
- [Complete Configuration Example](#complete-configuration-example)
- [S3 Configuration Storage](#s3-configuration-storage)
- [Validation and Defaults](#validation-and-defaults)
- [Related Documentation](#related-documentation)

## Configuration Overview

The normalizer is fully configuration-driven. All customer-specific field names, namespace prefixes, and mapping rules are defined in configuration, not in code.

### Configuration Sources

Configuration can be provided in two ways:

1. **Inline Configuration** - Directly in the node configuration
2. **S3-Based Configuration** - Referenced by path, loaded at runtime

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/customer-config.json",
    "config": {
      "include_raw_source": true
    }
  }
}
```

When both are provided, inline config values override S3 config values.

## Configuration Schema

### Core Settings

| Property                  | Type    | Default    | Description                                     |
| ------------------------- | ------- | ---------- | ----------------------------------------------- |
| `source_namespace_prefix` | string  | `"SOURCE"` | Customer namespace prefix for identifiers       |
| `default_language`        | string  | `"en-US"`  | Default language code for LocalizedInfo         |
| `primary_id_field`        | string  | `"id"`     | Field name for primary content identifier       |
| `ref_id_field`            | string  | `"ref_id"` | Field name for reference/correlation ID         |
| `include_raw_source`      | boolean | `false`    | Include original source in output for debugging |

### Identifier Mappings

Maps source identifier fields to MEC AltIdentifier namespaces.

```json
{
  "identifier_mappings": {
    "field_name": "namespace_suffix"
  }
}
```

**Namespace Suffix Rules:**

- `""` (empty) → Uses `source_namespace_prefix` directly
- `"-SUFFIX"` → Appends to prefix (e.g., `"CUSTOMER-SUFFIX"`)
- `"ABSOLUTE"` → Uses as-is (no prefix)

**Example:**

```json
{
  "source_namespace_prefix": "CUSTOMER",
  "identifier_mappings": {
    "content_id": "",
    "reference_id": "-REF",
    "version_id": "-VERSION",
    "sequence_id": "-SEQ",
    "gracenote_series_id": "TMS",
    "gracenote_episode_id": "TMS",
    "ad_content_id": "-AD"
  }
}
```

### Title Mappings

Maps source title and description fields to MEC LocalizedInfo elements.

| Property                   | Type   | Default                | Description            |
| -------------------------- | ------ | ---------------------- | ---------------------- |
| `title_field`              | string | `"title"`              | Full title field       |
| `title_brief_field`        | string | `"titlebrief"`         | Short title field      |
| `short_description_field`  | string | `"short_description"`  | Short summary field    |
| `medium_description_field` | string | `"medium_description"` | Medium summary field   |
| `long_description_field`   | string | `"long_description"`   | Full description field |
| `copyright_field`          | string | `"copyright_holder"`   | Copyright notice field |
| `keywords_field`           | string | `"keywords"`           | Keywords field         |

**Example:**

```json
{
  "title_mappings": {
    "title_field": "episode_title",
    "title_brief_field": "short_title",
    "short_description_field": "synopsis_short",
    "long_description_field": "synopsis_full"
  }
}
```

### Classification Mappings

Maps content type and genre fields.

| Property               | Type   | Default          | Description                                  |
| ---------------------- | ------ | ---------------- | -------------------------------------------- |
| `is_movie_field`       | string | `"is_movie"`     | Boolean field for movie detection            |
| `content_type_field`   | string | `"content_type"` | Content type field                           |
| `video_type_field`     | string | `"video_type"`   | Video type detail field                      |
| `genres_field`         | string | `"genres"`       | Genres container field                       |
| `genre_type_attr`      | string | `"@type"`        | Genre type attribute (for platform-specific) |
| `genre_text_key`       | string | `"#text"`        | Genre text content key                       |
| `platform_genre_types` | array  | `[]`             | Platform types to extract to custom fields   |

**Example:**

```json
{
  "classification_mappings": {
    "is_movie_field": "is_movie",
    "content_type_field": "content_type",
    "video_type_field": "video_type",
    "genres_field": "genres",
    "genre_type_attr": "@type",
    "genre_text_key": "#text"
  },
  "platform_genre_types": ["Amazon", "Apple", "Roku", "SN Series"]
}
```

### Hierarchy Mappings

Maps episode/season/series hierarchy fields.

| Property               | Type   | Default            | Description             |
| ---------------------- | ------ | ------------------ | ----------------------- |
| `episode_number_field` | string | `"episode_number"` | Episode number field    |
| `season_number_field`  | string | `"season_number"`  | Season number field     |
| `series_id_field`      | string | `"tms_series_id"`  | Series identifier field |
| `season_id_field`      | string | `"season_id"`      | Season identifier field |

**Example:**

```json
{
  "hierarchy_mappings": {
    "episode_number_field": "episode_number",
    "season_number_field": "season_number",
    "series_id_field": "gracenote_series_id",
    "season_id_field": "internal_season_id"
  }
}
```

### Parent Metadata Mappings

Maps fields for denormalized parent (series/season) metadata.

| Property                         | Type   | Default                      | Description              |
| -------------------------------- | ------ | ---------------------------- | ------------------------ |
| `show_name_field`                | string | `"show_name"`                | Series title field       |
| `short_series_description_field` | string | `"short_series_description"` | Series short description |
| `long_series_description_field`  | string | `"long_series_description"`  | Series full description  |
| `series_premiere_date_field`     | string | `"series_premiere_date"`     | Series premiere date     |
| `season_count_field`             | string | `"season_count"`             | Number of seasons        |
| `short_season_description_field` | string | `"short_season_description"` | Season short description |
| `long_season_description_field`  | string | `"long_season_description"`  | Season full description  |
| `episode_count_field`            | string | `"episode_count"`            | Episodes in season       |

**Example:**

```json
{
  "parent_metadata_mappings": {
    "show_name_field": "series_title",
    "short_series_description_field": "series_synopsis_short",
    "long_series_description_field": "series_synopsis_full",
    "series_premiere_date_field": "series_premiere",
    "season_count_field": "total_seasons"
  }
}
```

### People Field Mappings

Maps cast and crew fields to MEC JobFunction values.

```json
{
  "people_field_mappings": {
    "source_field": "JobFunction"
  }
}
```

**Default Mappings:**

```json
{
  "people_field_mappings": {
    "actors": "Actor",
    "directors": "Director",
    "writers": "Writer",
    "producers": "Producer",
    "executive_producers": "ExecutiveProducer",
    "series_creators": "Creator",
    "guest_actors": "Actor"
  }
}
```

**Person Attribute Configuration:**

| Property                 | Type   | Default          | Description                |
| ------------------------ | ------ | ---------------- | -------------------------- |
| `guest_actors_field`     | string | `"guest_actors"` | Field that sets Guest=true |
| `person_first_name_attr` | string | `"@first_name"`  | First name attribute       |
| `person_last_name_attr`  | string | `"@last_name"`   | Last name attribute        |
| `person_order_attr`      | string | `"@order"`       | Billing order attribute    |
| `person_role_attr`       | string | `"@role"`        | Character/role attribute   |

**Example:**

```json
{
  "people_field_mappings": {
    "cast": "Actor",
    "director": "Director",
    "writer": "Writer",
    "guest_stars": "Actor"
  },
  "guest_actors_field": "guest_stars",
  "person_first_name_attr": "@firstName",
  "person_last_name_attr": "@lastName",
  "person_order_attr": "@billingOrder",
  "person_role_attr": "@characterName"
}
```

### Rating System Mappings

Maps rating system identifiers to region (country) codes.

```json
{
  "rating_system_mappings": {
    "rating_system": "country_code"
  }
}
```

**Default Mappings:**

```json
{
  "rating_system_mappings": {
    "us-tv": "US",
    "TV Rating": "US",
    "ca-tv": "CA",
    "au-tv": "AU",
    "ACMA": "AU",
    "DMEC": "MX",
    "in-tv": "IN",
    "nz-tv": "NZ",
    "nz-am": "NZ"
  }
}
```

**Rating Field Configuration:**

| Property                 | Type   | Default         | Description                  |
| ------------------------ | ------ | --------------- | ---------------------------- |
| `ratings_field`          | string | `"ratings"`     | Ratings container field      |
| `rating_type_attr`       | string | `"@type"`       | Rating system attribute      |
| `rating_value_attr`      | string | `"@value"`      | Rating value attribute       |
| `rating_descriptor_attr` | string | `"@Descriptor"` | Content descriptor attribute |

**Example:**

```json
{
  "rating_system_mappings": {
    "US-TV": "US",
    "CA-TV": "CA",
    "UK-BBFC": "GB"
  },
  "ratings_field": "content_ratings",
  "rating_type_attr": "@system",
  "rating_value_attr": "@rating",
  "rating_descriptor_attr": "@reasons"
}
```

### Technical Mappings

Maps video, audio, and subtitle technical fields.

**Video Fields:**

| Property               | Type   | Default           | Description                          |
| ---------------------- | ------ | ----------------- | ------------------------------------ |
| `frame_rate_field`     | string | `"frame_rate"`    | Frame rate field                     |
| `aspect_ratio_field`   | string | `"video_dar"`     | Aspect ratio field                   |
| `resolution_field`     | string | `"resolution"`    | Resolution field (e.g., "1920x1080") |
| `active_picture_field` | string | `"activepicture"` | Active picture area field            |
| `color_type_field`     | string | `"in_color_flag"` | Color/B&W indicator                  |
| `video_codec_field`    | string | `"videocodec"`    | Video codec field                    |

**Audio Fields:**

| Property                 | Type   | Default             | Description                  |
| ------------------------ | ------ | ------------------- | ---------------------------- |
| `audio_attributes_field` | string | `"audioattributes"` | Audio container field        |
| `audio_language_attr`    | string | `"audiolanguage"`   | Audio language attribute     |
| `audio_dvs_attr`         | string | `"DVS"`             | DVS (descriptive video) flag |
| `audio_track_ref_attr`   | string | `"fileposition"`    | Track reference attribute    |

**Subtitle Fields:**

| Property                    | Type   | Default                      | Description                 |
| --------------------------- | ------ | ---------------------------- | --------------------------- |
| `subtitle_attributes_field` | string | `"closedcaptionsattributes"` | Subtitle container field    |
| `subtitle_language_attr`    | string | `"language"`                 | Subtitle language attribute |
| `subtitle_type_attr`        | string | `"type"`                     | Subtitle type attribute     |

### Custom Field Categories

Defines which unmapped fields to preserve and how to categorize them.

```json
{
    "custom_field_categories": {
        "category_name": ["field1", "field2", ...]
    }
}
```

**Default Categories:**

```json
{
  "custom_field_categories": {
    "advertising": [
      "ad_category",
      "ad_content_id",
      "cue_points",
      "adopportunitiesmarkers"
    ],
    "timing": ["timelines", "timelines_df30", "segments", "markers"],
    "technical": [
      "AFD",
      "needs_watermark",
      "semitextless",
      "conform_materials_list",
      "format"
    ],
    "rights": ["platform_rights", "carousel"],
    "other": ["placement"]
  }
}
```

### Temporal Field Mappings

Maps date and time fields.

| Property                  | Type   | Default               | Description             |
| ------------------------- | ------ | --------------------- | ----------------------- |
| `premiere_year_field`     | string | `"premiere_year"`     | Release year field      |
| `original_air_date_field` | string | `"original_air_date"` | Original air date field |
| `run_length_field`        | string | `"run_length"`        | Duration field          |

### Geographic/Linguistic Mappings

| Property             | Type   | Default          | Description             |
| -------------------- | ------ | ---------------- | ----------------------- |
| `country_code_field` | string | `"country_code"` | Country of origin field |
| `language_field`     | string | `"language"`     | Original language field |

## Complete Configuration Example

Here's a complete configuration example for a hypothetical customer:

```json
{
  "source_namespace_prefix": "ACME",
  "default_language": "en-US",
  "primary_id_field": "content_id",
  "ref_id_field": "reference_id",
  "include_raw_source": false,

  "identifier_mappings": {
    "content_id": "",
    "reference_id": "-REF",
    "version_id": "-VERSION",
    "gracenote_series_id": "TMS",
    "gracenote_episode_id": "TMS",
    "gracenote_movie_id": "TMS"
  },

  "title_mappings": {
    "title_field": "episode_title",
    "title_brief_field": "short_title",
    "short_description_field": "synopsis_short",
    "long_description_field": "synopsis_full",
    "copyright_field": "copyright_notice"
  },

  "classification_mappings": {
    "is_movie_field": "is_movie",
    "content_type_field": "content_type",
    "video_type_field": "video_type",
    "genres_field": "genres",
    "genre_type_attr": "@type",
    "genre_text_key": "#text"
  },
  "platform_genre_types": ["Amazon", "Apple", "Roku"],

  "hierarchy_mappings": {
    "episode_number_field": "episode_number",
    "season_number_field": "season_number",
    "series_id_field": "gracenote_series_id"
  },

  "parent_metadata_mappings": {
    "show_name_field": "series_title",
    "short_series_description_field": "series_synopsis_short",
    "long_series_description_field": "series_synopsis_full"
  },

  "people_field_mappings": {
    "actors": "Actor",
    "directors": "Director",
    "writers": "Writer",
    "producers": "Producer",
    "executive_producers": "ExecutiveProducer",
    "guest_actors": "Actor"
  },
  "guest_actors_field": "guest_actors",
  "person_first_name_attr": "@first_name",
  "person_last_name_attr": "@last_name",
  "person_order_attr": "@order",
  "person_role_attr": "@role",

  "rating_system_mappings": {
    "us-tv": "US",
    "TV Rating": "US",
    "ca-tv": "CA",
    "au-tv": "AU"
  },
  "ratings_field": "ratings",
  "rating_type_attr": "@type",
  "rating_value_attr": "@value",
  "rating_descriptor_attr": "@Descriptor",

  "premiere_year_field": "premiere_year",
  "original_air_date_field": "original_air_date",
  "run_length_field": "duration",
  "country_code_field": "country_code",
  "language_field": "language",

  "custom_field_categories": {
    "advertising": ["ad_category", "ad_content_id", "cue_points"],
    "timing": ["timelines", "segments", "markers"],
    "technical": ["AFD", "needs_watermark", "semitextless"]
  }
}
```

## S3 Configuration Storage

For large configurations, store them in S3 and reference by path:

### S3 Path Convention

```
s3://{IAC_ASSETS_BUCKET}/normalizer-configs/{customer}-{normalizer-type}-config.json
```

**Examples:**

- `normalizer-configs/acme-generic-xml-config.json`
- `normalizer-configs/customer-a-generic-xml-config.json`

### Node Configuration with S3 Reference

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/acme-generic-xml-config.json",
    "config": {
      "include_raw_source": true
    }
  }
}
```

### Environment Requirements

The Lambda function requires:

- `IAC_ASSETS_BUCKET` environment variable set
- IAM permissions to read from the IAC assets bucket

## Validation and Defaults

The normalizer provides sensible defaults for all configuration options. If a configuration key is not provided:

1. The normalizer uses the default value
2. Field mappers gracefully handle missing fields
3. Validation warnings are generated for recommended but missing fields

## Related Documentation

- [Normalizer Architecture](./architecture.md) - System architecture overview
- [Field Mapping Reference](./field-mappings.md) - Source to MEC field mappings
- [MovieLabs MEC v2.25](https://movielabs.com/md/) - Official MEC specification
