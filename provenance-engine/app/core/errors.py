"""Domain errors shared across the engine."""


class ReplayAttackError(Exception):
    """Raised when a client-supplied nonce was already bound to another record."""


class VerificationError(Exception):
    """Raised when a verification request is malformed beyond repair."""
