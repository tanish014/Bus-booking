"""Database setup. Works with PostgreSQL (docker) and SQLite (tests)."""

import os
import random
import string
from datetime import date, timedelta

from sqlalchemy import create_engine, text


def get_engine():
    url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    if url.startswith("sqlite"):
        # timeout so concurrent writers wait instead of crashing
        return create_engine(url, connect_args={"timeout": 30})
    return create_engine(url, pool_pre_ping=True)


# note: the partial UNIQUE index is the real protection against double booking.
# Python checks alone are not enough when 2 requests come at the same time.
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY,
        origin VARCHAR(50) NOT NULL,
        destination VARCHAR(50) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS stops (
        id INTEGER PRIMARY KEY,
        route_id INTEGER NOT NULL REFERENCES routes(id),
        name VARCHAR(50) NOT NULL,
        seq INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY,
        route_id INTEGER NOT NULL REFERENCES routes(id),
        travel_date DATE NOT NULL,
        departure_time VARCHAR(5) NOT NULL,
        fare INTEGER NOT NULL,
        total_seats INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bookings (
        pnr VARCHAR(12) PRIMARY KEY,
        trip_id INTEGER NOT NULL REFERENCES trips(id),
        seat_no INTEGER NOT NULL,
        passenger_name VARCHAR(80) NOT NULL,
        passenger_age INTEGER NOT NULL,
        passenger_phone VARCHAR(15) NOT NULL,
        boarding_stop VARCHAR(50) NOT NULL,
        drop_stop VARCHAR(50) NOT NULL,
        status VARCHAR(12) NOT NULL,
        created_at VARCHAR(30) NOT NULL
    )""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_confirmed_seat
       ON bookings (trip_id, seat_no) WHERE status = 'CONFIRMED'""",
]

ROUTES = [
    (1, "Ludhiana", "Delhi", ["Ludhiana", "Ambala", "Karnal", "Delhi"]),
    (2, "Chandigarh", "Amritsar", ["Chandigarh", "Ludhiana", "Jalandhar", "Amritsar"]),
]


def init_db(engine):
    """Create tables and put in seed data (only if tables are empty)."""
    with engine.begin() as conn:
        for stmt in SCHEMA:
            conn.execute(text(stmt))
        count = conn.execute(text("SELECT COUNT(*) FROM routes")).scalar()
        if count > 0:
            return
        stop_id = 1
        trip_id = 1
        today = date.today()
        for rid, origin, dest, stops in ROUTES:
            conn.execute(
                text("INSERT INTO routes (id, origin, destination) VALUES (:i,:o,:d)"),
                {"i": rid, "o": origin, "d": dest},
            )
            for seq, name in enumerate(stops, start=1):
                conn.execute(
                    text("INSERT INTO stops (id, route_id, name, seq) VALUES (:i,:r,:n,:s)"),
                    {"i": stop_id, "r": rid, "n": name, "s": seq},
                )
                stop_id += 1
            # trips for the next 10 days, 2 per day
            for day in range(1, 11):
                for hhmm, fare in (("06:30", 450), ("21:00", 550)):
                    conn.execute(
                        text(
                            "INSERT INTO trips (id, route_id, travel_date, departure_time, fare, total_seats) "
                            "VALUES (:i,:r,:d,:t,:f,40)"
                        ),
                        {"i": trip_id, "r": rid, "d": str(today + timedelta(days=day)), "t": hhmm, "f": fare},
                    )
                    trip_id += 1


def make_pnr():
    chars = string.ascii_uppercase + string.digits
    return "PNR" + "".join(random.choices(chars, k=8))


if __name__ == "__main__":
    # run by the container before gunicorn starts: python -m app.db
    import time

    eng = get_engine()
    for attempt in range(10):
        try:
            init_db(eng)
            print("database ready")
            break
        except Exception as e:  # db may still be starting
            print(f"db not ready (try {attempt + 1}): {e}")
            time.sleep(3)
    else:
        raise SystemExit("could not connect to database")
