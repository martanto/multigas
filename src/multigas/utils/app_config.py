"""Environment defaults shared by local HTTP and command-line ingestion."""

import os


def upload_limit_bytes() -> int:
    """Read a positive upload limit, defaulting to 5 GiB.

    Returns:
        int: Maximum accepted source bytes.

    Raises:
        ValueError: If MULTIGAS_UPLOAD_LIMIT_BYTES is not a positive integer.

    Example:
        >>> upload_limit_bytes()
        5368709120
    """
    try:
        limit = int(os.getenv("MULTIGAS_UPLOAD_LIMIT_BYTES", "5368709120"))
        if limit <= 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError(
            "MULTIGAS_UPLOAD_LIMIT_BYTES must be a positive integer"
        ) from exc
    return limit
