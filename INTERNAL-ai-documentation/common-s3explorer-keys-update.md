# Common and S3Explorer i18n Keys Update

## Overview

This document describes the addition of `common.root` and `common.folder` keys to all locale files, and the addition of root-level `s3Explorer` sections to match the English locale structure.

## Changes Implemented

### 1. Added common.root and common.folder to All Locales

Added two new keys to the `common` section in all 11 locale files:

| Locale             | common.root | common.folder |
| ------------------ | ----------- | ------------- |
| English (en.ts)    | "Root"      | "Folder"      |
| Chinese (zh.ts)    | "根目录"    | "文件夹"      |
| Arabic (ar.ts)     | "الجذر"     | "مجلد"        |
| German (de.ts)     | "Wurzel"    | "Ordner"      |
| Spanish (es.ts)    | "Raíz"      | "Carpeta"     |
| French (fr.ts)     | "Racine"    | "Dossier"     |
| Hebrew (he.ts)     | "שורש"      | "תיקייה"      |
| Hindi (hi.ts)      | "रूट"       | "फ़ोल्डर"     |
| Japanese (ja.ts)   | "ルート"    | "フォルダ"    |
| Korean (ko.ts)     | "루트"      | "폴더"        |
| Portuguese (pt.ts) | "Raiz"      | "Pasta"       |

### 2. Added Root-Level s3Explorer Section to All Locales

The English locale file (`en.ts`) had a root-level `s3Explorer` section (lines 642-663) that was missing from other locale files. This section has now been added to all 10 other locale files with the following structure:

```typescript
s3Explorer: {
  filter: {
    label: "Filter by name",
    clear: "Clear filter",
    resultsCount: "Showing {{count}} of {{total}} items",
  },
  loading: {
    initializing: "Loading...",
    fetchingContents: "Fetching contents...",
  },
  empty: {
    folder: "This folder is empty",
    noResults: "No items match your filter",
  },
  keyboard: {
    navigation: "Use arrow keys to navigate, Enter to open, Backspace to go back",
  },
  menu: {
    rename: "Rename",
    delete: "Delete",
  },
}
```

**Status**: ✅ Added to all 10 non-English locales (zh, ar, de, es, fr, he, hi, ja, ko, pt)

**Note**: All locale files also retain the `translation.s3Explorer` section which includes additional error handling keys not present in the root-level section.

## File Locations

All updated files are in:

```
medialake_user_interface/src/i18n/locales/
├── en.ts
├── zh.ts
├── ar.ts
├── de.ts
├── es.ts
├── fr.ts
├── he.ts
├── hi.ts
├── ja.ts
├── ko.ts
└── pt.ts
```

## Verification

- ✅ No TypeScript syntax errors
- ✅ No linter errors in any locale file
- ✅ All locale files maintain consistent structure
- ✅ All keys properly translated in each language

## Usage Examples

### common.root and common.folder

```typescript
// Display root directory
t("common.root"); // Returns: "Root" (in English)

// Display folder label
t("common.folder"); // Returns: "Folder" (in English)
```

### s3Explorer Keys (already existing)

```typescript
// Show empty folder message
t("translation.s3Explorer.empty.folder"); // Returns: "This folder is empty"

// Show keyboard navigation hint
t("translation.s3Explorer.keyboard.navigation");
// Returns: "Use arrow keys to navigate, Enter to open, Backspace to go back"
```

## Structure Differences

### Root-Level vs Translation-Level s3Explorer

The locale files now contain **two separate** `s3Explorer` sections:

1. **Root-Level** (e.g., `en.s3Explorer`):
   - Simpler structure with core UI elements
   - Contains: filter, loading, empty, keyboard, menu
   - Used for basic S3 explorer interface

2. **Translation-Level** (e.g., `en.translation.s3Explorer`):
   - Extended structure with error handling
   - Contains: filter, error, loading, empty, keyboard, menu
   - Includes additional error states and messages

This dual structure allows for flexible usage throughout the application.

## Notes

- Both `common.root` and `common.folder` were newly added to all 11 locales
- Root-level `s3Explorer` section was added to match English locale structure
- The `translation.s3Explorer` section (which includes error handling) was already present in all locales
- All translations follow the established patterns and conventions of the codebase
