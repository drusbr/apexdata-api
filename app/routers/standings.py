import fastf1
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/standings", tags=["Standings"])


# ── GET /standings/drivers ────────────────────────────────────────────────────

@router.get("/drivers", summary="Current driver championship standings")
async def get_driver_standings():
    """
    Returns the current driver championship standings via FastF1's Ergast wrapper.
    """
    try:
        standings = fastf1.ergast.Ergast().get_driver_standings(season='current')
        result = standings.content[0]
        return result.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /standings/constructors ───────────────────────────────────────────────

@router.get("/constructors", summary="Current constructor championship standings")
async def get_constructor_standings():
    """
    Returns the current constructor championship standings via FastF1's Ergast wrapper.
    """
    try:
        standings = fastf1.ergast.Ergast().get_constructor_standings(season='current')
        result = standings.content[0]
        return result.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
