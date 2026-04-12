from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    """Create a directory (and any missing parents) if it does not already exist.

    A thin wrapper around ``Path.mkdir(parents=True, exist_ok=True)`` that
    returns the path so callers can chain it inline.

    Args:
        path (Path | str): Directory path to create.

    Returns:
        Path: The same path as a ``Path`` object.

    Raises:
        PermissionError: If the process lacks permission to create the directory.

    Example:
        >>> log_dir = ensure_dir("logs/daily")
        >>> log_dir.is_dir()
        True
    """
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
