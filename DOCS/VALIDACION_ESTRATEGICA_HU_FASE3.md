# Validación estratégica HU — Fase 3
## Preparación de evidencia real y protocolo prospectivo

Fecha: 2026-11-15

## 1. Estado inicial verificado

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin modificaciones en live/serving, datos, artefactos, pines ni PR-03.

## 2. Inventario de información disponible

Población:

- Manos totales: 1344.
- Manos fiables: 877.
- Eventos preflop analizados: 4594.
- Acciones preflop registradas: 10403.
- Manos con más de una mano conocida: 336.

Campos disponibles en todas las manos:

| Campo | Cobertura | Semántica observada | Limitación |
|---|---:|---|---|
| `hand_id` | 100% | Identificador de mano | No garantiza unicidad global fuera de la base |
| `date` | 100% | Fecha de la mano | No permite por sí sola separación temporal robusta sin más metadatos |
| `btn_idx`, `btn_player` | 100% | Posición del botón | Dependiente de la codificación de asientos |
| `players` | 100% | Seis asientos con nombre, posición, stack y cartas | La calidad de nombres y cartas varía |
| `comunitarias` | 100% | Cartas comunitarias | Puede requerir normalización |
| `streets` | 100% | Acciones preflop y posteriores | La completitud depende del recorder |
| `final_pot` | 100% | Bote final | No detalla contribuciones intermedias |
| `showdown` | 100% | Ganador registrado | No contiene cartas reveladas de forma estructurada |
| `winner` | 100% | Ganador interno | No equivale a etiqueta estratégica |

Campos de jugador:

| Campo | Cobertura | Observación |
|---|---:|---|
| `active` | 100% | Estado del asiento |
| `name` | 100% | Alias del jugador |
| `pos` | 100% | Posición |
| `stack` | 100% | Stack observado |
| `cards` | 22.9% | Cartas conocidas; 1847 no vacías de 8064 asientos |

La presencia de cartas no implica un showdown completo ni una muestra aleatoria de todas las manos del rival.

## 3. Viabilidad de evidencia para rangos

### 3.1 Rangos observados

Viabilidad: `REQUIERE_NUEVA_EVIDENCIA`.

Motivo:
- Existen 336 manos con más de una mano conocida.
- Las cartas conocidas pueden corresponder a showdowns, pero `showdown` solo registra el ganador, no una lista estructurada de cartas reveladas.
- La muestra está sesgada por showdown y por disponibilidad de cartas.
- No se puede asumir que las manos reveladas representan aleatoriamente todas las manos jugadas por un rival.

### 3.2 Rangos estimados

Viabilidad: `REQUIERE_NUEVA_EVIDENCIA`.

Motivo:
- Los contratos de `EstimatedRange` y `GenericPrior` están aceptados.
- No existe todavía una población con procedencia suficiente para validar rangos estimados frente a showdown de forma reproducible.
- La base actual no contiene la trazabilidad necesaria para reconstruir la distribución real de rangos sin inferencias no demostradas.

### 3.3 Priors genéricos

Viabilidad: `VIABLE_CON_LIMITACIONES`.

Motivo:
- Se pueden usar como hipótesis iniciales.
- No deben presentarse como evidencia específica del rival.
- HU-P4 ya impide que un EV con `GenericPrior` se presente como decisión demostrada.

### 3.4 Frecuencias por jugador

Viabilidad: `VIABLE_CON_LIMITACIONES`.

Motivo:
- Existen alias de jugador y posiciones.
- Las frecuencias agregadas de acciones no equivalen a probabilidades predictivas sin comprobar denominadores y contexto.
- No se debe utilizar `ActionStatistics` como distribución de combos.

## 4. Viabilidad de calibración de respuestas

Se puede reconstruir parcialmente:

- Acciones preflop registradas: 10403.
- Posiciones y acciones por jugador.
- Niveles de apuesta y stacks iniciales.

Bloqueadores:
- No se puede demostrar automáticamente que cada acción tuvo una oportunidad real de fold, call o raise.
- No hay metadatos suficientes para identificar oportunidades de respuesta de forma inequívoca.
- Las frecuencias agregadas no son probabilidades predictivas sin separación temporal y denominadores explícitos.
- La base es dinámica y puede cambiar entre ejecuciones.

Conclusión: calibración de respuestas queda como `REQUIERE_NUEVA_EVIDENCIA`.

## 5. Viabilidad de evaluación de equity

Estado: `REQUIERE_NUEVA_EVIDENCIA`.

Motivo:
- Los contratos de equity (`CurrentBoardStrength`, `EquityToShowdown`) están aceptados.
- La base contiene cartas comunitarias y cartas conocidas en algunos asientos.
- No existe una trazabilidad suficiente para calcular equity condicionada a rangos reales de forma reproducible.
- No se puede inferir cartas ocultas a partir del resultado.

## 6. Viabilidad de evaluación económica

Estado: `VIABLE_CON_LIMITACIONES`.

Motivo:
- Los contratos HU-P3 y HU-P4 están aceptados.
- Existen stacks iniciales, botes finales y acciones.
- Faltan contribuciones intermedias detalladas y una reconstrucción económica completa por mano.
- Los resultados observados no demuestran rentabilidad.
- Los EVs calculados deben mantenerse como expectativas bajo supuestos, no como resultados realizados.

## 7. Sesgos y limitaciones estadísticas

- Sesgo de showdown: las manos con cartas reveladas no representan todas las manos jugadas.
- Sesgo de disponibilidad: solo 22.9% de los asientos tienen cartas conocidas.
- Sesgo de población: la base puede mezclar sesiones, jugadores y contextos.
- Sesgo de recorder: la calidad de acciones y stacks depende del registro.
- Riesgo de fuga temporal si no se separan entrenamiento y evaluación.
- Riesgo de duplicados si no se preserva la identidad de oportunidades.

No se deben normalizar silenciosamente distribuciones incompletas ni usar resultados de manos aisladas como etiquetas de acción correcta.

## 8. Protocolo prospectivo propuesto

Para recopilar evidencia futura sin modificar el recorder ni el pipeline live:

1. Registrar cada oportunidad de decisión con identificador único.
2. Registrar acción realizada, alternativas legales y cantidades.
3. Registrar stacks antes y después de la acción.
4. Registrar cartas conocidas y board.
5. Registrar rango utilizado y su procedencia.
6. Registrar equity y su método.
7. Registrar respuesta rival y su distribución.
8. Registrar resultado económico posterior.
9. Preservar la secuencia temporal para evitar fuga.
10. Separar datos de entrenamiento y evaluación por tiempo o grupo.
11. Conservar casos no evaluables con su causa.
12. No modificar el recorder ni crear writers reales en esta fase.

## 9. Tamaños de muestra y supuestos

No se proponen tamaños universales. Los supuestos son:

- La precisión depende de la varianza de la métrica y del tamaño del estrato.
- Los estratos con pocas observaciones deben declararse insuficientes.
- No se deben duplicar observaciones ni presentar sintéticos como reales.
- La calibración requiere denominadores explícitos y separación temporal.
- Los intervalos de confianza deben conservar su método y su incertidumbre.

Ejemplo orientativo, no vinculante:
- Para estimar una probabilidad con margen aproximado de ±5% al 95%, se requieren del orden de cientos de oportunidades independientes por estrato.
- Para calibración por intervalos, cada intervalo debe tener suficientes observaciones para no ser inestable.

Estos valores son ilustrativos y dependen de la métrica exacta.

## 10. Matriz de viabilidad

| Dimensión | Evidencia actual | Evidencia faltante | Viabilidad | Bloqueador |
|---|---|---|---|---|
| Rangos observados | Cartas parciales en 336 manos | Showdown estructurado y muestreo no sesgado | REQUIERE_NUEVA_EVIDENCIA | Sesgo de showdown |
| Rangos estimados | Contratos aceptados | Población con procedencia suficiente | REQUIERE_NUEVA_EVIDENCIA | Falta trazabilidad |
| Priors genéricos | Disponibles | No aplicable como evidencia específica | VIABLE_CON_LIMITACIONES | No es evidencia rival |
| Respuestas | Acciones registradas | Oportunidades demostrables y denominadores | REQUIERE_NUEVA_EVIDENCIA | Ambigüedad de oportunidad |
| Equity | Contratos aceptados | Rangos y cartas suficientes | REQUIERE_NUEVA_EVIDENCIA | Falta evidencia real |
| EV | Contratos y fixtures aceptados | Stacks, contribuciones y rangos completos | VIABLE_CON_LIMITACIONES | Falta reconstrucción económica |
| Estrategia | Escenarios sintéticos y mecánica | Etiquetas independientes y resultados reales | NO_EVALUABLE | Sin verdad estratégica independiente |

## 11. Recomendación de siguiente etapa

La siguiente etapa debería centrarse en la recopilación y validación de evidencia real, no en ampliar el motor.

Prioridades:
1. Definir el esquema de registro prospectivo de oportunidades de decisión.
2. Validar la calidad de cartas y showdowns disponibles.
3. Construir un piloto pequeño con trazabilidad completa.
4. Calcular rangos y respuestas con denominadores explícitos.
5. Evaluar equity y EV solo cuando existan rangos compatibles.
6. Mantener HU-P4 experimental hasta que la calidad estratégica esté demostrada.

## 12. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección o fase posterior.