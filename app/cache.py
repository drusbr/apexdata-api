"""
Supabase-backed response cache using direct httpx HTTP calls to the REST API.
No supabase-py dependency — httpx is already in requirements.txt.

All functions are non-fatal: a cache failure never breaks an API response.
If SUPABASE_URL / SUPABASE_KEY are not set the helpers return immediately,
so the API works identically without caching when Supabase is not configured.
"""

import os
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def get_cached(table: str, match_fields: dict):
    """Return the cached ``data`` value or ``None`` if not found / on error."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        params = {k: f"eq.{v}" for k, v in match_fields.items()}
        params["select"] = "data"
        params["limit"] = "1"
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_headers(),
            params=params,
            timeout=3.0,
        )
        if r.status_code == 200 and r.json():
            print(f"[Cache] HIT {table} {match_fields}")
            return r.json()[0]["data"]
        print(f"[Cache] MISS {table} {match_fields}")
        return None
    except Exception as e:
        print(f"[Cache] Read failed: {e}")
        return None


def set_cache(table: str, match_fields: dict, data):
    """Upsert *data* into the cache table — never raises, failure is non-fatal."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        payload = {**match_fields, "data": data}
        httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_headers(),
            json=payload,
            timeout=5.0,
        )
        print(f"[Cache] Stored {table} {match_fields}")
    except Exception as e:
        print(f"[Cache] Write failed: {e}")
