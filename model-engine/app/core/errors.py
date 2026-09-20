"""Domain errors shared across the engine."""


class AnalysisError(Exception):
    """Raised when an assessment cannot be performed (bad input, unloadable model…)."""
