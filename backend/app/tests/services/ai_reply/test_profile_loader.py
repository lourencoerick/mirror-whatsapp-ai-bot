# backend/tests/services/ai_reply/test_profile_loader.py

import pytest
import json
import os

# Import the function to test and the schema
from app.services.ai_reply.profile_loader import (
    load_company_profile,
    PROFILE_DIR as LOADER_PROFILE_DIR,
)
from app.api.schemas.company_profile import CompanyProfileSchema

# --- Test Data ---

VALID_PROFILE_DATA = {
    "company_name": "Test Bakery",
    "website": "http://testbakery.com/",
    "business_description": "A test bakery.",
    "sales_tone": "friendly",
    "language": "en-US",
    "ai_objective": "sell test cakes",
    # Omitting optional fields for brevity, add if needed for specific tests
    "profile_version": 1,
}

# Profile missing a required field (company_name)
INVALID_SCHEMA_MISSING_FIELD = {
    "website": "http://testbakery.com/",
    "business_description": "A test bakery.",
    "sales_tone": "friendly",
    "language": "en-US",
    "ai_objective": "sell test cakes",
    "profile_version": 1,
}

# Profile with wrong data type (profile_version is string)
INVALID_SCHEMA_WRONG_TYPE = {
    "company_name": "Test Bakery",
    "website": "http://testbakery.com/",
    "business_description": "A test bakery.",
    "sales_tone": "friendly",
    "language": "en-US",
    "ai_objective": "sell test cakes",
    "profile_version": "should_be_int",  # Wrong type
}

# --- Test Functions ---


def test_load_company_profile_success(tmp_path, monkeypatch):
    """Tests successful loading of a valid profile."""
    # Arrange: Create a temporary profile directory and file
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    company_id = "test_bakery"
    profile_file = profile_dir / f"{company_id}.json"
    profile_file.write_text(json.dumps(VALID_PROFILE_DATA), encoding="utf-8")

    # Use monkeypatch to temporarily set the PROFILE_DIR used by the loader
    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", str(profile_dir)
    )

    # Act: Call the function under test
    profile = load_company_profile(company_id)

    # Assert: Check if the profile was loaded and is the correct type
    assert profile is not None
    assert isinstance(profile, CompanyProfileSchema)
    assert profile.company_name == VALID_PROFILE_DATA["company_name"]
    assert str(profile.website) == VALID_PROFILE_DATA["website"]  # Check a few fields


def test_load_company_profile_file_not_found(tmp_path, monkeypatch):
    """Tests behavior when the profile file does not exist."""
    # Arrange: Create the directory but not the file
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    company_id = "non_existent_bakery"
    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", str(profile_dir)
    )

    # Act
    profile = load_company_profile(company_id)

    # Assert
    assert profile is None


def test_load_company_profile_invalid_json(tmp_path, monkeypatch):
    """Tests behavior with a file containing invalid JSON."""
    # Arrange
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    company_id = "invalid_json_co"
    profile_file = profile_dir / f"{company_id}.json"
    profile_file.write_text("{invalid json", encoding="utf-8")  # Malformed JSON
    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", str(profile_dir)
    )

    # Act
    profile = load_company_profile(company_id)

    # Assert
    assert profile is None


def test_load_company_profile_invalid_schema_missing_field(tmp_path, monkeypatch):
    """Tests behavior when JSON is valid but misses a required schema field."""
    # Arrange
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    company_id = "missing_field_co"
    profile_file = profile_dir / f"{company_id}.json"
    profile_file.write_text(json.dumps(INVALID_SCHEMA_MISSING_FIELD), encoding="utf-8")
    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", str(profile_dir)
    )

    # Act
    profile = load_company_profile(company_id)

    # Assert
    assert profile is None  # Pydantic validation should fail


def test_load_company_profile_invalid_schema_wrong_type(tmp_path, monkeypatch):
    """Tests behavior when JSON is valid but has incorrect data type for a field."""
    # Arrange
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    company_id = "wrong_type_co"
    profile_file = profile_dir / f"{company_id}.json"
    profile_file.write_text(json.dumps(INVALID_SCHEMA_WRONG_TYPE), encoding="utf-8")
    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", str(profile_dir)
    )

    # Act
    profile = load_company_profile(company_id)

    # Assert
    assert profile is None  # Pydantic validation should fail


def test_load_company_profile_empty_company_id():
    """Tests behavior with an empty company_id."""
    # Act
    profile = load_company_profile("")
    # Assert
    assert profile is None

    # Act
    profile_none = load_company_profile(None)  # type: ignore Test None explicitly
    # Assert
    assert profile_none is None


def test_load_company_profile_invalid_company_id_chars():
    """Tests behavior with invalid characters in company_id."""
    # Act & Assert
    assert load_company_profile("test/co") is None
    assert load_company_profile("../testco") is None
    assert load_company_profile("test\\co") is None  # Check backslash too


def test_load_company_profile_directory_not_found(monkeypatch):
    """Tests behavior when the base PROFILE_DIR does not exist."""
    # Arrange: Set PROFILE_DIR to a non-existent path
    non_existent_dir = "/path/to/hopefully/non/existent/dir/xyz123"
    # Ensure it really doesn't exist (highly unlikely but good practice)
    if os.path.exists(non_existent_dir):
        pytest.skip(f"Skipping test, directory '{non_existent_dir}' actually exists.")

    monkeypatch.setattr(
        "app.services.ai_reply.profile_loader.PROFILE_DIR", non_existent_dir
    )
    company_id = "any_company"

    # Act
    profile = load_company_profile(company_id)

    # Assert
    assert profile is None
