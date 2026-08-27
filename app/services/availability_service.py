from datetime import datetime, timedelta

from app.models.teacher_availability import TeacherAvailabilitySlot
from app.services.slot_service import get_available_slots


DAY_NAMES = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


def _time_value(value):
    if value is None:
        return None

    if hasattr(value, "hour"):
        return value

    if isinstance(value, str):
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                pass

    return None


def get_teacher_availability_for_date(teacher_id, target_date):
    """
    Return the teacher's configured availability windows for one date.

    This function deliberately adapts to the existing TeacherAvailabilitySlot
    model rather than changing its schema.
    """
    weekday = DAY_NAMES[target_date.weekday()]

    query = TeacherAvailabilitySlot.query.filter(
        TeacherAvailabilitySlot.teacher_id == teacher_id,
    )

    slots = query.all()
    result = []

    for slot in slots:
        day_value = getattr(slot, "day_of_week", None)

        if hasattr(day_value, "value"):
            day_value = day_value.value

        if isinstance(day_value, str):
            day_value = day_value.lower()

        if day_value not in (weekday, str(target_date.weekday()), target_date.weekday()):
            continue

        start_value = _time_value(
            getattr(slot, "start_time", None)
        )
        end_value = _time_value(
            getattr(slot, "end_time", None)
        )

        if not start_value or not end_value:
            continue

        result.append(
            {
                "slot": slot,
                "start": datetime.combine(target_date, start_value),
                "end": datetime.combine(target_date, end_value),
            }
        )

    return result


def get_real_available_slots(
    teacher_id,
    target_date,
    duration_minutes=60,
    step_minutes=15,
    travel_buffer_minutes=0,
):
    """
    Combine teacher availability with already-booked ClassSessions.
    """
    availability = get_teacher_availability_for_date(
        teacher_id,
        target_date,
    )

    results = []

    for window in availability:
        slots = get_available_slots(
            teacher_id=teacher_id,
            window_start=window["start"],
            window_end=window["end"],
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
            travel_buffer_minutes=travel_buffer_minutes,
        )

        for slot in slots:
            results.append(slot)

    results.sort(key=lambda item: item["start"])

    return results
