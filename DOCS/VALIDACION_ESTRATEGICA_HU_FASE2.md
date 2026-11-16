# Validación estratégica HU — Fase 2
## Ampliación de escenarios, evaluación probabilística y referencias independientes

Fecha: 2026-11-15

## 1. Estado inicial verificado

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU ejecutadas: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin modificaciones en live/serving, datos, artefactos, pines ni PR-03.

## 2. Población disponible

Fuente: `data/hands_db.jsonl`, filtrada por fiabilidad.

- Manos totales: 1344.
- Manos fiables: 877.
- Eventos preflop analizados en la suite histórica: 4594.
- Posiciones disponibles en eventos fiables:
  - UTG: 457
  - MP: 741
  - CO: 861
  - BTN: 877
  - SB: 852
  - BB: 806

No se modificó la base ni se generaron muestras artificiales.

## 3. Escenarios HU-P5 existentes

Se reutilizaron los 11 escenarios autorizados:

- 6 reales.
- 5 sintéticos.

Resultado de la ejecución:
- 11 aprobados.
- 9 decisiones resueltas.
- 1 sin acción voluntaria del héroe.
- 1 unresolved por subida inválida.
- 8 coberturas exactas.
- 2 coberturas partial.

Los escenarios HU-P5 no contienen rangos, equity, stacks ni respuestas del rival. Por tanto, sirven para validar mecánica, cobertura y secuencia, pero no permiten validar calidad estratégica por sí solos.

## 4. Matriz estratificada ampliada

Se amplió la evaluación mediante los escenarios sintéticos controlados ya existentes y los fixtures numéricos aprobados en HU-P3/HU-P4.

### Estratos cubiertos

| Estrato | Cobertura actual | Limitación |
|---|---|---|
| Apertura preflop | Sí | Escenarios HU-P5 y sintéticos |
| Respuesta a apertura | Sí | R02, S_current_relative_node |
| Limpe corto | Sí | R05, S_short_limp_then_raise |
| Check de BB | Sí | R06 |
| Apertura tras folds | Sí | R10 |
| 3-bet | Sí | R18 |
| Cobertura exacta | Sí | 8 escenarios |
| Cobertura partial | Sí | R02, S_current_relative_node |
| Sin decisión del héroe | Sí | S_no_decision_historical |
| Subida inválida | Sí | S_unresolved_invalid_raise |
| Nodo relativo por `at_index` | Sí | S_current_relative_node |
| Fold / call / raise en EV | Sí | Fixtures HU-P3 |
| All-in igual y desigual | Sí | Fixtures HU-P3/HU-P4 |
| Rival all-in con contribución previa | Sí | Fixtures HU-P3/HU-P4 |
| Rangos observados vs estimados | Parcial | Contratos aprobados, sin flujo real completo |
| Probabilidades de respuesta | Parcial | Fixtures sintéticos |
| Equity condicionada | Parcial | Compatibilidad verificada, no cálculo automático completo |
| Calibración estadística | No | Sin denominadores suficientes en esta fase |

### Estratos insuficientes

- No existe una muestra real estratificada de decisiones HU con rangos, equity, stacks y respuestas rival.
- No hay suficientes observaciones por estrato para afirmar calibración estadística.
- No hay etiquetas de acción óptima independientes.

## 5. Separación real / sintético

### Reales
- 6 escenarios HU-P5.
- Derivados de manos reales, pero recortados y reproducibles.
- No se modificaron sus registros.
- No se usan resultados de manos aisladas como verdad estratégica.

### Sintéticos
- 5 escenarios HU-P5.
- Fixtures HU-P3 y HU-P4.
- Casos controlados con EV calculable manualmente.
- Incluyen casos favorables y adversos para el motor.

No se presentaron escenarios sintéticos como manos reales.

## 6. Referencias matemáticas independientes

Se reutilizaron las referencias aprobadas de HU-P3 y HU-P4, aplicadas directamente y no como oráculo del helper bajo prueba.

Casos verificados:
- Fold: `0`
- Check: `equity * pot`
- Call: `equity * (pot + 2 * to_call) - to_call`
- Bet con fold del rival: `pf * pot`
- Bet con call del rival: `pc * (equity * (pot + 2 * amount) - amount)`
- Bet con raise y abandono: `pr * (-amount)`
- All-in: `pf * pot + (pc + pr) * (equity * (pot + 2 * amount) - amount)`

Casos all-in verificados:
- Rival all-in con contribución previa: EV = 9.2.
- Stack efectivo menor: EV = 7.45.
- Héroe no puede igualar completo: EV = 6.6.
- Exceso no contestado: EV = 7.45.

Todos los resultados coincidieron con `calculate_ev()`.

## 7. Evaluación probabilística

### Rangos

Se verificó la separación de procedencias:
- `ObservedRange`: no se convierte en distribución.
- `EstimatedRange`: conserva posterior, método y procedencia.
- `ActionStatistics`: no se interpreta como distribución de combos.
- `GenericPrior`: permanece identificado como prior y no produce decisión demostrada.

### Probabilidades de respuesta

Se comprobó:
- Validez de probabilidades.
- Suma igual a uno para distribuciones completas.
- Rechazo de probabilidades inválidas.
- Propagación de `unknown` cuando falta información.
- Precedencia de equity calculada sobre equity declarada.
- Mismatch de equity detectado y bloqueado.

No se afirmó calibración estadística porque no hay denominadores suficientes ni separación temporal aplicable en esta muestra.

## 8. Sensibilidad y estabilidad

Se evaluaron variaciones controladas de:
- Equity.
- Probabilidades de fold, call y raise.
- Tamaño de apuesta.
- Pot.
- Stack efectivo.
- Procedencia de rango.
- Cobertura.

Resultados:
- Pequeñas variaciones producen cambios razonables en EV.
- Las discontinuidades se explican por cambios de legalidad de acciones o de cobertura.
- Una acción puede cambiar de preferible a no preferible al variar la equity o la respuesta rival.
- La evaluación se vuelve `provisional` cuando la incertidumbre impide comparar.
- Las acciones ilegales quedan excluidas.
- Una rama no evaluable no se convierte en cero.

No se ajustaron parámetros para mejorar resultados.

## 9. Clasificación de hallazgos

| ID | Tipo | Escenario / área | Evidencia | Impacto | Severidad |
|---|---|---|---|---|---|
| F2-001 | LIMITACION_DE_COBERTURA | R02 | `Call_OR_MP_vs_UTG` ausente | Acción no evaluable | Media |
| F2-002 | INFORMACION_INSUFICIENTE | Todos los escenarios HU-P5 | Sin rangos, equity, stacks ni respuestas rival | No valida calidad estratégica | Alta |
| F2-003 | INFORMACION_INSUFICIENTE | Estratos reales | Sin muestra estratificada suficiente | No hay calibración estadística | Alta |
| F2-004 | LIMITACION_DE_COBERTURA | HU-P4 | Equity condicionada calculada solo si existe rango compatible | Ramas pueden quedar unknown | Media |
| F2-005 | LIMITACION_DE_COBERTURA | HU-P4 | Sin bote lateral ni multiway | Escenarios HU complejos no representados | Baja |

No se encontraron defectos mecánicos, probabilísticos ni económicos nuevos.

No se corrigió ningún defecto durante esta fase.

## 10. Limitaciones y estratos insuficientes

- No hay etiquetas de acción óptima independientes.
- No hay resultados de manos aisladas suficientes para validar rentabilidad.
- Los escenarios HU-P5 no incluyen información económica.
- La muestra real es limitada y no permite calibración por intervalos.
- No se utilizaron simulaciones Monte Carlo en esta fase.

## 11. Veredicto por dimensión

- VALIDACION_MECANICA: respaldada.
- VALIDACION_PROBABILISTICA: parcial.
- VALIDACION_ECONOMICA: parcial.
- VALIDACION_ESTRATEGICA: no demostrada.

No se declara rentabilidad ni se autoriza producción.

## 12. Recomendaciones de siguiente etapa, sin ejecutarlas

1. Construir una muestra HU estratificada con rangos, equity, stacks y respuestas rival.
2. Calcular equities condicionadas automáticamente a partir de rangos compatibles.
3. Añadir referencias estratégicas independientes para escenarios controlados.
4. Medir calibración solo cuando existan denominadores suficientes y separación temporal.
5. Mantener HU-P4 experimental hasta que la calidad estratégica esté demostrada.

## 13. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección o fase posterior.