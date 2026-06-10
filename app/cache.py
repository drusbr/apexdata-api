"""
Supabase-backed response cache.

All functions are non-fatal — a cache failure never breaks an API response.
The Supabase client is created lazily on first use, and returns None if the
SUPABASE_URL / SUPABASE_KEY environment variables are not set, which means
the API works identically without caching if Supabase is not configured.
"""

import os
from supabase import create_client

_client = None


def get_client():
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if url and key:
            _client = create_client(url, key)
    return _client


def get_cached(table: str, match_fields: dict):
    """Return the cached ``data`` value or ``None`` if not found / on error."""
    try:
        client = get_client()
        if not client:
            return None
        result = (
            client.table(table)
            .select("data")
            .match(match_fields)
            .limit(1)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]["data"]
        return None
    except Exception as e:
        print(f"[Cache] Read failed for {table}: {e}")
        return None


def set_cache(table: str, match_fields: dict, data):
    """Upsert *data* into the cache table — never raises, failure is non-fatal."""
    try:
        client = get_client()
        if not client:
            return
        client.table(table).upsert(
            {**match_fields, "data": data, "cached_at": "now()"}
        ).execute()
        print(f"[Cache] Stored {table} {match_fields}")
    except Exception as e:
        print(f"[Cache] Write failed for {table}: {e}")
