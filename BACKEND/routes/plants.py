"""
Botanical reference data.

Documented in docs/API_CONTRACT.md since the beginning and never implemented,
so `POST /api/batches/raw` validated plant_id against a collection nothing
could browse - you had to already know the id to create a batch. The frontend
says as much in Frontend/src/lib/batches.js, where it falls back to showing a
bare plant id because there is no endpoint to resolve it into a name.

Read-only: the 2,300 rows come from the BSI/NMPB reference dataset and are not
something the application edits.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from database import db
from dependencies import require_authenticated


router = APIRouter(prefix="/api/plants", tags=["Plants"])


# Columns worth returning. The source CSV carries eighteen, several of them
# ingestion bookkeeping that no screen has any use for.
PROJECTION = {
    "_id": 0,
    "plant_id": 1,
    "scientific_name": 1,
    "common_name": 1,
    "family": 1,
    "vernacular_names": 1,
    "medicinal_system": 1,
    "medicinal_use": 1,
    "parts_used": 1,
    "habit": 1,
    "distribution_region": 1,
    "source_reference": 1,
}


@router.get("")
def list_plants(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):
    """
    Paginated listing. The default is small on purpose - the collection holds
    2,300 rows and no screen wants all of them at once.
    """

    plants = list(
        db.plants.find({}, PROJECTION)
        .sort("plant_id", 1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "plants": plants,
        "count": len(plants),
        "total": db.plants.count_documents({}),
    }


@router.get("/search")
def search_plants(
    name: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=25, ge=1, le=200),
    user: dict = Depends(require_authenticated),
):
    """
    Case-insensitive substring search across the name fields.

    The term is regex-escaped before it reaches MongoDB. Interpolating it raw
    would let a caller send a pathological pattern and pin the server on one
    query, and would make punctuation in a genuine plant name behave as
    syntax rather than as text.
    """

    pattern = re.escape(name.strip())

    if not pattern:
        raise HTTPException(status_code=422, detail="name must not be blank")

    condition = {"$regex": pattern, "$options": "i"}

    plants = list(
        db.plants.find(
            {
                "$or": [
                    {"common_name": condition},
                    {"scientific_name": condition},
                    {"vernacular_names": condition},
                ]
            },
            PROJECTION,
        ).limit(limit)
    )

    return {
        "query": name,
        "plants": plants,
        "count": len(plants),
    }


# Registered after /search so that path is not swallowed by {plant_id}.
@router.get("/{plant_id}")
def get_plant(
    plant_id: str,
    user: dict = Depends(require_authenticated),
):

    plant = db.plants.find_one({"plant_id": plant_id}, PROJECTION)

    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    return plant
