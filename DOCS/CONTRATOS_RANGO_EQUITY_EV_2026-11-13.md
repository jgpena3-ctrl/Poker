# Contratos de rango, equity y EV (2026-11-13)

**Estado:** diseño. No implementa modelos, no modifica `motor/`, no escribe `data/` y no activa multiway.

**Objetivo:** separar observaciones, rangos estimados, priors, equity y EV para mejorar HU sin mezclar objetos, fuentes de evidencia ni resultados de simulación.

Este documento define contratos conceptuales y sus invariantes. No certifica que las implementaciones actuales los cumplan ni autoriza migraciones de serving.

---

## 1. Objetos y relaciones

```text
Acciones y cartas observadas
        │
        ├──> ObservedRange
        │      Combos efectivamente revelados
        │
        ├──> ActionStatistics
        │      Frecuencias observadas con denominadores
        │
        └──> EstimatedRange
               Distribución estimada sobre combos
                    ▲
                    │
              GenericPrior
              Prior genérico o de tabla

Board + mano del héroe + rango + blockers
        │
        ├──> CurrentBoardStrength
        │      Fuerza de la mano en el board existente
        │
        └──> EquityToShowdown
               Equity considerando runouts futuros

Acción + creencias + modelo de respuesta + árbol
        │
        └──> EvByAction
               Valor esperado de cada acción
```

Los objetos no se convierten entre sí sin una transformación declarada y trazable.

Distinciones obligatorias:

- Ver una mano revelada no equivale a observar un rango completo.
- Una frecuencia histórica no equivale a una probabilidad calibrada.
- Un prior no equivale a una observación del rival.
- Una distribución estimada no equivale a una lista de manos conocidas.
- La fuerza actual de una mano no equivale a su equity al showdown.
- La equity no equivale al EV de una acción.
- El EV calculado bajo un modelo no demuestra que ese modelo sea correcto.

---

## 2. `ObservedRange`

**Definición:** conjunto de combos efectivamente revelados y observados en una mano o conjunto de manos. No es una distribución de probabilidad.

```text
ObservedRange:
    player
    street
    board
    observations:
        - hand_id
        - exact_combo
        - reveal_source
        - reveal_event
        - data_snapshot_hash
    coverage
    source_window
```

Reglas:

1. Solo se incluyen combos cuyas cartas hayan sido efectivamente reveladas y cuya procedencia pueda identificarse.
2. Un fold sin cartas reveladas no proporciona un combo observado.
3. Una acción como call, raise o fold no revela por sí sola las cartas del jugador.
4. El conjunto no representa todas las manos posibles del rival.
5. No se normaliza a 100 % como si fuera un rango completo.
6. No se usa directamente como distribución de un rival en live.
7. Las observaciones repetidas deben conservar su identidad por mano. No se confunden varias apariciones del mismo combo con varios combos distintos.
8. Un `coverage_gap` de tabla no crea ni elimina observaciones.
9. Si la fuente no permite conocer las cartas, el resultado es ausencia de observación, no un combo desconocido convertido en cero.

Las frecuencias de acciones por posición y categoría son `ActionStatistics`, no `ObservedRange`. No se derivan combos observados a partir de frecuencias de acción.
`ObservedRange` puede alimentar estadísticas o estimaciones, pero cualquier transformación debe declarar filtros, selección de manos y sesgos de observación.

---

## 3. `ActionStatistics`

**Definición:** agregados de acciones observadas con denominadores y filtros explícitos.

```text
ActionStatistics:
    player_scope
    spot_definition
    action
    numerator
    denominator
    frequency
    filters
    source_window
    data_snapshot_hash
    confidence_interval
    method
```

Reglas:

1. Toda frecuencia debe tener numerador y denominador reproducibles.
2. El denominador representa oportunidades comparables, no todas las manos del jugador.
3. Los filtros de posición, stack, formato, secuencia y acción previa deben declararse.
4. Una acción no observada no se interpreta automáticamente como una acción que no ocurrió.
5. No se mezclan ventanas, formatos o definiciones de spot diferentes sin declarar la transformación.
6. Las observaciones de una misma sesión o jugador pueden estar correlacionadas. Los intervalos deben respetar la unidad de agrupación pertinente.
7. Una frecuencia observada no es automáticamente una predicción calibrada de la próxima acción.
8. Una frecuencia con cobertura insuficiente no se convierte en una frecuencia exacta por tener muchos registros.

Las frecuencias de acciones por posición y categoría no son combos observados. No deben usarse como `ObservedRange`.
---

## 4. `EstimatedRange`

**Definición:** distribución estimada sobre combos posibles, condicionada por la información disponible y por un modelo explícito.

```text
EstimatedRange:
    player
    street
    board
    combo_space
    prior_id
    likelihood_model
    unnormalized_weights
    posterior
    reach
    n_obs
    n_opp
    n_eff
    coverage
    empty_status
    model_version
    data_snapshot_hash
```

**Compatibilidad parcial:** mientras no se demuestre que sus campos y su semántica satisfacen el contrato aprobado, `EstimatedRange` se clasifica como compatibilidad parcial, no como completamente compatible.

### 4.1 Construcción de pesos
Para cada combo legal \(i\):

\[
w_i = \pi_i \cdot L_i
\]

Donde:

- \(\pi_i\) es la masa del prior para el combo.
- \(L_i\) es la verosimilitud de la secuencia observada bajo el modelo, incluyendo las acciones relevantes.
- \(w_i\) es el peso no normalizado resultante.

Si:

\[
\sum_i w_i > 0
\]

la distribución posterior se normaliza:

\[
p_i = \frac{w_i}{\sum_j w_j}
\]

Si:

\[
\sum_i w_i = 0
\]

el resultado es `empty` o `unsupported`, según la causa. No se crea una distribución artificial.

### 4.2 Reach

`reach` describe la probabilidad o peso de que un combo llegue al nodo observado bajo la secuencia modelada.

Debe declararse cómo se obtiene:

- likelihood de las acciones;
- probabilidad de supervivencia hasta el nodo;
- modelo de selección;
- o una aproximación explícita.

**No se multiplica nuevamente por `reach` si ese efecto ya está incluido en `L_i`.**

Si se conserva como campo separado, debe indicarse si es:
- un componente de la verosimilitud;
- un diagnóstico;
- o un factor independiente que todavía no se ha incorporado a los pesos.

No se permite aplicar dos veces el mismo efecto.

### 4.3 Reglas

1. Solo se incluyen combos legales respecto a cartas conocidas, board y dead cards.
2. Los blockers se aplican antes de normalizar la distribución.
3. Un combo imposible recibe masa cero por una razón identificable; no por ausencia de datos.
4. Un rango vacío no es una distribución nula ni una predicción de que el rival no tiene manos.
5. `empty` debe llevar `empty_reason`.
6. Un rango `unknown` no se convierte en un rango vacío.
7. `n_obs` y `n_opp` describen observaciones y oportunidades según una definición explícita.
8. `n_eff` no es el número de manos observadas.
9. Un rango estimado no se presenta como “las manos que tiene el rival” sin identificar modelo, fuente, cobertura e incertidumbre.
10. Un rango construido con prior y poca evidencia debe seguir identificándose como fuertemente dependiente del prior.

### 4.4 Tamaño efectivo

Cuando los pesos representen contribuciones ponderadas de observaciones comparables, puede utilizarse:

\[
n_{\mathrm{eff}} =
\frac{(\sum_i w_i)^2}{\sum_i w_i^2}
\]

La interpretación depende de cómo se construyeron los pesos.

No se presenta `n_eff` como muestra observacional ni se usa automáticamente como denominador de una frecuencia histórica.

Si los pesos representan masas de combos de un prior y no pesos de observaciones, `n_eff` puede describir concentración, pero no tamaño de muestra estadística.

---

## 5. `GenericPrior`

**Definición:** distribución inicial o genérica para un spot, sin atribuirla como observación individual del rival.

```text
GenericPrior:
    key
    combo_space
    vector
    source:
        flat
        preflop_table
        profile_template
        alias
        prior_fallback
    coverage
    alias_of
    fallback_key
    provenance
    version
    data_snapshot_hash
```

Reglas:

1. `FLAT_PRIOR` es un prior, no una estimación observada del rival.
2. Un prior de tabla puede tener cobertura `exact`, `alias` o `coverage_gap`.
3. Un alias debe declarar su origen y regla de equivalencia.
4. Un `coverage_gap` no se imputa con `FLAT_PRIOR` en silencio.
5. Si se utiliza un prior alternativo, el resultado declara `prior_fallback`, su fuente y el motivo.
6. Un prior no se presenta como una frecuencia observada.
7. Un prior no se calibra con información posterior a la decisión evaluada.
8. Un prior no se ajusta utilizando la misma mano que después se presenta como evaluación independiente.
9. Un vector vacío no se sustituye por una distribución uniforme sin declararlo como fallback.
10. La normalización del vector no demuestra que el prior sea representativo o calibrado.

Los priors deben distinguir masa por combo, cobertura de la tabla y procedencia. No se utiliza un único campo `n` para representar indistintamente tamaño de muestra, oportunidades y masa de distribución.

---

## 6. Blockers y legalidad de combos

Los blockers forman parte de la construcción del espacio de combos y deben aplicarse antes de calcular equity.

Entradas mínimas:

```text
KnownCards:
    hero_hand
    board
    dead_cards
    known_opponent_cards
```

Reglas:

1. No puede existir una carta repetida entre manos, board y dead cards.
2. Los combos incompatibles se eliminan o reciben masa cero con motivo explícito.
3. La distribución restante se renormaliza solo si conserva masa positiva.
4. Si no queda masa válida, el rango pasa a `empty` o `unsupported`; no se inventa una distribución.
5. En multiway, los blockers son conjuntos compartidos. No se pueden aplicar de forma independiente a cada rival y después asumir que las distribuciones resultantes son una distribución conjunta válida.
6. La independencia entre rivales es una hipótesis de modelo, no una consecuencia automática de tener rangos individuales.

---

## 7. `CurrentBoardStrength`

**Definición:** evaluación de la fuerza de una mano en el board existente, sin considerar runouts futuros.

Este objeto no es la equity de showdown.

```text
CurrentBoardStrength:
    hero_hand
    board
    opponent_range
    method
    result_definition
    value
    coverage
    evaluator_version
```

El campo `result_definition` debe identificar qué se está midiendo, por ejemplo:

- categoría de mano actual;
- fuerza relativa frente a un rango en el board actual;
- proporción de combos rivales que están por detrás, empatados o por delante en ese momento.

Reglas:

1. No se interpreta como probabilidad de ganar al showdown.
2. No incluye cartas futuras.
3. No se utiliza como sustituto de equity para justificar una acción futura.
4. Debe declarar la definición de fuerza utilizada.
5. Debe respetar blockers y combos legales.
6. Si el rango está vacío o no es utilizable, el resultado es `unknown`, no cero.

---

## 8. `EquityToShowdown`

**Definición:** participación esperada del héroe en el resultado de showdown, condicionada por las cartas conocidas, el board actual y los rangos o creencias utilizados.

La equity considera los runouts futuros posibles hasta el showdown. En all-in, puede calcularse sin decisiones futuras pendientes; si todavía hay decisiones, debe declararse que la equity no representa por sí sola el valor de una política completa.

```text
EquityToShowdown:
    hero_hand
    board
    opponent_ranges
    dead_cards
    method:
        exact
        monte_carlo
    equity_share
    win_probability
    tie_probability
    lose_probability
    n_combos
    n_runouts
    n_samples
    seed
    ci_low
    ci_high
    coverage
    range_provenance
    equity_version
```

### 8.1 Definición de equity

La equity debe representar la participación esperada en el bote elegible, considerando victorias y empates.

En un caso simple de un único bote:

\[
Equity = P(win) + \frac{P(tie)}{2}
\]

En escenarios con varios jugadores, side pots o distintos derechos de elegibilidad, la participación debe calcularse según las reglas del bote correspondiente. No se aplica automáticamente la fórmula HU a un bote multiway.

### 8.2 Métodos

- `exact`: enumeración completa del espacio válido.
- `monte_carlo`: muestreo de combos y/o runouts.

La elección del método debe responder al tamaño del espacio y al presupuesto de cómputo.

### 8.3 Reglas

1. `n_combos`, `n_runouts` y `n_samples` son cantidades distintas.
2. No se intercambian ni se presentan como si midieran el mismo volumen.
3. En MC se declara semilla, método de muestreo e intervalo.
4. En cálculo exacto, la incertidumbre de muestreo no aplica; sí puede existir incertidumbre por el rango o modelo de respuesta.
5. Los empates se reparten conforme al número de jugadores y a la elegibilidad del bote.
6. Board y dead cards son entradas explícitas.
7. Mismo método, mismas entradas, mismo orden de enumeración y misma versión deben producir resultados reproducibles.
8. Rango vacío o no utilizable produce `unknown` o `unsupported`, nunca `0.0`.
9. Un `fallback_other_vs` conserva `coverage_gap` y la etiqueta de fallback.
10. Una equity calculada con un prior no se presenta como equity basada en observaciones individuales.
11. Una equity multiway requiere rangos compatibles y tratamiento conjunto de blockers.
12. No se utiliza `RangeState.union()` como sustituto de una distribución conjunta de manos rivales.
13. Las hipótesis de independencia, correlación o dependencia entre rivales se declaran y comparan como modelos distintos.

### 8.4 Nombre histórico `CurrentEquity`

Si una implementación existente utiliza `CurrentEquity`, el nombre no autoriza a calcular solo la fuerza de la mano en el board actual.

En el contrato nuevo:
- `CurrentBoardStrength` representa fuerza sin runouts.
- `EquityToShowdown` representa equity con runouts.

Cualquier adaptador desde `CurrentEquity` debe declarar cuál de esos dos objetos estaba calculando realmente. No se renombra ni interpreta por intuición.

---

## 9. Side pots y elegibilidad

Cuando existen all-ins o stacks distintos, el cálculo debe distinguir los botes y los jugadores elegibles.

```text
PotEligibility:
    pot_id
    amount
    eligible_players
    contribution_levels
    odd_chip_rule
```

Reglas:

1. La equity y el EV se calculan por bote cuando las contribuciones generan side pots.
2. Un jugador no elegible no recibe participación en ese bote.
3. Los empates se resuelven dentro del conjunto de jugadores elegibles.
4. Los odd chips siguen la regla de la sala o del formato declarado.
5. No se asigna todo el bote principal a todos los jugadores por defecto.
6. Los importes comprometidos previamente se distinguen de los importes adicionales que una acción todavía puede ganar o perder.
7. El contrato debe identificar si el resultado es equity de un bote específico, equity agregada ponderada o valor esperado de cobro.

---

## 10. `EvByAction`

**Definición:** valor esperado de una acción bajo un modelo declarado de creencias, respuestas rivales, árbol de juego y estructura de pagos.

```text
EvByAction:
    action
    ev
    ev_reference_node
    unit
    method
    response_model
    beliefs
    action_tree
    tree_depth
    terminal_conditions
    pot_structure
    side_pots
    n_samples
    seed
    ci_low
    ci_high
    coverage
    range_provenance
    model_version
    ev_version
```

### 10.1 Requisitos

1. Sin creencias declaradas no hay EV válido.
2. Sin modelo de respuesta no hay EV completo de una subida.
3. Si se utiliza un rival genérico, debe declararse como prior y no como observación.
4. El EV debe especificar el nodo de referencia y la unidad utilizada.
5. Las inversiones ya realizadas se tratan de manera coherente. No se vuelven a contar como coste futuro de la acción.
6. El EV de fold suele ser cero respecto al nodo actual porque las inversiones anteriores son costes hundidos. Esto no significa que el jugador recupere lo invertido.
7. El EV de call considera el coste adicional, el bote elegible y la distribución de resultados.
8. El EV de raise debe modelar las respuestas posibles: fold, call y nuevas subidas cuando sean legales y relevantes.
9. No se aproxima el EV de raise exclusivamente con fold equity y equity cuando pagan si se omiten ramas materiales del árbol.
10. El EV de check puede requerir modelar calles posteriores y respuestas rivales.
11. Si el árbol está truncado, se declara `tree_depth` y las condiciones de truncamiento.
12. Un EV truncado no se presenta como solución completa.
13. Un EV con `coverage_gap` no se compara como equivalente a otro con cobertura exacta.
14. No se elige una acción por el EV de una sola muestra sin analizar incertidumbre y sensibilidad.
15. Si varias acciones tienen intervalos muy solapados o dependen de supuestos débiles, se declara la ambigüedad.
16. El resultado de un modelo de EV no demuestra por sí solo que la política sea estratégicamente correcta.

### 10.2 Comparabilidad

Dos EV solo son comparables si coinciden, o se ha justificado la diferencia, en:

- nodo de referencia;
- unidad;
- estructura de bote;
- stacks y elegibilidad;
- creencias;
- modelo de respuesta;
- profundidad y condiciones terminales;
- método de cálculo;
- cobertura y procedencia.

No se compara un EV de una acción con una equity como si fueran la misma magnitud.

---

## 11. Incertidumbre y confianza

No existe un único `confidence_score` que resuma correctamente todas las fuentes de incertidumbre.

Se reportan componentes independientes:

```text
uncertainty:
    coverage
    n_obs
    n_opp
    n_eff
    n_combos
    n_runouts
    n_samples
    ci_low
    ci_high
    model_version
    data_snapshot_hash
    calibration_status:
        none
        provisional
        validated
```

Reglas:

1. `coverage` no se sustituye por tamaño de muestra.
2. Un `n` alto con `coverage_gap` sigue teniendo cobertura insuficiente.
3. Un intervalo estrecho de una simulación no corrige un prior mal especificado.
4. El intervalo de muestreo no representa automáticamente incertidumbre del modelo.
5. La incertidumbre de rango, modelo de respuesta, datos y simulación se identifica por separado cuando sea posible.
6. `n_eff` no sustituye a `n_obs`.
7. Una etiqueta `validated` exige cumplir el proceso de evaluación de la sección siguiente.
8. Si no existe evaluación suficiente, se utiliza `none` o `provisional`.

---

## 12. Política de calibración y evaluación

**No se declara calibración sin un dataset de evaluación definido, congelado y separado.**

### 12.1 `EvaluationDataset`

```text
EvaluationDataset:
    name
    snapshot_hash
    date_from
    date_to
    sessions
    stakes
    format
    player_scope
    label_definition
    features_available_at_decision
    exclusions
    train_split
    validation_split
    test_split
    n_hands
    n_decisions
    grouping_unit
```

### 12.2 Reglas contra fuga de información

1. El split debe respetar el tiempo y la dependencia entre manos.
2. No se distribuyen manos de una misma sesión entre train y test si eso genera fuga.
3. Las features no pueden incluir información posterior a la decisión.
4. No se usa la misma mano para construir un prior y evaluarlo como si fuera independiente.
5. No se calibra con logs de sombra que dependan del modelo evaluado.
6. El test no se reajusta después de observar sus resultados.
7. Si se itera después de consultar el test, ese test deja de ser una evaluación independiente para la nueva versión.
8. Las exclusiones deben quedar documentadas y cuantificadas.

### 12.3 Métricas de predicción

Brier score, log loss y curvas de fiabilidad solo se aplican cuando existe una predicción probabilística y una etiqueta de resultado con definición compatible.

Métricas mínimas cuando correspondan:

- Brier score por clase;
- log loss por clase;
- curvas de fiabilidad;
- ECE, con bins y metodología declarados;
- intervalos de confianza;
- comparación contra baseline explícito.

Una predicción de acción, una predicción de combo y una predicción de resultado no comparten automáticamente la misma etiqueta ni la misma métrica.

### 12.4 Evaluación estratégica

La calidad estratégica requiere una evaluación diferente de la calibración predictiva.

Debe incluir:
- evaluación temporal held-out;
- utilidad o EV bajo una metodología declarada;
- comparación contra baseline;
- análisis por posición, stack, tipo de spot y cobertura;
- intervalos y sensibilidad;
- análisis de errores y escenarios individuales.

Accuracy no sustituye a EV ni demuestra superioridad estratégica.

### 12.5 Criterios previos

Los umbrales de aceptación deben fijarse antes de consultar el test.

Un resultado favorable en accuracy no compensa un EV held-out peor. Una mejora agregada tampoco compensa regresiones graves en segmentos relevantes sin una explicación y una decisión explícita.

---

## 13. Invariantes

1. `ObservedRange` no se normaliza como distribución completa.
2. Una acción no revela un combo si las cartas no fueron mostradas.
3. `ActionStatistics` siempre conserva denominador y filtros.
4. `EstimatedRange` distingue prior, likelihood y posterior.
5. `reach` no se aplica dos veces.
6. Un rango vacío no produce equity.
7. `GenericPrior` no se presenta como observación.
8. Los blockers se aplican antes de calcular equity.
9. `CurrentBoardStrength` no se presenta como equity al showdown.
10. `EquityToShowdown` considera runouts futuros.
11. HU y MW no se mezclan sin declarar el modelo conjunto.
12. `EvByAction` requiere creencias y modelo de respuesta.
13. El EV declara nodo de referencia y costes adicionales.
14. Un `0.0` nunca significa “no hay datos”.
15. Toda estimación declara procedencia, cobertura y versión.
16. Toda simulación declara método, tamaño, semilla e incertidumbre aplicable.
17. La incertidumbre de muestreo no oculta incertidumbre de modelo.
18. Toda calibración declara dataset, split y criterio previo.
19. Los resultados de test no se reutilizan indefinidamente como evaluación independiente después de iterar.
20. Ningún resultado de este contrato activa serving automáticamente.

---

## 14. Criterios de aceptación

### 14.1 Rangos

- Los combos observados requieren cartas reveladas y procedencia.
- Los folds sin revelación no generan combos observados.
- Los pesos de rangos estimados tienen una construcción reproducible.
- Prior, likelihood, reach y posterior no duplican factores.
- Los rangos vacíos conservan una razón.
- Los blockers eliminan combos incompatibles antes de normalizar.
- `n_eff` no se presenta como número de manos.

### 14.2 Equity

- `CurrentBoardStrength` y `EquityToShowdown` son objetos distintos.
- Equity al showdown considera runouts.
- Exact y MC se comparan con tolerancia y metodología declaradas.
- Las semillas permiten reproducibilidad.
- Los empates y side pots respetan elegibilidad.
- Los rangos vacíos o no utilizables no producen equity cero.
- Las hipótesis de dependencia multiway están declaradas.

### 14.3 EV

- Cada acción tiene un nodo de referencia definido.
- Las inversiones previas no se contabilizan dos veces.
- Raise requiere modelo de respuesta y ramas relevantes.
- Los árboles truncados se identifican.
- Los EV solo se comparan bajo supuestos compatibles.
- Las incertidumbres relevantes se conservan.

### 14.4 Evaluación

- La calibración utiliza un dataset congelado y separado.
- Las features están disponibles en el instante de decisión.
- No existe fuga entre train, validation y test.
- Las métricas corresponden al objeto predicho.
- La evaluación estratégica está separada de la calibración.
- Los umbrales se fijan antes de consultar el test.
- Ningún resultado aislado autoriza activar una nueva política.

---

## 15. Límites de esta fase

Este documento define contratos y criterios. No autoriza:

- Implementar o sustituir modelos en esta fase documental.
- Modificar `motor/`.
- Modificar `data/`.
- Corregir registros históricos.
- Regenerar tablas, rangos o perfiles.
- Cambiar la ruta live.
- Activar multiway.
- Cambiar `MULTIWAY_SOPORTADO`.
- Declarar calibración o validación estratégica sin el proceso de evaluación correspondiente.

**Principio final:** una observación, una estadística, un prior, un rango estimado, una equity y un EV son objetos diferentes. Cada transformación debe conservar su procedencia, supuestos, cobertura e incertidumbre. Ningún objeto puede adquirir más certeza que la evidencia y el modelo que lo producen.