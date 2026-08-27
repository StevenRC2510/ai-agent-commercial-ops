# ADR 0002 — Confirmación de escritura fuera de banda

## Contexto

Toda escritura del agente necesita consentimiento explícito del usuario, y la conversación
con el modelo es exactamente la superficie de ataque que este proyecto está mitigando: un
dato envenenado (el cliente adversarial del seed, o cualquier texto de un tercero) llega al
modelo mezclado con instrucciones legítimas. Si el "sí, confirmo" viviera dentro del chat,
sería texto — y el texto es el vector, no la defensa.

## Decisión

El consentimiento es un evento HTTP autenticado (`POST /confirm`) sobre un identificador
opaco de un solo uso (`pending_id`), con TTL, vinculado al `actor` y `role` que originaron la
propuesta, y **revalidado contra `policy.evaluate()` en el momento de ejecutar** — nunca un
"sí" interpretado por el modelo dentro de la conversación.

## Consecuencias

Un dato envenenado no puede forjar una aprobación, porque la aprobación no es lenguaje: es
un evento de sistema sobre un recurso que el modelo ni siquiera puede nombrar de antemano. El
modelo queda completamente fuera de la decisión de ejecutar — solo propone. El costo es un
endpoint adicional y un store (`PendingActionStore`) para las acciones pendientes. Es el
mismo principio que tomar el rol del usuario de una cabecera HTTP y no de lo que el prompt
dice que el usuario es: la autorización nunca se deriva de texto que el modelo pudo haber
visto o generado.
