import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/standings", tags=["Standings"])

_ERGAST_BASE = "http://ergast.com/api/f1/current"
_TIMEOUT = 10.0  # seconds


async def _fetch_ergast(path: str) -> dict:
    url = f"{_ERGAST_BASE}/{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Upstream request to Ergast timed out")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Ergast returned {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach Ergast: {exc}") from exc
    return resp.json()


def _standings_list(data: dict, key: str) -> list:
    try:
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        if not lists:
            return []
        return lists[0][key]
    except (KeyError, IndexError):
        return []


# ── GET /standings/drivers ────────────────────────────────────────────────────

@router.get("/drivers", summary="Current driver championship standings")
async def get_driver_standings():
    """
    Fetches live driver standings from Jolpica/Ergast and returns the
    parsed DriverStandings array for the current season.
    """
    data = await _fetch_ergast("driverStandings.json")
    return _standings_list(data, "DriverStandings")


# ── GET /standings/constructors ───────────────────────────────────────────────

@router.get("/constructors", summary="Current constructor championship standings")
async def get_constructor_standings():
    """
    Fetches live constructor standings from Jolpica/Ergast and returns the
    parsed ConstructorStandings array for the current season.
    """
    data = await _fetch_ergast("constructorStandings.json")
    return _standings_list(data, "ConstructorStandings")
