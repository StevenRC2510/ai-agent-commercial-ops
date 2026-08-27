# NOTES — SPEC 1: plataforma determinista

Registro de decisiones, ambigüedades y abstracciones deliberadamente no construidas durante
la implementación de SPEC 1. Se apoya en el ledger completo de la sesión de build
(`.superpowers/sdd/2026-08-26-spec1-deterministic-platform/progress.md`, no versionado) y
en las diez ADRs de `docs/adr/`. Este documento alimenta el README de SPEC 2.

## 1. Decisiones tomadas durante la construcción

- **PostgreSQL en vez de SQLite.** `Numeric` en SQLite se coacciona a `float` en algún punto
  de la cadena ORM/driver; `credit_limit`, `total` y `amount` no pueden permitírselo. Ver
  ADR 0001.
- **La política devuelve estructura; la presentación renderiza texto.** `policy.evaluate()`
  (`backend/app/application/policy.py`) nunca construye una frase — devuelve un
  `PolicyDecision` con un código de motivo y, para escrituras, un `OrderStatusChange`.
  `presentation.py` es el único módulo que arma el español que lee un humano. La separación
  está reforzada, no solo documentada: `tests/architecture/test_imports.py::
  test_presentation_module_never_imports_policy` falla si esa dependencia aparece.
- **El caso de uso posee la transacción.** `tools.update_order_status` aplica el cambio de
  estado y escribe su `AuditLog` en la misma transacción, con `commit()`/`rollback()`
  explícitos; si el `AuditLog` fallara a mitad, la actualización de la orden se revierte con
  él. No hay dos escrituras que puedan quedar a medias.
- **`safe_args` se normaliza en el schema, no en la tool.** El recorte de `limit` a
  `MAX_ORDER_LIMIT` vive en el `model_validator` de `GetSalesOrdersArgs`
  (`backend/app/application/tool_args.py`), no en `tools.py`. Un solo punto de
  normalización evita que se audite un `limit` distinto del que realmente se ejecutó.
- **Los motivos de denegación deliberadamente no son un oráculo.** En `policy.evaluate()`,
  un rol inexistente, vacío o `None` deniega con el mismo código
  (`role_lacks_permission`) que un rol válido sin permiso — así el sistema nunca revela,
  por el código de motivo, si un nombre de rol existe.
- **`/health` separado de `/ready`.** `/health` no toca nada; `/ready` sí consulta la base.
  El healthcheck de Docker usa `/health`, así un corte momentáneo de Postgres no reinicia
  el backend en bucle (`backend/app/api/routes/health.py`).
- **El vocabulario de autorización vive en enums, no en strings sueltos.** `Role`,
  `ToolName` y `DenialReason` (`backend/app/application/permissions.py`) son `str, Enum`
  cerrados; `ROLE_PERMISSIONS` está envuelto en `MappingProxyType` para que ni siquiera el
  propio proceso pueda reescribir la tabla en caliente. Un typo como `get_sales_order` deja
  de ser un tool que la política silenciosamente no reconoce y pasa a ser un `AttributeError`
  en el propio código.
- **La base de tests está separada de la base de la aplicación.** `commercial_ops_test` se
  crea con `db/init/01-create-test-database.sh`, y `conftest.py` aborta con `RuntimeError` en
  tiempo de colección si `TEST_DATABASE_URL` llegara a coincidir con `DATABASE_URL` — la
  suite hace `TRUNCATE` y no debe poder alcanzar nunca los datos sembrados de la app.
- **La puerta de cobertura mide solo `policy`, `tools` y `presentation`.** Medir todo el
  paquete dejaría que `constants.py` o `errors.py` inflaran el número y ocultaran un hueco
  real en `policy.py`, que es el módulo que el ejercicio pone a prueba.
- **`Order.status` es un `Enum` real de SQLAlchemy, no un `String(20)`.** Con
  `create_constraint=True` y `values_callable`, la vocabulario válido se aplica en dos capas
  independientes: Python y una constraint `CHECK` en la base de datos.
- **`update_order_status` bloquea la fila con `SELECT ... FOR UPDATE`.** Dos confirmaciones
  concurrentes sobre la misma orden se serializan; la segunda espera en vez de pisar a la
  primera.
- **Las 15 advertencias de `pip-audit` se resolvieron subiendo versiones, no documentándolas
  como aceptadas.** `starlette` es el framework ASGI que sirve cada petición, no tooling de
  build; dejarlo con seis avisos conocidos en un proyecto evaluado en seguridad habría sido
  un doble estándar frente a cómo se trató `npm audit`. Se subió `fastapi` a `0.141.1` —cuya
  propia restricción (`starlette>=0.46.0`, sin tope) admite `starlette==1.6.0`— en vez de
  fijar `starlette` solo y dejar un `fastapi` viejo exigiendo `<0.42.0`, lo que habría sido
  una imposibilidad de resolución. `pytest` subió a `9.0.3`; `pip` y `setuptools` —que no son
  dependencias de ningún `requirements*.txt`, sino parte de la imagen base— se fijan
  explícitamente en `backend/Dockerfile` a `26.2` y `83.0.0`. Los 169 tests, la cobertura del
  100%, `/ready` (200 y 503), el CORS y `make check` se reverificaron después del salto de
  versión; `pip-audit` vuelve a correr limpio: "No known vulnerabilities found".

## 2. Ambigüedades resueltas de forma independiente

- **No existía un código de motivo para una orden inexistente.** El vocabulario original
  solo distinguía transiciones inválidas; se añadió `DenialReason.ORDER_NOT_FOUND` para que
  "la orden no existe" y "la transición no es legal" queden distinguibles en el audit trail.
- **`AuditLog.reason` significaba dos cosas a la vez** — el código de la política y el
  motivo de negocio escrito por el usuario. Se separó en `reason_code` (código máquina,
  mismo vocabulario que `PolicyDecision.reason`) y `args` (evidencia completa, incluido ese
  motivo). Cada columna tiene ahora un solo significado.
- **Un schema estricto y un test de recorte (`clamp`) no pueden sostenerse juntos sobre el
  mismo campo si "estricto" significa rechazar cualquier valor fuera de rango.** Se resolvió
  por campo: `limit` por encima de `MAX_ORDER_LIMIT` se recorta silenciosamente en el
  `model_validator` (un valor "demasiado entusiasta" no es un ataque), mientras que
  `order_id`/`client_id` siguen con `gt=0, strict=True` y rechazan de plano cualquier valor
  fuera de tipo o de rango — incluida una carga con forma de inyección SQL.
- **La spec nunca fijó un orden de resultados para `get_sales_orders`.** Se fijó
  `created_at DESC, id DESC`: el `id` desempata las órdenes creadas el mismo día, así la
  paginación es reproducible entre llamadas.
- **CORS no aparecía en la fase 1 original, pero el criterio de aceptación 3 lo exige** —
  el frontend en `:5173` debe poder leer el estado del backend en `:8000`, otro origen. Se
  añadió `CORSMiddleware` restringido a `FRONTEND_ORIGIN` (nunca `*`) en `app/main.py`.
- **`LOG_LEVEL` estaba declarado pero no se leía.** `uvicorn.run(log_config=...)` volvía a
  ejecutar `dictConfig` con niveles `INFO` fijos, deshaciendo en silencio cualquier ajuste.
  `configure_logging()` ahora aplica `settings.log_level` a cada logger configurado;
  verificado empíricamente que `LOG_LEVEL=WARNING` suprime el evento `app_start`.

## 3. Abstracciones deliberadamente NO construidas

- **Sin capa de repositorios** (ADR 0003). La `Session` de SQLAlchemy ya es un Unit of Work;
  envolver tres consultas en repositorios añadiría indirección entre `tools.py` y una API ya
  estable y testeable, sin desacoplar nada — solo hay un destino de persistencia.
- **Sin DTOs ni mappers** (ADR 0003). Los `dict` que devuelven las tools ya son la frontera
  de serialización; duplicar su forma en clases solo garantiza que ambas versiones deriven.
- **Sin clases `UseCase`.** Con tres operaciones, `tools.py` con tres funciones *es* la capa
  de aplicación; envolver cada una en una clase de un solo método sería ceremonia sin
  polimorfismo que la justifique.
- **Sin `PolicyPort`.** Hacer que el punto de aplicación de la autorización fuera
  inyectable/intercambiable es, en sí mismo, una superficie de ataque: una abstracción así
  permitiría que la raíz de composición — o, peor, un futuro orquestador — apuntara la
  autorización a una implementación distinta en tiempo de ejecución. `tools.py` y el
  orquestador de SPEC 2 dependen de `policy.py` de forma concreta, a propósito.

## 4. Limitaciones conocidas

- **`AuditLog` es inmutable por convención, no por permiso de base de datos.** El docstring
  de la clase (`backend/app/domain/models.py`) lo declara explícitamente; no existe todavía
  un `REVOKE UPDATE, DELETE` a nivel de rol de Postgres, así que una credencial de aplicación
  comprometida podría en teoría alterar el historial.
- **La identidad es una cabecera sin autenticar** (`X-User-Role`, `X-User-Id`, ver
  `docs/SPEC-2.md`), un sustituto de un claim JWT verificado. Cambiarla por autenticación
  real modifica un único adaptador — el punto donde `api/deps.py` extrae `actor`/`role` de
  la petición — y cero líneas de `policy.py`, que solo recibe `role` como string ya resuelto.
- **El frontend es solo andamiaje.** Lint, tests, providers y un `HealthIndicator` validado
  con Zod; la UI de producto (chat, tarjeta de confirmación) es la fase 2, documentada como
  árbol reservado en `frontend/src/features/chat/README.md`.
