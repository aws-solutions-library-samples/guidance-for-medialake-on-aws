#!/usr/bin/env node

/**
 * Check for unused translation keys in locale files
 * Finds keys defined in en.ts that are never used in the codebase
 * Supports detection of dynamic key patterns (translationPrefix, actionKey, etc.)
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const LOCALES_DIR = path.join(__dirname, "../src/i18n/locales");
const SRC_DIR = path.join(__dirname, "../src");

const COLORS = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
};

// Get all keys from nested object with dot notation
function getAllKeys(obj, prefix = "") {
  const keys = [];

  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;

    if (value && typeof value === "object" && !Array.isArray(value)) {
      keys.push(...getAllKeys(value, fullKey));
    } else {
      keys.push(fullKey);
    }
  }

  return keys;
}

// Load English locale
function loadEnglishLocale() {
  const enPath = path.join(LOCALES_DIR, "en.ts");
  const content = fs.readFileSync(enPath, "utf8");
  const match = content.match(/export default\s+({[\s\S]*?});?\s*$/m);

  if (!match) {
    throw new Error("Could not parse en.ts");
  }

  try {
    return eval(`(${match[1]})`);
  } catch (error) {
    console.error(`${COLORS.red}Error parsing en.ts: ${error.message}${COLORS.reset}`);
    return null;
  }
}

// Get all translation key usage from codebase with dynamic pattern detection
function getAllUsedKeys() {
  try {
    const usedKeys = new Set();
    const dynamicPrefixes = [];

    // Read all .tsx and .ts files (excluding i18n directory)
    const files = execSync(
      `find "${SRC_DIR}" -type f \\( -name "*.tsx" -o -name "*.ts" \\) ! -path "*/i18n/*" 2>/dev/null`,
      { encoding: "utf8", maxBuffer: 50 * 1024 * 1024 }
    )
      .trim()
      .split("\n")
      .filter(Boolean);

    // Scan each file for translation keys
    for (const file of files) {
      try {
        const content = fs.readFileSync(file, "utf8");

        // Static patterns: t("key") or t('key')
        const staticPattern = /t\(\s*["']([^"'$`]+)["']/g;
        for (const match of content.matchAll(staticPattern)) {
          usedKeys.add(match[1].trim());
        }

        // Detect translation keys stored in arrays/constants that are later passed to t()
        // Pattern: "namespace.key" where it looks like a translation key
        const arrayKeyPattern = /["']([a-z][a-zA-Z]*\.[a-z][a-zA-Z.]+)["']/g;
        for (const match of content.matchAll(arrayKeyPattern)) {
          const potentialKey = match[1];
          // Only add if it looks like a translation key (has dots, lowercase start)
          if (potentialKey.includes(".") && /^[a-z]/.test(potentialKey)) {
            usedKeys.add(potentialKey);
          }
        }

        // Detect translationPrefix patterns - these dynamically use .fields.*.label, .tooltip, .helper, .options.*
        const prefixPattern = /translationPrefix[=:]\s*["']([^"']+)["']/g;
        for (const match of content.matchAll(prefixPattern)) {
          dynamicPrefixes.push({ type: "translationPrefix", prefix: match[1] });
        }

        // Detect actionKey patterns for apiMessages (e.g., enabling, disabling, creating, updating, deleting)
        const actionKeyPattern = /actionKey\s*=\s*["']([^"']+)["']/g;
        for (const match of content.matchAll(actionKeyPattern)) {
          dynamicPrefixes.push({ type: "actionKey", value: match[1] });
        }

        // Detect ternary actionKey patterns: newEnabled ? "enabling" : "disabling"
        const ternaryPattern = /\?\s*["'](\w+)["']\s*:\s*["'](\w+)["']/g;
        for (const match of content.matchAll(ternaryPattern)) {
          const lineStart = content.lastIndexOf("\n", match.index);
          const lineEnd = content.indexOf("\n", match.index);
          const line = content.substring(lineStart, lineEnd);
          if (
            line.includes("actionKey") ||
            line.includes("apiMessages") ||
            line.includes("Mutation")
          ) {
            dynamicPrefixes.push({ type: "actionKey", value: match[1] });
            dynamicPrefixes.push({ type: "actionKey", value: match[2] });
          }
        }
      } catch (error) {
        continue;
      }
    }

    return { usedKeys, dynamicPrefixes };
  } catch (error) {
    console.error(
      `${COLORS.yellow}Warning: Error scanning codebase: ${error.message}${COLORS.reset}`
    );
    return { usedKeys: new Set(), dynamicPrefixes: [] };
  }
}

// Check if a key is used dynamically via translationPrefix or actionKey patterns
function isDynamicallyUsed(key, dynamicPrefixes) {
  for (const dp of dynamicPrefixes) {
    if (dp.type === "translationPrefix") {
      // Keys like users.form.fields.*.label/tooltip/helper/options.* are used via translationPrefix
      if (key.startsWith(dp.prefix + ".fields.")) {
        return true;
      }
    }
    if (dp.type === "actionKey") {
      // Keys like users.apiMessages.enabling.* are used via actionKey
      if (key.includes(`.apiMessages.${dp.value}.`)) {
        return true;
      }
    }
  }
  return false;
}

// Main check function
function checkUnusedTranslations() {
  console.log(`${COLORS.cyan}🔍 Checking for unused translation keys...${COLORS.reset}\n`);

  const enObj = loadEnglishLocale();
  if (!enObj) {
    console.error(`${COLORS.red}❌ Failed to load en.ts${COLORS.reset}`);
    process.exit(1);
  }

  const allKeys = getAllKeys(enObj);
  console.log(`📝 Found ${allKeys.length} keys in en.ts`);
  console.log(`🔎 Scanning codebase for usage (this may take a moment)...\n`);

  // Get all used keys with dynamic pattern detection
  const { usedKeys, dynamicPrefixes } = getAllUsedKeys();
  console.log(`✓ Found ${usedKeys.size} static translation keys used in code`);
  console.log(`✓ Found ${dynamicPrefixes.length} dynamic translation patterns\n`);

  // Find unused keys (excluding dynamically used ones)
  const unusedKeys = allKeys.filter((key) => {
    if (usedKeys.has(key)) return false;
    if (isDynamicallyUsed(key, dynamicPrefixes)) return false;
    return true;
  });

  if (unusedKeys.length === 0) {
    console.log(`${COLORS.green}✅ No unused translation keys found!${COLORS.reset}`);
    console.log(
      `${COLORS.green}   All ${allKeys.length} keys are being used in the codebase.${COLORS.reset}\n`
    );
    process.exit(0);
  }

  // Report unused keys
  console.log(
    `${COLORS.yellow}═══════════════════════════════════════════════════════════════════${COLORS.reset}`
  );
  console.log(`${COLORS.yellow} WARNING: Unused translation keys found${COLORS.reset}`);
  console.log(
    `${COLORS.yellow}═══════════════════════════════════════════════════════════════════${COLORS.reset}\n`
  );

  console.log(`${COLORS.yellow}Found ${unusedKeys.length} unused keys in en.ts:${COLORS.reset}\n`);

  // Group by top-level section
  const bySection = {};
  unusedKeys.forEach((key) => {
    const section = key.split(".")[0];
    if (!bySection[section]) bySection[section] = [];
    bySection[section].push(key);
  });

  for (const [section, keys] of Object.entries(bySection)) {
    console.log(`${COLORS.cyan}${section}:${COLORS.reset} ${keys.length} unused keys`);

    // Show first 5 as examples
    const examples = keys.slice(0, 5);
    examples.forEach((key) => {
      console.log(`  - ${key}`);
    });

    if (keys.length > 5) {
      console.log(`  ... and ${keys.length - 5} more`);
    }
    console.log("");
  }

  console.log(
    `${COLORS.yellow}⚠ Total: ${unusedKeys.length} unused translation keys${COLORS.reset}\n`
  );
  console.log(
    `${COLORS.cyan}💡 Consider removing unused keys to keep locale files clean${COLORS.reset}`
  );
  console.log(
    `${COLORS.cyan}   Note: This is a warning, not an error. Commit will proceed.${COLORS.reset}\n`
  );

  // Exit with 0 (warning only, don't block commit)
  process.exit(0);
}

// Run the check
checkUnusedTranslations();
