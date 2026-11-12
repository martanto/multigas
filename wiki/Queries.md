# Fluent Queries

Complete reference for `Query`, the fluent query mixin inherited by
`MultiGasData`. Methods that change rows or selected columns mutate the
working object in place. `refresh()` restores the original DataFrame.

> Back to [Home](Home.md) · See also [Getting Started](Getting-Started.md) and [API Reference](API-Reference.md#query-mixin).

## Query index

| Name | Description | File location | Argument details |
|---|---|---|---|
| `Query(...)` | Initialize a DataFrame wrapper with a datetime index and pristine copy. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Constructor](#query) |
| `missing_columns` | List columns containing missing values or empty strings. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Property](#missing_columns) |
| `empty_columns` | List columns considered empty (all missing, all zero, or all empty strings). | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Property](#empty_columns) |
| `intersection(...)` | Return shared names in the order of the first list. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Static helper](#intersection) |
| `unique(...)` | Return the deduplicated union of two name lists. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Static helper](#unique) |
| `reset_selected_columns()` | Clear any staged column selection. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#reset_selected_columns) |
| `refresh()` | Restore the pristine DataFrame and reset selection and derived metadata. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#refresh) |
| `is_filtered()` | Check whether the working DataFrame differs from its original copy. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#is_filtered) |
| `column_has_missing(...)` | Check a column for nulls or empty strings. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#column_has_missing) |
| `column_is_empty(...)` | Check whether a column contains no meaningful values. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#column_is_empty) |
| `select_columns(...)` | Stage named columns for selection; optionally keep numeric columns only. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#select_columns) |
| `select_numeric_columns(...)` | Stage all numeric columns or a numeric subset. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#select_numeric_columns) |
| `count()` | Count rows in the current working DataFrame. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#count) |
| `where(...)` | Filter rows by a comparator against a column or the datetime index. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#where) |
| `where_date(...)` | Filter rows to a partial-string date on the datetime index. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#where_date) |
| `where_date_between(...)` | Filter rows between inclusive partial-string date bounds. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#where_date_between) |
| `where_values_between(...)` | Filter a numeric column between inclusive bounds. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#where_values_between) |
| `get()` | Commit a staged selection and return the working DataFrame. | [`src/multigas/core/query.py`](../src/multigas/core/query.py) | [Method](#get) |

## Constructor and properties

### `Query`

```python
Query(df: pd.DataFrame, index_col: str | None = None, verbose: bool = False)
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `df` | `pd.DataFrame` | required | Non-empty DataFrame containing `index_col`, or already carrying a `pd.DatetimeIndex`. |
| `index_col` | `str \| None` | `None` (→ `TIMESTAMP`) | Source column to convert to a datetime index. |
| `verbose` | `bool` | `False` | Emit informational logs for operations. |

### `missing_columns`

Property with no arguments. Returns `list[str]`; uses the active selection when present, otherwise all current columns.

### `empty_columns`

Property with no arguments. Returns `list[str]`; uses the active selection when present, otherwise all current columns.

## Selection and inspection

### `intersection`

```python
Query.intersection(first_list: list[str], second_list: list[str]) -> list[str]
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `first_list` | `list[str]` | required | Primary list; determines result order and duplicate preservation. |
| `second_list` | `list[str]` | required | Names checked for membership. |

### `unique`

```python
Query.unique(first_list: list[str], second_list: list[str]) -> list[str]
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `first_list` | `list[str]` | required | First list of names. |
| `second_list` | `list[str]` | required | Second list of names. |

### `reset_selected_columns`

```python
Query.reset_selected_columns() -> Self
```

No arguments. Clears the staged selection and returns the same instance.

### `refresh`

```python
Query.refresh() -> Self
```

No arguments. Restores `df_original`, clears selection, and recomputes numeric columns and date bounds.

### `is_filtered`

```python
Query.is_filtered() -> bool
```

No arguments. Returns whether the current DataFrame differs from `df_original`.

### `column_has_missing`

```python
Query.column_has_missing(column_name: str) -> bool
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_name` | `str` | required | Column to inspect for NaN, `pd.NA`, or empty string values. |

### `column_is_empty`

```python
Query.column_is_empty(column_name: str) -> bool
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_name` | `str` | required | Column to test for all missing values, all numeric zeroes, or all empty strings, depending on dtype. |

### `select_columns`

```python
Query.select_columns(column_names: str | list[str], numeric_column_only: bool = False, validate: bool = True) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_names` | `str \| list[str]` | required | One column name or a list of names to stage. |
| `numeric_column_only` | `bool` | `False` | Keep only numeric columns from the requested names. |
| `validate` | `bool` | `True` | Raise `ColumnError` if any requested name is unknown. |

### `select_numeric_columns`

```python
Query.select_numeric_columns(column_names: str | list[str] | None = None, validate: bool = True) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_names` | `str \| list[str] \| None` | `None` | `None` selects every numeric column; otherwise select the numeric intersection of the requested names. |
| `validate` | `bool` | `True` | Raise `ColumnError` for names absent from the original columns; existing non-numeric names are dropped. |

### `count`

```python
Query.count() -> int
```

No arguments. Returns the number of rows in the current DataFrame.

## Filtering and result

### `where`

```python
Query.where(column_name: str, comparator: str, value: Any) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_name` | `str` | required | Column name, or the index name to compare against the DatetimeIndex. |
| `comparator` | `str` | required | Comparison operator or alias from `COMPARATOR` (symbolic, English, or Indonesian). |
| `value` | `Any` | required | Right-hand value used in the comparison. |

### `where_date`

```python
Query.where_date(date_str: str) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `date_str` | `str` | required | Partial date such as `2025`, `2025-01`, or `2025-01-15`; the whole named interval is selected. |

### `where_date_between`

```python
Query.where_date_between(start_date: str, end_date: str) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `start_date` | `str` | required | Inclusive partial-string lower bound. |
| `end_date` | `str` | required | Inclusive partial-string upper bound. |

### `where_values_between`

```python
Query.where_values_between(column_name: str, start_value: int | float, end_value: int | float) -> Self
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `column_name` | `str` | required | Numeric column to filter. |
| `start_value` | `int \| float` | required | Inclusive lower bound. |
| `end_value` | `int \| float` | required | Inclusive upper bound. |

Raises `ColumnError` when the column is missing or not numeric.

### `get`

```python
Query.get() -> pd.DataFrame
```

No arguments. Applies staged columns to `df`, recomputes numeric columns, and returns the current DataFrame. With no staged selection, returns `df` unchanged.

## Example

```python
(
    ds.where("CO2", ">", 1.0)
      .where_date_between("2025-01-01", "2025-01-31")
      .select_columns(["CO2", "SO2"])
      .get()
)
ds.refresh()  # restore the original rows and columns
```
