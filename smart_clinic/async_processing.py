"""M7: sequential and concurrent asyncio collection of preloaded doctor availability.

Snapshots are prepared synchronously before any coroutine starts. Each doctor's
coroutine only waits with asyncio.sleep (a simulated delay) and then calls the
existing pure AppointmentService.available_slots_using_snapshot method. No HTTP,
file reads, time.sleep, booking or clinic mutation happen inside a coroutine.
"""

import asyncio
import math


def _checked_delays(doctors, delays):
    """Return one validated delay per doctor, before any coroutine is started.

    A delay must be a finite, non-negative int or float (zero is valid). bool,
    infinity and NaN are rejected; NaN would otherwise pass the `< 0` check.
    """
    checked = []
    for doctor in doctors:
        delay = delays.get(doctor.id)
        if (isinstance(delay, bool) or not isinstance(delay, (int, float))
                or (isinstance(delay, float) and not math.isfinite(delay)) or delay < 0):
            raise ValueError(f"Doctor {doctor.id} needs a finite, non-negative simulated delay in seconds.")
        checked.append(delay)
    return checked


async def doctor_availability(service, patient, doctor, window_start, window_end, snapshot, delay):
    """Wait without blocking the event loop, then run the existing pure calculation.

    A valid result may be an empty list. A missing or unsuitable snapshot is not
    turned into an empty list: the service raises AvailabilityUnknownError.
    """
    await asyncio.sleep(delay)
    slots = service.available_slots_using_snapshot(
        patient, doctor, window_start, window_end, snapshot,
    )
    return doctor.id, slots


async def collect_sequential(service, patient, doctors, snapshots, window_start, window_end, delays):
    """Await each doctor's coroutine to completion before starting the next one.

    Returns [(doctor_id, slots), ...] in input order. The first failure stops the
    collection and propagates unchanged; later doctors are not started.
    """
    results = []
    for doctor, delay in zip(doctors, _checked_delays(doctors, delays)):
        results.append(await doctor_availability(
            service, patient, doctor, window_start, window_end, snapshots.get(doctor.id), delay,
        ))
    return results


async def collect_concurrent(service, patient, doctors, snapshots, window_start, window_end, delays):
    """Schedule every doctor's coroutine as a Task first, then collect all results.

    asyncio.gather returns results in the order the tasks were given (input order),
    whatever order they finish in. Every task is allowed to finish, so no work is
    left running; then the first failure in input order is raised unchanged, the
    same error collect_sequential would raise for the same inputs.
    """
    delay_values = _checked_delays(doctors, delays)
    tasks = [
        asyncio.create_task(doctor_availability(
            service, patient, doctor, window_start, window_end, snapshots.get(doctor.id), delay,
        ))
        for doctor, delay in zip(doctors, delay_values)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results
