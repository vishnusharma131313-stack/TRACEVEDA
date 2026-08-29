"""
Concurrency stress test for the hash chain.

This is the test that catches the ordering bug. The old implementation
picked the previous event with `sort=[("created_at", -1)]` (millisecond
precision, no tiebreak) and minted transaction ids with
`count_documents({}) + 1` (read-then-write). Under simultaneous writers both
fork the chain and mint duplicate ids.

Run with:
    python -m pytest tests/test_blockchain_concurrency.py -v
or:
    python tests/test_blockchain_concurrency.py
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

import threading  # noqa: E402

import pytest  # noqa: E402

from services import blockchain_service  # noqa: E402


THREAD_COUNT = 50


@pytest.fixture(autouse=True)
def fresh_database():
    """A clean chain per test - see mongo_harness for why this is per-test."""

    mongo_harness.install()


def test_fifty_concurrent_anchors_keep_the_chain_valid():

    # Released together so every thread contends for the counter at once.
    barrier = threading.Barrier(THREAD_COUNT)

    results = []
    errors = []
    results_lock = threading.Lock()

    def worker(index):

        try:

            barrier.wait()

            event = blockchain_service.anchor_event(
                "BATCH_CREATED",
                "RAW",
                f"RAW-CONCURRENT-{index:03d}",
                {"worker": index}
            )

            with results_lock:
                results.append(event)

        except Exception as error:  # noqa: BLE001

            with results_lock:
                errors.append(error)

    threads = [
        threading.Thread(target=worker, args=(index,))
        for index in range(THREAD_COUNT)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    assert not errors, f"anchor_event raised: {errors[:3]}"
    assert len(results) == THREAD_COUNT

    # ---------------------------------------------
    # No duplicate transaction ids (count_documents+1 would produce them)
    # ---------------------------------------------

    transaction_ids = {event["transaction_id"] for event in results}

    assert len(transaction_ids) == THREAD_COUNT, (
        f"duplicate transaction ids: "
        f"{THREAD_COUNT - len(transaction_ids)} collision(s)"
    )

    # ---------------------------------------------
    # Sequences are exactly 1..N, with no gaps or repeats
    # ---------------------------------------------

    sequences = sorted(event["sequence"] for event in results)

    assert sequences == list(range(1, THREAD_COUNT + 1)), (
        f"sequence numbers are not contiguous: {sequences}"
    )

    # ---------------------------------------------
    # The chain itself holds
    # ---------------------------------------------

    result = blockchain_service.verify_chain()

    assert result["valid"] is True, result
    assert result["checked"] == THREAD_COUNT, result
    assert result["broken_at"] is None

    # Exactly one GENESIS link - more than one means the chain forked.
    genesis_links = mongo_harness.current_db().blockchain_events.count_documents(
        {"previous_hash": "GENESIS"}
    )

    assert genesis_links == 1, (
        f"chain forked: {genesis_links} events claim to be the genesis event"
    )

    print(
        f"OK  {THREAD_COUNT} concurrent anchors, "
        f"chain valid, {result['checked']} events checked"
    )


if __name__ == "__main__":

    mongo_harness.run_standalone(
        test_fifty_concurrent_anchors_keep_the_chain_valid
    )
