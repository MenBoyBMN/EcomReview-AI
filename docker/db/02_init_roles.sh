#!/bin/sh
# Rotate ecom_agent_ro password from environment variable during Postgres container init
set -e

if [ -n "${POSTGRES_RO_PASSWORD:-}" ]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v ro_pass="$POSTGRES_RO_PASSWORD" <<'EOSQL'
ALTER ROLE ecom_agent_ro WITH LOGIN PASSWORD :'ro_pass';
REVOKE SELECT ON users FROM ecom_agent_ro;
REVOKE SELECT ON pilot_shops FROM ecom_agent_ro;
REVOKE SELECT ON shop_api_keys FROM ecom_agent_ro;
REVOKE SELECT ON audit_logs FROM ecom_agent_ro;
REVOKE SELECT ON refresh_tokens FROM ecom_agent_ro;
REVOKE SELECT ON shop_marketplace_connections FROM ecom_agent_ro;
REVOKE SELECT ON tenant_subscriptions FROM ecom_agent_ro;
EOSQL
fi

# CreBy: MenBoyBMN
