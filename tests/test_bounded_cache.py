"""BoundedCache: FIFO eviction by entry count and key characters (port of BoundedCache.cs)."""

from __future__ import annotations

import threading

import pytest

from amrie import antibiotic_rules
from amrie.bounded_cache import MISSING, BoundedCache, key_characters


def test_get_returns_missing_sentinel_and_caches_none_values():
    cache: BoundedCache[str, object] = BoundedCache(4, 100)
    assert cache.get("a") is MISSING
    assert cache.add("a", None) is None
    assert cache.get("a") is None  # None is a real cached value, not a miss
    assert "a" in cache


def test_add_keeps_first_writer_value():
    cache: BoundedCache[str, int] = BoundedCache(4, 100)
    assert cache.add("k", 1) == 1
    assert cache.add("k", 2) == 1
    assert cache.get("k") == 1


def test_evicts_oldest_when_entry_limit_reached():
    cache: BoundedCache[str, int] = BoundedCache(2, 100)
    cache.add("a", 1)
    cache.add("b", 2)
    cache.get("a")  # FIFO: access does not refresh age
    cache.add("c", 3)

    assert list(cache) == ["b", "c"]
    assert cache.statistics.evictions == 1


def test_evicts_until_key_character_budget_fits():
    cache: BoundedCache[str, int] = BoundedCache(10, 6)
    cache.add("aa", 1)
    cache.add("bb", 2)
    cache.add("cccc", 3)  # 2 + 2 + 4 = 8 > 6: evict "aa"; "bb" + "cccc" = 6 fits exactly

    assert list(cache) == ["bb", "cccc"]
    stats = cache.statistics
    assert (stats.entries, stats.key_characters, stats.evictions) == (2, 6, 1)

    cache.add("ddddd", 4)  # 6 + 5 > 6: evicting "bb" (4 left) is not enough; evict "cccc" too
    assert list(cache) == ["ddddd"]
    assert cache.statistics.evictions == 3


def test_oversized_key_is_returned_but_not_stored():
    cache: BoundedCache[str, int] = BoundedCache(10, 3)
    assert cache.add("toolong", 7) == 7
    assert cache.get("toolong") is MISSING
    assert cache.statistics.uncached_keys == 1


def test_clear_resets_entries_and_counters():
    cache: BoundedCache[str, int] = BoundedCache(1, 100)
    cache.add("a", 1)
    cache.add("b", 2)
    cache.clear()
    assert len(cache) == 0
    assert cache.statistics == type(cache.statistics)(0, 0, 0, 0)


@pytest.mark.parametrize(("max_entries", "max_chars"), [(0, 1), (1, 0), (-1, 5)])
def test_rejects_non_positive_limits(max_entries, max_chars):
    with pytest.raises(ValueError):
        BoundedCache(max_entries, max_chars)


def test_key_characters_sums_nested_text():
    assert key_characters(("eco", "CLSI", 2026, ("AMP_NM", None, ("Human",)))) == 3 + 4 + 4 + 6 + 5


def test_concurrent_adds_never_exceed_limits():
    cache: BoundedCache[tuple[int, int], int] = BoundedCache(50, 10_000)

    def worker(n: int) -> None:
        for i in range(500):
            cache.add((n, i), i)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = cache.statistics
    assert stats.entries == 50
    assert stats.entries + stats.evictions == 8 * 500


def test_engine_caches_use_upstream_limits():
    bp, intrinsic = antibiotic_rules._breakpoint_cache, antibiotic_rules._intrinsic_cache
    assert (bp.max_entries, bp.max_key_characters) == (262_144, 16_777_216)
    assert (intrinsic.max_entries, intrinsic.max_key_characters) == (131_072, 4_194_304)
    breakpoint_stats, intrinsic_stats = antibiotic_rules.cache_statistics()
    assert breakpoint_stats.entries == len(bp)
    assert intrinsic_stats.entries == len(intrinsic)
