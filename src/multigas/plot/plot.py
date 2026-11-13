"""Provide the public API for rendering multi-gas datasets.

Example:
    >>> plotter = Plot("site_6h.csv", "6h", save_as="PNG")
    >>> paths = plotter.plot_all()
"""

from pathlib import Path

import pandas as pd

from multigas.core.io import read_file
from multigas.core.types import DatasetType
from multigas.plot.six_hours import REQUIRED_COLUMNS, render
from multigas.core.exceptions import DatasetError
from multigas.plot.dimensions import validate_dimension
from multigas.utils.validation import check_columns_exist
from multigas.data.multigas_data import MultiGasData


class Plot:
    """Plot multi-gas datasets using layouts registered by dataset type.

    CSV paths are loaded and normalized with :func:`multigas.read_file`.
    Existing :class:`MultiGasData` instances are used directly. The six-hour
    PNG and PDF layouts use a compact, Nature-inspired publication style.

    Attributes:
        width (float | None): Validated whole-figure width in millimetres.
        height (float | None): Validated whole-figure height in millimetres.
        columns (int): Number of panel columns.
        log_scale (bool): Whether positive ratio panels use logarithmic axes.
        save_as (str): Uppercase output format.
        output_dir (Path): Root directory for generated output.
        verbose (bool): Whether loading emits informational messages.
        start_date (str | pd.Timestamp | None): Inclusive lower date bound.
        end_date (str | pd.Timestamp | None): Inclusive upper date bound.
        data (MultiGasData): Loaded dataset used by the renderers.
        dataset_type (DatasetType): Sampling interval of ``data``.

    Example:
        >>> Plot("site_6h.csv", "6h").plot_all()
    """

    def __init__(
        self,
        source: str | Path | MultiGasData,
        dataset_type: DatasetType | str | None = None,
        save_as: str = "PNG",
        output_dir: str | Path | None = None,
        verbose: bool = False,
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
        columns: int = 2,
        width: float | None = None,
        height: float | None = None,
        log_scale: bool = False,
    ):
        """Prepare normalized input and validate the selected layout.

        Args:
            source (str | Path | MultiGasData): CSV path or loaded dataset.
            dataset_type (DatasetType | str | None, optional): Dataset type,
                required for paths and inferred for loaded data.
            save_as (str, optional): Output format: ``PNG``, ``PDF``, or
                ``HTML``. Defaults to ``"PNG"``.
            output_dir (str | Path | None, optional): Output root containing
                the generated ``figures`` directory.
            verbose (bool, optional): Whether CSV loading emits messages.
                Defaults to ``False``.
            start_date (str | pd.Timestamp | None, optional): Inclusive lower
                date bound.
            end_date (str | pd.Timestamp | None, optional): Inclusive upper
                date bound.
            columns (int, optional): Number of panel columns, either ``1`` or
                ``2``. Defaults to ``2``.
            width (float | None, optional): Whole-figure width in millimetres.
            height (float | None, optional): Whole-figure height in millimetres.
            log_scale (bool, optional): Whether positive ratio panels use
                logarithmic axes. Defaults to ``False``.

        Raises:
            DatasetError: If the supplied type conflicts or is unsupported.
            ColumnError: If a required six-hour plot column is missing.
            ValueError: If dimensions, format, columns, or path type are invalid.

        Example:
            >>> plotter = Plot("site_6h.csv", "6h", save_as="HTML")
        """
        self.width = validate_dimension(width, "width")
        self.height = validate_dimension(height, "height")

        if (
            isinstance(columns, bool)
            or not isinstance(columns, int)
            or columns not in {1, 2}
        ):
            raise ValueError("columns must be 1 or 2")

        self.columns = columns
        self.log_scale = log_scale
        self.save_as = save_as.upper()

        if self.save_as not in {"PNG", "PDF", "HTML"}:
            raise ValueError("save_as must be PNG, PDF, or HTML")

        self.output_dir = (
            Path.cwd() / "output" if output_dir is None else Path(output_dir)
        )

        self.verbose = verbose
        self.start_date = start_date
        self.end_date = end_date

        if isinstance(source, MultiGasData):
            self.data = source
            if (
                dataset_type is not None
                and DatasetType(dataset_type) != source.dataset_type
            ):
                raise DatasetError(
                    f"Supplied dataset_type {dataset_type!r} conflicts with "
                    f"MultiGasData type {source.dataset_type.value!r}"
                )
            self.dataset_type = source.dataset_type
        else:
            if dataset_type is None:
                raise ValueError("dataset_type is required when source is a CSV path")
            self.dataset_type = DatasetType(dataset_type)
            if self.dataset_type != DatasetType.SIX_HOURS:
                raise DatasetError(
                    f"Plot layout is not supported for {self.dataset_type.value!r}"
                )
            self.data = read_file(
                source,
                self.dataset_type,
                normalize=True,
                verbose=verbose,
                output_dir=self.output_dir,
            )

        if self.dataset_type != DatasetType.SIX_HOURS:
            raise DatasetError(
                f"Plot layout is not supported for {self.dataset_type.value!r}"
            )

        check_columns_exist(REQUIRED_COLUMNS, self.data.df.columns.tolist())

    def plot_all(self) -> dict[str, Path]:
        """Render full-period and trailing-three-month plots.

        Returns:
            dict[str, Path]: Output paths named ``full_period`` and
                ``trailing_three_months``.

        Raises:
            DatasetError: If the dataset has no usable datetime index or the
                configured date range contains no data.

        Example:
            >>> paths = Plot(
            ...     data, start_date="2025-01-01", end_date="2025-03-31"
            ... ).plot_all()
            >>> paths["full_period"].suffix
            '.png'
        """
        index = self.data.df.index

        if not isinstance(index, pd.DatetimeIndex) or index.empty:
            raise DatasetError("Plot data must have a non-empty DatetimeIndex")

        start_bound = pd.Timestamp(self.start_date) if self.start_date else None
        end_bound = pd.Timestamp(self.end_date) if self.end_date else None

        if isinstance(self.end_date, str) and len(self.end_date.strip()) == 10:
            end_bound = (
                pd.Timestamp(self.end_date).normalize()
                + pd.Timedelta(days=1)
                - pd.Timedelta(1, "ns")
            )

        selected = self.data.df.loc[start_bound:end_bound]

        if selected.empty:
            start_label = (
                self.start_date
                if self.start_date is not None
                else "first available date"
            )
            end_label = self.end_date if self.end_date else "last available date"
            raise DatasetError(
                f"No data found between {start_label} and {end_label}. "
                "Choose a date range that overlaps the dataset."
            )

        selected_index = selected.index
        end = selected_index.max()
        start = selected_index.min()
        three_month_start = end - pd.DateOffset(months=3)

        if not (selected_index >= three_month_start).any():
            three_month_start = end

        ext = {"PNG": ".png", "PDF": ".pdf", "HTML": ".html"}[self.save_as]

        directory = self.output_dir / "figures"
        directory.mkdir(parents=True, exist_ok=True)
        full_path = directory / f"{self.data.basename}-full-period{ext}"
        recent_path = directory / f"{self.data.basename}-trailing-three-months{ext}"

        return {
            "full_period": render(
                self.data,
                start,
                end,
                full_path,
                self.save_as,
                columns=self.columns,
                width=self.width,
                height=self.height,
                log_scale=self.log_scale,
            ),
            "trailing_three_months": render(
                self.data,
                max(start, three_month_start),
                end,
                recent_path,
                self.save_as,
                columns=self.columns,
                width=self.width,
                height=self.height,
                log_scale=self.log_scale,
            ),
        }
