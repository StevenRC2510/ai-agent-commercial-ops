# ADR 0003 — Sin capa de repositorios

## Contexto

La ortodoxia hexagonal sugiere interponer repositorios entre los casos de uso y la base de
datos, como abstracción sobre la persistencia. El proyecto tiene tres operaciones de negocio
y una única base de datos relacional.

## Decisión

No hay repositorios. La `Session` de SQLAlchemy ya cumple el rol de Unit of Work, y
`application/tools.py` consulta directamente a través de ella.

## Consecuencias

Con tres operaciones y una sola base de datos, un repositorio no desacopla nada: solo añade
una capa de indirección entre `tools.py` y una API (la de SQLAlchemy) que ya es
suficientemente estable y testeable por sí misma. Si algún día aparece un segundo destino de
persistencia real, el repositorio se introduce entonces, cuando exista algo concreto que
abstraer — no antes, por especulación. Por la misma razón tampoco hay DTOs ni mappers (los
dicts que devuelven las tools ya son la frontera de serialización; duplicar su forma en
clases solo garantiza que ambas versiones diverjan) ni clases `UseCase` (con tres funciones,
`tools.py` ya es la capa de aplicación completa).
