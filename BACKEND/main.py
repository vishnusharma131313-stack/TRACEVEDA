from fastapi import FastAPI

from database import db

from routes.batches import router as batches_router
from routes.lab import router as lab_router
from routes.iot import router as iot_router
from routes.medicine import router as medicine_router
from routes.transport import router as transport_router
from routes.storage import router as storage_router
from routes.trace import router as trace_router
from routes.blockchain import router as blockchain_router
from routes.consumer import router as consumer_router


app = FastAPI(
    title="TraceVeda API"
)


# =========================
# ROUTERS
# =========================

app.include_router(batches_router)
app.include_router(lab_router)
app.include_router(iot_router)
app.include_router(medicine_router)
app.include_router(transport_router)
app.include_router(storage_router)
app.include_router(trace_router)
app.include_router(blockchain_router)
app.include_router(consumer_router)


# =========================
# BASIC ENDPOINTS
# =========================

@app.get("/")
def home():
    return {
        "message": "TraceVeda Backend is running"
    }


@app.get("/api/health")
def health():

    try:
        db.command("ping")

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception:

        return {
            "status": "unhealthy",
            "database": "disconnected"
        }