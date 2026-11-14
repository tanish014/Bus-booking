#!/usr/bin/env bash
# quick check after deploy: health, ready, seat conflict
BASE="${1:-https://localhost:8443}"
D=$(date -d "+1 day" +%F)
BODY='{"trip_id":1,"seat_no":21,"travel_date":"'$D'","boarding_stop":"Ludhiana","drop_stop":"Delhi","passenger":{"name":"Test User","age":22,"phone":"9999999999"}}'
echo "health:"; curl -sk "$BASE/health"; echo
echo "ready:";  curl -sk "$BASE/ready"; echo
echo "booking 1 (expect 201):"; curl -sk -w " -> %{http_code}\n" -X POST -H 'Content-Type: application/json' -d "$BODY" "$BASE/bookings"
echo "booking 2 same seat (expect 409):"; curl -sk -w " -> %{http_code}\n" -X POST -H 'Content-Type: application/json' -d "$BODY" "$BASE/bookings"
