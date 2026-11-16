# Validación estratégica HU — Fase 4
## Especificación operativa de evaluación prospectiva HU

Fecha: 2026-11-15

## 1. Referencias y estado inicial

Documentos y contratos utilizados:

- `DOCS/VALIDACION_ESTRATEGICA_HU_FASE1.md`
- `DOCS/VALIDACION_ESTRATEGICA_HU_FASE2.md`
- `DOCS/VALIDACION_ESTRATEGICA_HU_FASE3.md`
- `motor/preflop_contract.py`
- `motor/preflop_coverage.py`
- `motor/preflop_canonical.py`
- `motor/hu_range_contracts.py`
- `motor/hu_scenarios.py`
- `motor/hu_ev.py`
- `motor/hu_evaluation.py`

Estado verificado:

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.

Esta fase es exclusivamente documental. No se implementa el protocolo.

## 2. Principio de integridad temporal

Toda predicción se evalúa exclusivamente con la información disponible antes de la decisión.

Reglas:

1. Ningún dato futuro puede aparecer como entrada de una predicción histórica.
2. La acción observada posterior no puede modificar retroactivamente la evaluación.
3. El resultado de la mano no puede usarse como etiqueta de la acción correcta.
4. Una corrección posterior de una mano no puede sobrescribir silenciosamente la evidencia existente al emitir la predicción.
5. Cada predicción debe conservar sus inputs originales, versión del contrato y fecha de emisión.

La ausencia de información no se convierte en cero. Un campo ausente se registra como ausente y se propaga como incertidumbre.

## 3. Esquema conceptual de registro

### 3.1 Identidad y temporalidad

- `observation_id`: identificador único de la observación.
- `hand_id`: identificador de la mano.
- `decision_timestamp`: fecha y hora de la decisión.
- `prediction_version`: versión de los contratos y parámetros usados.
- `data_snapshot_id`: identificación del snapshot de datos disponible en ese momento.

### 3.2 Contexto de decisión

- `hero_position`
- `villain_positions`
- `street`
- `board_known`
- `hero_cards_known`
- `villain_cards_known`, si estuvieran disponibles por showdown o revelación
- `prior_actions`
- `current_bet`
- `pot_before_decision`
- `hero_stack_before`
- `villain_stack_before`
- `hero_contribution_before`
- `villain_contribution_before`
- `legal_actions`

### 3.3 Evaluación emitida

- `canonical_status`
- `coverage_state`
- `range_kind`
- `range_source`
- `range_provenance`
- `equity`
- `equity_scenario`
- `response_distribution`
- `response_equities`
- `action_ev`
- `comparability`
- `selection_status`
- `best_action`
- `provisional_best_action`
- `uncertainty_reasons`

### 3.4 Información posterior

- `observed_action`
- `observed_result`
- `showdown_cards`, si estuvieran disponibles
- `final_pot`
- `final_stacks`
- `exclusion_reason`, si la observación no es evaluable

### 3.5 Separación de fases

1. Información disponible antes de la decisión.
2. Predicciones emitidas por el motor.
3. Información observada después de la decisión.
4. Resultados posteriores.

Ningún campo de las fases 3 o 4 puede usarse como entrada de las fases 1 o 2.

## 4. Unidades de observación y denominadores

### 4.1 Rangos

- Unidad válida: una oportunidad de decisión con rango disponible y procedencia identificable.
- Denominador: número de oportunidades con rango compatible.
- Exclusiones: rango ausente, rango incompatible, cartas conocidas incoherentes, procedencia no demostrable.
- Observaciones repetidas: deben identificarse por jugador, posición, contexto y fecha para evitar dependencia oculta.

### 4.2 Probabilidades de respuesta

- Unidad válida: una oportunidad real de fold, call o raise.
- Denominador: número de oportunidades demostrables de esa acción en el contexto definido.
- Exclusiones: oportunidad no demostrable, acción ambigua, tamaño de apuesta no comparable, datos incompletos.
- No usar el total de acciones como denominador de oportunidades de respuesta.
- No convertir frecuencias agregadas en probabilidades predictivas sin comprobar población y contexto.

### 4.3 Equity

- Unidad válida: una evaluación con rango utilizable y escenario compatible.
- Denominador: número de evaluaciones con equity calculable.
- Exclusiones: rango no utilizable, equity incompatible, cartas conocidas incoherentes, cobertura insuficiente.
- La equity debe conservar su método, muestras y definición.

### 4.4 EV

- Unidad válida: una evaluación con acciones legales, EVs comparables y supuestos compatibles.
- Denominador: número de evaluaciones con al menos una acción evaluable.
- Exclusiones: EV incomparable, rama no evaluable, secuencia no resuelta, cobertura insuficiente.

### 4.5 Decisiones estratégicas

- Unidad válida: una evaluación con mejor acción demostrable.
- Denominador: número de evaluaciones con `selection_status=demonstrated`.
- Exclusiones: evaluaciones provisionales, sin acción justificable, con incertidumbre no resuelta o con supuestos incompatibles.
- Una acción histórica no constituye automáticamente una decisión correcta.

## 5. Controles contra sesgos y fugas

### 5.1 Duplicados

- Cada observación debe tener `observation_id` único.
- Detectar duplicados por mano, fecha, posición, acción y contexto.
- Los duplicados no se eliminan silenciosamente: se registran y excluyen del denominador con motivo.

### 5.2 Separación temporal

- Separar desarrollo, calibración y evaluación por tiempo o por grupos.
- No usar datos futuros para entrenar o calibrar modelos evaluados en el pasado.
- Registrar la fecha de cada predicción y de cada observación.

### 5.3 Fuga de información

- Bloquear cualquier campo posterior a la decisión en las entradas de predicción.
- Verificar que las cartas ocultas no se utilicen antes de su revelación.
- Verificar que el resultado de la mano no se use como entrada.

### 5.4 Cambios de población

- Registrar jugador, posición, contexto y condiciones de juego.
- Detectar cambios de población, rivales o parámetros.
- No mezclar poblaciones sin documentarlo.

### 5.5 Sesgo de showdown

- Las manos que llegan a showdown no representan todas las manos jugadas.
- Las cartas reveladas solo son válidas para el subconjunto que llegó a showdown.
- No inferir cartas ocultas a partir del resultado.

### 5.6 Sesgo de disponibilidad

- Registrar la disponibilidad de stacks, cartas y acciones.
- No convertir campos ausentes en cero.
- Documentar el impacto de la disponibilidad parcial.

### 5.7 Versiones y correcciones

- Conservar la versión de cada predicción.
- Si una mano se corrige posteriormente, la predicción original debe seguir auditando la decisión emitida en su momento.
- No sobrescribir silenciosamente evidencia histórica.

## 6. Plan estadístico

### 6.1 Métricas aplicables

- Brier score para probabilidades de respuesta, cuando exista predicción previa válida.
- Log loss solo cuando las probabilidades sean válidas y los ceros se traten explícitamente.
- Calibración por intervalos.
- Error de equity frente a referencias independientes válidas.
- Sensibilidad del EV a equity, probabilidades, stacks y tamaños.
- Intervalos de confianza cuando el método esté definido.

### 6.2 Dependencia entre observaciones

- Las manos de un mismo jugador o sesión pueden estar correlacionadas.
- Los intervalos de confianza deben considerar la dependencia o declararla como limitación.
- No tratar observaciones correlacionadas como independientes sin justificación.

### 6.3 Muestras insuficientes

- Si un estrato tiene pocas observaciones, declararlo insuficiente.
- No duplicar observaciones.
- No presentar sintéticos como reales.
- No fabricar métricas con datos insuficientes.

### 6.4 Tamaños de muestra

No se establecen umbrales universales arbitrarios. Los tamaños deben derivarse de:

- Precisión pretendida.
- Variabilidad esperada.
- Dependencia entre observaciones.
- Tamaño del estrato.
- Método de intervalo.

Si estos parámetros no están disponibles, documentar qué falta para calcularlos.

## 7. Matriz de aceptación

| Dimensión | Evidencia necesaria | Métrica | Exclusiones | Limitación | Criterio para avanzar | Criterio para detenerse |
|---|---|---|---|---|---|---|
| Integridad del registro | Campos completos y trazables | Cobertura de campos | Campos ausentes o ambiguos | Recorder incompleto | Registro consistente | Fuga temporal o datos alterados |
| Representatividad | Muestra estratificada | Tamaño por estrato | Duplicados y sesgos | Sesgo de showdown | Estratos documentados | Muestra no representativa |
| Calidad de rangos | Procedencia y método | Coherencia de blockers | Rangos incompatibles | Observaciones sesgadas | Rango compatible | Rango presentado como evidencia sin procedencia |
| Calibración de respuestas | Predicciones previas y oportunidades demostrables | Brier, log loss, calibración por intervalos | Probabilidades inválidas | Denominadores insuficientes | Probabilidades válidas y calibradas | Fuga o etiquetas retrospectivas |
| Precisión de equity | Rango y escenario compatibles | Error frente a referencia independiente | Equity incompatible | Muestreo insuficiente | Equity trazable | Reutilización indebida |
| Fiabilidad de EV | EVs comparables y supuestos compatibles | Diferencia frente a referencia independiente | EVs incomparables | Información insuficiente | Comparación demostrable | Unknown convertido en cero |
| Calidad estratégica | Referencias independientes y resultados reproducibles | Coherencia de decisiones | Acciones históricas usadas como verdad | Sin etiquetas independientes | Decisión justificable | Rentabilidad declarada sin evidencia |

El éxito en una dimensión no implica validación de las demás.

## 8. Diseño del piloto, sin ejecutarlo

### 8.1 Población y contextos

- Limitar a HU.
- Seleccionar contextos con información económica suficiente.
- Incluir aperturas, respuestas a apertura, limpes y all-ins.
- Incluir casos de cobertura exacta, alias, gap e impossible.

### 8.2 Procedimiento

1. Registrar la predicción antes de la acción.
2. Registrar la acción observada posteriormente.
3. Registrar el resultado solo después de la acción.
4. Conservar versión, inputs y supuestos.
5. Excluir observaciones incompletas con motivo.
6. Revisar calidad de los registros antes del análisis.

### 8.3 Campos obligatorios

- Identificador de observación.
- Fecha y hora.
- Posición del héroe.
- Board conocido.
- Cartas del héroe.
- Acciones anteriores.
- Pot y stacks.
- Acción recomendada.
- Alternativas evaluadas.
- Cobertura y procedencia.
- EV por acción.
- Estado de comparabilidad.

### 8.4 Tratamiento de manos no evaluables

- Registrar la causa de exclusión.
- No descartarlas silenciosamente.
- No convertir unknown en cero.
- Mantenerlas en el denominador cuando corresponda a la métrica.

### 8.5 Condiciones de cierre del piloto

El piloto se considera cerrado cuando:
- Los registros son completos y auditables.
- Las predicciones se emitieron antes de los resultados.
- Las exclusiones están documentadas.
- Las métricas pueden recalcularse de forma independiente.
- No se detectó fuga temporal.

El piloto no autoriza producción ni validación estratégica.

## 9. Riesgos y cuestiones pendientes

- Sesgo de showdown.
- Sesgo de disponibilidad de cartas.
- Sesgo de población y recorder.
- Fuga temporal.
- Duplicados.
- Cambios manuales posteriores en datos históricos.
- Insuficiencia de denominadores.
- Dependencia entre observaciones.
- Confusión entre resultado observado y expectativa previa.

## 10. Recomendación de la siguiente fase

La siguiente fase debería ser un piloto documental y read-only, sin modificar el recorder ni el pipeline live.

Prioridades:
1. Validar la calidad de los registros disponibles.
2. Definir el esquema final de observación.
3. Estimar denominadores por estrato.
4. Calcular rangos y respuestas con procedencia.
5. Evaluar equity y EV solo con datos compatibles.
6. Mantener HU-P4 experimental hasta que la calidad estratégica esté demostrada.

## 11. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 115 passed, 1 xfailed.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.
- No se modificó código ni se crearon writers.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección o fase posterior.