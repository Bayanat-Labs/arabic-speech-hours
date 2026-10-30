"""Read selected columns of a remote Parquet file with HTTP range requests.

Only the footer and the byte ranges of the requested column chunks are fetched, so a duration
column can be summed without downloading the audio stored in other columns of the same file.
"""
from __future__ import annotations

import io
import struct

import pyarrow as pa
import pyarrow.parquet as pq

from .http import Fetcher

TAIL = 1 << 16


class RangeFile(io.RawIOBase):
    """A read-only, seekable file whose bytes are fetched on demand by range requests."""

    def __init__(self, fetcher: Fetcher, url: str, size: int, min_fetch: int = 1 << 15):
        self.f, self.url, self.size, self.min_fetch = fetcher, url, size, min_fetch
        self.pos = 0
        self.chunks: list[tuple[int, bytes]] = []
        self.bytes_fetched = 0
        self.n_ranges = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        if whence == 0:
            self.pos = off
        elif whence == 1:
            self.pos += off
        else:
            self.pos = self.size + off
        return self.pos

    def _have(self, start, end):
        for s, b in self.chunks:
            if s <= start and end <= s + len(b):
                return b[start - s:end - s]
        return None

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        start, end = self.pos, min(self.pos + n, self.size)
        if start >= end:
            return b""
        got = self._have(start, end)
        if got is None:
            fend = min(max(end, start + self.min_fetch), self.size)
            data = self.f.get_range(self.url, start, fend - 1)
            self.bytes_fetched += len(data)
            self.n_ranges += 1
            self.chunks.append((start, data))
            got = data[:end - start]
        self.pos = end
        return got

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)

    def prime_tail(self):
        """Fetch the footer in one or two requests."""
        n = min(TAIL, self.size)
        tail = self.f.get_range(self.url, self.size - n, self.size - 1)
        self.n_ranges += 1
        self.bytes_fetched += len(tail)
        if tail[-4:] != b"PAR1":
            raise ValueError(f"not a parquet file: {self.url}")
        flen = struct.unpack("<I", tail[-8:-4])[0]
        if flen + 8 > n:
            start = self.size - (flen + 8)
            tail = self.f.get_range(self.url, start, self.size - 1)
            self.n_ranges += 1
            self.bytes_fetched += len(tail)
            self.chunks.append((start, tail))
        else:
            self.chunks.append((self.size - n, tail))


def read_columns(fetcher: Fetcher, url: str, columns: list[str]) -> tuple[pa.Table, dict]:
    """Return (table with the requested columns, stats about the transfer)."""
    final, size = fetcher.resolve_with_size(url)
    rf = RangeFile(fetcher, final, size)
    rf.prime_tail()
    pf = pq.ParquetFile(rf)
    names = pf.schema_arrow.names
    cols = [c for c in columns if c in names]
    missing = [c for c in columns if c not in names]
    table = pf.read(columns=cols) if cols else pa.table({})
    return table, {"url": url, "file_bytes": size, "bytes_fetched": rf.bytes_fetched, "ranges": rf.n_ranges,
                   "row_groups": pf.metadata.num_row_groups, "rows": pf.metadata.num_rows,
                   "schema": names, "missing_columns": missing}


def read_schema(fetcher: Fetcher, url: str) -> dict:
    final, size = fetcher.resolve_with_size(url)
    rf = RangeFile(fetcher, final, size)
    rf.prime_tail()
    pf = pq.ParquetFile(rf)
    return {"url": url, "file_bytes": size, "rows": pf.metadata.num_rows,
            "row_groups": pf.metadata.num_row_groups, "schema": pf.schema_arrow.names,
            "types": [str(t) for t in pf.schema_arrow.types]}
