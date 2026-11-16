# Validación estratégica HU — Fase 1
## Protocolo, ejecución offline y evaluación independiente

Fecha: 2026-11-15

## 1. Estado inicial verificado

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- Estado Git: cambios locales no commiteados heredados de HU-P1A/HU-P2/HU-P5/HU-P3/HU-P4; sin commits nuevos.
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU ejecutadas: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin modificaciones en live/serving, datos, artefactos, pines ni PR-03.

## 2. Separación de dimensiones

1. Corrección mecánica: contratos, cantidades, secuencias y cálculos.
2. Corrección probabilística: rangos, respuestas, equity e incertidumbre.
3. Corrección económica: EV y comparabilidad.
4. Calidad estratégica: capacidad de distinguir decisiones razonables de deficientes.
5. Rentabilidad: no demostrada en esta fase.

Una acción histórica no se considera automáticamente correcta. Un EV teórico no demuestra rentabilidad.

## 3. Inventario de escenarios HU-P5

### Escenarios reales

| ID | Origen | Mano | Héroe | Modo | Contexto | Tabla principal | Cobertura |
|---|---|---|---|---|---|---|---|
| R01_open_utg | real | H_0001 | UTG | historical | Nadie abrió | OR | complete_exact |
| R02_mp_vs_utg_open | real | H_0001 | MP | historical | Vs apertura UTG | 3B / Call_OR | partial |
| R05_sb_call_limp | real | H_0005 | SB | historical | Vs limp corto | ROL | complete_exact |
| R06_bb_check_after_short_limp | real | H_0012 | BB | historical | Check tras limp corto | ROL | complete_exact |
| R10_sb_open_after_folds | real | H_0066 | SB | historical | Folds previos, apertura SB | OR | complete_exact |
| R18_h0032_bb_vs_sb_3bet | real | H_0032 | BB | historical | 3-bet BB vs SB | 3B / Call_OR | complete_exact |

### Escenarios sintéticos

| ID | Origen | Héroe | Modo | Contexto | Tabla principal | Cobertura |
|---|---|---|---|---|---|---|
| S_open_r | synthetic | UTG | historical | Apertura con `r` | OR | complete_exact |
| S_short_limp_then_raise | synthetic | MP | historical | Limpe corto y subida posterior | ROL | complete_exact |
| S_current_relative_node | synthetic | CO | current, at_index=4 | Nodo relativo sin última acción global | 3B / Call_OR | partial |
| S_no_decision_historical | synthetic | CO | historical | Sin acción voluntaria del héroe | ninguna | no_decision |
| S_unresolved_invalid_raise | synthetic | MP | historical | Subida sin incremento | ninguna | unresolved |

## 4. Protocolo definido antes de ejecutar

Criterios de evaluación:
- Una decisión resuelta debe tener plan y cobertura coherentes.
- Un hueco de cobertura debe declararse, no rellenarse.
- Una decisión sin acción voluntaria del héroe no inventa nodo.
- Una subida sin incremento no produce plan ni rango.
- `GenericPrior` no produce decisión demostrada.
- `ObservedRange` no se convierte en distribución.
- Los EVs no comparables no seleccionan acción demostrada.
- Una rama no evaluable no se convierte en cero ni desaparece.

Resultados esperados:
- Escenarios resueltos: `resolved`.
- Escenario sin decisión: `no_decision`.
- Escenario con subida inválida: `unresolved`.
- Cobertura exacta: `complete_exact`.
- Cobertura con hueco real: `partial`.

## 5. Resultados agregados

- Escenarios ejecutados: 11.
- Escenarios aprobados: 11.
- Escenarios fallidos: 0.
- Escenarios resueltos: 9.
- Escenarios sin decisión: 1.
- Escenarios unresolved: 1.
- Cobertura exacta: 8.
- Cobertura partial: 2.
- Cobertura no aplicable: 1 unresolved + 1 no_decision.

## 6. Resultados por escenario

| ID | Estado | Categoría | Plan | Cobertura | Action ready | Evaluación estratégica |
|---|---|---|---|---|---|---|
| R01_open_utg | resolved | open | OR | complete_exact | sí | Mecánicamente coherente; cobertura exacta |
| R02_mp_vs_utg_open | resolved | call_open | 3B / Call_OR | partial | no | Hueco real de tabla declarado |
| R05_sb_call_limp | resolved | call_limp | ROL | complete_exact | sí | Limp corto reconocido |
| R06_bb_check_after_short_limp | resolved | bb_check | ROL | complete_exact | sí | Check de BB tras limp corto |
| R10_sb_open_after_folds | resolved | open | OR | complete_exact | sí | Apertura SB tras folds |
| R18_h0032_bb_vs_sb_3bet | resolved | 3bet | 3B / Call_OR | complete_exact | sí | 3-bet BB vs SB |
| S_open_r | resolved | open | OR | complete_exact | sí | `r` de apertura no es 3-bet |
| S_short_limp_then_raise | resolved | rol | ROL | complete_exact | sí | ROL tras limp corto |
| S_current_relative_node | resolved | sin decisión directa del héroe | 3B / Call_OR | partial | no | Nodo relativo por `at_index` |
| S_no_decision_historical | no_decision | ninguna | ninguna | none | no | No inventa nodo |
| S_unresolved_invalid_raise | unresolved | ninguna | ninguna | none | no | Subida sin incremento bloqueada |

## 7. Casos numéricos y comparación independiente

Los contratos HU-P3 ya aportaron 9 fixtures de EV con coincidencia exacta. En esta fase se reutilizan como evidencia mecánica, no como prueba de rentabilidad.

Ejemplos reutilizados:
- Call: `0.6 * (14 + 8) - 4 = 9.2`
- All-in desigual: `0.25 * 10 + 0.75 * (0.6 * 16 - 3) = 7.45`
- Bet con raise y abandono: `-5.0`

Estos valores demuestran coherencia aritmética bajo supuestos declarados. No demuestran calidad estratégica.

## 8. Auditoría de resultados

Hallazgos clasificados:
- DEFECTO_MECANICO: 0 nuevos en esta fase.
- DEFECTO_PROBABILISTICO: 0 nuevos en esta fase.
- DEFECTO_ECONOMICO: 0 nuevos en esta fase.
- DEFECTO_ESTRATEGICO: no evaluado con datos suficientes.
- LIMITACION_DE_COBERTURA: R02 presenta hueco real de tabla (`Call_OR_MP_vs_UTG`).
- INFORMACION_INSUFICIENTE: los escenarios HU-P5 no incluyen rangos, equity ni stacks; por tanto no permiten validar calidad estratégica.
- SIN_DEFECTO_REPRODUCIBLE: los 11 escenarios pasan sus expectativas declaradas.

Escenarios no evaluables estratégicamente:
- Todos los escenarios HU-P5 carecen de rangos, equity, respuestas del rival y stacks.
- R02 tiene cobertura partial.
- S_no_decision_historical y S_unresolved_invalid_raise no tienen evaluación económica.

## 9. Limitaciones restantes

- No se han utilizado rangos reales observados o estimados en la evaluación.
- No se han calculado equities condicionadas a respuestas del rival.
- No se han evaluado stacks ni all-ins en los escenarios HU-P5.
- No hay resultados de manos aisladas suficientes para validar rentabilidad.
- No se han comparado decisiones con una verdad estratégica independiente.

## 10. Veredicto estratégico

- VALIDACION_MECANICA: respaldada.
- VALIDACION_PROBABILISTICA: parcial, limitada por ausencia de rangos y equity en los escenarios.
- VALIDACION_ECONOMICA: parcial, limitada a contratos y fixtures numéricos.
- VALIDACION_ESTRATEGICA: no demostrada.

No se declara rentabilidad. No se autoriza producción. HU-P4 permanece experimental.

## 11. Estado final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- Sin commits.
- Sin modificaciones en live/serving, datos, artefactos, pines ni PR-03.

La fase termina aquí. Se requiere autorización explícita para iniciar la siguiente etapa.