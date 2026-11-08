"""Reusable daily CSV extraction, preserving legacy file layout and stats."""

import os
import json
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed
from slugify import slugify

from multigas.logging import logger
from multigas.core.types import DatasetType, ExtractedStats
from multigas.utils.dataframe import count_csv_rows, calculate_completeness


def extract_daily(
    df: pd.DataFrame,
    dataset_type: DatasetType,
    source_path: Path,
    output_dir: Path | str | None = None,
    return_as_list: bool = False,
    n_jobs: int = 1,
    overwrite: bool = True,
    plot: bool = True,
    verbose: bool = False,
) -> list[ExtractedStats] | pd.DataFrame:
    """Shared daily extraction implementation; see MultiGasData for the public contract."""
    if output_dir is None:
        output_dir = Path.cwd() / "output"
    else:
        output_dir = Path(output_dir)

    dataset_dir = output_dir / "daily" / dataset_type.label
    daily_dir = dataset_dir / slugify(source_path.stem)
    daily_dir.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    dates = (
        pd.DatetimeIndex([])
        if df.empty
        else pd.date_range(
            df.index.min().normalize(),
            df.index.max().normalize(),
            freq="D",
        )
    )

    if n_jobs > 1:
        max_jobs = max(1, (os.cpu_count() or 1) - 2)
        n_jobs = min(n_jobs, max_jobs)

    jobs = build_jobs(dates, df, daily_dir, overwrite)

    if n_jobs == 1:
        results = [
            extract_one_day(
                date_str,
                df_daily,
                output_file,
                dataset_type,
                verbose=verbose,
                overwrite=job_overwrite,
            )
            for date_str, df_daily, output_file, job_overwrite in jobs
        ]
    else:
        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(extract_one_day)(
                date_str,
                df_daily,
                output_file,
                dataset_type,
                verbose=verbose,
                overwrite=job_overwrite,
            )
            for date_str, df_daily, output_file, job_overwrite in jobs
        )

    skipped_count = sum(1 for _, _, _, job_overwrite in jobs if not job_overwrite)
    if skipped_count > 0:
        logger.info(f"Skipped {skipped_count} existing files under {daily_dir}")

    extracted_files: list[ExtractedStats] = []
    missing_dates: list[str] = []
    for stats, is_missing in results:
        if is_missing:
            missing_dates.append(stats["date"])
            continue
        extracted_files.append(stats)

    if missing_dates:
        logger.warning(
            f"Found {len(missing_dates)} missing dates for file {source_path}"
        )
        logger.warning(f"Missing files: {', '.join(missing_dates)}")

    df_results = pd.DataFrame(
        extracted_files, columns=["date", "total_data", "completeness"]
    )
    csv_filepath = dataset_dir / f"{slugify(source_path.stem)}-completeness.csv"
    df_results.to_csv(csv_filepath, index=False)

    if plot:
        # Imported lazily so ``import multigas`` doesn't pull in matplotlib.
        from multigas.plot.plot_completeness import plot_completeness

        plot_completeness(
            filepath=csv_filepath,
            title=f"{source_path.stem} ({dataset_type.label})",
            verbose=verbose,
        )

    if return_as_list:
        json_path = dataset_dir / f"{slugify(source_path.stem)}.json"
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(extracted_files, file, indent=4, ensure_ascii=False)
        return extracted_files

    return df_results


def build_jobs(
    dates: pd.DatetimeIndex,
    df: pd.DataFrame,
    daily_dir: Path,
    overwrite: bool,
) -> list[tuple[str, pd.DataFrame, Path, bool]]:
    """Shared daily extraction implementation; see MultiGasData for the public contract."""
    jobs: list[tuple[str, pd.DataFrame, Path, bool]] = []
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        output_file = daily_dir / f"{date_str}.csv"
        if not overwrite and output_file.exists():
            jobs.append((date_str, pd.DataFrame(), output_file, False))
        else:
            df_daily = df.loc[date_str:date_str]
            jobs.append((date_str, df_daily, output_file, True))
    return jobs


def extract_one_day(
    date_str: str,
    df_daily: pd.DataFrame,
    output_file: Path,
    dataset_type: DatasetType,
    verbose: bool,
    overwrite: bool,
) -> tuple[ExtractedStats, bool]:
    """Shared daily extraction implementation; see MultiGasData for the public contract."""
    if not overwrite:
        if verbose:
            logger.info(
                f"{date_str} :: Already exists, reading stats from: {output_file}"
            )
        total_data = count_csv_rows(output_file)
        return (
            ExtractedStats(
                date=date_str,
                total_data=total_data,
                completeness=calculate_completeness(
                    total_data,
                    dataset_type,
                    as_percentage=True,
                ),
            ),
            False,
        )

    if verbose:
        logger.info(f"{date_str} :: Extracting ...")

    if df_daily.empty:
        return (
            ExtractedStats(date=date_str, total_data=0, completeness=0.0),
            True,
        )

    total_data = len(df_daily)
    stats = ExtractedStats(
        date=date_str,
        total_data=total_data,
        completeness=calculate_completeness(
            total_data,
            dataset_type,
            as_percentage=True,
        ),
    )
    df_daily.to_csv(output_file, index=True)

    if verbose:
        logger.info(f"{date_str} :: Extracted to: {output_file}")

    return stats, False
