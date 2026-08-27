# ADR 0005 — Modelo de dominio consciente de persistencia

## Contexto

`app/domain/models.py` contiene las entidades declarativas de SQLAlchemy (`Client`, `Order`,
`Payment`, `AuditLog`). Eso significa que la capa de dominio conoce el ORM y, por extensión,
conoce que existe una base de datos relacional detrás — lo cual, en la lectura más estricta de
hexagonal, no debería pasar: el dominio debería ser ajeno a cómo se persiste.

## Decisión

Se acepta deliberadamente. No hay entidades de dominio puras separadas de las entidades de
SQLAlchemy, ni mappers entre unas y otras.

## Consecuencias

La alternativa pura — entidades de dominio desacopladas más mappers hacia/desde SQLAlchemy —
es correcta a mayor escala, pero aquí es exactamente la ceremonia de DTOs que el ADR 0003 ya
rechazó, aplicada al mismo problema con otro nombre. La regla de dependencia que de verdad
importa en este ejercicio no es "el dominio no debe saber de SQLAlchemy", sino la dirección de
*confianza y control*: `agent → policy`, nunca al revés, y esa regla se hace cumplir aparte,
con el test de importaciones de la SPEC 1 (sección 16, criterio 8). Este ADR existe para que
esto se lea como una decisión tomada con los ojos abiertos, no como un descuido que alguien
"corrige" a mitad de la SPEC 2.
