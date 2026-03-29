# Normalizer Field Mapping Reference

This document provides a comprehensive reference for how source metadata fields are mapped to MovieLabs MEC (Media Entertainment Core) v2.25 elements.

## Table of Contents

- [Quick Reference](#quick-reference)
- [Overview](#overview)
- [Field Mapping Categories](#field-mapping-categories)
  - [1. Identification Fields](#1-identification-fields)
  - [2. Title and Description Fields](#2-title-and-description-fields)
  - [3. Content Classification Fields](#3-content-classification-fields)
  - [4. Hierarchy and Sequence Fields](#4-hierarchy-and-sequence-fields)
  - [5. People and Credits Fields](#5-people-and-credits-fields)
  - [6. Ratings Fields](#6-ratings-fields)
  - [7. Technical Metadata Fields](#7-technical-metadata-fields)
- [Custom Fields Handling](#custom-fields-handling)
- [Complete Output Structure](#complete-output-structure)
- [Related Documentation](#related-documentation)

## Quick Reference

This section provides a condensed view of all field mappings for operations team reference.

### Field Category Summary

| Category       | Source Fields                                     | MEC Elements                         | Config Key                |
| -------------- | ------------------------------------------------- | ------------------------------------ | ------------------------- |
| Identifiers    | `content_id`, `ref_id`, `version_id`, `tms_*_id`  | `AltIdentifier`                      | `identifier_mappings`     |
| Titles         | `title`, `title_brief`, `*_description`           | `LocalizedInfo`                      | `title_mappings`          |
| Classification | `is_movie`, `content_type`, `genre`               | `WorkType`, `Genre`                  | `classification_mappings` |
| Hierarchy      | `episode_number`, `season_number`, `series_id`    | `SequenceInfo`, `Parent`             | `hierarchy_mappings`      |
| People         | `actors`, `directors`, `writers`, `producers`     | `People/Job`                         | `people_field_mappings`   |
| Ratings        | `ratings` (with `@type`, `@value`, `@Descriptor`) | `RatingSet/Rating`                   | `rating_system_mappings`  |
| Technical      | `frame_rate`, `resolution`, `audio*`, `subtitle*` | `VideoAttributes`, `AudioAttributes` | `technical_mappings`      |
| Custom         | Platform genres, ad fields, timing data           | `CustomFields`                       | `custom_field_categories` |

### MEC Element Quick Reference

| MEC Element      | Purpose                           | Required | Source Example                    |
| ---------------- | --------------------------------- | -------- | --------------------------------- |
| `ContentId`      | Primary identifier                | Yes      | Generated from `primary_id_field` |
| `WorkType`       | Content type (Movie/Episode/etc.) | Yes      | `is_movie`, `content_type`        |
| `LocalizedInfo`  | Titles, descriptions, genres      | Yes      | `title`, `*_description`          |
| `AltIdentifiers` | External system IDs               | No       | `content_id`, `tms_episode_id`    |
| `People`         | Cast and crew                     | No       | `actors`, `directors`             |
| `Ratings`        | Content ratings                   | No       | `ratings` container               |
| `SequenceInfo`   | Episode/season number             | No       | `episode_number`                  |
| `Parents`        | Hierarchy relationships           | No       | `series_id`, `season_id`          |
| `ReleaseYear`    | Release year                      | No       | `premiere_year`                   |
| `ReleaseDate`    | Original air date                 | No       | `original_air_date`               |

### Rating System to Region Mapping

| Rating System        | Region Code | Description               |
| -------------------- | ----------- | ------------------------- |
| `us-tv`, `TV Rating` | US          | US TV Parental Guidelines |
| `ca-tv`              | CA          | Canadian TV               |
| `au-tv`, `ACMA`      | AU          | Australian TV             |
| `DMEC`               | MX          | Mexico                    |
| `in-tv`              | IN          | India                     |
| `nz-tv`, `nz-am`     | NZ          | New Zealand               |

### People JobFunction Values

| Source Field          | MEC JobFunction     | Notes             |
| --------------------- | ------------------- | ----------------- |
| `actors`              | `Actor`             | Main cast         |
| `guest_actors`        | `Actor`             | Sets `Guest=true` |
| `directors`           | `Director`          |                   |
| `writers`             | `Writer`            |                   |
| `producers`           | `Producer`          |                   |
| `executive_producers` | `ExecutiveProducer` |                   |
| `series_creators`     | `Creator`           |                   |

### Custom Fields Categories

| Category          | Fields Captured                              | Purpose                                |
| ----------------- | -------------------------------------------- | -------------------------------------- |
| `platform_genres` | Amazon, Apple, Roku genres                   | Platform-specific categorization       |
| `advertising`     | `ad_category`, `ad_content_id`, `cue_points` | Ad insertion data                      |
| `timing`          | `timelines`, `segments`, `markers`           | Content timing/chapters                |
| `technical`       | `AFD`, `needs_watermark`, `semitextless`     | Technical flags without MEC equivalent |
| `rights`          | `platform_rights`, `carousel`                | Distribution data                      |

---

## Overview

The normalizer transforms source metadata into MEC-compliant structure using configuration-driven field mappings. All field names are defined in configuration, not hardcoded in the normalizer code.

## Field Mapping Categories

### 1. Identification Fields

Source identifiers are mapped to MEC `AltIdentifier` elements with configurable namespaces.

| Source Field (configurable) | MEC Element     | Namespace Pattern             |
| --------------------------- | --------------- | ----------------------------- |
| `primary_id`                | `AltIdentifier` | `{PREFIX}` (e.g., "CUSTOMER") |
| `ref_id`                    | `AltIdentifier` | `{PREFIX}-REF`                |
| `version_id`                | `AltIdentifier` | `{PREFIX}-VERSION`            |
| `sequence_id`               | `AltIdentifier` | `{PREFIX}-SEQ`                |
| `tms_series_id`             | `AltIdentifier` | `TMS` (absolute)              |
| `tms_episode_id`            | `AltIdentifier` | `TMS` (absolute)              |
| `ad_content_id`             | `AltIdentifier` | `{PREFIX}-AD`                 |

**Namespace Resolution Rules:**

- Empty suffix (`""`) → Uses prefix directly (e.g., `"CUSTOMER"`)
- Relative suffix (`"-REF"`) → Appends to prefix (e.g., `"CUSTOMER-REF"`)
- Absolute namespace (`"TMS"`) → Uses as-is

**Example Configuration:**

```json
{
  "source_namespace_prefix": "CUSTOMER",
  "identifier_mappings": {
    "content_id": "",
    "reference_id": "-REF",
    "gracenote_id": "TMS"
  }
}
```

**Example Output:**

```json
{
  "AltIdentifiers": [
    { "Namespace": "CUSTOMER", "Identifier": "RLA236635" },
    { "Namespace": "CUSTOMER-REF", "Identifier": "L01039285" },
    { "Namespace": "TMS", "Identifier": "EP043931170004" }
  ]
}
```

### 2. Title and Description Fields

Source title/description fields are mapped to MEC `LocalizedInfo` elements.

| Source Field (configurable) | MEC Element             | Description                    |
| --------------------------- | ----------------------- | ------------------------------ |
| `title`                     | `TitleDisplayUnlimited` | Full title (no length limit)   |
| `title_brief`               | `TitleDisplay19`        | Short title (≤19 chars)        |
| `title_brief`               | `TitleInternalAlias`    | Internal reference title       |
| `short_description`         | `Summary190`            | Short summary (~190 chars)     |
| `medium_description`        | `Summary400`            | Medium summary (~400 chars)    |
| `long_description`          | `Summary4000`           | Full description (≤4000 chars) |
| `copyright_holder`          | `CopyrightLine`         | Copyright notice               |
| `keywords`                  | `Keywords`              | List of keyword strings        |

**Example Configuration:**

```json
{
  "title_mappings": {
    "title_field": "episode_title",
    "title_brief_field": "short_title",
    "short_description_field": "synopsis_short",
    "long_description_field": "synopsis_full"
  },
  "default_language": "en-US"
}
```

**Example Output:**

```json
{
  "LocalizedInfo": [
    {
      "Language": "en-US",
      "TitleDisplayUnlimited": "The Sample Episode",
      "TitleDisplay19": "Sample Episode",
      "Summary190": "A brief description of the episode...",
      "Summary4000": "A comprehensive description of the episode content..."
    }
  ]
}
```

### 3. Content Classification Fields

Source classification fields are mapped to MEC `WorkType` and genre elements.

| Source Field (configurable)  | MEC Element                    | Values                                    |
| ---------------------------- | ------------------------------ | ----------------------------------------- |
| `is_movie` / `content_type`  | `WorkType`                     | Movie, Episode, Season, Series, Promotion |
| `video_type`                 | `WorkTypeDetail`               | Additional type detail                    |
| `genre` (primary)            | `LocalizedInfo/Genres`         | Standard genre list                       |
| `genres` (platform-specific) | `CustomFields/platform_genres` | Platform-specific genres                  |

**WorkType Determination Logic:**

1. If `is_movie` = TRUE → `WorkType` = "Movie"
2. If `content_type` = "Series" with episode data → `WorkType` = "Episode"
3. If `content_type` = "Interstitial" → `WorkType` = "Promotion"

**Example Configuration:**

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
  "platform_genre_types": ["Amazon", "Apple", "Roku"]
}
```

**Example Output:**

```json
{
  "WorkType": "Episode",
  "WorkTypeDetail": "Full Episode",
  "LocalizedInfo": [
    {
      "Genres": ["Drama", "Horror"]
    }
  ]
}
```

### 4. Hierarchy and Sequence Fields

Source hierarchy fields are mapped to MEC `SequenceInfo` and `Parent` elements.

| Source Field (configurable) | MEC Element                               | Description                 |
| --------------------------- | ----------------------------------------- | --------------------------- |
| `episode_number`            | `SequenceInfo/Number`                     | Episode number              |
| `season_number`             | `SequenceInfo/Number`                     | Season number (for seasons) |
| Series relationship         | `Parent[@relationshipType="isepisodeof"]` | Episode → Season            |
| Season relationship         | `Parent[@relationshipType="isseasonof"]`  | Season → Series             |

**Parent Metadata Extraction:**
The normalizer also extracts denormalized parent metadata for optional storage:

| Source Field               | Parent Metadata Field  |
| -------------------------- | ---------------------- |
| `show_name`                | `series.title`         |
| `short_series_description` | `series.summary_190`   |
| `long_series_description`  | `series.summary_4000`  |
| `series_premiere_date`     | `series.premiere_date` |
| `season_count`             | `series.season_count`  |
| `short_season_description` | `season.summary_190`   |
| `long_season_description`  | `season.summary_4000`  |
| `episode_count`            | `season.episode_count` |

**Example Configuration:**

```json
{
  "hierarchy_mappings": {
    "episode_number_field": "episode_number",
    "season_number_field": "season_number",
    "series_id_field": "tms_series_id",
    "season_id_field": "season_id"
  }
}
```

**Example Output:**

```json
{
  "SequenceInfo": { "Number": 4 },
  "Parents": [
    { "RelationshipType": "isepisodeof", "ParentContentId": "SEASON-001" }
  ]
}
```

### 5. People and Credits Fields

Source cast/crew fields are mapped to MEC `People/Job` elements.

| Source Field (configurable) | MEC JobFunction     | Notes               |
| --------------------------- | ------------------- | ------------------- |
| `actors/actor`              | `Actor`             | Main cast           |
| `guest_actors`              | `Actor`             | Sets `Guest` = true |
| `directors/director`        | `Director`          |                     |
| `writers/writer`            | `Writer`            |                     |
| `producers/producer`        | `Producer`          |                     |
| `executive_producers`       | `ExecutiveProducer` |                     |
| `series_creators`           | `Creator`           |                     |

**Person Attribute Mapping:**

| Source Attribute       | MEC Element           | Notes                  |
| ---------------------- | --------------------- | ---------------------- |
| `@first_name`          | `Name/FirstGivenName` | NOT FirstName          |
| `@last_name`           | `Name/FamilyName`     | NOT LastName           |
| `#text` or constructed | `Name/DisplayName`    | REQUIRED               |
| `@order`               | `BillingBlockOrder`   | Element, not attribute |
| `@role`                | `Character`           | For actors only        |

**Example Configuration:**

```json
{
  "people_field_mappings": {
    "actors": "Actor",
    "directors": "Director",
    "writers": "Writer",
    "guest_actors": "Actor"
  },
  "guest_actors_field": "guest_actors",
  "person_first_name_attr": "@first_name",
  "person_last_name_attr": "@last_name",
  "person_order_attr": "@order",
  "person_role_attr": "@role"
}
```

**Example Output:**

```json
{
  "People": [
    {
      "JobFunction": "Actor",
      "Name": {
        "DisplayName": "John Actor",
        "FirstGivenName": "John",
        "FamilyName": "Actor"
      },
      "BillingBlockOrder": 1,
      "Character": "Main Character"
    },
    {
      "JobFunction": "Director",
      "Name": { "DisplayName": "Jane Director" },
      "BillingBlockOrder": 1
    }
  ]
}
```

### 6. Ratings Fields

Source rating fields are mapped to MEC `RatingSet/Rating` elements.

| Source Field        | MEC Element | Notes                   |
| ------------------- | ----------- | ----------------------- |
| Rating system       | `System`    | e.g., "us-tv", "ca-tv"  |
| Rating value        | `Value`     | e.g., "TV-MA", "TV-14"  |
| Content descriptors | `Reason`    | e.g., "LSV", "V", "L"   |
| Derived from system | `Region`    | REQUIRED - country code |

**Rating System to Region Mapping:**

| Rating System        | Region (Country) |
| -------------------- | ---------------- |
| `us-tv`, `TV Rating` | US               |
| `ca-tv`              | CA               |
| `au-tv`, `ACMA`      | AU               |
| `DMEC`               | MX               |
| `in-tv`              | IN               |
| `nz-tv`, `nz-am`     | NZ               |

**Example Configuration:**

```json
{
  "rating_system_mappings": {
    "us-tv": "US",
    "TV Rating": "US",
    "ca-tv": "CA",
    "au-tv": "AU",
    "ACMA": "AU"
  },
  "ratings_field": "ratings",
  "rating_type_attr": "@type",
  "rating_value_attr": "@value",
  "rating_descriptor_attr": "@Descriptor"
}
```

**Example Output:**

```json
{
  "Ratings": [
    { "Region": "US", "System": "us-tv", "Value": "TV-MA", "Reason": "LSV" },
    { "Region": "CA", "System": "ca-tv", "Value": "18+" }
  ]
}
```

### 7. Technical Metadata Fields

Source technical fields are mapped to MEC video/audio/subtitle attributes.

**Video Attributes:**

| Source Field    | MEC Element                               | Notes                      |
| --------------- | ----------------------------------------- | -------------------------- |
| `frame_rate`    | `FrameRate`                               | Converted from ×100 format |
| `video_dar`     | `AspectRatio`                             | e.g., "16:9"               |
| `resolution`    | `WidthPixels`, `HeightPixels`             | Parsed from "1920x1080"    |
| `activepicture` | `ActiveWidthPixels`, `ActiveHeightPixels` |                            |
| `in_color_flag` | `ColorType`                               | "Color" or "BlackAndWhite" |
| `videocodec`    | `Codec`                                   | e.g., "H.264"              |

**Audio Attributes:**

| Source Field    | MEC Element              | Notes                      |
| --------------- | ------------------------ | -------------------------- |
| `audiolanguage` | `Language`               | e.g., "en", "es"           |
| `DVS`           | `Type`                   | "VisuallyImpaired" if true |
| `fileposition`  | `InternalTrackReference` | Track identifier           |

**Subtitle Attributes:**

| Source Field | MEC Element | Notes             |
| ------------ | ----------- | ----------------- |
| `language`   | `Language`  | Subtitle language |
| `type`       | `Type`      | CC, SDH, Forced   |

**Example Output:**

```json
{
  "VideoAttributes": {
    "FrameRate": "23.976",
    "AspectRatio": "16:9",
    "WidthPixels": 1920,
    "HeightPixels": 1080,
    "ColorType": "Color"
  },
  "AudioAttributes": [
    { "Language": "en", "Type": "Primary" },
    { "Language": "en", "Type": "VisuallyImpaired" }
  ],
  "SubtitleAttributes": [{ "Language": "en", "Type": "CC" }]
}
```

## Custom Fields Handling

Fields that don't map to standard MEC elements are preserved in `CustomFields`, organized by category.

### Custom Field Categories

| Category          | Fields                                                                 | Description                             |
| ----------------- | ---------------------------------------------------------------------- | --------------------------------------- |
| `platform_genres` | Platform-specific genres                                               | Amazon, Apple, Roku genres              |
| `advertising`     | `ad_category`, `ad_content_id`, `cue_points`, `adopportunitiesmarkers` | Ad-related data                         |
| `timing`          | `timelines`, `segments`, `markers`                                     | Timing/segment data                     |
| `technical`       | `AFD`, `needs_watermark`, `semitextless`, `conform_materials_list`     | Technical fields without MEC equivalent |
| `rights`          | `platform_rights`, `carousel`                                          | Rights/distribution data                |
| `other`           | `placement`                                                            | Miscellaneous unmapped fields           |

**Example Configuration:**

```json
{
  "custom_field_categories": {
    "advertising": ["ad_category", "ad_content_id", "cue_points"],
    "timing": ["timelines", "segments", "markers"],
    "technical": ["AFD", "needs_watermark", "semitextless"]
  }
}
```

**Example Output:**

```json
{
  "CustomFields": {
    "platform_genres": {
      "amazon": ["Drama", "Horror"],
      "apple": ["Drama", "Thriller"]
    },
    "advertising": {
      "ad_category": "Entertainment:General",
      "ad_content_id": "L01039285"
    },
    "technical": {
      "AFD": "10",
      "needs_watermark": false
    }
  }
}
```

## Complete Output Structure

The normalized output follows this structure:

```json
{
    "BasicMetadata": {
        "ContentId": "RLA236635",
        "WorkType": "Episode",
        "WorkTypeDetail": "Full Episode",
        "LocalizedInfo": [...],
        "ReleaseYear": 2024,
        "ReleaseDate": "2024-03-15",
        "Ratings": [...],
        "People": [...],
        "CountryOfOrigin": "US",
        "OriginalLanguage": "en",
        "SequenceInfo": {...},
        "Parents": [...],
        "AltIdentifiers": [...],
        "VideoAttributes": {...},
        "AudioAttributes": [...],
        "SubtitleAttributes": [...],
        "RunLength": "PT45M"
    },
    "CustomFields": {...},
    "ParentMetadata": {...},
    "SourceAttribution": {
        "SourceSystem": "customer",
        "SourceType": "generic_xml",
        "CorrelationId": "L01039285",
        "NormalizedAt": "2024-03-15T10:30:00Z"
    },
    "SchemaVersion": "1.0.0"
}
```

## Related Documentation

- [Normalizer Architecture](./architecture.md) - System architecture overview
- [Configuration Options](./configuration.md) - Complete configuration schema
- [MovieLabs MEC v2.25](https://movielabs.com/md/) - Official MEC specification
