"""Bounded Arrow transport for complete, full-resolution scatter series."""

import io

from multigas.utils.analysis import PANEL_MAP
from multigas.utils.app_ingest import quote


def stream_series(query):
    """Yield one Arrow IPC stream in 8,000-row batches, without reducing data.

    Args:
        query (DatasetQuery): Isolated analysis connection, closed by this generator.

    Yields:
        bytes: Sequential chunks of a single Arrow stream with numeric UTC times.

    Example:
        >>> chunks = stream_series(query)
    """
    import pyarrow.ipc as ipc

    try:
        channels = query.spec.channels or [
            c
            for p in query.spec.panels or list(PANEL_MAP)
            for c in PANEL_MAP[p].columns
            if c in query.columns
        ]
        fields = ["epoch_ms(__mg_time) AS timestamp"] + [
            f"CASE WHEN isfinite(TRY_CAST({quote(c)} AS DOUBLE)) THEN TRY_CAST({quote(c)} AS DOUBLE) ELSE NULL END AS {quote(c)}"
            for c in dict.fromkeys(channels)
        ]
        reader = query.connection.sql(
            f"SELECT {','.join(fields)} FROM ({query.sql}) ORDER BY __mg_time",
            params=query.params,
        ).to_arrow_reader(8000)
        sink = io.BytesIO()
        with ipc.new_stream(sink, reader.schema) as writer:
            for batch in reader:
                writer.write_batch(batch)
                yield sink.getvalue()
                sink.seek(0)
                sink.truncate()
        yield sink.getvalue()
    finally:
        query.close()
