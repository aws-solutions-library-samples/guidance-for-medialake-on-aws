#!/usr/bin/env node

/**
 * Check that all locale files have translations for keys present in en.ts
 * This ensures translation completeness across all languages
 */

const fs = require("fs");
const path = require("path");

const LOCALES_DIR = path.join(__dirname, "../src/i18n/locales");
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

// Load a locale file
function loadLocale(localeName) {
  const localePath = path.join(LOCALES_DIR, `${localeName}.ts`);

  if (!fs.existsSync(localePath)) {
    return null;
  }

  const content = fs.readFileSync(localePath, "utf8");
  const match = content.match(/export default\s+({[\s\S]*?});?\s*$/m);

  if (!match) {
    console.error(`${COLORS.red}Error: Could not parse ${localeName}.ts${COLORS.reset}`);
    return null;
  }

  try {
    return eval(`(${match[1]})`);
  } catch (error) {
    console.error(`${COLORS.red}Error parsing ${localeName}.ts: ${error.message}${COLORS.reset}`);
    return null;
  }
}

// Main check function
function checkLocaleCompleteness() {
  console.log(`${COLORS.cyan}🌍 Checking locale file completeness...${COLORS.reset}\n`);

  // Load English locale as baseline
  const enObj = loadLocale("en");
  if (!enObj) {
    console.error(`${COLORS.red}❌ Failed to load en.ts${COLORS.reset}`);
    process.exit(1);
  }

  const enKeys = getAllKeys(enObj);
  console.log(`📝 English locale has ${enKeys.length} keys\n`);

  // Get all locale files except en.ts and index.ts
  const localeFiles = fs
    .readdirSync(LOCALES_DIR)
    .filter((file) => file.endsWith(".ts") && file !== "en.ts" && file !== "index.ts")
    .map((file) => file.replace(".ts", ""));

  let hasErrors = false;
  const missingByLocale = {};
  const extraByLocale = {};

  for (const locale of localeFiles) {
    const localeObj = loadLocale(locale);
    if (!localeObj) {
      hasErrors = true;
      continue;
    }

    const localeKeys = getAllKeys(localeObj);
    const missing = enKeys.filter((key) => !localeKeys.includes(key));
    const extra = localeKeys.filter((key) => !enKeys.includes(key));

    if (missing.length > 0) {
      missingByLocale[locale] = missing;
      hasErrors = true;
    }

    if (extra.length > 0) {
      extraByLocale[locale] = extra;
      hasErrors = true;
    }
  }

  if (Object.keys(missingByLocale).length === 0 && Object.keys(extraByLocale).length === 0) {
    console.log(`${COLORS.green}✅ All locale files are complete!${COLORS.reset}`);
    console.log(
      `${COLORS.green}   All ${localeFiles.length} secondary locales have translations for all ${enKeys.length} keys.${COLORS.reset}\n`
    );
    process.exit(0);
  }

  // Report missing translations
  console.log(
    `${COLORS.red}═══════════════════════════════════════════════════════════════════${COLORS.reset}`
  );
  console.log(`${COLORS.red} ERROR: Missing translations in secondary locale files${COLORS.reset}`);
  console.log(
    `${COLORS.red}═══════════════════════════════════════════════════════════════════${COLORS.reset}\n`
  );

  for (const [locale, missing] of Object.entries(missingByLocale)) {
    console.log(`${COLORS.yellow}${locale}.ts: ${missing.length} missing keys${COLORS.reset}`);

    // Show first 5 as examples
    const examples = missing.slice(0, 5);
    examples.forEach((key) => {
      console.log(`  - ${key}`);
    });

    if (missing.length > 5) {
      console.log(`  ... and ${missing.length - 5} more`);
    }
    console.log("");
  }

  const totalMissing = Object.values(missingByLocale).reduce((sum, arr) => sum + arr.length, 0);
  console.log(
    `${COLORS.red}✖ Total: ${totalMissing} missing translations across ${Object.keys(missingByLocale).length} locales${COLORS.reset}\n`
  );
  console.log(
    `${COLORS.yellow}💡 To fix: Ensure all keys in en.ts are translated in all locale files${COLORS.reset}`
  );
  console.log(
    `${COLORS.yellow}   Run: node medialake_user_interface/scripts/check-i18n-strings.cjs${COLORS.reset}\n`
  );

  // Report extra keys
  if (Object.keys(extraByLocale).length > 0) {
    console.log(
      `${COLORS.red}═══════════════════════════════════════════════════════════════════${COLORS.reset}`
    );
    console.log(`${COLORS.red} ERROR: Extra keys in secondary locale files (not in en.ts)${COLORS.reset}`);
    console.log(
      `${COLORS.red}═══════════════════════════════════════════════════════════════════${COLORS.reset}\n`
    );

    for (const [locale, extra] of Object.entries(extraByLocale)) {
      console.log(`${COLORS.yellow}${locale}.ts: ${extra.length} extra keys${COLORS.reset}`);

      // Show first 5 as examples
      const examples = extra.slice(0, 5);
      examples.forEach((key) => {
        console.log(`  - ${key}`);
      });

      if (extra.length > 5) {
        console.log(`  ... and ${extra.length - 5} more`);
      }
      console.log("");
    }

    const totalExtra = Object.values(extraByLocale).reduce((sum, arr) => sum + arr.length, 0);
    console.log(
      `${COLORS.red}✖ Total: ${totalExtra} extra keys across ${Object.keys(extraByLocale).length} locales${COLORS.reset}\n`
    );
    console.log(
      `${COLORS.yellow}💡 To fix: Remove extra keys from secondary locale files${COLORS.reset}`
    );
    console.log(
      `${COLORS.yellow}   These keys should only exist in en.ts or be removed entirely${COLORS.reset}\n`
    );
  }

  process.exit(1);
}

// Run the check
checkLocaleCompleteness();
