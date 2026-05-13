import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const resultsPath = resolve(process.cwd(), "../e2e-artifacts/frontend-e2e-results.json");
const reportPath = resolve(process.cwd(), "../e2e-artifacts/frontend-e2e-report.md");

function formatDuration(ms) {
  if (!Number.isFinite(ms)) return "unknown";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function collectTests(suite, collected = []) {
  for (const spec of suite.specs ?? []) {
    for (const test of spec.tests ?? []) {
      collected.push({
        title: [...(suite.titlePath ?? []), spec.title, test.projectName]
          .filter(Boolean)
          .join(" / "),
        status: test.outcome ?? "unknown",
        duration: (test.results ?? []).reduce((sum, result) => sum + (result.duration ?? 0), 0),
      });
    }
  }
  for (const child of suite.suites ?? []) {
    collectTests(child, collected);
  }
  return collected;
}

function writeFallbackReport(reason) {
  mkdirSync(dirname(reportPath), { recursive: true });
  writeFileSync(
    reportPath,
    [
      "## Frontend E2E Test Report",
      "",
      "Playwright did not produce a JSON result file.",
      "",
      `Reason: ${reason}`,
      "",
    ].join("\n"),
  );
}

let results;
try {
  results = JSON.parse(readFileSync(resultsPath, "utf8"));
} catch (error) {
  writeFallbackReport(error instanceof Error ? error.message : String(error));
  process.exit(0);
}

const tests = collectTests(results);
const counts = tests.reduce(
  (acc, test) => {
    acc.total += 1;
    acc[test.status] = (acc[test.status] ?? 0) + 1;
    return acc;
  },
  { total: 0 },
);
const failed = tests.filter((test) => !["expected", "skipped"].includes(test.status));
const totalDuration = tests.reduce((sum, test) => sum + test.duration, 0);

const lines = [
  "## Frontend E2E Test Report",
  "",
  `- Total: ${counts.total}`,
  `- Passed: ${counts.expected ?? 0}`,
  `- Failed: ${failed.length}`,
  `- Skipped: ${counts.skipped ?? 0}`,
  `- Duration: ${formatDuration(totalDuration)}`,
  "",
];

if (failed.length > 0) {
  lines.push("### Failed Tests", "");
  for (const test of failed) {
    lines.push(`- ${test.title} (${test.status}, ${formatDuration(test.duration)})`);
  }
  lines.push("");
} else {
  lines.push("All frontend E2E tests passed or were skipped.", "");
}

mkdirSync(dirname(reportPath), { recursive: true });
writeFileSync(reportPath, lines.join("\n"));
