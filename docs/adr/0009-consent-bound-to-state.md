# ADR 0009 — El consentimiento está atado al estado, no solo a la acción

## Contexto

ADR 0002 ya resolvió que el consentimiento es un evento HTTP fuera de banda, no una
conversación. Pero eso no basta por sí solo: entre que se propone la escritura y se confirma,
el estado de la orden puede cambiar por otra vía (otra confirmación concurrente, otro canal).
Hoy `/confirm` revalida contra `policy.evaluate()`, que comprueba si la transición pedida
sigue siendo legal — pero legal no es lo mismo que la transición exacta que el usuario
aprobó. El usuario no consintió "un cambio de estado válido en abstracto"; consintió una
frase concreta: "de en proceso a entregada". Si el estado ya cambió a otra cosa, la nueva
transición puede ser legal según `ALLOWED_TRANSITIONS` y aun así no ser lo que la persona
aprobó.

## Decisión

`/confirm` valida contra el `OrderStatusChange` guardado en la acción pendiente, no solo
contra el resultado de `policy.evaluate()`. Si el `from_status` actual de la orden ya no
coincide con el `from_status` que el usuario vio y aprobó, se rechaza con el código
`state_changed_since_consent`, incluso si la transición nueva sería legal por sí sola. En la
capa de datos, `update_order_status` además lockea la fila (`with_for_update()`, o un UPDATE
condicional con verificación de `rowcount`) para que dos confirmaciones concurrentes no
puedan leer el mismo estado de partida y pisarse una a la otra.

## Consecuencias

Sin esto, dos confirmaciones concurrentes sobre la misma orden producen un lost update en la
operación con las garantías más fuertes del sistema: la segunda escritura gana en silencio y
la primera desaparece sin error. Con la validación contra el descriptor, un cambio de estado
ocurrido entre la propuesta y la confirmación siempre se detecta y se rechaza explícitamente,
en vez de ejecutar una transición que ya no es la que la persona vio en la tarjeta. El costo
es un código de motivo nuevo y una comparación adicional en `/confirm`; a cambio, "aprobar"
deja de significar "cualquier transición legal desde donde sea" y pasa a significar
exactamente lo que la tarjeta mostró.
