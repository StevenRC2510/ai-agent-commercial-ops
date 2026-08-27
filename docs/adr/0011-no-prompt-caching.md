# ADR 0011 — Sin prompt caching

## Contexto

El system prompt y las definiciones de tools son idénticos en cada turno, así que son el
objetivo natural del prompt caching. Pero el mínimo cacheable no es monótono entre modelos: por
debajo de ese mínimo no se cachea nada y no hay error — `cache_creation_input_tokens` sale en
cero, en silencio. Activar `cache_control` sin medir produce una optimización que no optimiza y
que nadie nota.

| Modelo | Prefijo cacheable mínimo |
|---|---|
| `claude-opus-5` | 512 tokens |
| `claude-sonnet-5` | 1024 tokens |
| `claude-haiku-4-5` | 4096 tokens |

`make measure-prompt` compone el prefijo real — `SYSTEM_PROMPT` formateado más los schemas que
`tool_schemas_for(role)` declara — y lo mide. Con `claude-haiku-4-5`, el modelo configurado:

| Rol | Tools | System | Schemas | Total | Tokens estimados |
|---|---|---|---|---|---|
| operator | 2 | 1509 | 1656 | 3165 chars | 792–1266 |
| supervisor | 3 | 1511 | 2566 | 4077 chars | 1020–1631 |

La cuenta de tokens es una estimación por caracteres, no una medición: el tokenizador de
Anthropic no es público y `/v1/messages/count_tokens` — que normalmente no se factura — tampoco
está disponible aquí, porque la cuenta no tiene saldo y devuelve 400. Por eso el script informa
una banda de 2.5 a 4.0 chars/token — de JSON denso en puntuación a prosa española acentuada — y
solo concluye cuando la banda entera cae del mismo lado del mínimo.
Aquí cae: el prefijo más grande alcanzaría los 4096 tokens únicamente a 0.995 chars/token, un
ritmo que ningún tokenizador BPE se acerca a producir. La conclusión sobrevive a su propio
margen de error, que es lo que la vuelve utilizable sin la medición exacta.

## Decisión

No se activa `cache_control` en ninguna petición. Con `claude-haiku-4-5` el prefijo está tres a
cuatro veces por debajo del mínimo: cachearlo no ahorraría un token ni un centavo, y dejaría en
el código una optimización que cualquier lector supondría activa.

## Consecuencias

Cada turno paga el prefijo completo como input normal — entre 1000 y 1600 tokens, es decir
entre $0.0010 y $0.0016 por llamada al precio de Haiku. Es el costo de no tener la
optimización, y es menor que el costo de creer que se tiene.

Qué cambiaría la respuesta, en orden de probabilidad. **Cambiar de modelo:** con
`claude-opus-5` (512) este mismo prefijo, sin tocar una línea de prompt, queda holgadamente por
encima del mínimo y el veredicto pasa a `cacheable`; con `claude-sonnet-5` (1024) queda tan al
borde que la estimación por caracteres devuelve `inconclusive` — ahí no alcanza este ADR, hay
que contar los tokens reales contra la API antes de decidir. **Crecer la superficie de tools:**
tres tools ocupan 2566 caracteres, así que una decena más de tamaño parecido llevaría el
prefijo al mínimo de Haiku por sí sola. En cualquiera de los dos casos, `make measure-prompt`
vuelve a dar el veredicto sin volver a razonarlo, y la economía a partir de ahí es la de la
sección 5.2 de la SPEC 2: la lectura de cache cuesta ~0.1x y la escritura 1.25x, con punto de
equilibrio en dos peticiones con TTL de 5 minutos.

Mientras tanto, `cache_read_input_tokens` y `cache_creation_input_tokens` ya se loguean en el
evento `llm_call`: si alguien activa el caching, el ahorro — o su ausencia — se ve en los logs
sin tener que confiar en este documento.
