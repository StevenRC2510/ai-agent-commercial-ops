# ADR 0008 — Sin router de modelos

## Contexto

Varios sistemas de agentes enrutan cada tarea a un modelo distinto según su complejidad
percibida, para balancear costo y calidad. Este sistema tiene exactamente un tipo de tarea:
leer un mensaje, elegir una de tres herramientas, escribir el resultado. No hay una segunda
categoría de trabajo — clasificación, generación larga, resumen — que justifique un
enrutamiento distinto por caso.

## Decisión

No hay router. Un único modelo, configurado en `LLM_MODEL`, atiende todas las tareas. La
única flexibilidad es que el modelo se fija al construir el cliente — usar otro desde un test
o un script de evals es instanciar un `AnthropicClient` con esa configuración distinta, sin
ninguna lógica de selección.

## Consecuencias

Construir un router hoy sería generalidad especulativa: la misma razón por la que ADR 0003
rechaza los repositorios y los DTOs — no hay una segunda variante concreta que abstraer, solo
la posibilidad de que aparezca. Si en el futuro aparecen tools con lógica de negocio real y la
precisión de selección de herramienta cae, o aparecen consultas que exigen razonamiento
multi-paso que el modelo configurado no resuelve bien, el cambio es local: pasar un `model`
distinto donde haga falta, no rediseñar el cliente. La elección del modelo único se justifica
con la tabla de evals de la sección 5.2 de la SPEC 2, no con intuición — y esa misma tabla es
la que definiría, con números, el momento de introducir un router.
