import fastf1
from app.core.config import CACHE_DIR

fastf1.Cache.enable_cache(str(CACHE_DIR))


def load_session(year: int, round_number: int, session_name: str) -> fastf1.core.Session:
    session = fastf1.get_session(year, round_number, session_name)
    session.load()
    return session
