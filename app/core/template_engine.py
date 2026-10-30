"""
Template rendering engine – replaces {placeholders} with real values.
"""
import re
from typing import Any


PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")


def render_template(content: str, context: dict[str, Any]) -> str:
    """
    Replace all {key} placeholders in *content* with values from *context*.
    Unknown placeholders are left intact.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(context.get(key, match.group(0)))

    return PLACEHOLDER_PATTERN.sub(replacer, content)


def build_doctor_context(doctor) -> dict[str, Any]:
    """Build a rendering context dict from a Doctor ORM object."""
    return {
        "doctor_name": doctor.name,
        "specialty": doctor.specialty,
        "mobile": doctor.mobile,
        "clinic_name": doctor.clinic_name or "",
        "city": doctor.city or "",
    }


def extract_placeholders(content: str) -> list[str]:
    """Return a list of placeholder names found in a template string."""
    return PLACEHOLDER_PATTERN.findall(content)
