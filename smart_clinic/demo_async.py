"""Explicitly invoked M7 demonstration: python -m smart_clinic.demo_async

Not part of main.py yet; final integration belongs to M9. Timing is measured
here, outside the collection functions, around one complete run of each version.
"""

import asyncio
import time

from smart_clinic.async_processing import collect_concurrent, collect_sequential
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs


# Different simulated delays make completion order differ from input order.
DEMO_DELAYS = {"D001": 0.15, "D002": 0.05, "D003": 0.10}


def timed(run, coroutine):
    started = time.perf_counter()
    result = run(coroutine)
    return result, time.perf_counter() - started


def run_m7_demo(delays=DEMO_DELAYS, run=asyncio.run):
    """Run both versions on the same prepared inputs; return results and durations.

    `run` drives one coroutine to completion (asyncio.run by default).
    """
    print("\n=== M7: sequential vs concurrent availability (asyncio, simulated) ===")
    service, patient, doctors, snapshots = prepare_demo_inputs()  # synchronous, before any coroutine
    inputs = (service, patient, doctors, snapshots, WINDOW_START, WINDOW_END, delays)
    print("Window 2026-10-29 09:00-12:00; simulated delays: "
          + ", ".join(f"{doctor.id}={delays[doctor.id]:.2f}s" for doctor in doctors))

    sequential, sequential_seconds = timed(run, collect_sequential(*inputs))
    concurrent, concurrent_seconds = timed(run, collect_concurrent(*inputs))

    for doctor_id, slots in concurrent:
        starts = ", ".join(f"{start:%H:%M}" for start, _ in slots) or "none (no available slots)"
        print(f"{doctor_id}: {len(slots)} slots; starts {starts}")
    print(f"Same complete results, in input order: {sequential == concurrent}")
    print(f"Sequential: {sequential_seconds:.3f}s (delays add up)")
    print(f"Concurrent: {concurrent_seconds:.3f}s (delays overlap)")
    print("Durations are observations of this run, not a guaranteed speedup.")
    return {"sequential": sequential, "concurrent": concurrent,
            "sequential_seconds": sequential_seconds, "concurrent_seconds": concurrent_seconds}


if __name__ == "__main__":
    run_m7_demo()
