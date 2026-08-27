#!/bin/bash
set -e

# Only runs when the data volume is initialised: `docker compose down -v` is required to re-apply it.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE ${POSTGRES_DB}_test;
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB}_test TO ${POSTGRES_USER};
EOSQL
