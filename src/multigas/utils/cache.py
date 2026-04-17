import hashlib
from pathlib import Path


def get_cache_key(file_path: Path | str) -> str:
    """Generate a cache key from the absolute file path and its mtime.

    The key is an MD5 hex digest of ``"<absolute_path>_<mtime>"``, so it
    changes automatically whenever the source file is modified.

    Args:
        file_path: Path to the source file.

    Returns:
        Hex-encoded MD5 digest string used as the cache filename stem.

    Example:
        >>> key = get_cache_key(Path("data/site_a.csv"))
        >>> len(key)
        32
    """
    resolved_path = Path(file_path)
    mtime = resolved_path.stat().st_mtime
    key_string = f"{resolved_path.absolute()}_{mtime}"
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cache_path(cache_dir: Path | str, file_path: Path | str) -> Path:
    """Resolve the on-disk path for a cached version of a source file.

    Args:
        cache_dir: Directory where cache files are stored.
        file_path: Path to the source file whose cache path is resolved.

    Returns:
        Absolute path to the ``.pkl`` cache file inside ``cache_dir``.

    Example:
        >>> path = get_cache_path("/tmp/cache", "data/site_a.csv")
        >>> path.suffix
        '.pkl'
    """
    cache_dir: Path = Path(cache_dir)
    cache_key = get_cache_key(file_path)
    return cache_dir / f"{cache_key}.pkl"
