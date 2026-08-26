# ADR 0007 — `FakeChatGateway` en vez de MSW

## Contexto

El frontend necesita un doble de test para el backend: algo que sustituya las llamadas HTTP
reales en los tests de componentes y de hooks sin depender de red ni de un backend
levantado. La opción por defecto en el ecosistema React es Mock Service Worker (MSW),
interceptando a nivel de red.

## Decisión

`FakeChatGateway`, una implementación en memoria del puerto `ChatGateway` que ya define la
arquitectura. No se usa MSW.

## Consecuencias

Con `FakeChatGateway` hay una sola estrategia de mocking en todo el frontend, no dos
compitiendo por el mismo propósito (interceptar HTTP a nivel de red vs. sustituir en el
límite arquitectónico). El doble se ubica exactamente en la frontera que el diseño ya
define — la misma que usa `HttpChatGateway` en producción — así que sustituirlo no exige
conocer detalles de transporte (URLs, headers, formato exacto de la petición). Y como
`FakeChatGateway` valida sus propias respuestas contra el mismo schema de Zod que el
adaptador real, un test que pasa contra el fake no puede estar verificando una forma de
datos que el backend real nunca produciría.
