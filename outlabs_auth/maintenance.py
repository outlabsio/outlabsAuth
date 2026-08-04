"""Typed outcomes for deterministic OutlabsAuth maintenance cycles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _reported_errors(value: object) -> int:
    if not isinstance(value, Mapping):
        return 0
    errors = value.get("errors", 0)
    if isinstance(errors, bool) or not isinstance(errors, int):
        return 0
    return max(errors, 0)


class MaintenanceReport(BaseModel):
    """Secret-free summary of one at-least-once maintenance invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    results: dict[str, Any]
    expected_steps: tuple[str, ...]
    completed_steps: tuple[str, ...]
    missing_steps: tuple[str, ...]
    error_steps: tuple[str, ...]
    reported_errors: int = Field(ge=0)

    @classmethod
    def from_results(
        cls,
        results: Mapping[str, Any],
        *,
        expected_steps: Iterable[str] = (),
    ) -> MaintenanceReport:
        """Build a stable report from the library's per-step result mapping."""

        normalized_results = dict(results)
        expected = _ordered_unique(expected_steps)
        completed = tuple(normalized_results)
        missing = tuple(step for step in expected if step not in normalized_results)
        error_counts = {step: _reported_errors(result) for step, result in normalized_results.items()}
        error_steps = tuple(step for step, count in error_counts.items() if count)
        reported_errors = sum(error_counts.values())
        return cls(
            ok=not missing and reported_errors == 0,
            results=normalized_results,
            expected_steps=expected,
            completed_steps=completed,
            missing_steps=missing,
            error_steps=error_steps,
            reported_errors=reported_errors,
        )


__all__ = ["MaintenanceReport"]
