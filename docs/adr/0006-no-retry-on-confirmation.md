# ADR 0006 — Sin reintento en la confirmación

## Contexto

TanStack Query reintenta mutaciones fallidas por defecto. En este frontend hay dos
mutaciones con implicaciones muy distintas si se reintentan: enviar un mensaje de chat
(`sendMessage`) y confirmar una acción de escritura (`confirmAction`).

## Decisión

`sendMessage` reintenta 2 veces con backoff. `confirmAction` **no reintenta nunca, cero
veces**.

## Consecuencias

`pending_id` es de un solo uso, así que un reintento de `confirmAction` fallaría de forma
limpia en el peor caso — el backend ya garantiza que no hay doble ejecución por diseño (ADR
0002). Pero eso no es razón suficiente para reintentar: si la red se cae **después** de que
el servidor ya ejecutó la acción, un reintento automático le mostraría al usuario un mensaje
de error sobre algo que en realidad sí ocurrió. Reportar incertidumbre ("no sabemos si esto
se completó, revisa el estado") es preferible a reportar una falsedad ("esto falló") cuando en
verdad no falló. `sendMessage`, en cambio, es una operación de lectura desde la perspectiva
del cliente — reintentarla es seguro y mejora la experiencia ante fallos de red transitorios.
