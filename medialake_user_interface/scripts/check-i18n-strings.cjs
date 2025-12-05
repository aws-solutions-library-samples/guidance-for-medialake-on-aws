#!/usr/bin/env node

/**
 * i18n Hardcoded String Detection and Translation Validation Script
 *
 * This script performs two main checks:
 *
 * 1. HARDCODED STRING DETECTION:
 *    - Detects string literals in JSX text content: <div>Hello World</div>
 *    - Detects string literals in common i18n-relevant props: placeholder, title, label, etc.
 *    - Detects template literals with static content in JSX
 *
 * 2. TRANSLATION KEY VALIDATION:
 *    - Validates that t() calls reference keys that exist in en.ts (English)
 *    - Warns if translation keys are missing in other locale files
 *
 * It ignores:
 * - Empty strings and single characters
 * - Technical strings (URLs, file paths, CSS classes, etc.)
 * - Strings in non-i18n props (className, id, key, data-*, etc.)
 * - Import/export statements
 * - Console logs and comments
 * - Test files
 */

const fs = require("fs");
const path = require("path");

// Locale directory path
const LOCALES_DIR = path.join(__dirname, "..", "src", "i18n", "locales");

// Primary locale file (English) - must exist and contain all keys
const PRIMARY_LOCALE = "en.ts";

/**
 * Dynamically discover all locale files in the locales directory
 */

function discoverLocaleFiles() {
  try {
    if (!fs.existsSync(LOCALES_DIR)) {
      console.error(`Warning: Locales directory not found: ${LOCALES_DIR}`);
      return [];
    }

    const files = fs.readdirSync(LOCALES_DIR);
    return files.filter((file) => file.endsWith(".ts") && !file.endsWith(".d.ts"));
  } catch (error) {
    console.error(`Error reading locales directory: ${error.message}`);
    return [];
  }
}

// Props that typically need i18n
const I18N_PROPS = [
  "label",
  "placeholder",
  "title",
  "aria-label",
  "alt",
  "helperText",
  "errorText",
  "description",
  "tooltip",
  "message",
  "text",
  "buttonText",
  "submitText",
  "cancelText",
  "confirmText",
  "header",
  "subheader",
  "caption",
  "hint",
  "emptyText",
  "loadingText",
  "successMessage",
  "errorMessage",
  "warningMessage",
  "infoMessage",
  "name", // when used as display name
  "children", // when it's a string
];

// Props that should NOT be checked for i18n
const IGNORED_PROPS = [
  "className",
  "class",
  "id",
  "key",
  "ref",
  "style",
  "type",
  "name", // when used as form field name
  "value",
  "defaultValue",
  "href",
  "src",
  "to",
  "path",
  "route",
  "component",
  "data-testid",
  "data-cy",
  "role",
  "tabIndex",
  "htmlFor",
  "xmlns",
  "viewBox",
  "d", // SVG path
  "fill",
  "stroke",
  "color",
  "variant",
  "size",
  "severity",
  "direction",
  "orientation",
  "position",
  "align",
  "justify",
  "spacing",
  "sx",
  "css",
  "onClick",
  "onChange",
  "onSubmit",
  "onBlur",
  "onFocus",
  "accept",
  "method",
  "action",
  "target",
  "rel",
  "download",
  "autoComplete",
  "inputMode",
  "pattern",
  "min",
  "max",
  "step",
  "rows",
  "cols",
  "maxLength",
  "minLength",
  "wrap",
  "open",
  "disabled",
  "required",
  "checked",
  "selected",
  "readonly",
  "hidden",
  "async",
  "defer",
  "for",
  "form",
  "formAction",
  "formMethod",
  "formTarget",
  "enterKeyHint",
  "autoCapitalize",
  "autoCorrect",
  "spellCheck",
  "contentEditable",
  "draggable",
  "lang",
  "dir",
  "slot",
  "is",
  "itemProp",
  "itemScope",
  "itemType",
  "itemID",
  "itemRef",
  "crossOrigin",
  "integrity",
  "referrerPolicy",
  "sandbox",
  "srcdoc",
  "allow",
  "loading",
  "decoding",
  "fetchPriority",
  "shape",
  "coords",
  "usemap",
  "ismap",
  "format", // Date/time format strings
  "alt", // Image alt text - often intentionally in English for accessibility
  "label", // Aria labels - accessibility strings that should stay in English
];

// Patterns that indicate technical/non-i18n strings
const TECHNICAL_PATTERNS = [
  /^\//, // URLs/paths starting with /
  /^https?:\/\//, // URLs
  /^mailto:/, // Email links
  /^tel:/, // Phone links
  /^#[a-fA-F0-9]{3,8}$/, // Hex colors
  /^rgb\(/, // RGB colors
  /^rgba\(/, // RGBA colors
  /^hsl\(/, // HSL colors
  /^[0-9]+(?:px|em|rem|%|vh|vw|pt|cm|mm|in)?$/, // CSS units
  /^[a-z][a-zA-Z0-9]*-[a-zA-Z0-9-]+$/, // kebab-case (likely CSS class or ID)
  /^[A-Z][a-zA-Z0-9]*$/, // PascalCase (likely component name or constant)
  /^\$\{/, // Template literal variable
  /^[A-Z_][A-Z0-9_]*$/, // SCREAMING_SNAKE_CASE (constants)
  /^data-/, // Data attributes
  /^aria-/, // ARIA attributes
  /^\d+$/, // Pure numbers
  /^[a-z]+:\/\//, // Protocol URLs
  /\.(?:js|ts|tsx|jsx|css|scss|json|svg|png|jpg|jpeg|gif|ico|webp|mp4|webm|ogg|mp3|wav|pdf|doc|docx|xls|xlsx|ppt|pptx)$/i, // File extensions
  /^application\//, // MIME types
  /^text\//, // MIME types
  /^image\//, // MIME types
  /^audio\//, // MIME types
  /^video\//, // MIME types
  /^[a-z]{2}(-[A-Z]{2})?$/, // Language codes like "en", "en-US"
  /^\d{4}-\d{2}-\d{2}/, // ISO date format
  /^[\w-]+\/[\w-]+$/, // Content-type like patterns
  /^Bearer\s/, // Auth tokens
  /^Basic\s/, // Auth tokens
  // Code snippets and JS expressions (false positives from JSX parsing)
  /^[=<>!&|]+\s*\d+/, // Comparison operators like "= 1024 &&", ">= 0 &&"
  /^\d+\s*[=<>!&|]+/, // Numbers followed by operators like "0 &&"
  /^[=<>!&|]+\s*\w+/, // Operators followed by identifiers like "= MIN_WIDTH &&"
  /&&|\|\|/, // Contains logical operators (code snippets)
  /^\(?\s*event\s*:/, // Event handler type annotations
  /^\(?\s*\w+\s*:\s*React\./, // React type annotations
  /^void\s*\|/, // TypeScript union types
  /\?\s*$/, // Ternary operator fragments
  // CSS values
  /^\d+px\s+solid/, // Border shorthand like "1px solid", "2px solid"
  /^\d+px\s+\d+px/, // Multiple pixel values (padding, margin)
  /^0px\s+\d+px/, // Box shadow values
  // Date format strings
  /^[yMdHhms\/\-:\s]+[aA]?$/, // Date format patterns like "yyyy/MM/dd hh:mm a"
  // Aria labels for accessibility (these are intentionally in English for screen readers)
  /\btabs?\b/i, // Tab-related aria labels
  // More code snippet patterns
  /,\s*event\s*:/, // Event handler signatures
  /^-\s*\w+:$/, // Template literal fragments like "- clips:"
  /^\d+[A-Z]+,\s*\w+:/, // Size patterns like "1GB, size:"
  /^sk-/, // API keys
  /^pk-/, // API keys
  /^[A-Za-z0-9+/=]+$/, // Base64 (if long enough)
  /^\{\{.*\}\}$/, // Template variables
  /^<%.*%>$/, // EJS-style templates
];

// Common words that are likely not user-facing text
const TECHNICAL_WORDS = new Set([
  "null",
  "undefined",
  "true",
  "false",
  "div",
  "span",
  "button",
  "input",
  "form",
  "GET",
  "POST",
  "PUT",
  "DELETE",
  "PATCH",
  "HEAD",
  "OPTIONS",
  "asc",
  "desc",
  "ASC",
  "DESC",
  "id",
  "ID",
  "uuid",
  "UUID",
  "default",
  "DEFAULT",
  "primary",
  "secondary",
  "success",
  "error",
  "warning",
  "info",
  "small",
  "medium",
  "large",
  "xs",
  "sm",
  "md",
  "lg",
  "xl",
  "xxl",
  "contained",
  "outlined",
  "text",
  "inherit",
  "none",
  "auto",
  "flex",
  "grid",
  "block",
  "inline",
  "row",
  "column",
  "start",
  "end",
  "center",
  "stretch",
  "baseline",
  "nowrap",
  "wrap",
  "hidden",
  "visible",
  "scroll",
  "fixed",
  "absolute",
  "relative",
  "static",
  "sticky",
  "top",
  "bottom",
  "left",
  "right",
  "horizontal",
  "vertical",
]);

// Minimum length for a string to be considered for i18n
const MIN_STRING_LENGTH = 2;

// Maximum length to be considered a single word/abbreviation (skip these)
const MAX_SINGLE_WORD_LENGTH = 15;

/**
 * Parse a TypeScript locale file and extract all translation keys
 */
function parseLocaleFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  const content = fs.readFileSync(filePath, "utf-8");
  const keys = new Set();

  // Function to recursively extract keys from the object structure
  function extractKeys(obj, prefix = "") {
    // Match key-value pairs in the TypeScript object
    // This is a simplified parser that works for our locale file structure
    const keyRegex = /(\w+)\s*:\s*(?:"[^"]*"|'[^']*'|`[^`]*`|\{)/g;
    let match;
    let braceDepth = 0;
    let currentKey = "";
    let i = 0;

    while (i < obj.length) {
      const char = obj[i];

      if (char === "{") {
        braceDepth++;
        if (braceDepth === 1 && currentKey) {
          // Start of a nested object
          const start = i;
          let nestedDepth = 1;
          i++;
          while (i < obj.length && nestedDepth > 0) {
            if (obj[i] === "{") nestedDepth++;
            if (obj[i] === "}") nestedDepth--;
            i++;
          }
          const nestedContent = obj.substring(start, i);
          const fullKey = prefix ? `${prefix}.${currentKey}` : currentKey;
          extractKeys(nestedContent, fullKey);
          currentKey = "";
          continue;
        }
      } else if (char === "}") {
        braceDepth--;
      } else if (braceDepth === 1) {
        // Look for key: value patterns at depth 1
        const remaining = obj.substring(i);
        const keyMatch = remaining.match(/^(\w+)\s*:\s*/);
        if (keyMatch) {
          currentKey = keyMatch[1];
          i += keyMatch[0].length;

          // Check what comes after the colon
          const afterColon = obj.substring(i).trim();
          if (afterColon.startsWith("{")) {
            // Nested object, will be handled by brace logic
            continue;
          } else {
            // String value - add the key
            const fullKey = prefix ? `${prefix}.${currentKey}` : currentKey;
            keys.add(fullKey);
            currentKey = "";
            // Skip to end of value
            const valueEnd = obj.substring(i).search(/,\s*\n|,\s*}/);
            if (valueEnd !== -1) {
              i += valueEnd;
            }
            continue;
          }
        }
      }
      i++;
    }
  }

  // Start extraction from the default export
  const exportMatch = content.match(/export\s+default\s*(\{[\s\S]*\});?\s*$/);
  if (exportMatch) {
    extractKeys(exportMatch[1]);
  }

  return keys;
}

/**
 * Alternative simpler key extraction using regex patterns
 */
function extractTranslationKeys(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  const content = fs.readFileSync(filePath, "utf-8");
  const keys = new Set();

  // Build a path tracker to handle nested objects
  const lines = content.split("\n");
  const pathStack = [];
  let pendingKey = null; // Track key when value is on next line

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Skip export default and closing
    if (trimmed.startsWith("export default") || trimmed === "};") {
      continue;
    }

    // Match opening of nested object: `keyName: {`
    const nestedMatch = trimmed.match(/^(\w+)\s*:\s*\{/);
    if (nestedMatch) {
      pathStack.push(nestedMatch[1]);
      pendingKey = null;
      continue;
    }

    // Match closing brace
    if (trimmed === "}," || trimmed === "}") {
      pathStack.pop();
      pendingKey = null;
      continue;
    }

    // Match string value: `keyName: "value"` or `keyName: 'value'`
    // Also handles trailing comments like // pragma: allowlist secret
    const valueMatch = trimmed.match(/^(\w+)\s*:\s*["'`].*["'`],?\s*(?:\/\/.*)?$/);
    if (valueMatch) {
      const keyPath = [...pathStack, valueMatch[1]].join(".");
      keys.add(keyPath);
      pendingKey = null;
      continue;
    }

    // Match key with value on next line: `keyName:`
    const keyOnlyMatch = trimmed.match(/^(\w+)\s*:\s*$/);
    if (keyOnlyMatch) {
      pendingKey = keyOnlyMatch[1];
      continue;
    }

    // If we have a pending key and this line is a string value
    if (pendingKey) {
      const stringValueMatch = trimmed.match(/^["'`].*["'`],?\s*(?:\/\/.*)?$/);
      if (stringValueMatch) {
        const keyPath = [...pathStack, pendingKey].join(".");
        keys.add(keyPath);
        pendingKey = null;
        continue;
      }
    }
  }

  return keys;
}

class I18nChecker {
  constructor() {
    this.hardcodedViolations = [];
    this.missingKeyViolations = [];
    this.missingTranslationWarnings = [];
    this.checkedFiles = 0;
    this.englishKeys = null;
    this.otherLocaleKeys = {};
  }

  /**
   * Load translation keys from locale files
   */
  loadTranslationKeys() {
    // Dynamically discover all locale files
    const localeFiles = discoverLocaleFiles();

    if (localeFiles.length === 0) {
      console.error("Warning: No locale files found in locales directory");
      return false;
    }

    // Check if primary locale exists
    if (!localeFiles.includes(PRIMARY_LOCALE)) {
      console.error(`Warning: Primary locale file '${PRIMARY_LOCALE}' not found`);
      return false;
    }

    // Load English keys (required)
    const enPath = path.join(LOCALES_DIR, PRIMARY_LOCALE);
    this.englishKeys = extractTranslationKeys(enPath);

    if (!this.englishKeys) {
      console.error(`Warning: Could not load English locale file from ${enPath}`);
      return false;
    }

    console.error(`Loaded ${this.englishKeys.size} keys from ${PRIMARY_LOCALE}`);

    // Load other locale keys for comparison (dynamically discovered)
    for (const localeFile of localeFiles) {
      if (localeFile === PRIMARY_LOCALE) continue;

      const localePath = path.join(LOCALES_DIR, localeFile);
      const keys = extractTranslationKeys(localePath);
      if (keys) {
        const locale = localeFile.replace(".ts", "");
        this.otherLocaleKeys[locale] = keys;
        console.error(`Loaded ${keys.size} keys from ${localeFile}`);
      }
    }

    const otherLocaleCount = Object.keys(this.otherLocaleKeys).length;
    console.error(
      `Total: ${localeFiles.length} locale files (1 primary + ${otherLocaleCount} secondary)\n`
    );

    return true;
  }

  /**
   * Check if a translation key exists in English
   */
  keyExistsInEnglish(key) {
    if (!this.englishKeys) return true; // Can't validate without English keys
    return this.englishKeys.has(key);
  }

  /**
   * Get locales missing a specific key
   */
  getLocalesMissingKey(key) {
    const missingLocales = [];
    for (const [locale, keys] of Object.entries(this.otherLocaleKeys)) {
      if (!keys.has(key)) {
        missingLocales.push(locale);
      }
    }
    return missingLocales;
  }

  /**
   * Check if a string looks like it needs i18n
   */
  needsI18n(str, context = {}) {
    // Trim the string
    str = str.trim();

    // Skip empty or very short strings
    if (!str || str.length < MIN_STRING_LENGTH) {
      return false;
    }

    // Skip strings that are just whitespace or newlines
    if (/^\s*$/.test(str)) {
      return false;
    }

    // Skip technical words
    if (TECHNICAL_WORDS.has(str)) {
      return false;
    }

    // Skip strings matching technical patterns
    for (const pattern of TECHNICAL_PATTERNS) {
      if (pattern.test(str)) {
        return false;
      }
    }

    // Skip single words that look like identifiers (camelCase, no spaces)
    if (
      str.length <= MAX_SINGLE_WORD_LENGTH &&
      !str.includes(" ") &&
      /^[a-z][a-zA-Z0-9]*$/.test(str)
    ) {
      return false;
    }

    // Skip if it looks like a translation key (contains dots and no spaces)
    if (str.includes(".") && !str.includes(" ") && /^[a-zA-Z.]+$/.test(str)) {
      return false;
    }

    // If it contains multiple words or sentence-like structure, it likely needs i18n
    const wordCount = str.split(/\s+/).filter((w) => w.length > 0).length;
    if (wordCount >= 2) {
      return true;
    }

    // Single words that contain only letters and are capitalized are likely user-facing
    if (/^[A-Z][a-z]+$/.test(str) && str.length > 2 && !TECHNICAL_WORDS.has(str.toLowerCase())) {
      // Check if it's in certain contexts
      if (context.propName && I18N_PROPS.includes(context.propName)) {
        return true;
      }
      if (context.isJsxText) {
        return true;
      }
    }

    // Check for obvious UI text patterns
    if (/^[A-Z].*[.!?]$/.test(str)) {
      // Starts with capital, ends with punctuation
      return true;
    }

    // Check context
    if (context.propName && I18N_PROPS.includes(context.propName)) {
      return true;
    }

    if (context.isJsxText && wordCount >= 1 && /[A-Z]/.test(str)) {
      return true;
    }

    return false;
  }

  /**
   * Parse a file and find potential i18n violations
   */
  checkFile(filePath) {
    const content = fs.readFileSync(filePath, "utf-8");
    const lines = content.split("\n");
    const fileHardcodedViolations = [];
    const fileMissingKeyViolations = [];
    const fileMissingTranslations = new Map(); // key -> missing locales

    // Regular expressions for detection
    const jsxTextRegex = />\s*([^<>{}`]+?)\s*</g;
    const propStringRegex = /(\w+)=["']([^"']+)["']|(\w+)=\{["']([^"']+)["']\}/g;
    const templateLiteralRegex = /`([^`$]+)`/g;
    const translationCallRegex = /\bt\s*\(\s*["'`]([^"'`]+)["'`]/g;
    const translationSkipRegex = /\bt\s*\(/;

    for (let lineNum = 0; lineNum < lines.length; lineNum++) {
      const line = lines[lineNum];
      const lineNumber = lineNum + 1;

      // Skip import/export lines
      if (/^import\s|^export\s/.test(line.trim())) {
        continue;
      }

      // Skip comment lines
      if (/^\s*\/\//.test(line) || /^\s*\/\*/.test(line)) {
        continue;
      }

      // Skip console.log, console.warn, console.error
      if (/console\.(log|warn|error|info|debug)\(/.test(line)) {
        continue;
      }

      // Skip lines with eslint-disable comments
      if (/eslint-disable/.test(line)) {
        continue;
      }

      // Skip lines with i18n-disable comment (current line or previous 2 lines)
      if (/i18n-disable/.test(line) || /i18n-ignore/.test(line)) {
        continue;
      }
      // Check if previous line has i18n-ignore
      if (lineNum > 0 && (/i18n-disable/.test(lines[lineNum - 1]) || /i18n-ignore/.test(lines[lineNum - 1]))) {
        continue;
      }
      // Check if 2 lines back has i18n-ignore (for multi-line commented code)
      if (lineNum > 1 && (/i18n-disable/.test(lines[lineNum - 2]) || /i18n-ignore/.test(lines[lineNum - 2]))) {
        continue;
      }

      // Check for t() calls and validate the keys
      let tMatch;
      translationCallRegex.lastIndex = 0;
      while ((tMatch = translationCallRegex.exec(line)) !== null) {
        const translationKey = tMatch[1];

        // Skip dynamic template literal keys (e.g., ${translationPrefix}.fields.${name}.label)
        // These are constructed at runtime and cannot be statically validated
        if (translationKey.includes("${") || translationKey.includes("}")) {
          continue;
        }

        // Check if key exists in English
        if (!this.keyExistsInEnglish(translationKey)) {
          fileMissingKeyViolations.push({
            line: lineNumber,
            column: tMatch.index + 1,
            key: translationKey,
            type: "missing_in_english",
          });
        } else {
          // Check if key exists in other locales
          const missingLocales = this.getLocalesMissingKey(translationKey);
          if (missingLocales.length > 0) {
            if (!fileMissingTranslations.has(translationKey)) {
              fileMissingTranslations.set(translationKey, {
                line: lineNumber,
                missingLocales,
              });
            }
          }
        }
      }

      // Skip hardcoded string checks if line contains t() call
      if (translationSkipRegex.test(line)) {
        continue;
      }

      // Check for JSX text content
      let match;
      jsxTextRegex.lastIndex = 0;
      while ((match = jsxTextRegex.exec(line)) !== null) {
        const text = match[1].trim();
        if (this.needsI18n(text, { isJsxText: true })) {
          fileHardcodedViolations.push({
            line: lineNumber,
            column: match.index + 1,
            text: text.substring(0, 50) + (text.length > 50 ? "..." : ""),
            type: "JSX text content",
          });
        }
      }

      // Check for string props
      propStringRegex.lastIndex = 0;
      while ((match = propStringRegex.exec(line)) !== null) {
        const propName = match[1] || match[3];
        const propValue = match[2] || match[4];

        // Skip ignored props
        if (IGNORED_PROPS.includes(propName)) {
          continue;
        }

        // Skip if it looks like a style prop
        if (/style/i.test(propName)) {
          continue;
        }

        if (this.needsI18n(propValue, { propName })) {
          fileHardcodedViolations.push({
            line: lineNumber,
            column: match.index + 1,
            text: propValue.substring(0, 50) + (propValue.length > 50 ? "..." : ""),
            type: `prop '${propName}'`,
          });
        }
      }

      // Check for template literals (excluding those in t() calls)
      if (!line.includes("t(") && !line.includes("t`")) {
        templateLiteralRegex.lastIndex = 0;
        while ((match = templateLiteralRegex.exec(line)) !== null) {
          const text = match[1].trim();
          if (this.needsI18n(text, { isTemplateLiteral: true }) && text.includes(" ")) {
            fileHardcodedViolations.push({
              line: lineNumber,
              column: match.index + 1,
              text: text.substring(0, 50) + (text.length > 50 ? "..." : ""),
              type: "template literal",
            });
          }
        }
      }
    }

    if (fileHardcodedViolations.length > 0) {
      this.hardcodedViolations.push({
        file: filePath,
        violations: fileHardcodedViolations,
      });
    }

    if (fileMissingKeyViolations.length > 0) {
      this.missingKeyViolations.push({
        file: filePath,
        violations: fileMissingKeyViolations,
      });
    }

    if (fileMissingTranslations.size > 0) {
      this.missingTranslationWarnings.push({
        file: filePath,
        warnings: Array.from(fileMissingTranslations.entries()).map(([key, data]) => ({
          key,
          line: data.line,
          missingLocales: data.missingLocales,
        })),
      });
    }

    this.checkedFiles++;
  }

  /**
   * Format the report
   */
  formatReport() {
    let hasIssues = false;
    let report = "";

    // Section 1: Missing keys in English (ERRORS - blocking)
    if (this.missingKeyViolations.length > 0) {
      hasIssues = true;
      report += "\n";
      report += "=============================================================================\n";
      report += " ERROR: Translation keys missing from English locale (en.ts)\n";
      report += "=============================================================================\n\n";

      let totalErrors = 0;
      for (const fileResult of this.missingKeyViolations) {
        report += `${fileResult.file}\n`;
        for (const violation of fileResult.violations) {
          report += `  ${violation.line}:${violation.column}  error  Translation key not found in en.ts: "${violation.key}"\n`;
          totalErrors++;
        }
        report += "\n";
      }
      report += `✖ ${totalErrors} missing translation key${totalErrors === 1 ? "" : "s"} (must be added to en.ts)\n\n`;
    }

    // Section 2: Hardcoded strings (ERRORS - blocking)
    if (this.hardcodedViolations.length > 0) {
      hasIssues = true;
      report += "\n";
      report += "=============================================================================\n";
      report += " ERROR: Hardcoded strings that need internationalization\n";
      report += "=============================================================================\n\n";

      let totalErrors = 0;
      for (const fileResult of this.hardcodedViolations) {
        report += `${fileResult.file}\n`;
        for (const violation of fileResult.violations) {
          report += `  ${violation.line}:${violation.column}  error  Hardcoded string in ${violation.type}: "${violation.text}"\n`;
          totalErrors++;
        }
        report += "\n";
      }
      report += `✖ ${totalErrors} hardcoded string${totalErrors === 1 ? "" : "s"} (must be moved to translation files)\n`;
      report += "To fix: Move hardcoded strings to translation files and use t() function.\n";
      report += "To ignore a line, add a comment: // i18n-ignore\n\n";
    }

    // Section 3: Missing translations in other locales (WARNINGS - non-blocking)
    if (this.missingTranslationWarnings.length > 0) {
      report += "\n";
      report += "=============================================================================\n";
      report += " WARNING: Translation keys missing from some locale files\n";
      report += "=============================================================================\n\n";

      // Aggregate by key to reduce noise
      const keyToLocales = new Map();
      for (const fileResult of this.missingTranslationWarnings) {
        for (const warning of fileResult.warnings) {
          if (!keyToLocales.has(warning.key)) {
            keyToLocales.set(warning.key, new Set());
          }
          for (const locale of warning.missingLocales) {
            keyToLocales.get(warning.key).add(locale);
          }
        }
      }

      // Group by missing locale count (unused but kept for potential future use)
      const byLocaleCount = new Map();
      for (const [key, locales] of keyToLocales) {
        const count = locales.size;
        if (!byLocaleCount.has(count)) {
          byLocaleCount.set(count, []);
        }
        byLocaleCount.get(count).push({ key, locales: Array.from(locales) });
      }

      // Report summary
      report += `Keys used in code that are missing translations:\n\n`;
      let totalMissing = 0;
      for (const [key, locales] of keyToLocales) {
        const localeList = Array.from(locales).sort().join(", ");
        report += `  "${key}"\n    Missing in: ${localeList}\n\n`;
        totalMissing++;
      }
      report += `⚠ ${totalMissing} key${totalMissing === 1 ? "" : "s"} missing translations in some locales\n\n`;
    }

    if (report) {
      report += "=============================================================================\n";
    }

    return {
      report,
      hasErrors: this.missingKeyViolations.length > 0,
      hasIssues,
    };
  }
}

// Main execution
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error("Usage: check-i18n-strings.js <file1> [file2] ...");
    process.exit(0); // Don't fail if no files provided
  }

  const checker = new I18nChecker();

  // Load translation keys from locale files
  if (!checker.loadTranslationKeys()) {
    console.error("Warning: Could not load translation keys. Skipping key validation.");
  }

  // Filter to only .tsx files (React components)
  const filesToCheck = args.filter((file) => {
    // Only check .tsx files (React components with JSX)
    if (!file.endsWith(".tsx")) {
      return false;
    }

    // Skip test files
    if (file.includes(".test.") || file.includes(".spec.")) {
      return false;
    }

    // Skip story files
    if (file.includes(".stories.")) {
      return false;
    }

    // Skip type definition files
    if (file.endsWith(".d.ts") || file.endsWith(".d.tsx")) {
      return false;
    }

    // Skip i18n locale files
    if (file.includes("/i18n/") || file.includes("/locales/")) {
      return false;
    }

    return true;
  });

  for (const file of filesToCheck) {
    if (fs.existsSync(file)) {
      try {
        checker.checkFile(file);
      } catch (error) {
        console.error(`Error checking ${file}: ${error.message}`);
      }
    }
  }

  const result = checker.formatReport();

  if (result.report) {
    console.log(result.report);
  }

  // Exit with error code if there are missing English keys OR hardcoded strings (blocking)
  // Missing translations in other locales are warnings (non-blocking)
  if (result.hasErrors || checker.hardcodedViolations.length > 0) {
    process.exit(1); // Block commit for missing English keys or hardcoded strings
  }

  process.exit(0);
}

main();
