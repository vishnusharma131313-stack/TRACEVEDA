"""
Swap the real MongoDB connection for mongomock.

IMPORT THIS FIRST, before anything under routes/ or services/.

Every route does `from database import db`, which binds the *value* at import
time. Patching `database.db` afterwards does not reach a module that has
already imported it, so `install()` reloads each consumer - service first,
then the routes and scripts that call it.

`install()` must run before EVERY test, not once per module: pytest imports
all test modules before running anything, so a module-level install would
leave every test sharing whichever module was imported last. Each test module
wires it up with an autouse fixture and each test builds the state it needs.

Works under pytest and under plain `python <test file>`.
"""

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


import mongomock  # noqa: E402

import database  # noqa: E402


# Reloaded in dependency order: the service before anything that calls it.
_CONSUMER_MODULES = [
    "services.blockchain_service",
    "routes.batches",
    "routes.lab",
    "routes.medicine",
    "routes.iot",
    "routes.blockchain",
    "import_csv",
    "migrate_seed_blockchain_events"
]


def install():
    """Point `database.db` at a fresh mongomock database and reload users."""

    database.db = mongomock.MongoClient()["traceveda_test"]

    for name in _CONSUMER_MODULES:

        module = importlib.import_module(name)
        importlib.reload(module)

    return database.db


def current_db():
    """
    The database the routes and service are currently bound to.

    Always read through this rather than caching the object `install()`
    returned - a later `install()` replaces it.
    """

    return database.db


def run_standalone(*test_functions):
    """Run tests without pytest, reinstalling between each."""

    for test_function in test_functions:

        install()
        test_function()

    print(f"\nALL {len(test_functions)} TESTS PASSED")
