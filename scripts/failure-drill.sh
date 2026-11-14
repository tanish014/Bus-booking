#!/usr/bin/env bash
# kills the database on purpose and shows the app notices + recovers
BASE="${1:-https://localhost:8443}"
echo "== before =="; curl -sk "$BASE/ready"; echo
echo "== stopping db =="; docker-compose stop db
sleep 3
echo "== during outage (expect 503 on /ready, /health still ok) =="
curl -sk -w " -> %{http_code}\n" "$BASE/ready"
curl -sk -w " -> %{http_code}\n" "$BASE/health"
echo "== starting db again =="; docker-compose start db
for i in $(seq 1 20); do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "$BASE/ready")
  echo "try $i: /ready -> $code"
  [ "$code" = "200" ] && break
  sleep 3
done
echo "== recent api logs =="; docker-compose logs --tail=8 api
