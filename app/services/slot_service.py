from datetime import timedelta

from app.models.class_session import (
    ClassSession,
    ClassSessionStatus,
)
from app.models.hire_request import HireRequest, HireStatus


ACTIVE_SESSION_STATUSES = (
    ClassSessionStatus.SCHEDULED,
    ClassSessionStatus.TRAVELLING,
    ClassSessionStatus.ARRIVED,
    ClassSessionStatus.IN_PROGRESS,
)


def intervals_overlap(start_a, end_a, start_b, end_b):
    """True when two half-open time intervals overlap."""
    return start_a < end_b and end_a > start_b


def get_teacher_sessions(teacher_id, start, end):
    """
    Return active scheduled sessions that intersect the requested window.
    """
    return (
        ClassSession.query
        .filter(
            ClassSession.teacher_id == teacher_id,
            ClassSession.status.in_(ACTIVE_SESSION_STATUSES),
            ClassSession.scheduled_start < end,
            ClassSession.scheduled_end > start,
        )
        .order_by(ClassSession.scheduled_start.asc())
        .all()
    )


def is_teacher_slot_free(
    teacher_id,
    scheduled_start,
    scheduled_end,
    travel_buffer_minutes=0,
):
    """
    Basic conflict protection.

    The requested interval is expanded by the travel buffer on both sides.
    This prevents booking classes back-to-back when travel is required.
    """
    buffer = timedelta(minutes=max(0, int(travel_buffer_minutes or 0)))

    effective_start = scheduled_start - buffer
    effective_end = scheduled_end + buffer

    sessions = get_teacher_sessions(
        teacher_id,
        effective_start,
        effective_end,
    )

    for session in sessions:
        if intervals_overlap(
            effective_start,
            effective_end,
            session.scheduled_start,
            session.scheduled_end,
        ):
            return False

    return True


def get_available_slots(
    teacher_id,
    window_start,
    window_end,
    duration_minutes=60,
    step_minutes=15,
    travel_buffer_minutes=0,
):
    """
    Generate bookable start/end slots inside a teacher's availability window.

    Existing ClassSession records are treated as hard blocks.
    """
    duration = timedelta(minutes=int(duration_minutes))
    step = timedelta(minutes=max(1, int(step_minutes)))

    if window_end <= window_start:
        return []

    if duration > (window_end - window_start):
        return []

    sessions = get_teacher_sessions(
        teacher_id,
        window_start,
        window_end,
    )

    slots = []
    cursor = window_start

    while cursor + duration <= window_end:
        slot_end = cursor + duration

        buffer = timedelta(
            minutes=max(0, int(travel_buffer_minutes or 0))
        )

        effective_start = cursor - buffer
        effective_end = slot_end + buffer

        conflict = any(
            intervals_overlap(
                effective_start,
                effective_end,
                session.scheduled_start,
                session.scheduled_end,
            )
            for session in sessions
        )

        if not conflict:
            slots.append(
                {
                    "start": cursor,
                    "end": slot_end,
                    "duration_minutes": int(duration.total_seconds() / 60),
                }
            )

        cursor += step

    return slots


def create_class_session_from_hire(
    hire,
    scheduled_start,
    scheduled_end,
    teaching_mode,
    travel_mode,
    origin_latitude=None,
    origin_longitude=None,
    destination_latitude=None,
    destination_longitude=None,
    travel_buffer_minutes=0,
    notes=None,
):
    """
    Create the actual ClassSession only after the requested hire has
    passed scheduling validation.

    The final conflict check is intentionally performed immediately
    before insertion so callers cannot rely only on a UI availability check.
    """
    from app import db

    if hire.status != HireStatus.ACCEPTED:
        raise ValueError(
            "Only accepted hire requests can create a class session."
        )

    if scheduled_end <= scheduled_start:
        raise ValueError("Class end time must be after start time.")

    if not is_teacher_slot_free(
        hire.teacher_id,
        scheduled_start,
        scheduled_end,
        travel_buffer_minutes=travel_buffer_minutes,
    ):
        raise ValueError("Teacher is no longer available for this time slot.")

    session = ClassSession(
        teacher_id=hire.teacher_id,
        student_id=hire.student_id,
        hire_request_id=hire.id,
        scheduled_date=scheduled_start.date(),
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        teaching_mode=teaching_mode,
        travel_mode=travel_mode,
        status=ClassSessionStatus.SCHEDULED,
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        travel_buffer_minutes=max(0, int(travel_buffer_minutes or 0)),
        notes=notes,
    )

    db.session.add(session)
    db.session.flush()

    return session
