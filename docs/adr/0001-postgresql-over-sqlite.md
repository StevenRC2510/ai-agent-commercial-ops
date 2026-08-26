# ADR 0001 — PostgreSQL en vez de SQLite

## Contexto

El enunciado lista tres servicios de Compose (base de datos, backend, frontend) y permite
SQLite como base de datos. La SPEC 1 original eligió SQLite precisamente para eliminar un
servicio de la orquestación y simplificar el arranque. Esa elección tiene un costo que se
vuelve visible en cuanto el dinero entra en la ecuación: SQLite no tiene un tipo `Decimal`
nativo, y las columnas `Numeric` terminan coaccionadas a float en algún punto de la cadena
ORM/driver, lo cual es exactamente lo que este proyecto no puede permitirse en `credit_limit`,
`total` y `amount`.

## Decisión

PostgreSQL 16 como servicio de Compose (`postgres:16-alpine`), con `pg_isready` como
healthcheck, un volumen nombrado (`pgdata`) para los datos, y el puerto **sin publicar** al
host — solo la red interna de Compose necesita alcanzarlo.

## Consecuencias

Ganamos semántica exacta de `Decimal` de punta a punta, sin coerciones silenciosas a float.
Al no usar un bind mount, el contenedor no-root no puede toparse con un fallo de permisos de
propietario sobre un directorio del host. `docker compose down -v` resetea el estado de
verdad porque el volumen es nombrado y gestionado por Docker, no un directorio que sobrevive
por accidente. Y de paso cumplimos el mínimo de tres servicios que pide el enunciado sin
necesidad de justificar por qué "solo dos" bastan. El costo es un contenedor más y unas
quince líneas de Compose — barato comparado con lo que evita.
