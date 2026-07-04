#!/bin/sh
# Waits for Kafka Connect's REST API to be up, then registers (or updates)
# the Debezium Postgres connector. Run as a one-shot compose service so the
# stack is fully wired up with a single `docker compose up`.
set -eu

CONNECT_URL="http://connect:8083"
CONNECTOR_NAME="freshdex-outbox-connector"

until curl -sf "${CONNECT_URL}/connectors" > /dev/null; do
  echo "waiting for Kafka Connect at ${CONNECT_URL}..."
  sleep 2
done

echo "Kafka Connect is up, registering ${CONNECTOR_NAME}..."

curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "${CONNECT_URL}/connectors/${CONNECTOR_NAME}" > /dev/null 2>&1 || true

curl -sf -X POST \
  -H "Content-Type: application/json" \
  --data @/connectors/debezium-postgres-connector.json \
  "${CONNECT_URL}/connectors"

echo ""
echo "Registered. Status:"
# Best-effort only: the task may not have spun up yet, so a transient
# non-2xx here shouldn't fail the whole registration, which already
# succeeded via the POST above.
curl -s "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/status" || true
echo ""
