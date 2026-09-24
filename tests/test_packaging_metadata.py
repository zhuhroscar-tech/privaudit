"""Regression tests for current setuptools license metadata.

setuptools 77+ deprecates the old ``project.license`` table and license
classifier combination. Keep this tiny packaging contract in CI so the
published sdist/wheel metadata stays warning-free.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject_text() -> str:
    return PYPROJECT.read_text()


def test_project_license_uses_spdx_string_not_deprecated_table():
    text = _pyproject_text()

    assert 'license = "MIT"' in text
    assert "license = {" not in text


def test_license_file_is_declared_for_built_distributions():
    text = _pyproject_text()

    assert 'license-files = ["LICENSE"]' in text


def test_deprecated_mit_classifier_is_not_reintroduced():
    text = _pyproject_text()

    assert "License :: OSI Approved :: MIT License" not in text


def test_setuptools_floor_supports_spdx_license_metadata():
    text = _pyproject_text()

    assert 'requires = ["setuptools>=77", "wheel"]' in text
