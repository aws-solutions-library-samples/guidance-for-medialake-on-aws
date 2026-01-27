"""Base interfaces for source-specific metadata normalizers.

This module defines the abstract base class and data structures that all
source normalizers must implement. The design supports pluggable normalizers
for different metadata source formats while producing consistent MEC-compliant output.

Key Classes:
    SourceNormalizer: Abstract base class for all normalizers
    ValidationResult: Result of input validation
    ValidationIssue: Individual validation issue (warning or error)
    NormalizationResult: Complete result of normalization process
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationSeverity(Enum):
    """Severity level for validation issues.

    WARNING: Non-blocking issue that allows normalization to proceed
    ERROR: Blocking issue that prevents normalization
    """

    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationIssue:
    """Represents a single validation issue found during normalization.

    Attributes:
        severity: Whether this is a warning or error
        field_path: Dot-notation path to the problematic field (e.g., "ratings.0.value")
        message: Human-readable description of the issue
        source_value: The actual value that caused the issue (for debugging)
    """

    severity: ValidationSeverity
    field_path: str
    message: str
    source_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation with severity as string
        """
        result: dict[str, Any] = {
            "severity": self.severity.value,
            "field_path": self.field_path,
            "message": self.message,
        }
        if self.source_value is not None:
            result["source_value"] = self.source_value
        return result


@dataclass
class ValidationResult:
    """Result of input validation.

    Attributes:
        is_valid: True if no blocking errors were found
        issues: List of all validation issues (warnings and errors)
    """

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all warning-level issues.

        Returns:
            List of ValidationIssue with WARNING severity
        """
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all error-level issues.

        Returns:
            List of ValidationIssue with ERROR severity
        """
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def add_warning(
        self, field_path: str, message: str, source_value: Any | None = None
    ) -> None:
        """Add a warning-level validation issue.

        Args:
            field_path: Path to the field with the issue
            message: Description of the issue
            source_value: The problematic value (optional)
        """
        self.issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=field_path,
                message=message,
                source_value=source_value,
            )
        )

    def add_error(
        self, field_path: str, message: str, source_value: Any | None = None
    ) -> None:
        """Add an error-level validation issue and mark result as invalid.

        Args:
            field_path: Path to the field with the issue
            message: Description of the issue
            source_value: The problematic value (optional)
        """
        self.issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field_path=field_path,
                message=message,
                source_value=source_value,
            )
        )
        self.is_valid = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with is_valid flag and list of issues
        """
        return {
            "is_valid": self.is_valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "warning_count": len(self.warnings),
            "error_count": len(self.errors),
        }


@dataclass
class NormalizationResult:
    """Result of the normalization process.

    Attributes:
        success: True if normalization completed successfully
        normalized_metadata: The MEC-compliant normalized metadata (if successful)
        validation: Validation result with any warnings or errors
        raw_source: Original source metadata for debugging (if configured)
        schema_version: Version of the normalization schema used
    """

    success: bool
    normalized_metadata: dict[str, Any] | None = None
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(is_valid=True)
    )
    raw_source: dict[str, Any] | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for storage or API response
        """
        result: dict[str, Any] = {
            "success": self.success,
            "schema_version": self.schema_version,
            "validation": self.validation.to_dict(),
        }

        if self.normalized_metadata is not None:
            result["normalized_metadata"] = self.normalized_metadata

        if self.raw_source is not None:
            result["raw_source"] = self.raw_source

        return result


class SourceNormalizer(ABC):
    """Abstract base class for source-specific metadata normalizers.

    All source normalizers must implement this interface. The normalizer
    architecture is configuration-driven - all customer-specific field names
    and namespace prefixes are defined in the config parameter, NOT in code.

    Example:
        class MySourceNormalizer(SourceNormalizer):
            def get_source_type(self) -> str:
                return "my_source"

            def validate_input(self, raw_metadata: dict) -> ValidationResult:
                # Validate using configured field names
                ...

            def normalize(self, raw_metadata: dict) -> NormalizationResult:
                # Transform using configured mappings
                ...

    Attributes:
        config: Configuration dictionary containing customer-specific settings
    """

    config: dict[str, Any]

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the normalizer with configuration.

        Args:
            config: Configuration dictionary containing:
                - source_namespace_prefix: Customer namespace (e.g., "CUSTOMER")
                - identifier_mappings: Field name → namespace mappings
                - title_mappings: Title field configurations
                - people_field_mappings: People field configurations
                - rating_system_mappings: Rating system configurations
                - And other customer-specific settings
        """
        self.config = config or {}

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type identifier.

        This identifier is used by the factory to select the appropriate
        normalizer and is included in source attribution.

        Returns:
            Source type string (e.g., "generic_xml", "json_api")
        """

    @abstractmethod
    def validate_input(self, raw_metadata: dict[str, Any]) -> ValidationResult:
        """Validate the source metadata structure before normalization.

        This method should check for:
        - Required fields (using configured field names)
        - Valid data formats
        - Structural integrity

        Args:
            raw_metadata: Raw metadata dictionary from the source system

        Returns:
            ValidationResult with is_valid=True if validation passes,
            or is_valid=False with error details if validation fails
        """

    @abstractmethod
    def normalize(self, raw_metadata: dict[str, Any]) -> NormalizationResult:
        """Transform source metadata to MEC-compliant normalized format.

        This method should:
        1. Validate input (call validate_input)
        2. Transform fields using configured mappings
        3. Build MEC-compliant output structure
        4. Extract unmapped fields to custom_fields
        5. Populate source attribution

        Args:
            raw_metadata: Raw metadata dictionary from the source system

        Returns:
            NormalizationResult with success=True and normalized_metadata
            if successful, or success=False with validation errors if failed
        """

    def get_config_value(self, key: str, default: Any | None = None) -> Any | None:
        """Get a configuration value with optional default.

        Helper method for accessing configuration values safely.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
