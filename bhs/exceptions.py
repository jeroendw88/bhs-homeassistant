"""Exceptions for the BHS integration."""


class BHSApiError(Exception):
    """Base exception for BHS API errors."""


class BHSConnectionError(BHSApiError):
    """Raised when the BHS controller cannot be reached."""
