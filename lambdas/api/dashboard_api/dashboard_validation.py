"""Layout validation utilities."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from dashboard_defaults import WIDGET_CONSTRAINTS

MAX_WIDGETS = 20
MAX_LAYOUT_SIZE_BYTES = 32 * 1024  # 32KB
MAX_CONFIG_SIZE_BYTES = 4 * 1024  # 4KB per widget


@dataclass
class ValidationError:
    """Validation error details."""

    field: str
    message: str


@dataclass
class ValidationResult:
    """Result of layout validation."""

    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)

    def add_error(self, field_name: str, message: str):
        self.is_valid = False
        self.errors.append(ValidationError(field=field_name, message=message))


def validate_widget_count(widgets: List[Dict[str, Any]]) -> ValidationResult:
    """Validate widget count does not exceed maximum."""
    result = ValidationResult()
    if len(widgets) > MAX_WIDGETS:
        result.add_error(
            "widgets",
            f"Cannot have more than {MAX_WIDGETS} widgets (got {len(widgets)})",
        )
    return result


def validate_widget_sizes(
    widgets: List[Dict[str, Any]], layouts: Dict[str, List[Dict[str, Any]]]
) -> ValidationResult:
    """Validate widget sizes against type constraints."""
    result = ValidationResult()

    widget_types = {w["id"]: w.get("type") for w in widgets}

    for breakpoint, layout_items in layouts.items():
        for item in layout_items:
            widget_id = item.get("i")
            widget_type = widget_types.get(widget_id)

            if not widget_type or widget_type not in WIDGET_CONSTRAINTS:
                continue

            constraints = WIDGET_CONSTRAINTS[widget_type]
            min_size = constraints["minSize"]
            max_size = constraints["maxSize"]

            w, h = item.get("w", 0), item.get("h", 0)

            if w < min_size["w"]:
                result.add_error(
                    f"layouts.{breakpoint}[{widget_id}].w",
                    f"Width {w} below minimum {min_size['w']} for '{widget_type}'",
                )
            if w > max_size["w"]:
                result.add_error(
                    f"layouts.{breakpoint}[{widget_id}].w",
                    f"Width {w} exceeds maximum {max_size['w']} for '{widget_type}'",
                )
            if h < min_size["h"]:
                result.add_error(
                    f"layouts.{breakpoint}[{widget_id}].h",
                    f"Height {h} below minimum {min_size['h']} for '{widget_type}'",
                )
            if h > max_size["h"]:
                result.add_error(
                    f"layouts.{breakpoint}[{widget_id}].h",
                    f"Height {h} exceeds maximum {max_size['h']} for '{widget_type}'",
                )

    return result


def validate_layout_size(
    widgets: List[Dict[str, Any]], layouts: Dict[str, List[Dict[str, Any]]]
) -> ValidationResult:
    """Validate total layout configuration size."""
    result = ValidationResult()

    layout_data = {"widgets": widgets, "layouts": layouts}
    size = len(json.dumps(layout_data).encode("utf-8"))

    if size > MAX_LAYOUT_SIZE_BYTES:
        result.add_error(
            "layout",
            f"Layout size {size} bytes exceeds maximum {MAX_LAYOUT_SIZE_BYTES} bytes",
        )

    return result


def validate_config_size(widgets: List[Dict[str, Any]]) -> ValidationResult:
    """Validate individual widget configuration sizes."""
    result = ValidationResult()

    for widget in widgets:
        config = widget.get("config", {})
        if config:
            size = len(json.dumps(config).encode("utf-8"))
            if size > MAX_CONFIG_SIZE_BYTES:
                result.add_error(
                    f"widgets[{widget['id']}].config",
                    f"Config size {size} bytes exceeds maximum {MAX_CONFIG_SIZE_BYTES} bytes",
                )

    return result


def validate_layout(
    widgets: List[Dict[str, Any]], layouts: Dict[str, List[Dict[str, Any]]]
) -> ValidationResult:
    """Run all layout validations and aggregate results."""
    result = ValidationResult()

    for validation_result in [
        validate_widget_count(widgets),
        validate_widget_sizes(widgets, layouts),
        validate_layout_size(widgets, layouts),
        validate_config_size(widgets),
    ]:
        if not validation_result.is_valid:
            result.is_valid = False
            result.errors.extend(validation_result.errors)

    return result
