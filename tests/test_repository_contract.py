"""Repository-level completeness contracts.

These tests guard the project-facing files that make releases usable after
implementation bugs are fixed: discoverable license/changelog/docs, CI, and
release artifact expectations.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_required_project_files_are_present():
    required = [
        "LICENSE",
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "docs/REFERENCE.md",
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
    ]

    for relative_path in required:
        assert (ROOT / relative_path).is_file(), f"missing {relative_path}"


def test_readmes_link_license_releases_download_and_changelog():
    for relative_path in ("README.md", "README.zh-CN.md"):
        text = _read(relative_path)

        assert "https://github.com/zhuhroscar-tech/privaudit/releases" in text
        assert "privaudit.pyz" in text
        assert "CHANGELOG.md" in text
        assert "LICENSE" in text


def test_changelog_documents_current_version_and_core_release_history():
    changelog = _read("CHANGELOG.md")
    pyproject = _read("pyproject.toml")
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert version_match, "pyproject.toml must declare a project version"
    current_version = version_match.group(1)

    assert f"## v{current_version}" in changelog
    for previous_version in ("0.1.7", "0.1.6", "0.1.5", "0.1.0"):
        assert f"## v{previous_version}" in changelog
    assert "PipeWire" in changelog
    assert "pw-dump" in changelog


def test_ci_builds_installable_artifacts_and_smoke_tests_zipapp():
    ci = _read(".github/workflows/ci.yml")

    assert "python -m pytest" in ci
    assert "python -m build" in ci
    assert "python -m zipapp" in ci
    assert "dist/privaudit.pyz --version" in ci
    assert "sha256sum" in ci
    assert "actions/upload-artifact@v4" in ci
    assert 'tags: ["v*"]' in ci


def test_project_urls_link_maintenance_resources():
    pyproject = _read("pyproject.toml")

    assert 'Homepage = "https://github.com/zhuhroscar-tech/privaudit"' in pyproject
    assert 'Issues = "https://github.com/zhuhroscar-tech/privaudit/issues"' in pyproject
    assert 'Changelog = "https://github.com/zhuhroscar-tech/privaudit/blob/main/CHANGELOG.md"' in pyproject


def test_codeql_workflow_is_present_for_static_analysis():
    codeql = _read(".github/workflows/codeql.yml")

    assert "github/codeql-action" in codeql
    assert "python" in codeql.lower()
