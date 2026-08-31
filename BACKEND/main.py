"""
TraceVeda API.

Ayurvedic supply-chain traceability: farm collection through processing,
quality testing, manufacture and distribution, with dispute-relevant events
anchored to a SHA-256 hash chain.

    uvicorn main:app --reload

First run on a fresh database:

    python import_csv.py                     # load the seed dataset
    python migrate_seed_blockchain_events.py # put seed events on the chain
    python seed_users.py                     # create the demo accounts
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from config import settings
from services import accounts
from services.indexes import ensure_indexes

from routes.auth import router as auth_router
from routes.batches import router as batches_router
from routes.blockchain import router as blockchain_router
from routes.consumer import router as consumer_router
from routes.investigations import router as investigations_router
from routes.iot import router as iot_router
from routes.lab import router as lab_router
from routes.medicine import router as medicine_router
from routes.plants import router as plants_router
from routes.storage import router as storage_router
from routes.trace import router as trace_router
from routes.transport import router as transport_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)

logger = logging.getLogger("traceveda")


# =========================
# LIFESPAN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):

    settings.warn_about_fallbacks()

    if database.ping():

        created, failed = ensure_indexes(database.db)
        logger.info("Indexes ready (%s applied, %s failed)", created, len(failed))

        try:
            if accounts.count_users() == 0:
                logger.warning(
                    "No user accounts exist - every authenticated endpoint "
                    "will reject every request. Run: python seed_users.py"
                )
        except Exception:
            logger.exception("Could not count user accounts")

    else:
        # Not fatal: /api/health has to stay reachable to report the outage.
        logger.error(
            "MongoDB is unreachable at startup. The API will serve /api/health "
            "and return errors elsewhere. Check MONGO_URI in BACKEND/.env"
        )

    yield

    database.close()
    logger.info("MongoDB connection closed")


app = FastAPI(
    title="TraceVeda API",
    version="1.1.0",
    description=(
        "Botanical traceability for Ayurvedic medicine. All write endpoints "
        "require a bearer token from POST /api/auth/login; IoT nodes may "
        "instead present the X-Device-Key header. The consumer QR lookup and "
        "consumer report submission are intentionally public."
    ),
    lifespan=lifespan
)


# =========================
# CORS
# =========================
# Credentials are off because this API authenticates with an Authorization
# header, not a cookie. That also keeps the configuration valid: browsers
# reject allow_origins=["*"] together with allow_credentials=True, which is
# what the previous configuration asked for.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Key"],
    max_age=600,
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# ROUTERS
# =========================

app.include_router(auth_router)
app.include_router(batches_router)
app.include_router(plants_router)
app.include_router(lab_router)
app.include_router(iot_router)
app.include_router(medicine_router)
app.include_router(transport_router)
app.include_router(storage_router)
app.include_router(trace_router)
app.include_router(blockchain_router)
app.include_router(consumer_router)
app.include_router(investigations_router)


# =========================
# BASIC ENDPOINTS
# =========================

@app.get("/", tags=["Health"])
def home():

    return {
        "message": "TraceVeda Backend is running",
        "version": app.version,
        "docs": "/docs"
    }


@app.get("/api/health", tags=["Health"])
def health():
    """
    Liveness plus a straight answer about the security configuration.

    `hardened` is false whenever a secret is running on a generated
    development value, so nobody has to guess whether the deployment in front
    of them is the demo one.
    """

    connected = database.ping()

    return {
        "status": "healthy" if connected else "unhealthy",
        "database": "connected" if connected else "disconnected",
        "version": app.version,
        "hardened": settings.is_hardened,
    }
