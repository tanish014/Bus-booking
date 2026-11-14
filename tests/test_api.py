import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    # a fresh sqlite file for every test so tests do not affect each other
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"timeout": 30})
    app = create_app(engine)
    return app.test_client()


def trip_date(trip_id=1):
    # seed trip 1 is always (today + 1 day)
    return str(date.today() + timedelta(days=1))


def booking(seat=5, **changes):
    body = {
        "trip_id": 1,
        "seat_no": seat,
        "travel_date": trip_date(),
        "boarding_stop": "Ludhiana",
        "drop_stop": "Delhi",
        "passenger": {"name": "Ravi Kumar", "age": 24, "phone": "9876543210"},
    }
    body.update(changes)
    return body


# ---------- health ----------
def test_health_and_ready(client):
    assert client.get("/health").status_code == 200
    r = client.get("/ready")
    assert r.status_code == 200 and r.json["database"] == "up"


def test_ready_returns_503_when_db_is_down(client):
    # point the app at a broken database to simulate an outage
    client.application.engine = create_engine("sqlite:////nonexistent_dir/x.db")
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200  # app itself still alive


# ---------- read APIs ----------
def test_routes_and_trips(client):
    routes = client.get("/routes").json
    assert len(routes) == 2 and routes[0]["stops"][0] == "Ludhiana"
    assert len(client.get("/trips?route_id=1").json) == 20
    assert len(client.get(f"/trips?date={trip_date()}").json) == 4


def test_seat_map(client):
    r = client.get("/trips/1/seats").json
    assert len(r["seats"]) == 40 and r["available"] == 40
    assert client.get("/trips/9999/seats").status_code == 404


# ---------- booking ----------
def test_create_and_get_booking(client):
    r = client.post("/bookings", json=booking())
    assert r.status_code == 201
    pnr = r.json["pnr"]
    assert pnr.startswith("PNR") and r.json["status"] == "CONFIRMED"
    assert client.get(f"/bookings/{pnr}").json["seat_no"] == 5
    assert client.get("/trips/1/seats").json["available"] == 39


def test_conflicting_seat_fails_and_makes_no_second_pnr(client):
    first = client.post("/bookings", json=booking(seat=7))
    second = client.post("/bookings", json=booking(seat=7))
    assert first.status_code == 201
    assert second.status_code == 409
    assert "pnr" not in second.json
    with client.application.engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM bookings WHERE trip_id=1 AND seat_no=7")).scalar()
    assert n == 1


def test_concurrent_requests_only_one_wins(client):
    results = []

    def try_book():
        results.append(client.post("/bookings", json=booking(seat=12)).status_code)

    threads = [threading.Thread(target=try_book) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(201) == 1
    assert results.count(409) == 9
    with client.application.engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM bookings WHERE seat_no=12 AND status='CONFIRMED'")).scalar()
    assert n == 1


def test_cancel_then_seat_can_be_rebooked(client):
    pnr = client.post("/bookings", json=booking(seat=3)).json["pnr"]
    assert client.post(f"/bookings/{pnr}/cancel").json["status"] == "CANCELLED"
    assert client.post(f"/bookings/{pnr}/cancel").status_code == 409  # cancel twice
    assert client.get(f"/bookings/{pnr}").json["status"] == "CANCELLED"
    assert client.post("/bookings", json=booking(seat=3)).status_code == 201


def test_unknown_pnr(client):
    assert client.get("/bookings/PNRXXXXXXXX").status_code == 404
    assert client.post("/bookings/PNRXXXXXXXX/cancel").status_code == 404


# ---------- validation ----------
@pytest.mark.parametrize(
    "changes",
    [
        {"travel_date": str(date.today() - timedelta(days=1))},  # past date
        {"travel_date": "not-a-date"},
        {"travel_date": str(date.today() + timedelta(days=5))},  # does not match trip
        {"boarding_stop": "Delhi", "drop_stop": "Ludhiana"},  # wrong order
        {"boarding_stop": "Mumbai"},  # not on route
        {"seat_no": 0},
        {"seat_no": 41},
        {"passenger": {"name": "A", "age": 24, "phone": "9876543210"}},
        {"passenger": {"name": "Ravi", "age": 0, "phone": "9876543210"}},
        {"passenger": {"name": "Ravi", "age": 24, "phone": "12345"}},
    ],
)
def test_bad_input_is_rejected(client, changes):
    assert client.post("/bookings", json=booking(**changes)).status_code == 400


def test_missing_field_and_bad_json(client):
    body = booking()
    del body["passenger"]
    assert client.post("/bookings", json=body).status_code == 400
    assert client.post("/bookings", data="hello").status_code == 400
    assert client.post("/bookings", json=booking(trip_id=9999)).status_code == 404
