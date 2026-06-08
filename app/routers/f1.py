from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from typing import Annotated
import fastf1
import fastf1.ergast
import pandas as pd

from app.core.fastf1_client import load_session
from app.core.serializers import dataframe_to_records, serialize
from app.core.config import CACHE_DIR

router = APIRouter(prefix="/f1", tags=["F1"])

# In-memory cache for circuit layout — this data is immutable for a given round
# so we never need to re-compute it after the first successful request.
_circuit_cache: dict = {}

# ── helpers ──────────────────────────────────────────────────────────────────

SESSION_ALIASES = {
    "r": "R",
    "race": "R",
    "q": "Q",
    "qualifying": "Q",
    "sprint": "S",
    "s": "S",
    "fp1": "FP1",
    "fp2": "FP2",
    "fp3": "FP3",
}


def _normalise_session(session: str) -> str:
    return SESSION_ALIASES.get(session.lower(), session.upper())


def _safe_load(year: int, round_number: int, session_name: str):
    try:
        return load_session(year, round_number, _normalise_session(session_name))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── GET /f1/sessions/{year}/{round} ──────────────────────────────────────────

@router.get("/sessions/{year}/{round}")
def get_session_info(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: Annotated[int, Path(ge=1, le=25)],
):
    """Return metadata for every session in a race weekend."""
    try:
        event = fastf1.get_event(year, round)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    sessions = []
    for i in range(1, 6):
        name_col = f"Session{i}"
        date_col = f"Session{i}Date"
        name = event.get(name_col)
        if not name or (isinstance(name, float)):
            continue
        date = event.get(date_col)
        sessions.append(
            {
                "number": i,
                "name": str(name),
                "date": serialize(date),
            }
        )

    return {
        "year": year,
        "round": round,
        "event_name": event.get("EventName"),
        "official_name": event.get("OfficialEventName"),
        "country": event.get("Country"),
        "location": event.get("Location"),
        "circuit": event.get("CircuitShortName"),
        "format": event.get("EventFormat"),
        "sessions": sessions,
    }


# ── GET /f1/results/{year}/{round}/{session} ──────────────────────────────────

@router.get("/results/{year}/{round}/{session}")
def get_results(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: Annotated[int, Path(ge=1, le=25)],
    session: str,
):
    """Race, qualifying, sprint, or practice results."""
    sess = _safe_load(year, round, session)

    results: pd.DataFrame = sess.results
    if results is None or results.empty:
        return {"year": year, "round": round, "session": session, "results": []}

    cols = [
        "DriverNumber", "BroadcastName", "Abbreviation",
        "FullName", "TeamName", "TeamColor",
        "GridPosition", "Position", "ClassifiedPosition",
        "Status", "Points",
        "Q1", "Q2", "Q3",
        "Time", "FastestLap", "FastestLapTime", "FastestLapSpeed",
    ]
    available = [c for c in cols if c in results.columns]
    return {
        "year": year,
        "round": round,
        "session": sess.name,
        "event": sess.event.get("EventName"),
        "results": dataframe_to_records(results[available]),
    }


# ── GET /f1/laps/{year}/{round}/{session}/{driver} ───────────────────────────

@router.get("/laps/{year}/{round}/{session}/{driver}")
def get_laps(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: Annotated[int, Path(ge=1, le=25)],
    session: str,
    driver: str,
    accurate_only: bool = Query(False, description="Return only accurately timed laps"),
):
    """All lap times for a specific driver in a session."""
    sess = _safe_load(year, round, session)

    try:
        laps = sess.laps.pick_drivers(driver.upper())
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Driver '{driver}' not found: {exc}") from exc

    if accurate_only:
        laps = laps.pick_accurate()

    cols = [
        "LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
        "Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime",
        "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST",
        "Compound", "TyreLife", "FreshTyre",
        "Team", "Driver",
        "PitOutTime", "PitInTime",
        "TrackStatus", "IsAccurate",
        "LapStartTime", "LapStartDate",
    ]
    available = [c for c in cols if c in laps.columns]

    return {
        "year": year,
        "round": round,
        "session": sess.name,
        "driver": driver.upper(),
        "lap_count": len(laps),
        "laps": dataframe_to_records(laps[available]),
    }


# ── GET /f1/telemetry/{year}/{round}/{session}/{driver}/{lap} ─────────────────

@router.get("/telemetry/{year}/{round}/{session}/{driver}/{lap}")
def get_telemetry(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: Annotated[int, Path(ge=1, le=25)],
    session: str,
    driver: str,
    lap: Annotated[int, Path(ge=1)],
    frequency: int = Query(
        10,
        ge=1,
        le=240,
        description="Resample frequency in Hz (default 10, max 240 = native)",
    ),
):
    """Car telemetry channels for a specific lap."""
    sess = _safe_load(year, round, session)

    try:
        driver_laps = sess.laps.pick_drivers(driver.upper())
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Driver '{driver}' not found: {exc}") from exc

    lap_row = driver_laps[driver_laps["LapNumber"] == lap]
    if lap_row.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap} not found for driver '{driver}'",
        )

    lap_obj = lap_row.iloc[0]
    try:
        tel = lap_obj.get_telemetry()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load telemetry: {exc}") from exc

    if frequency < 240:
        # Resample to requested Hz
        interval_ms = int(1000 / frequency)
        tel = tel.resample_channels(rule=f"{interval_ms}ms")

    cols = [
        "SessionTime", "Date", "Time",
        "Speed", "RPM", "nGear",
        "Throttle", "Brake", "DRS",
        "X", "Y", "Z",
        "Distance", "RelativeDistance",
        "Status", "Source",
    ]
    available = [c for c in cols if c in tel.columns]

    return {
        "year": year,
        "round": round,
        "session": sess.name,
        "driver": driver.upper(),
        "lap": lap,
        "lap_time": serialize(lap_obj.get("LapTime")),
        "compound": lap_obj.get("Compound"),
        "sample_count": len(tel),
        "frequency_hz": frequency,
        "telemetry": dataframe_to_records(tel[available]),
    }


# ── GET /f1/circuit/{year}/{round} ───────────────────────────────────────────

_SESSION_FALLBACK_ORDER = ["R", "Q", "FP3", "FP2", "FP1"]


@router.get("/circuit/{year}/{round}", summary="Lightweight circuit layout for a race weekend")
def get_circuit_layout(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: Annotated[int, Path(ge=1, le=25)],
):
    """
    Returns a downsampled X/Y circuit outline derived from the fastest lap
    of the most data-rich session available for the given round.

    Session priority: Race → Qualifying → FP3 → FP2 → FP1.
    Results are cached in memory — circuit layouts never change.
    """
    cache_key = (year, round)
    if cache_key in _circuit_cache:
        return JSONResponse(
            content=_circuit_cache[cache_key],
            headers={"Cache-Control": "public, max-age=2592000"},  # 30 days
        )

    # Try sessions in priority order, stop at the first one that loads cleanly.
    sess = None
    for session_name in _SESSION_FALLBACK_ORDER:
        try:
            candidate = fastf1.get_session(year, round, session_name)
            candidate.load(laps=True, telemetry=True, weather=False, messages=False)
            if candidate.laps is not None and not candidate.laps.empty:
                sess = candidate
                break
        except Exception:
            continue

    if sess is None:
        raise HTTPException(
            status_code=404,
            detail=f"No session data found for {year} round {round}",
        )

    # Pick fastest lap from the first driver that has telemetry with X/Y.
    fastest = None
    for driver in sess.laps["Driver"].unique():
        try:
            lap = sess.laps.pick_drivers(driver).pick_fastest()
            tel = lap.get_telemetry()
            if {"X", "Y"}.issubset(tel.columns) and tel["X"].notna().any():
                fastest = tel
                break
        except Exception:
            continue

    if fastest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry with X/Y coordinates found for {year} round {round}",
        )

    # Keep only the columns we need, drop null X/Y rows, downsample.
    cols = [c for c in ["X", "Y", "Distance"] if c in fastest.columns]
    layout = fastest[cols].dropna(subset=["X", "Y"]).iloc[::5].reset_index(drop=True)

    points = [
        {"x": round(row["X"], 3), "y": round(row["Y"], 3)}
        | ({"distance": round(row["Distance"], 2)} if "Distance" in row else {})
        for _, row in layout.iterrows()
    ]

    circuit_name = sess.event.get("CircuitShortName") or sess.event.get("EventName") or ""

    payload = {
        "year": year,
        "round": round,
        "circuit": str(circuit_name),
        "points": points,
    }

    _circuit_cache[cache_key] = payload
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "public, max-age=2592000"},  # 30 days
    )


# ── GET /f1/standings/{year} ──────────────────────────────────────────────────

@router.get("/standings/{year}")
def get_standings(
    year: Annotated[int, Path(ge=1950, le=2100)],
    round: int = Query(
        None,
        ge=1,
        le=25,
        description="Standing after a specific round (omit for final/latest)",
    ),
):
    """Driver and constructor championship standings."""
    ergast = fastf1.ergast.Ergast()

    try:
        driver_resp = ergast.get_driver_standings(season=year, round=round)
        constructor_resp = ergast.get_constructor_standings(season=year, round=round)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        driver_df: pd.DataFrame = driver_resp.content[0]
    except (IndexError, AttributeError):
        driver_df = pd.DataFrame()

    try:
        constructor_df: pd.DataFrame = constructor_resp.content[0]
    except (IndexError, AttributeError):
        constructor_df = pd.DataFrame()

    driver_cols = [
        "position", "points", "wins",
        "driverCode", "driverNumber",
        "givenName", "familyName",
        "driverNationality", "constructorNames",
    ]
    constructor_cols = [
        "position", "points", "wins",
        "constructorName", "constructorNationalities",
    ]

    return {
        "year": year,
        "round": round,
        "drivers": dataframe_to_records(
            driver_df[[c for c in driver_cols if c in driver_df.columns]]
            if not driver_df.empty else driver_df
        ),
        "constructors": dataframe_to_records(
            constructor_df[[c for c in constructor_cols if c in constructor_df.columns]]
            if not constructor_df.empty else constructor_df
        ),
    }
