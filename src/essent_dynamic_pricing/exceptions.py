"""Exceptions for the Essent dynamic pricing client."""

class EssentError(Exception):
    """Base exception for Essent client errors."""


class EssentConnectionError(EssentError):
    """Raised when communication with the API fails."""


class EssentResponseError(EssentError):
    """Raised when the API returns an unexpected response."""


class EssentDataError(EssentError):
    """Raised when the response data is missing or invalid."""
