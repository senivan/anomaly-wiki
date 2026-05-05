from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from helpers import register_and_login


GATEWAY_BASE_URL = os.getenv("E2E_GATEWAY_BASE_URL", "http://localhost:8000")


@dataclass
class _TestResult:
    nodeid: str
    outcome: str
    duration: float
    phase: str
    details: str = ""


_REPORT_STARTED_AT: datetime | None = None
_RESULTS: dict[str, _TestResult] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--e2e-report-path",
        action="store",
        default=None,
        help="Write a markdown summary report for this E2E run.",
    )


def _resolve_report_path(config: pytest.Config) -> Path:
    cli_path = config.getoption("--e2e-report-path")
    if cli_path:
        return Path(str(cli_path))

    env_path = os.getenv("E2E_MARKDOWN_REPORT_PATH")
    if env_path:
        return Path(env_path)

    return Path("e2e-artifacts/e2e-test-report.md")


def _trim_details(text: str, max_lines: int = 60) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n... (truncated)"


def pytest_sessionstart(session: pytest.Session) -> None:
    global _REPORT_STARTED_AT, _RESULTS
    _REPORT_STARTED_AT = datetime.now(timezone.utc)
    _RESULTS = {}


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    existing = _RESULTS.get(report.nodeid)

    if report.when == "call":
        _RESULTS[report.nodeid] = _TestResult(
            nodeid=report.nodeid,
            outcome=report.outcome,
            duration=report.duration,
            phase=report.when,
            details=_trim_details(getattr(report, "longreprtext", "")) if report.failed else "",
        )
        return

    # Setup/teardown failures do not have a call-phase result.
    if report.failed:
        _RESULTS[report.nodeid] = _TestResult(
            nodeid=report.nodeid,
            outcome="failed",
            duration=report.duration,
            phase=report.when,
            details=_trim_details(getattr(report, "longreprtext", "")),
        )
        return

    # Setup-phase skip (e.g., skipif) without a call-phase result.
    if report.skipped and existing is None and report.when == "setup":
        _RESULTS[report.nodeid] = _TestResult(
            nodeid=report.nodeid,
            outcome="skipped",
            duration=report.duration,
            phase=report.when,
            details="",
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    report_path = _resolve_report_path(session.config)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    started_at = _REPORT_STARTED_AT or datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc)

    ordered_results = sorted(_RESULTS.values(), key=lambda result: result.nodeid)
    passed = sum(1 for result in ordered_results if result.outcome == "passed")
    failed = sum(1 for result in ordered_results if result.outcome == "failed")
    skipped = sum(1 for result in ordered_results if result.outcome == "skipped")

    lines: list[str] = [
        "# E2E Test Report",
        "",
        f"- **Generated at (UTC):** {finished_at.isoformat()}",
        f"- **Started at (UTC):** {started_at.isoformat()}",
        f"- **Exit status:** {exitstatus}",
        f"- **Collected tests:** {session.testscollected}",
        f"- **Executed tests with outcomes:** {len(ordered_results)}",
        "",
        "## Summary",
        "",
        "| Outcome | Count |",
        "|---|---:|",
        f"| passed (succeeded) | {passed} |",
        f"| failed | {failed} |",
        f"| skipped | {skipped} |",
        "",
        "## Per-test outcomes",
        "",
        "| Test | Outcome | Phase | Duration (s) |",
        "|---|---|---|---:|",
    ]

    for result in ordered_results:
        lines.append(
            f"| `{result.nodeid}` | {result.outcome} | {result.phase} | {result.duration:.3f} |"
        )

    failed_results = [result for result in ordered_results if result.outcome == "failed"]
    lines.extend(["", "## Failure details", ""])
    if not failed_results:
        lines.append("All executed tests succeeded.")
    else:
        for result in failed_results:
            lines.extend(
                [
                    f"### `{result.nodeid}` ({result.phase})",
                    "",
                    "```text",
                    result.details or "No failure text captured.",
                    "```",
                    "",
                ]
            )

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


@pytest.fixture
async def gateway_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=GATEWAY_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def researcher_token(gateway_client: httpx.AsyncClient) -> str:
    token, user = await register_and_login(gateway_client)
    assert user["role"] == "Researcher"
    return token


@pytest.fixture
def auth_headers(researcher_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {researcher_token}"}
