"""Upstream discovery exceptions."""


class UpstreamCheckError(RuntimeError):
    """Raised when the upstream GitHub state cannot be queried or parsed."""
