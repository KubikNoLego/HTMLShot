"""In-memory LRU cache for rendered image bytes and cache key generation."""

import hashlib
import json
from collections import OrderedDict

DEFAULT_MAX_ENTRIES = 128
DEFAULT_MAX_BYTES = 256 * 1024 * 1024


def make_cache_key(template_id: str, context: dict,
                   image_format: str | None, quality: int | None) -> str:
    """Generate a deterministic SHA-256 hash key for caching rendered images.

    Serializes the template ID, render context, image format, and quality settings
    into a canonical JSON representation (with sorted keys and fallback string conversion
    for non-primitive objects) and computes its SHA-256 hex digest.

    Args:
        template_id: The unique identifier of the template.
        context: The context dictionary passed into the template rendering engine.
        image_format: Target image output format (e.g. 'webp', 'png', 'jpeg').
        quality: Image compression quality level (e.g. 1-100), or None for default.

    Returns:
        A 64-character hexadecimal SHA-256 string uniquely representing the render arguments.
    """
    payload = json.dumps(
        {"t": template_id, "c": context, "f": image_format, "q": quality},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RenderCache:
    """Least Recently Used (LRU) byte cache constrained by entry count and byte capacity.

    Stores rendered image byte sequences keyed by hash identifiers, evicting the
    least recently accessed items when either the maximum number of items or total
    byte consumption limits are exceeded.
    """

    def __init__(self,
                 max_entries: int = DEFAULT_MAX_ENTRIES,
                 max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        """Initialize a new LRU RenderCache instance.

        Args:
            max_entries: Maximum number of discrete items allowed before eviction triggers.
            max_bytes: Maximum cumulative bytes allowed across all cached entries.
        """
        self._data: OrderedDict[str, bytes] = OrderedDict()
        self._bytes = 0
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> bytes | None:
        """Retrieve a cached image by its key and mark it as most recently used.

        Increments the hit counter and updates LRU positioning if found;
        otherwise increments the miss counter and returns None.

        Args:
            key: The cache key string to look up.

        Returns:
            The cached image bytes, or None if the key does not exist.
        """
        value = self._data.get(key)
        if value is None:
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key: str, value: bytes) -> None:
        """Store or update a cached image entry, evicting older entries as required.

        Adjusts tracked byte size and evicts the oldest items in LRU order
        until both the entry count and byte consumption stay within their thresholds.

        Args:
            key: The unique cache key.
            value: The raw image byte payload to store.
        """
        if key in self._data:
            self._bytes -= len(self._data.pop(key))
        self._data[key] = value
        self._bytes += len(value)
        while self._data and (len(self._data) > self._max_entries
                              or self._bytes > self._max_bytes):
            _, evicted = self._data.popitem(last=False)
            self._bytes -= len(evicted)

    def clear(self) -> None:
        """Purge all entries from the cache and reset size and hit/miss metrics."""
        self._data.clear()
        self._bytes = 0
        self.hits = 0
        self.misses = 0

    @property
    def size(self) -> int:
        """Return the current number of cached items."""
        return len(self._data)

    @property
    def bytes_used(self) -> int:
        """Return the current total memory consumed by cached bytes."""
        return self._bytes


render_cache = RenderCache()
