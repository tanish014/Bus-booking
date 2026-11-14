"""Bus booking API - trips, seat maps, bookings, cancellation."""

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import date, datetime, timezone

from flask import Flask, g, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.db import get_engine, init_db, make_pnr

VERSION = os.environ.get("APP_VERSION", "dev")


class JsonFormatter(logging.Formatter):
    """prints each log line as json so it is easy to grep / parse"""

    def format(self, record):
        data = {
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        data.update(getattr(record, "extra_data", {}))
        return json.dumps(data)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("bus")
    log.handlers = [handler]
    log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    log.propagate = False
    return log


def validate(data, trip, stops):
    """returns an error message, or None if everything is fine"""
    for field in ("trip_id", "seat_no", "travel_date", "boarding_stop", "drop_stop", "passenger"):
        if field not in data:
            return f"missing field: {field}"
    p = data["passenger"]
    if not isinstance(p, dict):
        return "passenger must be an object"
    if len(str(p.get("name", "")).strip()) < 2:
        return "passenger name is too short"
    age = p.get("age")
    if not isinstance(age, int) or isinstance(age, bool) or not (1 <= age <= 120):
        return "passenger age must be a number between 1 and 120"
    if not re.fullmatch(r"\d{10}", str(p.get("phone", ""))):
        return "passenger phone must be 10 digits"
    try:
        tdate = date.fromisoformat(data["travel_date"])
    except (ValueError, TypeError):
        return "travel_date must look like YYYY-MM-DD"
    if tdate < date.today():
        return "travel_date is in the past"
    if str(trip.travel_date) != str(tdate):
        return "travel_date does not match the trip date"
    seat = data["seat_no"]
    if not isinstance(seat, int) or isinstance(seat, bool) or not (1 <= seat <= trip.total_seats):
        return f"seat_no must be between 1 and {trip.total_seats}"
    if data["boarding_stop"] not in stops or data["drop_stop"] not in stops:
        return "boarding/drop stop is not on this route"
    if stops.index(data["boarding_stop"]) >= stops.index(data["drop_stop"]):
        return "boarding stop must come before the drop stop"
    return None


def create_app(engine=None):
    app = Flask(__name__)
    log = setup_logging()
    app.engine = engine or get_engine()
    if engine is not None or os.environ.get("AUTO_INIT_DB", "0") == "1":
        init_db(app.engine)

    @app.before_request
    def start_timer():
        g.start = time.time()
        g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:8])

    @app.after_request
    def log_request(resp):
        resp.headers["X-Request-ID"] = g.request_id
        if request.path != "/health":  # health is hit every few secs, too noisy
            log.info(
                "request",
                extra={
                    "extra_data": {
                        "request_id": g.request_id,
                        "method": request.method,
                        "path": request.path,
                        "status": resp.status_code,
                        "ms": round((time.time() - g.start) * 1000, 1),
                    }
                },
            )
        return resp

    def error(msg, code):
        return jsonify({"error": msg}), code

    # ---------- health ----------
    @app.get("/health")
    def health():
        # liveness: is the process alive? (does not touch the db)
        return jsonify({"status": "ok", "version": VERSION})

    @app.get("/ready")
    def ready():
        # readiness: can we actually reach the database?
        try:
            with app.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return jsonify({"status": "ready", "database": "up"})
        except Exception as e:
            log.error("readiness failed", extra={"extra_data": {"error": str(e)[:200]}})
            return jsonify({"status": "not ready", "database": "down"}), 503

    # ---------- read APIs ----------
    @app.get("/routes")
    def routes():
        out = []
        with app.engine.connect() as conn:
            rows = conn.execute(text("SELECT id, origin, destination FROM routes ORDER BY id")).mappings().all()
            for r in rows:
                stops = (
                    conn.execute(text("SELECT name FROM stops WHERE route_id=:r ORDER BY seq"), {"r": r["id"]})
                    .scalars()
                    .all()
                )
                out.append({**r, "stops": stops})
        return jsonify(out)

    @app.get("/trips")
    def trips():
        sql = "SELECT id, route_id, travel_date, departure_time, fare, total_seats FROM trips WHERE 1=1"
        params = {}
        if request.args.get("route_id"):
            sql += " AND route_id=:r"
            params["r"] = request.args["route_id"]
        if request.args.get("date"):
            sql += " AND travel_date=:d"
            params["d"] = request.args["date"]
        sql += " ORDER BY travel_date, departure_time"
        with app.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return jsonify([{**r, "travel_date": str(r["travel_date"])} for r in rows])

    @app.get("/trips/<int:trip_id>/seats")
    def seat_map(trip_id):
        with app.engine.connect() as conn:
            trip = conn.execute(text("SELECT total_seats FROM trips WHERE id=:i"), {"i": trip_id}).first()
            if not trip:
                return error("trip not found", 404)
            booked = (
                conn.execute(
                    text("SELECT seat_no FROM bookings WHERE trip_id=:i AND status='CONFIRMED'"),
                    {"i": trip_id},
                )
                .scalars()
                .all()
            )
        seats = [
            {"seat_no": n, "status": "BOOKED" if n in booked else "AVAILABLE"} for n in range(1, trip.total_seats + 1)
        ]
        return jsonify({"trip_id": trip_id, "available": trip.total_seats - len(booked), "seats": seats})

    # ---------- booking ----------
    @app.post("/bookings")
    def create_booking():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("body must be valid JSON", 400)
        if not isinstance(data.get("trip_id"), int):
            return error("trip_id must be a number", 400)

        with app.engine.connect() as conn:
            trip = conn.execute(
                text("SELECT id, route_id, travel_date, fare, total_seats FROM trips WHERE id=:i"),
                {"i": data["trip_id"]},
            ).first()
            if not trip:
                return error("trip not found", 404)
            stops = (
                conn.execute(text("SELECT name FROM stops WHERE route_id=:r ORDER BY seq"), {"r": trip.route_id})
                .scalars()
                .all()
            )

        problem = validate(data, trip, stops)
        if problem:
            return error(problem, 400)

        p = data["passenger"]
        for _ in range(5):  # retry only if the random PNR collides (very rare)
            pnr = make_pnr()
            try:
                with app.engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO bookings (pnr, trip_id, seat_no, passenger_name, passenger_age, "
                            "passenger_phone, boarding_stop, drop_stop, status, created_at) "
                            "VALUES (:pnr,:t,:s,:n,:a,:ph,:b,:d,'CONFIRMED',:c)"
                        ),
                        {
                            "pnr": pnr,
                            "t": trip.id,
                            "s": data["seat_no"],
                            "n": p["name"].strip(),
                            "a": p["age"],
                            "ph": p["phone"],
                            "b": data["boarding_stop"],
                            "d": data["drop_stop"],
                            "c": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        },
                    )
                log.info(
                    "booking created", extra={"extra_data": {"pnr": pnr, "trip_id": trip.id, "seat": data["seat_no"]}}
                )
                return (
                    jsonify(
                        {
                            "pnr": pnr,
                            "status": "CONFIRMED",
                            "trip_id": trip.id,
                            "seat_no": data["seat_no"],
                            "fare": trip.fare,
                        }
                    ),
                    201,
                )
            except IntegrityError as e:
                # either the seat is taken (unique index) or the PNR collided
                if "pnr" in str(e.orig).lower():
                    continue
                log.warning("seat conflict", extra={"extra_data": {"trip_id": trip.id, "seat": data["seat_no"]}})
                return error("seat already booked for this trip", 409)
        return error("could not generate PNR, try again", 500)

    @app.get("/bookings/<pnr>")
    def get_booking(pnr):
        with app.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT pnr, trip_id, seat_no, passenger_name, boarding_stop, drop_stop, "
                        "status, created_at FROM bookings WHERE pnr=:p"
                    ),
                    {"p": pnr},
                )
                .mappings()
                .first()
            )
        if not row:
            return error("PNR not found", 404)
        return jsonify(dict(row))

    @app.post("/bookings/<pnr>/cancel")
    def cancel_booking(pnr):
        with app.engine.begin() as conn:
            row = conn.execute(text("SELECT status FROM bookings WHERE pnr=:p"), {"p": pnr}).first()
            if not row:
                return error("PNR not found", 404)
            if row.status == "CANCELLED":
                return error("booking is already cancelled", 409)
            conn.execute(text("UPDATE bookings SET status='CANCELLED' WHERE pnr=:p"), {"p": pnr})
        log.info("booking cancelled", extra={"extra_data": {"pnr": pnr}})
        return jsonify({"pnr": pnr, "status": "CANCELLED"})

    @app.errorhandler(404)
    def not_found(_):
        return error("not found", 404)

    @app.errorhandler(405)
    def bad_method(_):
        return error("method not allowed", 405)

    @app.errorhandler(Exception)
    def unexpected(e):
        if isinstance(e, HTTPException):  # keep normal 400/415 etc as they are
            return error(e.description, e.code)
        log.error("unhandled error", extra={"extra_data": {"error": str(e)[:300]}})
        return error("internal server error", 500)

    return app


def app_factory():
    """used by gunicorn:  gunicorn 'app.main:app_factory()'"""
    return create_app()
