from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routers import f1, standings

app = FastAPI(
    title="ApexData API",
    description="F1 and sim racing data powered by FastF1.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(f1.router)
app.include_router(standings.router)


@app.get("/", include_in_schema=False)
def root():
    return JSONResponse({"status": "ok", "docs": "/docs"})


@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok"}
