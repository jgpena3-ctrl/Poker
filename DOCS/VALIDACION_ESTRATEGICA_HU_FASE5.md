# Validación estratégica HU — Fase 5
## Implementación de un registro prospectivo HU aislado

Fecha: 2026-11-15

## 1. Resumen

Se implementó un prototipo aislado para registrar evidencia prospectiva HU.

Archivos creados:
- `motor/hu_prospective.py`
- `motor/prospective_hu.py`
- `motor/hu_prospective_registry.py`
- `motor/test_hu_prospective.py`

No se modificaron contratos HU aceptados ni código live/serving.

## 2. Arquitectura

El prototipo define dos eventos separados:

- `HU_PREDICTION`: información disponible antes de la decisión y predicción emitida.
- `HU_OUTCOME`: acción observada posterior y resultado.

La predicción se conserva inmutable. El resultado posterior referencia la predicción original mediante `prediction_id`, pero no la modifica.

Persistencia:
- Append-only en JSONL.
- Ruta explícita obligatoria.
- Rechazo de rutas dentro de `data/` o hacia artefactos protegidos.
- Validación antes de escribir.
- Hash canónico SHA-256 por evento.

## 3. Esquema

Predicción:
- `prediction_id`
- `emitted_at`
- `hero_position`
- `canonical_status`
- `coverage_state`
- `sequence_status`
- `range_kind`
- `range_source`
- `range_provenance`
- `response_distribution`
- `equity`
- `equity_scenario`
- `equity_method`
- `action_ev`
- `selected_action`
- `provisional_selected_action`
- `legal_actions`
- `uncertainty_reasons`
- `pot`
- `to_call`
- `hero_stack`
- `villain_stack`
- `hero_contribution_before`
- `villain_contribution_before`
- `board`
- `hero_cards`
- `prior_actions`
- `code_version`
- `data_snapshot_id`
- `assumptions`
- `metadata`

Resultado:
- `outcome_id`
- `prediction_id`
- `observed_at`
- `observed_action`
- `new_information`
- `result`
- `exclusion_reason`
- `notes`

## 4. Validaciones implementadas

- Esquema y versión del evento.
- Identificadores únicos.
- Referencias entre predicción y resultado.
- Orden temporal entre emisión y observación.
- Tipos y dominios de valores.
- Probabilidades válidas y suma igual a 1.
- Valores económicos no negativos.
- Rechazo de datos posteriores en la predicción.
- Rechazo de rutas protegidas.
- Detección de identificadores duplicados.
- Lectura sin modificar bytes.

## 5. Persistencia e inmutabilidad

- Cada evento se escribe como una línea JSON canónica.
- El hash se calcula excluyendo `canonical_hash`.
- Un resultado posterior no modifica la predicción original.
- Los eventos anteriores permanecen intactos al añadir nuevos eventos.
- No se escriben datos históricos ni artefactos existentes.

## 6. Pruebas

`motor/test_hu_prospective.py`: 18 passed.

Casos cubiertos:
1. Registro válido de predicción.
2. Registro válido de resultado posterior.
3. Resultado que referencia predicción inexistente.
4. Identificador duplicado.
5. Intento de sobrescribir una predicción.
6. Timestamp inválido en predicción.
7. Campos ausentes y estados desconocidos.
8. Valores unknown no convertidos.
9. Probabilidades inválidas.
10. Valores económicos incoherentes.
11. Evento malformado.
12. Fallo de escritura sin registro parcial.
13. Integridad de eventos anteriores.
14. Rechazo de rutas protegidas.
15. Reproducción sin modificar bytes.
16. Ausencia de datos posteriores en la predicción.
17. Orden temporal de resultados.
18. Presencia y longitud del hash canónico.

## 7. Conjunto de pruebas

- `motor/test_hu_prospective.py`: 18 passed.
- Conjunto HU incluyendo el nuevo prototipo: 133 passed, 1 xfailed.

## 8. Limitaciones

- No se integra con live, serving, recorder, OCR ni captura.
- No calcula rentabilidad ni calidad estratégica.
- No ejecuta piloto real.
- No gestiona concurrencia entre procesos.
- No sincroniza datos remotos.
- No modifica contratos HU aceptados.

## 9. Riesgos pendientes

- Necesidad de validar la calidad de los registros en un piloto real.
- Riesgo de sesgo de showdown.
- Riesgo de fuga temporal si no se separan correctamente las fases.
- Riesgo de duplicados si no se preserva la identidad de oportunidades.
- Posible necesidad de una versión exacta de código y artefactos para auditoría completa.

## 10. Ejemplo sintético reproducible

Predicción:
- `prediction_id`: `p1`
- `emitted_at`: `2026-01-01T10:00:00`
- `hero_position`: `BTN`
- `canonical_status`: `resolved`

Resultado posterior:
- `outcome_id`: `o1`
- `prediction_id`: `p1`
- `observed_at`: `2026-01-01T10:05:00`
- `observed_action`: `call`

La predicción original no se modifica al registrar el resultado.

## 11. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 133 passed, 1 xfailed.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección o fase posterior.