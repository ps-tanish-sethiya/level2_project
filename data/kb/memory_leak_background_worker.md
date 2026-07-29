# Background Worker Memory Exhaustion

## Symptom
CI container or server process crashes unexpectedly with `OOMKilled` or `MemoryError: Unable to allocate array` after running for several hours under sustained load.

## Root Cause
Long-running background tasks append objects to global list caches without eviction policies or failsafe maximum limits, causing memory consumption to grow indefinitely.

## Recommended Fix
Replace unbounded in-memory lists with bounded LRU caches (`functools.lru_cache(maxsize=1000)`) or external cache stores with explicit TTL retention settings.
