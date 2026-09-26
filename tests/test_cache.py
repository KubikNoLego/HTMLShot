"""Unit tests for cache key calculation and rendered image LRU cache."""

from htmlshot.services.cache import RenderCache, make_cache_key


class TestMakeCacheKey:
    def test_same_input_same_key(self):
        context = {"username": "kubik", "vip": True}
        key1 = make_cache_key("profile_card", context, "webp", 75)
        key2 = make_cache_key("profile_card", dict(context), "webp", 75)
        assert key1 == key2

    def test_key_ignores_dict_order(self):
        a = make_cache_key("t", {"x": 1, "y": 2}, None, None)
        b = make_cache_key("t", {"y": 2, "x": 1}, None, None)
        assert a == b

    def test_key_depends_on_template(self):
        context = {"x": 1}
        assert (make_cache_key("t1", context, None, None)
                != make_cache_key("t2", context, None, None))

    def test_key_depends_on_context(self):
        assert (make_cache_key("t", {"x": 1}, None, None)
                != make_cache_key("t", {"x": 2}, None, None))

    def test_key_depends_on_format_and_quality(self):
        context = {"x": 1}
        assert (make_cache_key("t", context, "webp", 70)
                != make_cache_key("t", context, "png", 70))
        assert (make_cache_key("t", context, "webp", 70)
                != make_cache_key("t", context, "webp", 90))

    def test_unserializable_values_do_not_raise(self):
        key = make_cache_key("t", {"obj": object()}, None, None)
        assert isinstance(key, str) and len(key) == 64


class TestRenderCache:
    def test_miss_then_hit(self):
        cache = RenderCache()
        assert cache.get("k") is None
        cache.set("k", b"image")
        assert cache.get("k") == b"image"
        assert cache.hits == 1
        assert cache.misses == 1

    def test_set_overwrites_and_keeps_bytes_accounting(self):
        cache = RenderCache()
        cache.set("k", b"aaa")
        cache.set("k", b"bbbb")
        assert cache.get("k") == b"bbbb"
        assert cache.size == 1
        assert cache.bytes_used == 4

    def test_eviction_by_entry_count(self):
        cache = RenderCache(max_entries=2, max_bytes=1024)
        cache.set("a", b"1")
        cache.set("b", b"2")
        cache.set("c", b"3")
        assert cache.size == 2
        assert cache.get("a") is None
        assert cache.get("b") == b"2"
        assert cache.get("c") == b"3"

    def test_eviction_by_bytes(self):
        cache = RenderCache(max_entries=100, max_bytes=10)
        cache.set("a", b"x" * 6)
        cache.set("b", b"y" * 6)
        assert cache.size == 1
        assert cache.bytes_used == 6
        assert cache.get("a") is None
        assert cache.get("b") == b"y" * 6

    def test_lru_order_moves_hit_to_end(self):
        cache = RenderCache(max_entries=2, max_bytes=1024)
        cache.set("a", b"1")
        cache.set("b", b"2")
        cache.get("a")          # теперь "a" самая свежая
        cache.set("c", b"3")    # вытесняет "b"
        assert cache.get("a") == b"1"
        assert cache.get("b") is None
        assert cache.get("c") == b"3"

    def test_clear(self):
        cache = RenderCache()
        cache.set("k", b"data")
        cache.get("k")
        cache.clear()
        assert cache.size == 0
        assert cache.bytes_used == 0
        assert cache.hits == 0
        assert cache.misses == 0

