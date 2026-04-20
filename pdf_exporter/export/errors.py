"""Export-specific exceptions."""


class PDFExportError(RuntimeError):
    """Raised when an allowed workflow cannot produce a valid PDF."""
