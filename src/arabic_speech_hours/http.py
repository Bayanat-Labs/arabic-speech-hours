"""Polite HTTP access: one fixed User-Agent, a minimum gap per host, no credentials, stop on refusal.

Every request made by the counter goes through `Fetcher`. It waits at least `gap_s` seconds between
two requests to the same host (3 s for arxiv.org), sends no cookies or tokens, and raises `Refused`
on HTTP 401, 403 or 429 so that the run stops instead of retrying. Each response is logged as one
provenance row (URL, UTC time, status, bytes, SHA-256 of the body).
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import json
import os
import time
import urllib.parse

import requests

USER_AGENT = "BayanatLabs-OpenData/1.0 (+https://bayanatlabs.com/open; hello@bayanatlabs.com)"
DEFAULT_GAP_S = 1.05
HOST_GAPS = {"arxiv.org": 3.05, "export.arxiv.org": 3.05}
LOCK_DIR = os.environ.get("ASH_HOSTLOCK_DIR", os.path.join(os.path.expanduser("~"), ".cache", "arabic-speech-hours", "hostlocks"))


class Refused(RuntimeError):
    """The server refused the request (401, 403 or 429). The run stops; nothing is retried."""


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Fetcher:
    def __init__(self, provenance_path: str | None = None, gap_s: float = DEFAULT_GAP_S):
        self.gap_s = gap_s
        self.provenance_path = provenance_path
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.session.trust_env = False  # never pick up tokens or proxies from the environment
        self.n_requests = 0

    def _wait(self, host: str) -> None:
        """Keep at least the host's gap between requests, across all processes on this machine."""
        gap = HOST_GAPS.get(host, self.gap_s)
        os.makedirs(LOCK_DIR, exist_ok=True)
        path = os.path.join(LOCK_DIR, "".join(ch if ch.isalnum() or ch in ".-" else "_" for ch in host))
        with open(path, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            try:
                last = float(fh.read().strip() or 0)
            except ValueError:
                last = 0.0
            d = time.time() - last
            if d < gap:
                time.sleep(gap - d)
            fh.seek(0)
            fh.truncate()
            fh.write(repr(time.time()))
            fh.flush()
            fcntl.flock(fh, fcntl.LOCK_UN)
        self._last[host] = time.monotonic()

    def _log(self, url: str, status: int, body: bytes, extra: dict | None = None) -> dict:
        rec = {"url": url, "retrieved_at": utc_now(), "http_status": status, "bytes": len(body),
               "sha256": sha256_bytes(body)}
        if extra:
            rec.update(extra)
        if self.provenance_path:
            os.makedirs(os.path.dirname(self.provenance_path) or ".", exist_ok=True)
            with open(self.provenance_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def request(self, url: str, headers: dict | None = None, allow_redirects: bool = True,
                log: bool = True, timeout: float = 120) -> requests.Response:
        """GET with the per-host gap applied to every hop (redirects are followed by hand)."""
        hops = 0
        cur = url
        while True:
            host = urllib.parse.urlparse(cur).netloc
            self._wait(host)
            r = self.session.get(cur, headers=headers or {}, allow_redirects=False, timeout=timeout)
            self.n_requests += 1
            if r.status_code in (401, 403, 429):
                self._log(cur, r.status_code, b"", {"refused": True})
                raise Refused(f"HTTP {r.status_code} from {host} for {cur}")
            if allow_redirects and r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers:
                cur = urllib.parse.urljoin(cur, r.headers["location"])
                hops += 1
                if hops > 5:
                    raise RuntimeError(f"too many redirects for {url}")
                continue
            if log:
                extra = {"final_url": cur.split("?", 1)[0]} if cur != url else None
                if headers and "Range" in headers:
                    extra = dict(extra or {}, range=headers["Range"])
                self._log(url, r.status_code, r.content, extra)
            return r

    def get_bytes(self, url: str) -> tuple[bytes, dict]:
        r = self.request(url)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        return r.content, {"url": url, "retrieved_at": utc_now(), "http_status": r.status_code,
                           "sha256": sha256_bytes(r.content), "bytes": len(r.content)}

    def get_json(self, url: str):
        b, _ = self.get_bytes(url)
        return json.loads(b)

    def resolve(self, url: str) -> str:
        """Follow redirects without downloading the body; returns the final URL (for range reads)."""
        cur = url
        for _ in range(6):
            host = urllib.parse.urlparse(cur).netloc
            self._wait(host)
            r = self.session.head(cur, allow_redirects=False, timeout=60)
            self.n_requests += 1
            if r.status_code in (401, 403, 429):
                raise Refused(f"HTTP {r.status_code} from {host} for {cur}")
            if r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers:
                cur = urllib.parse.urljoin(cur, r.headers["location"])
                continue
            return cur
        raise RuntimeError(f"too many redirects for {url}")

    def resolve_with_size(self, url: str) -> tuple[str, int]:
        """Final URL after redirects and its Content-Length (from a HEAD request)."""
        cur = url
        for _ in range(6):
            host = urllib.parse.urlparse(cur).netloc
            self._wait(host)
            r = self.session.head(cur, allow_redirects=False, timeout=60)
            self.n_requests += 1
            if r.status_code in (401, 403, 429):
                raise Refused(f"HTTP {r.status_code} from {host} for {cur}")
            if r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers:
                cur = urllib.parse.urljoin(cur, r.headers["location"])
                continue
            size = r.headers.get("x-linked-size") or r.headers.get("content-length")
            if size is None:
                raise RuntimeError(f"no size for {url}")
            return cur, int(size)
        raise RuntimeError(f"too many redirects for {url}")

    def get_range(self, url: str, start: int, end: int) -> bytes:
        """Bytes start..end (inclusive) of url; url should already be resolved."""
        r = self.request(url, headers={"Range": f"bytes={start}-{end}"}, allow_redirects=True, log=False)
        if r.status_code not in (200, 206):
            raise RuntimeError(f"HTTP {r.status_code} for range {start}-{end} of {url}")
        if r.status_code == 200:  # server ignored the range
            return r.content[start:end + 1]
        return r.content
