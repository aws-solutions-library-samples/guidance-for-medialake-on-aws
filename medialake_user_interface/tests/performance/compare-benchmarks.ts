#!/usr/bin/env npx tsx
/**
 * Compares current benchmark results against a baseline.
 *
 * Usage:
 *   npx tsx tests/performance/compare-benchmarks.ts \
 *     --baseline tests/perf-results/baseline.json \
 *     --current tests/perf-results/benchmark-main-*.json
 *
 * Exit code 1 if regressions exceed threshold.
 */
import fs from "fs";
import path from "path";
import {
  loadBaselineReport,
  compareReports,
  BenchmarkReport,
} from "../fixtures/performance.fixtures";

const args = process.argv.slice(2);
const baselineIdx = args.indexOf("--baseline");
const currentIdx = args.indexOf("--current");

if (baselineIdx === -1 || currentIdx === -1) {
  console.error("Usage: compare-benchmarks.ts --baseline <file> --current <file>");
  process.exit(2);
}

const baselinePath = args[baselineIdx + 1];
const currentPath = args[currentIdx + 1];

// Support glob-like: pick the most recent file matching the pattern
function resolveFile(pattern: string): string {
  if (fs.existsSync(pattern)) return pattern;

  const dir = path.dirname(pattern);
  const prefix = path.basename(pattern).replace("*", "");
  if (!fs.existsSync(dir)) {
    console.error(`Directory not found: ${dir}`);
    process.exit(2);
  }

  const files = fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(prefix) || f.includes(prefix.replace("-", "")))
    .sort()
    .reverse();

  if (!files.length) {
    console.error(`No files matching ${pattern}`);
    process.exit(2);
  }
  return path.join(dir, files[0]);
}

const baseline = loadBaselineReport(resolveFile(baselinePath));
const current = loadBaselineReport(resolveFile(currentPath));

if (!baseline || !current) {
  console.error("Could not load one or both reports");
  process.exit(2);
}

const result = compareReports(baseline, current);

console.log("\n=== Performance Comparison ===\n");
console.log(`Baseline: ${baseline.branch} @ ${baseline.commitSha.slice(0, 8)}`);
console.log(`Current:  ${current.branch} @ ${current.commitSha.slice(0, 8)}\n`);

if (result.improvements.length) {
  console.log("✅ Improvements:");
  result.improvements.forEach((i) => console.log(`  ${i}`));
}

if (result.unchanged.length) {
  console.log("\n⏸  Unchanged:");
  result.unchanged.forEach((u) => console.log(`  ${u}`));
}

if (result.regressions.length) {
  console.log("\n🔴 Regressions:");
  result.regressions.forEach((r) => console.log(`  ${r}`));
  console.log(`\n${result.regressions.length} regression(s) detected — failing.`);
  process.exit(1);
} else {
  console.log("\nNo regressions detected. ✅");
  process.exit(0);
}
