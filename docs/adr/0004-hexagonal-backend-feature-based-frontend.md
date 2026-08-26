# ADR 0004 — Backend hexagonal, frontend por feature

## Contexto

El proyecto tiene dos codebases con patrones de cambio muy distintos: el backend tiene pocas
capas estables (dominio, aplicación, infraestructura, adaptadores) que casi no crecen en
número; el frontend, en cambio, va a acumular features independientes (hoy solo `chat/`,
mañana potencialmente más) que cambian con frecuencias distintas entre sí.

## Decisión

El backend se organiza por capa arquitectónica (`domain/`, `application/`, `infrastructure/`,
`api/`). El frontend se organiza por feature, con un interior hexagonal dentro de cada una
(`features/<name>/{domain,infrastructure,application,ui}/`).

## Consecuencias

En el backend, las capas son pocas y estables, así que organizar por capa es lo que más
información da de un vistazo: cualquiera sabe que la política vive en `application/` y nunca
en `infrastructure/`. En el frontend, las features son muchas e independientes entre sí, así
que co-localizar la UI, los hooks y los adaptadores de una misma feature reduce más
fricción que agruparlas por tipo técnico (todos los hooks juntos, todos los componentes
juntos) sin relación entre sí. La frontera del frontend queda trazada justo donde entraría
una segunda feature — añadirla es un cambio aditivo, no un reacomodo.
