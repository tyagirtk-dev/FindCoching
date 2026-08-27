from datetime import datetime, timedelta, time
from math import radians, sin, cos, sqrt, atan2

from app import db
from app.models.class_session import (
    ClassSession,
    ClassSessionStatus,
    TravelMode,
    SessionTeachingMode,
)
from app.models.teacher_availability import TeacherAvailabilitySlot


TRAVEL_SPEED_KMH = {
    TravelMode.WALKING: 5.0,
    TravelMode.BIKE: 25.0,
    TravelMode.CAR: 30.0,
    TravelMode.ONLINE: 999999.0,
}

DEFAULT_BUFFER_MINUTES = 10
MIN_SESSION_MINUTES = 30
MAX_SESSION_MINUTES = 180


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None

    r = 6371.0

    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)

    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def estimate_travel_minutes(distance_km, travel_mode):
    if distance_km is None:
        return None

    if travel_mode == TravelMode.ONLINE:
        return 0

    speed = TRAVEL_SPEED_KMH[travel_mode]

    # Add a modest real-world multiplier for stops/traffic.
    minutes = (distance_km / speed) * 60 * 1.20

    return max(1, int(round(minutes)))


def _overlapping_sessions(teacher_id, start, end):
    """
    Existing sessions that overlap [start, end).

    Cancelled sessions do not block a teacher.
    """
    return (
        ClassSession.query
        .filter(
            ClassSession.teacher_id == teacher_id,
            ClassSession.status != ClassSessionStatus.CANCELLED,
            ClassSession.scheduled_start < end,
            ClassSession.scheduled_end > start,
        )
        .order_by(ClassSession.scheduled_start.asc())
        .all()
    )


def _availability_for_datetime(teacher_id, dt):
    """
    Check weekly teacher availability.

    TeacherAvailabilitySlot:
      0 = Monday ... 6 = Sunday
    """
    weekday = dt.weekday()
    current = dt.strftime("%H:%M")

    return (
        TeacherAvailabilitySlot.query
        .filter(
            TeacherAvailabilitySlot.teacher_id == teacher_id,
            TeacherAvailabilitySlot.weekday == weekday,
            TeacherAvailabilitySlot.is_active.is_(True),
            TeacherAvailabilitySlot.start_time <= current,
            TeacherAvailabilitySlot.end_time > current,
        )
        .first()
    )


def teacher_is_available(teacher_id, start, end):
    """
    A class must fit completely inside one weekly availability slot.
    """
    if end <= start:
        return False

    slot = (
        TeacherAvailabilitySlot.query
        .filter(
            TeacherAvailabilitySlot.teacher_id == teacher_id,
            TeacherAvailabilitySlot.weekday == start.weekday(),
            TeacherAvailabilitySlot.is_active.is_(True),
            TeacherAvailabilitySlot.start_time <= start.strftime("%H:%M"),
            TeacherAvailabilitySlot.end_time >= end.strftime("%H:%M"),
        )
        .first()
    )

    return slot is not None


def has_schedule_conflict(teacher_id, start, end):
    return bool(_overlapping_sessions(teacher_id, start, end))


def calculate_route(
    origin_latitude,
    origin_longitude,
    destination_latitude,
    destination_longitude,
    travel_mode,
):
    """
    Booking-time route snapshot.

    This deliberately uses Haversine + mode speed for the first
    deterministic version. A road-routing provider can later replace
    this function without changing the booking/session architecture.
    """
    if travel_mode == TravelMode.ONLINE:
        return {
            "distance_km": 0.0,
            "estimated_travel_minutes": 0,
        }

    distance = haversine_km(
        origin_latitude,
        origin_longitude,
        destination_latitude,
        destination_longitude,
    )

    minutes = estimate_travel_minutes(distance, travel_mode)

    return {
        "distance_km": round(distance, 3) if distance is not None else None,
        "estimated_travel_minutes": minutes,
    }


def next_available_start(
    teacher_id,
    requested_start,
    duration_minutes,
    travel_minutes=0,
    buffer_minutes=DEFAULT_BUFFER_MINUTES,
):
    """
    Find the earliest start >= requested_start that can actually happen.

    The requested start is pushed forward when:
      - weekly availability doesn't allow it
      - another class occupies the teacher
      - required travel/buffer makes the slot unreachable
    """
    duration_minutes = max(
        MIN_SESSION_MINUTES,
        min(duration_minutes, MAX_SESSION_MINUTES),
    )

    search = requested_start.replace(second=0, microsecond=0)
    max_search = search + timedelta(days=7)

    while search < max_search:
        candidate_end = search + timedelta(minutes=duration_minutes)

        if not teacher_is_available(teacher_id, search, candidate_end):
            search += timedelta(minutes=5)
            continue

        sessions = (
            ClassSession.query
            .filter(
                ClassSession.teacher_id == teacher_id,
                ClassSession.status != ClassSessionStatus.CANCELLED,
                ClassSession.scheduled_end > search - timedelta(
                    minutes=travel_minutes + buffer_minutes
                ),
                ClassSession.scheduled_start < candidate_end,
            )
            .order_by(ClassSession.scheduled_start.asc())
            .all()
        )

        blocked_until = None

        for session in sessions:
            required_gap = timedelta(
                minutes=travel_minutes + buffer_minutes
            )

            # Existing class must finish + travel + buffer
            # before the next home-tuition class can begin.
            possible_after_previous = session.scheduled_end + required_gap

            if possible_after_previous > search:
                blocked_until = possible_after_previous
                break

        if blocked_until:
            search = blocked_until.replace(second=0, microsecond=0)
            continue

        return {
            "start": search,
            "end": candidate_end,
            "travel_minutes": travel_minutes,
            "buffer_minutes": buffer_minutes,
        }

    return None


def get_teacher_schedule(teacher_id, date):
    start = datetime.combine(date, time.min)
    end = start + timedelta(days=1)

    return (
        ClassSession.query
        .filter(
            ClassSession.teacher_id == teacher_id,
            ClassSession.status != ClassSessionStatus.CANCELLED,
            ClassSession.scheduled_start < end,
            ClassSession.scheduled_end > start,
        )
        .order_by(ClassSession.scheduled_start.asc())
        .all()
    )


def create_class_session(
    *,
    teacher_id,
    student_id,
    scheduled_start,
    duration_minutes,
    teaching_mode,
    travel_mode=TravelMode.ONLINE,
    hire_request_id=None,
    origin_latitude=None,
    origin_longitude=None,
    destination_latitude=None,
    destination_longitude=None,
    travel_buffer_minutes=DEFAULT_BUFFER_MINUTES,
    notes=None,
):
    if scheduled_start < datetime.utcnow():
        raise ValueError("A class cannot be scheduled in the past.")

    duration_minutes = max(
        MIN_SESSION_MINUTES,
        min(duration_minutes, MAX_SESSION_MINUTES),
    )

    scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)

    if teaching_mode == SessionTeachingMode.ONLINE:
        travel_mode = TravelMode.ONLINE
        travel_buffer_minutes = 0

    route = calculate_route(
        origin_latitude,
        origin_longitude,
        destination_latitude,
        destination_longitude,
        travel_mode,
    )

    travel_minutes = route["estimated_travel_minutes"] or 0

    availability = teacher_is_available(
        teacher_id,
        scheduled_start,
        scheduled_end,
    )

    if not availability:
        raise ValueError(
            "Teacher is not available for the complete requested time."
        )

    if has_schedule_conflict(
        teacher_id,
        scheduled_start,
        scheduled_end,
    ):
        raise ValueError(
            "Teacher already has another class at this time."
        )

    session = ClassSession(
        teacher_id=teacher_id,
        student_id=student_id,
        hire_request_id=hire_request_id,
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
        distance_km=route["distance_km"],
        estimated_travel_minutes=travel_minutes,
        travel_buffer_minutes=travel_buffer_minutes,
        notes=notes,
    )

    db.session.add(session)
    db.session.flush()

    return session
