"""
Unit tests for the validation module.

These tests verify that:
- validate_input_metadata correctly validates raw source metadata
- validate_output_metadata correctly validates normalized MEC output
- Validation results contain appropriate warnings and errors
- Data format validation works correctly for dates, years, durations
"""

from typing import Any

import pytest
from nodes.external_metadata_fetch.normalizers.base import (
    ValidationResult,
    ValidationSeverity,
)
from nodes.external_metadata_fetch.normalizers.validation import (
    VALID_JOB_FUNCTIONS,
    VALID_WORK_TYPES,
    validate_input_metadata,
    validate_output_metadata,
)


def create_sample_config() -> dict[str, Any]:
    """Create a sample configuration for testing."""
    return {
        "source_namespace_prefix": "ACME",
        "default_language": "en-US",
        "primary_id_field": "content_id",
        "ref_id_field": "reference_id",
        "premiere_year_field": "release_year",
        "original_air_date_field": "air_date",
        "run_length_field": "duration",
        "title_mappings": {
            "title_field": "title",
            "title_brief_field": "short_title",
            "description_field": "description",
            "description_short_field": "short_description",
        },
        "classification_mappings": {
            "content_type_field": "content_type",
        },
        "people_field_mappings": {
            "actors": "Actor",
            "directors": "Director",
        },
        "person_first_name_attr": "first_name",
        "person_last_name_attr": "last_name",
    }


def create_valid_metadata() -> dict[str, Any]:
    """Create valid raw metadata for testing."""
    return {
        "content_id": "ACME123456",
        "reference_id": "REF789",
        "title": "Test Episode Title",
        "short_title": "Test Ep",
        "description": "A sample episode for testing.",
        "release_year": 2024,
        "air_date": "2024-03-15",
        "duration": "PT45M",
        "content_type": "Episode",
        "actors": {
            "actor": [
                {"#text": "John Actor", "first_name": "John", "last_name": "Actor"},
            ]
        },
    }


def create_valid_normalized_output() -> dict[str, Any]:
    """Create valid normalized output for testing."""
    return {
        "basic_metadata": {
            "content_id": "ACME123456",
            "work_type": "Episode",
            "localized_info": [
                {
                    "language": "en-US",
                    "title_display_unlimited": "Test Episode Title",
                }
            ],
            "release_year": 2024,
            "release_date": "2024-03-15",
            "ratings": [{"region": "US", "system": "us-tv", "value": "TV-14"}],
            "people": [
                {
                    "job_function": "Actor",
                    "name": {"display_name": "John Actor"},
                    "billing_block_order": 1,
                }
            ],
            "alt_identifiers": [{"namespace": "ACME", "identifier": "ACME123456"}],
        },
        "source_attribution": {
            "source_system": "acme",
            "source_type": "generic_xml",
            "correlation_id": "REF789",
        },
        "schema_version": "1.0.0",
    }


@pytest.mark.unit
class TestValidateInputMetadata:
    """Tests for validate_input_metadata function"""

    def test_valid_input_passes(self):
        """Valid input metadata passes validation."""
        config = create_sample_config()
        metadata = create_valid_metadata()

        result = validate_input_metadata(metadata, config)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_none_metadata_fails(self):
        """None metadata fails validation with error."""
        config = create_sample_config()

        result = validate_input_metadata(None, config)  # type: ignore

        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert "None" in result.errors[0].message

    def test_empty_metadata_fails(self):
        """Empty metadata fails validation with error."""
        config = create_sample_config()

        result = validate_input_metadata({}, config)

        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert "Empty" in result.errors[0].message

    def test_non_dict_metadata_fails(self):
        """Non-dict metadata fails validation with error."""
        config = create_sample_config()

        result = validate_input_metadata("not a dict", config)  # type: ignore

        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_missing_identifier_warns(self):
        """Missing identifier generates warning, not error."""
        config = create_sample_config()
        metadata = {"title": "Test Title"}

        result = validate_input_metadata(metadata, config)

        assert result.is_valid is True  # Warnings don't invalidate
        warnings = [w for w in result.warnings if "identifier" in w.message.lower()]
        assert len(warnings) >= 1

    def test_missing_title_warns(self):
        """Missing title generates warning, not error."""
        config = create_sample_config()
        metadata = {"content_id": "123"}

        result = validate_input_metadata(metadata, config)

        assert result.is_valid is True
        warnings = [w for w in result.warnings if "title" in w.message.lower()]
        assert len(warnings) >= 1

    def test_missing_description_warns(self):
        """Missing description generates warning."""
        config = create_sample_config()
        metadata = {"content_id": "123", "title": "Test"}

        result = validate_input_metadata(metadata, config)

        assert result.is_valid is True
        warnings = [
            w
            for w in result.warnings
            if "description" in w.message.lower() or "summary" in w.message.lower()
        ]
        assert len(warnings) >= 1

    def test_invalid_year_format_errors(self):
        """Invalid year format generates error."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["release_year"] = "not-a-year"

        result = validate_input_metadata(metadata, config)

        # Invalid year should generate an error
        errors = [e for e in result.errors if "year" in e.field_path.lower()]
        assert len(errors) >= 1

    def test_year_out_of_range_warns(self):
        """Year outside reasonable range generates warning."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["release_year"] = 1700  # Too old

        result = validate_input_metadata(metadata, config)

        warnings = [w for w in result.warnings if "year" in w.field_path.lower()]
        assert len(warnings) >= 1

    def test_invalid_date_format_warns(self):
        """Invalid date format generates warning."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["air_date"] = "March 15, 2024"  # Not ISO format

        result = validate_input_metadata(metadata, config)

        warnings = [w for w in result.warnings if "date" in w.field_path.lower()]
        assert len(warnings) >= 1

    def test_invalid_duration_format_warns(self):
        """Invalid duration format generates warning."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["duration"] = "45 minutes"  # Not ISO or seconds

        result = validate_input_metadata(metadata, config)

        warnings = [w for w in result.warnings if "duration" in w.field_path.lower()]
        assert len(warnings) >= 1

    def test_negative_duration_warns(self):
        """Negative duration generates warning."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["duration"] = "-100"

        result = validate_input_metadata(metadata, config)

        warnings = [w for w in result.warnings if "duration" in w.field_path.lower()]
        assert len(warnings) >= 1

    def test_people_without_name_warns(self):
        """Person entry without name generates warning."""
        config = create_sample_config()
        metadata = create_valid_metadata()
        metadata["actors"] = {"actor": [{"order": "1"}]}  # No name info

        result = validate_input_metadata(metadata, config)

        warnings = [w for w in result.warnings if "actors" in w.field_path.lower()]
        assert len(warnings) >= 1

    def test_uses_configured_field_names(self):
        """Uses configured field names for validation."""
        config = {
            "primary_id_field": "custom_id",
            "ref_id_field": "custom_ref",
            "title_mappings": {
                "title_field": "custom_title",
                "title_brief_field": "custom_brief",
            },
        }
        metadata = {
            "custom_id": "123",
            "custom_title": "Test Title",
        }

        result = validate_input_metadata(metadata, config)

        assert result.is_valid is True


@pytest.mark.unit
class TestValidateOutputMetadata:
    """Tests for validate_output_metadata function"""

    def test_valid_output_passes(self):
        """Valid normalized output passes validation."""
        output = create_valid_normalized_output()

        result = validate_output_metadata(output)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_none_output_fails(self):
        """None output fails validation."""
        result = validate_output_metadata(None)

        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_non_dict_output_fails(self):
        """Non-dict output fails validation."""
        result = validate_output_metadata("not a dict")  # type: ignore

        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_missing_basic_metadata_fails(self):
        """Missing basic_metadata fails validation."""
        output = {"schema_version": "1.0.0"}

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "basic_metadata" in e.field_path]
        assert len(errors) >= 1

    def test_missing_content_id_fails(self):
        """Missing content_id fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["content_id"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "content_id" in e.field_path]
        assert len(errors) >= 1

    def test_unknown_content_id_warns(self):
        """content_id='unknown' generates warning."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["content_id"] = "unknown"

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "content_id" in w.field_path]
        assert len(warnings) >= 1

    def test_missing_work_type_fails(self):
        """Missing work_type fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["work_type"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "work_type" in e.field_path]
        assert len(errors) >= 1

    def test_invalid_work_type_warns(self):
        """Invalid work_type generates warning."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["work_type"] = "InvalidType"

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "work_type" in w.field_path]
        assert len(warnings) >= 1

    def test_valid_work_types_accepted(self):
        """All valid MEC work types are accepted."""
        for work_type in VALID_WORK_TYPES:
            output = create_valid_normalized_output()
            output["basic_metadata"]["work_type"] = work_type

            result = validate_output_metadata(output)

            work_type_warnings = [
                w
                for w in result.warnings
                if "work_type" in w.field_path and "not a standard" in w.message
            ]
            assert (
                len(work_type_warnings) == 0
            ), f"Work type {work_type} should be valid"

    def test_missing_localized_info_warns(self):
        """Missing localized_info generates warning."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["localized_info"] = []

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "localized_info" in w.field_path]
        assert len(warnings) >= 1

    def test_localized_info_missing_language_fails(self):
        """LocalizedInfo without language fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["localized_info"][0]["language"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "language" in e.field_path]
        assert len(errors) >= 1

    def test_localized_info_missing_title_warns(self):
        """LocalizedInfo without any title generates warning."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["localized_info"][0]["title_display_unlimited"]

        result = validate_output_metadata(output)

        warnings = [
            w
            for w in result.warnings
            if "localized_info" in w.field_path and "title" in w.message.lower()
        ]
        assert len(warnings) >= 1

    def test_invalid_release_year_type_fails(self):
        """Non-integer release_year fails validation."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["release_year"] = "2024"

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "release_year" in e.field_path]
        assert len(errors) >= 1

    def test_invalid_release_date_format_warns(self):
        """Invalid release_date format generates warning."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["release_date"] = "March 15, 2024"

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "release_date" in w.field_path]
        assert len(warnings) >= 1

    def test_rating_missing_region_fails(self):
        """Rating without region fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["ratings"][0]["region"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "region" in e.field_path]
        assert len(errors) >= 1

    def test_rating_missing_system_fails(self):
        """Rating without system fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["ratings"][0]["system"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "system" in e.field_path]
        assert len(errors) >= 1

    def test_rating_missing_value_fails(self):
        """Rating without value fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["ratings"][0]["value"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "value" in e.field_path]
        assert len(errors) >= 1

    def test_job_missing_job_function_fails(self):
        """Job without job_function fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["people"][0]["job_function"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "job_function" in e.field_path]
        assert len(errors) >= 1

    def test_invalid_job_function_warns(self):
        """Invalid job_function generates warning."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["people"][0]["job_function"] = "InvalidRole"

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "job_function" in w.field_path]
        assert len(warnings) >= 1

    def test_valid_job_functions_accepted(self):
        """All valid MEC job functions are accepted."""
        for job_function in list(VALID_JOB_FUNCTIONS)[:5]:  # Test a subset
            output = create_valid_normalized_output()
            output["basic_metadata"]["people"][0]["job_function"] = job_function

            result = validate_output_metadata(output)

            job_warnings = [
                w
                for w in result.warnings
                if "job_function" in w.field_path and "not a standard" in w.message
            ]
            assert (
                len(job_warnings) == 0
            ), f"Job function {job_function} should be valid"

    def test_job_missing_name_fails(self):
        """Job without name fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["people"][0]["name"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "name" in e.field_path]
        assert len(errors) >= 1

    def test_job_name_missing_display_name_fails(self):
        """Job name without display_name fails validation."""
        output = create_valid_normalized_output()
        output["basic_metadata"]["people"][0]["name"] = {"first_given_name": "John"}

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "display_name" in e.field_path]
        assert len(errors) >= 1

    def test_alt_identifier_missing_namespace_fails(self):
        """AltIdentifier without namespace fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["alt_identifiers"][0]["namespace"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "namespace" in e.field_path]
        assert len(errors) >= 1

    def test_alt_identifier_missing_identifier_fails(self):
        """AltIdentifier without identifier fails validation."""
        output = create_valid_normalized_output()
        del output["basic_metadata"]["alt_identifiers"][0]["identifier"]

        result = validate_output_metadata(output)

        assert result.is_valid is False
        errors = [e for e in result.errors if "identifier" in e.field_path]
        assert len(errors) >= 1

    def test_missing_schema_version_warns(self):
        """Missing schema_version generates warning."""
        output = create_valid_normalized_output()
        del output["schema_version"]

        result = validate_output_metadata(output)

        warnings = [w for w in result.warnings if "schema_version" in w.field_path]
        assert len(warnings) >= 1


@pytest.mark.unit
class TestValidationResultStructure:
    """Tests for ValidationResult structure and methods"""

    def test_validation_result_to_dict(self):
        """ValidationResult.to_dict() returns correct structure."""
        result = ValidationResult(is_valid=True)
        result.add_warning("test.field", "Test warning")

        result_dict = result.to_dict()

        assert "is_valid" in result_dict
        assert "issues" in result_dict
        assert "warning_count" in result_dict
        assert "error_count" in result_dict
        assert result_dict["is_valid"] is True
        assert result_dict["warning_count"] == 1
        assert result_dict["error_count"] == 0

    def test_validation_result_add_warning(self):
        """add_warning() adds warning without invalidating."""
        result = ValidationResult(is_valid=True)

        result.add_warning("field", "message")

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert len(result.errors) == 0

    def test_validation_result_add_error(self):
        """add_error() adds error and invalidates result."""
        result = ValidationResult(is_valid=True)

        result.add_error("field", "message")

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 0

    def test_validation_issue_to_dict(self):
        """ValidationIssue.to_dict() returns correct structure."""
        result = ValidationResult(is_valid=True)
        result.add_warning("test.field", "Test message", source_value="test_value")

        issue_dict = result.issues[0].to_dict()

        assert issue_dict["severity"] == "warning"
        assert issue_dict["field_path"] == "test.field"
        assert issue_dict["message"] == "Test message"
        assert issue_dict["source_value"] == "test_value"

    def test_validation_issue_without_source_value(self):
        """ValidationIssue without source_value excludes it from dict."""
        result = ValidationResult(is_valid=True)
        result.add_warning("test.field", "Test message")

        issue_dict = result.issues[0].to_dict()

        assert "source_value" not in issue_dict

    def test_warnings_property_filters_correctly(self):
        """warnings property returns only warning-level issues."""
        result = ValidationResult(is_valid=True)
        result.add_warning("field1", "warning1")
        result.add_error("field2", "error1")
        result.add_warning("field3", "warning2")

        assert len(result.warnings) == 2
        assert all(w.severity == ValidationSeverity.WARNING for w in result.warnings)

    def test_errors_property_filters_correctly(self):
        """errors property returns only error-level issues."""
        result = ValidationResult(is_valid=True)
        result.add_warning("field1", "warning1")
        result.add_error("field2", "error1")
        result.add_error("field3", "error2")

        assert len(result.errors) == 2
        assert all(e.severity == ValidationSeverity.ERROR for e in result.errors)
