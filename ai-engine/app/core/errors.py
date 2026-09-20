"""Domain errors shared across the engine."""

from __future__ import annotations


class AnalysisError(Exception):
    """Raised when an analysis cannot be performed (bad input, empty dataset…)."""
