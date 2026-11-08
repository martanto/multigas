"""Validated request contracts for local scientific analysis."""

from typing import Literal

from pydantic import Field, BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    """Reject unknown request fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ImportSpec(StrictModel):
    station: str = Field(min_length=1, max_length=120)
    timestamp: str = "TIMESTAMP"
    mode: Literal["1s", "2s", "1min", "6h", "zero", "span", "wx"] = "1min"
    units: dict[str, str] = Field(default_factory=dict)
    normalize: bool = True


class Filter(StrictModel):
    column: str
    comparator: Literal[">", ">=", "<", "<=", "=", "!="]
    value: float = Field(allow_inf_nan=False)


class AnalysisSpec(StrictModel):
    dataset: str
    start: str | None = None
    end: str | None = None
    channels: list[str] = Field(default_factory=list, max_length=40)
    panels: list[str] = Field(default_factory=list, max_length=10)
    ratio_source: Literal["onboard", "calculated"] = "onboard"
    filters: list[Filter] = Field(default_factory=list, max_length=20)


class ExportSpec(AnalysisSpec):
    kind: Literal["csv", "zip", "figure"] = "csv"
    format: Literal["png", "pdf", "svg"] = "png"
    width: float = Field(default=10, ge=1, le=30)
    height: float = Field(default=16, ge=1, le=40)
    dpi: int = Field(default=300, ge=50, le=600)
    days: list[str] = Field(default_factory=list, max_length=3660)
    y_limits: dict[str, tuple[float, float]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_render(self):
        """Bound renderer allocation before scheduling an export."""
        if self.width * self.height * self.dpi**2 > 80000000:
            raise ValueError(
                "Figure exceeds the 80 megapixel limit; reduce dimensions or DPI"
            )
        return self


class SavedView(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    analysis: AnalysisSpec
    arrangement: list[str] = Field(default_factory=list, max_length=10)
