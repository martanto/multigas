from __future__ import annotations

import joblib
import pandas as pd

from multigas.core.types import DatasetType
from multigas.data.loader import DataLoader
from multigas.utils.cache import get_cache_path
from multigas.utils.path import ensure_dir


def test_load_supports_timestamp_alias(tmp_path) -> None:
    file_path = tmp_path / "alias_timestamp.csv"
    file_path.write_text(
        "Timestamp,CO2,status\n2025-01-01 00:00:00,1.2,ok\n2025-01-01 00:01:00,2.3,ok\n",
        encoding="utf-8",
    )

    loader = DataLoader(cache_dir=tmp_path / "cache")
    result = loader.load(
        file_path=file_path,
        dataset_type=DatasetType.ONE_MINUTE,
        normalize=False,
        use_cache=False,
    )

    assert result.df.index.name == "TIMESTAMP"
    assert isinstance(result.df.index, pd.DatetimeIndex)
    assert result.df["CO2"].tolist() == [1.2, 2.3]


def test_normalize_preserves_non_numeric_text_columns() -> None:
    loader = DataLoader()
    raw = pd.DataFrame({"CO2": ["1.2", "2.3"], "status": ["ok", "fail"]})

    normalized = loader._normalize(raw)

    assert normalized["CO2"].tolist() == [1.2, 2.3]
    assert normalized["status"].tolist() == ["ok", "fail"]


def test_load_from_cache_invalidates_on_size_mismatch(tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "TIMESTAMP,CO2\n2025-01-01 00:00:00,1.2\n",
        encoding="utf-8",
    )
    ensure_dir(cache_dir)
    loader = DataLoader(cache_dir=cache_dir)

    stat = source_path.stat()
    cache_path = get_cache_path(cache_dir, source_path)
    cached_df = pd.DataFrame({"CO2": [1.2]})
    joblib.dump(
        {
            "dataframe": cached_df,
            "metadata": {
                "file_path": str(source_path.absolute()),
                "mtime": stat.st_mtime,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size + 1,
            },
        },
        cache_path,
        compress=3,
    )

    loaded_df = loader._load_from_cache(source_path)

    assert loaded_df is None
    assert cache_path.exists() is False
