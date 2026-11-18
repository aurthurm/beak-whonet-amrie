"""Thread-safe FIFO cache with entry-count and key-size limits.

Port of ``BoundedCache.cs``. The interpretation engine caches the most
applicable breakpoint / intrinsic-resistance rule per lookup key. In a
long-running process (the web API) the number of distinct keys is unbounded —
every distinct combination of breakpoint types, sites of infection and
user-defined breakpoints yields new keys — so the caches must be capped.

Eviction is first-in-first-out, as in C#: it keeps no access history and never
changes what a lookup returns, only whether it has to be recomputed.

Unlike the C# ``GetOrAdd`` (which computes the value while holding the lock),
callers here use :meth:`BoundedCache.get` and :meth:`BoundedCache.add` so the
expensive computation runs *outside* the lock and parallel cache preheating is
not serialised. :meth:`add` keeps the first writer's value on a race.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Hashable, Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

MISSING: object = object()
"""Sentinel returned by :meth:`BoundedCache.get` on a miss (``None`` is a valid cached value)."""


@dataclass(frozen=True)
class BoundedCacheStatistics:
    """Snapshot of a cache's occupancy and churn counters."""

    entries: int
    key_characters: int
    evictions: int
    uncached_keys: int


def key_characters(key: object) -> int:
    """Approximate the size of *key* as the total length of its textual parts.

    Strings count their length, ``None`` counts 0, other scalars count the
    length of their ``str()`` form, and tuples/lists are summed recursively.
    This mirrors C#, which sizes the cache by the characters in the string key.
    """
    if key is None:
        return 0
    if isinstance(key, str):
        return len(key)
    if isinstance(key, (tuple, list)):
        return sum(key_characters(part) for part in key)
    return len(str(key))


class BoundedCache(Generic[K, V]):
    """FIFO cache bounded by entry count and total key characters."""

    def __init__(self, max_entries: int, max_key_characters: int) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if max_key_characters <= 0:
            raise ValueError("max_key_characters must be positive")
        self.max_entries = max_entries
        self.max_key_characters = max_key_characters
        self._lock = threading.Lock()
        self._entries: OrderedDict[K, tuple[V, int]] = OrderedDict()
        self._key_characters = 0
        self._evictions = 0
        self._uncached_keys = 0

    def get(self, key: K, default: object = MISSING) -> V | object:
        """Return the cached value for *key*, or *default* on a miss."""
        with self._lock:
            entry = self._entries.get(key)
        return default if entry is None else entry[0]

    def add(self, key: K, value: V) -> V:
        """Store *value* under *key* unless already present; return the cached value.

        Keys larger than the character budget are not stored (counted in
        ``uncached_keys``); *value* is returned as-is. Otherwise the oldest
        entries are evicted until the new entry fits both limits.
        """
        characters = key_characters(key)
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                return existing[0]

            if characters > self.max_key_characters:
                self._uncached_keys += 1
                return value

            while self._entries and (
                len(self._entries) >= self.max_entries
                or self._key_characters > self.max_key_characters - characters
            ):
                _, (_, evicted_characters) = self._entries.popitem(last=False)
                self._key_characters -= evicted_characters
                self._evictions += 1

            self._entries[key] = (value, characters)
            self._key_characters += characters
            return value

    def clear(self) -> None:
        """Remove every entry and reset the counters."""
        with self._lock:
            self._entries.clear()
            self._key_characters = 0
            self._evictions = 0
            self._uncached_keys = 0

    @property
    def statistics(self) -> BoundedCacheStatistics:
        """Return a consistent snapshot of the cache counters."""
        with self._lock:
            return BoundedCacheStatistics(
                len(self._entries), self._key_characters, self._evictions, self._uncached_keys
            )

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __iter__(self) -> Iterator[K]:
        """Iterate over a snapshot of the keys, oldest first."""
        with self._lock:
            return iter(list(self._entries))
