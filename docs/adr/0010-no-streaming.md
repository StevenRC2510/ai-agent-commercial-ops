# ADR 0010 — Sin streaming

## Contexto

El enunciado lista el streaming de la respuesta del modelo como un extra deseable, y es una
mejora de experiencia obvia en un chat. Pero este agente no solo genera texto: puede terminar
un turno proponiendo una escritura, que la política debe aprobar antes de que nada llegue al
usuario. Con streaming se emiten tokens a medida que el modelo los produce, sin saber todavía
si el turno va a terminar en un bloque `tool_use`.

## Decisión

No se implementa streaming en esta fase. La razón es arquitectónica, no falta de tiempo: un
bloque `tool_use` no puede mostrarse al usuario hasta que `policy.evaluate()` lo apruebe, y
una tarjeta de confirmación no puede aparecer a medio dibujar. Streaming y los guardrails de
escritura interactúan mal — o se retiene el output hasta que la política resuelve, con lo cual
se pierde el beneficio del streaming, o se muestra al usuario algo que todavía puede ser
denegado, con lo cual el guardrail deja de proteger nada.

## Consecuencias

El chat espera la respuesta completa de cada turno, con el indicador "pensando…" (SPEC-2
sección 9) cubriendo la latencia. Si en el futuro hace falta streaming, la forma de
resolverlo sin romper el guardrail es streamear solo el texto final, una vez que el bucle de
tools ya terminó y no puede aparecer ningún `tool_use` más — nunca los bloques intermedios del
razonamiento. Eso da parte del beneficio percibido (la respuesta final aparece progresivamente)
sin exponer nunca una propuesta de escritura antes de que la política se pronuncie.
