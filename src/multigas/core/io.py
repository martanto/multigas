"""Convenience wrappers for one-call file loading."""

from pathlib import Path

from multigas.core import MultiGasData
from multigas.core.types import DatasetType
from multigas.data.loader import DataLoader


def read_file(
    file_path: Path | str,
    dataset_type: DatasetType | str,
    index_col: str = "TIMESTAMP",
    drop_empty_columns: bool = False,
    normalize: bool = True,
    use_cache: bool = True,
    output_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
    overwrite: bool = False,
    verbose: bool = False,
) -> MultiGasData:
    """Load a data file and return a :class:`MultiGasData` result.

    A thin wrapper around :class:`DataLoader` that constructs the loader,
    calls :meth:`DataLoader.load`, and returns the result in one call.

    Args:
        file_path: Path to the source CSV or dat file.
        dataset_type: Dataset type identifier — a :class:`DatasetType` member
            or its string value (e.g. ``"1min"``).
        index_col (str): Exact name of the column to promote to the
            DataFrame index. The column's values are coerced with
            :func:`pandas.to_datetime` (``errors="coerce"``) before
            being set as the index. Matching is case-sensitive; the
            column must exist in the source file. Defaults to
            ``"TIMESTAMP"``.
        drop_empty_columns: Drop columns that are entirely NaN after
            normalisation. Defaults to ``False``.
        normalize: Replace NAN sentinel strings with ``np.nan`` and coerce
            object columns to numeric. Defaults to ``True``.
        use_cache: Read from and write to the on-disk joblib cache when
            ``normalize`` is also ``True``. Defaults to ``True``.
        output_dir: Root output directory. String values are coerced to
            :class:`~pathlib.Path`. Defaults to ``<cwd>/output``.
        cache_dir: Directory for cached files. Defaults to
            ``<output_dir>/cache``.
        overwrite: Ignore any existing cache entry and re-load from source.
            Defaults to ``False``.
        verbose: Emit informational log messages during loading. Defaults to
            ``False``.

    Returns:
        A :class:`MultiGasData` instance containing the DataFrame, dataset
        type, and absolute source path.

    Raises:
        LoaderError: If the file does not exist or cannot be parsed.

    Example:
        >>> from multigas.core.io import read_file
        >>> ds = read_file("data/site_a.dat", dataset_type="1min")
        >>> ds.df.shape
        (1440, 10)
    """
    mutigas_data = DataLoader(
        output_dir=output_dir,
        cache_dir=cache_dir,
        overwrite=overwrite,
        verbose=verbose,
    ).load(
        file_path=file_path,
        dataset_type=dataset_type,
        index_col=index_col,
        drop_empty_columns=drop_empty_columns,
        normalize=normalize,
        use_cache=use_cache,
    )

    return mutigas_data
