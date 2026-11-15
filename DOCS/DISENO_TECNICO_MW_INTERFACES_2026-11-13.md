# Diseño técnico MW: interfaces y semántica (2026-11-13)

**Estado:** diseño. `MULTIWAY_SOPORTADO=False` se mantiene. No se implementa, no se activa UI, no se modifica `motor/` y no se escriben datos.

**Objetivo:** definir las interfaces mínimas para calcular multiway en sombra con semántica correcta, sin presentar una unión de rangos como distribución conjunta ni una equity HU como equity de campo.

**Base actual:** `recommend_loop._build_multiway_range` construye una unión de `RangeState`; `rules.py` bloquea MW; `situation.equity_vs_range` es HU. La unión no modela blockers compartidos, correlación de acciones, orden, empates ni side pots.

Este documento especifica contratos conceptuales. No certifica que las estructuras actuales del código sean compatibles ni autoriza su implementación.

---

## 1. Principios

1. **Un campo no es un rango.** No existe un único vector normalizado que represente correctamente todos los rangos del campo.
2. **Cada rival conserva su creencia.** `MultiwayRangeSet` contiene una creencia identificable por rival.
3. **La distribución conjunta es explícita.** Los rangos individuales no determinan por sí solos cómo se relacionan las manos de varios rivales.
4. **La independencia es un baseline.** No es una verdad ni una propiedad que pueda asumirse sin declararla.
5. **Los blockers son conjuntos compartidos.** Se aplican a asignaciones completas de cartas, no sumando o normalizando rangos individuales por separado.
6. **El orden y los botes forman parte del cálculo.** All-ins, empates, elegibilidad y side pots no son detalles de presentación.
7. **Actuación y elegibilidad son conceptos distintos.** Un jugador all-in no vuelve a actuar, pero puede ganar los botes para los que es elegible.
8. **Equity y EV son objetos diferentes.** La equity no incorpora por sí sola la respuesta estratégica de los rivales.
9. **Sombra primero.** Calcular y registrar no equivale a recomendar.
10. **La incertidumbre no se oculta.** Cobertura, calidad de rangos, muestreo y supuestos del modelo se reportan por separado.

---

## 2. Tipos de estado

### 2.1 `FieldState`

Representa el estado de una mano en un instante concreto de decisión.

```text
FieldState:
    hand_id
    street
    decision_id
    decision_timestamp
    board
    hero_id
    hero_hand
    players: [FieldPlayer]
    current_actor
    action_order
    action_history
    pot_state
    known_dead_cards
    blinds_and_forced_posts
    rules
    data_snapshot
    state_status
    state_provenance
```

`FieldPlayer`:

```text
FieldPlayer:
    player_id
    seat
    position
    stack_remaining
    total_contribution
    street_contribution
    is_hero
    participation_status:
        active
        all_in
        folded
        unknown
    cards_status:
        hidden
        revealed
        partially_known
    known_cards
```

`pot_state`:

```text
PotState:
    gross_pot
    contributions_by_player
    returned_unmatched_amounts
    rake_and_fees
    pot_layers
    accounting_status
```

Reglas:

1. `hero_hand` es exacta y nunca se muestrea.
2. `board` contiene únicamente cartas comunitarias conocidas en el instante de decisión.
3. `known_dead_cards` contiene cartas conocidas fuera de las manos activas y del board, cuando el formato las proporcione.
4. Las cartas quemadas solo se incluyen si son conocidas y su tratamiento está definido por el formato. No se inventan cartas quemadas desconocidas.
5. `players` conserva a todos los participantes de la mano, incluidos folded y all-in.
6. `participation_status` determina si un jugador puede realizar acciones futuras; no determina por sí solo su elegibilidad para cada bote.
7. Un jugador `folded` no puede ganar ningún bote.
8. Un jugador `all_in` no puede volver a actuar, pero mantiene su elegibilidad según sus contribuciones.
9. `current_actor` solo puede identificar a un jugador que esté en condiciones legales de actuar.
10. `action_order` debe proceder de la secuencia real y las reglas del formato. No se reconstruye con una lista fija de posiciones.
11. `total_contribution` y `street_contribution` deben tener semántica monetaria definida y no pueden mezclarse.
12. `pot_state` debe permitir reconciliar el bote con las contribuciones, devoluciones, rake y reglas aplicables.
13. `gross_pot` no sustituye a `contributions_by_player` para construir side pots.
14. Si el estado monetario no puede reconciliarse, `accounting_status` debe impedir un cálculo de equity o EV que dependa de esos importes.
15. Un estado incompleto o contaminado no se convierte en un estado válido mediante valores por defecto.

`state_status`:

```text
valid
incomplete
tainted
unsupported
```

Una operación solo puede consumir el estado si admite explícitamente su `state_status`.

### 2.2 `VillainBelief`

Representa la creencia individual sobre las manos posibles de un rival.

```text
VillainBelief:
    player_id
    position
    range
    source_kind:
        estimated
        prior
        observed_revealed
    reach
    profile
    n_obs
    n_opp
    coverage
    model_version
    data_snapshot_hash
    empty_status
    provenance
```

Reglas:

1. Una creencia corresponde a un solo rival.
2. `range` debe ser `EstimatedRange` o `GenericPrior` conforme al contrato de rangos.
3. `observed_revealed` solo se admite cuando existen cartas efectivamente reveladas. No equivale a un rango completo para un rival con cartas ocultas.
4. Una acción observada no permite etiquetar el rango como `observed_revealed`.
5. `reach` debe conservar la semántica del contrato de rangos y no volver a multiplicarse si ya forma parte de los pesos.
6. `coverage` viaja con la creencia. Agregar rivales no eleva la cobertura de ninguno.
7. Un rango vacío es ausencia de una distribución utilizable, no una distribución con probabilidad cero.
8. `source_kind` impide presentar un prior como observación.
9. La procedencia debe permitir reconstruir el origen del rango y las transformaciones aplicadas.
10. Una creencia desconocida no se sustituye silenciosamente por un prior genérico.

### 2.3 `MultiwayRangeSet`

Colección de creencias individuales para los rivales relevantes en el estado.

```text
MultiwayRangeSet:
    hero_id
    hero_hand
    board
    known_dead_cards
    beliefs_by_player
    joint_distribution
    joint_policy
    joint_model_version
    coverage_by_player
    joint_coverage
    data_snapshot_hash
```

`joint_policy`:

```text
independent_conditioned
correlated
conditional
unsupported
```

Reglas:

1. No tiene un método `union()` que produzca un rango de campo.
2. No se normaliza el conjunto de creencias a un vector único.
3. Cada rival conserva su identidad y procedencia.
4. La política conjunta es obligatoria.
5. `independent_conditioned` identifica independencia como hipótesis inicial antes de aplicar restricciones de cartas compartidas.
6. `correlated` exige una distribución conjunta o un modelo de dependencia definido.
7. `conditional` exige declarar las variables y observaciones condicionantes.
8. `joint_coverage` no puede ser mejor que la cobertura y compatibilidad de sus componentes sin justificación explícita.
9. La falta de creencia utilizable para un rival relevante impide declarar una equity de campo completa.
10. La exclusión de un rival solo se permite si el estado demuestra que no participa en el bote evaluado.
11. La colección no crea independencia entre rivales por el mero hecho de almacenar sus creencias separadamente.

---

## 3. Distribución conjunta, blockers y correlación

### 3.1 Distribución conjunta

Los rangos individuales describen distribuciones marginales:

\[
P(H_1), P(H_2), \ldots, P(H_n)
\]

El cálculo multiway requiere una distribución conjunta:

\[
P(H_1,H_2,\ldots,H_n)
\]

No se puede sustituir la segunda expresión por una suma de las primeras.

La distribución conjunta debe asignar masa únicamente a combinaciones compatibles con:

- la mano exacta del héroe;
- el board;
- las cartas muertas conocidas;
- las cartas asignadas a los demás rivales;
- las restricciones del formato.

### 3.2 Independencia condicionada a cartas legales

`independent_conditioned` define un baseline:

1. Se parte de las distribuciones individuales.
2. Se construye una propuesta conjunta conforme a esas distribuciones.
3. Se condiciona la asignación a que todas las cartas sean distintas y legales.
4. Se obtiene la distribución conjunta condicionada al evento de compatibilidad.

Formalmente:

\[
P(H_1,\ldots,H_n \mid L)
\propto
\mathbf{1}_L
\prod_i P(H_i)
\]

Donde \(L\) representa la legalidad de la asignación completa.

Reglas:

- El resultado se etiqueta `independence_baseline`.
- La independencia es una hipótesis de partida, no evidencia de que los rivales actúen independientemente.
- Las marginales resultantes pueden diferir de los rangos individuales originales después del condicionamiento por blockers.
- No se renormaliza cada rango individual por separado para fingir que eso produce la distribución conjunta.
- No se presenta este baseline como modelo calibrado.

### 3.3 Muestreo conjunto y ponderación

El rechazo de asignaciones incompatibles es válido solo si el mecanismo de propuesta y aceptación representa la distribución objetivo definida.

Reglas:

1. Si se muestrea desde el producto de las distribuciones individuales y se rechazan asignaciones ilegales, el resultado aceptado representa el producto condicionado a legalidad, siempre que el muestreo de propuesta sea correcto.
2. Si se utiliza un muestreo secuencial sin reemplazo, se debe definir su distribución y demostrar que corresponde al objetivo.
3. No se asume que muestrear A y después B sin sus cartas produce automáticamente la distribución condicionada correcta.
4. Si se emplea importance sampling, se conserva el peso de cada muestra y se reporta el tamaño efectivo correspondiente.
5. No se descartan pesos ni se renormaliza de forma distinta entre métodos sin declarar la transformación.
6. La tasa de rechazo se reporta, pero una tasa baja no demuestra que el modelo sea correcto.
7. Una tasa de rechazo elevada puede indicar rangos incompatibles, propuesta ineficiente o un modelo mal especificado. No se corrige alterando rangos de manera silenciosa.

### 3.4 Correlación

`correlated` exige un modelo explícito de dependencia conjunta.

Puede utilizar:

- un factor latente compartido;
- una distribución conjunta parametrizada;
- un modelo condicional entre rivales;
- otro mecanismo cuya distribución objetivo esté formalizada.

Debe declarar:

```text
CorrelationModel:
    model_id
    variables
    dependency_structure
    parameters
    conditioning_information
    estimation_source
    calibration_status
    model_version
```

Reglas:

1. `correlated` no es válido si solo contiene una etiqueta sin distribución conjunta implementada.
2. La dependencia debe tener una interpretación concreta.
3. No se inventan parámetros de correlación.
4. Un factor latente no demuestra por sí solo correlación estratégica real.
5. La correlación debe evaluarse frente al baseline de independencia.
6. No se declara calibrada sin evaluación fuera de muestra.

### 3.5 Condicionamiento por acciones

`conditional` permite condicionar las creencias a acciones observadas, siempre que esas acciones estuvieran disponibles en el instante de decisión.

Debe declarar:

```text
ConditioningRecord:
    observation_id
    player_id
    action
    action_order
    street
    information_timestamp
    likelihood_model
    already_applied
```

Reglas:

1. Una misma acción no puede incorporarse dos veces a la creencia.
2. No se utiliza información posterior al instante de decisión.
3. No se condiciona a una acción que todavía no ocurrió.
4. El orden de las acciones se conserva.
5. La acción observada debe tener un modelo de likelihood aplicable.
6. Si no existe un modelo para interpretar la acción, se conserva como observación contextual sin fingir que actualiza probabilidades.
7. El condicionamiento por acción no implica independencia entre las decisiones de los rivales.

---

## 4. `JointSampler`

Interfaz de muestreo de asignaciones completas de cartas.

```text
JointSampler:
    range_set
    joint_distribution
    sampling_method
    seed
    max_attempts
    sample(n) -> SamplingResult
```

`JointSample`:

```text
assignments:
    player_id -> exact_combo
hero_hand
board
known_dead_cards
sample_weight
valid
```

`SamplingResult`:

```text
samples
requested
accepted
rejected
attempts
rejection_rate
effective_sample_size
blocker_collisions
invalid_range_count
invalid_state_count
method
seed
termination_status
diagnostics
```

Reglas:

1. Una muestra es válida solo si todas las cartas son distintas y compatibles con board, héroe y dead cards.
2. Cada rival recibe exactamente una asignación legal.
3. Una muestra inválida se rechaza completa.
4. No se corrige una asignación eliminando una carta de un rival y dejando los demás sin actualizar.
5. La distribución de las muestras debe coincidir con `joint_distribution`.
6. Si se usan muestras ponderadas, `sample_weight` es obligatorio.
7. `effective_sample_size` se calcula sobre los pesos cuando corresponda y no se presenta como número de manos observadas.
8. `max_attempts` limita el trabajo. Si no se alcanza el número requerido de muestras válidas, el resultado declara fallo o insuficiencia.
9. No se devuelve una muestra parcial como si se hubiera completado la solicitud.
10. `rejection_rate` se reporta con denominador explícito.
11. `blocker_collisions` distingue colisiones entre rivales de incompatibilidades con cartas conocidas.
12. Mismas entradas, versión, método y semilla deben producir resultados reproducibles.
13. Si el orden de iteración forma parte de la reproducibilidad, debe estar definido.
14. Un rango inválido o vacío no se transforma en un rango uniforme.

---

## 5. `FieldEquity`

**Definición:** participación esperada del héroe en los botes para los que es elegible, contra una asignación conjunta de rivales y runouts futuros.

```text
FieldEquity:
    hero_id
    hero_hand
    board
    range_set
    pot_eligibility
    method:
        exact
        monte_carlo
    equity_by_pot
    aggregate_equity
    win_probability_by_pot
    tie_probability_by_pot
    lose_probability_by_pot
    n_joint_assignments
    n_runouts
    n_samples
    seed
    ci_low
    ci_high
    coverage_by_player
    joint_coverage
    sampling_diagnostics
    assumptions
    equity_version
```

`PotResult`:

```text
PotResult:
    pot_id
    amount
    eligible_players
    hero_eligible
    hero_expected_share
    win_probability
    tie_probability
    lose_probability
    odd_chip_rule
```

Reglas:

1. La equity de campo se calcula sobre asignaciones conjuntas, no sumando equities HU.
2. La equity considera los runouts futuros hasta showdown.
3. El cálculo respeta blockers compartidos.
4. Cada bote tiene su propio conjunto de jugadores elegibles.
5. Un jugador folded no gana ningún bote.
6. Un jugador all-in conserva elegibilidad según sus contribuciones.
7. Un jugador no elegible no participa en el resultado de ese bote.
8. `win/tie/lose` se reportan por bote cuando existen side pots.
9. Un empate puede involucrar dos o más jugadores; no se reduce a un empate HU.
10. `hero_expected_share` representa la participación esperada del héroe en ese bote, incluyendo empates y reglas de odd chips cuando corresponda.
11. `aggregate_equity` solo se calcula con una definición explícita de ponderación por bote.
12. No se aplica una equity única al bote total si hay side pots con elegibilidades distintas.
13. Un rango vacío o una creencia no utilizable produce `unknown` o `unsupported`, nunca `0.0`.
14. `n_joint_assignments`, `n_runouts` y `n_samples` son cantidades distintas.
15. En enumeración exacta se identifica el espacio completo enumerado.
16. En MC se declaran semilla, método, cantidad de muestras e intervalo de muestreo aplicable.
17. En cálculo exacto no se inventa un intervalo de muestreo; la incertidumbre de modelo y de rango sigue existiendo.
18. La cobertura por rival no se sustituye por un único promedio.
19. La independencia condicionada se etiqueta como baseline.
20. El resultado no se interpreta como EV de una acción futura.

---

## 6. Orden, actuación y elegibilidad

### 6.1 Orden de actuación

El orden de actuación se deriva del historial y las reglas del formato.

Debe distinguir:

- orden de actuación de la calle actual;
- jugadores que todavía pueden actuar;
- jugadores que ya actuaron;
- jugadores all-in;
- jugadores que abandonaron la mano;
- orden de desempate para odd chips.

No se utiliza una lista fija de posiciones como sustituto del historial real.

Si el orden no puede reconstruirse, el estado se marca `incomplete` o `unsupported` para operaciones que dependan de él.

### 6.2 All-ins

1. Un all-in no es un fold.
2. Un jugador all-in no puede realizar nuevas acciones.
3. Su contribución permanece en el cálculo de botes.
4. Su elegibilidad depende de los niveles de contribución.
5. Los jugadores activos pueden seguir disputando side pots entre sí.
6. El rango del jugador all-in se modela como la distribución compatible con la acción que lo llevó al all-in.
7. No se modela como un rival que todavía puede responder con fold, call o raise.

### 6.3 Ties y odd chips

1. Los empates se calculan entre los jugadores elegibles para cada bote.
2. Los odd chips siguen la regla determinista del formato o sala.
3. La regla se declara en `rules`.
4. No se introduce una distribución aleatoria de odd chips si existe una regla determinista.
5. Si la regla no se conoce, el resultado se marca incompleto para el reparto exacto.
6. Las probabilidades de ganar, empatar y perder se conservan separadas de la participación monetaria esperada.

---

## 7. Side pots y contribuciones

Los side pots se construyen por niveles de contribución, no a partir del importe total del bote.

Reglas:

1. `contributions_by_player` es la fuente para construir los niveles.
2. Las contribuciones deben distinguir importes vivos, apuestas, antes y dinero muerto cuando las reglas lo requieran.
3. Un jugador folded puede haber contribuido dinero al bote, aunque ya no sea elegible para ganarlo.
4. El dinero aportado por un jugador folded no se elimina del bote.
5. Los jugadores all-in conservan elegibilidad en los botes que cubren sus contribuciones.
6. Los excesos no igualados se devuelven conforme a las reglas del formato.
7. Las devoluciones no se confunden con dinero ganado en showdown.
8. Cada `PotResult` declara importe y jugadores elegibles.
9. Un call corto puede generar side pots.
10. Una subida inferior al mínimo se resuelve según las reglas del formato; no se corrige mediante una suposición genérica.
11. Rake, fees y reglas de reparto se incorporan cuando sean relevantes para el resultado monetario.
12. Si las contribuciones no pueden reconciliarse, no se declara un cálculo exacto de equity monetaria ni EV.

---

## 8. `FieldResponse`

**Definición:** modelo de las respuestas futuras de un rival ante una acción concreta, condicionado al estado y a la información disponible.

```text
FieldResponse:
    player_id
    decision_node
    legal_action_space
    response_distribution
    response_model
    conditioning_variables
    correlation_model
    coverage
    calibration_status
    model_version
```

La distribución de respuestas debe poder representar:

- fold;
- check;
- call;
- bet;
- raise;
- all-in;
- otras acciones legales del formato.

Las probabilidades de respuesta se condicionan a las variables que el modelo utilice:

```text
hand_belief
board
pot
stack
position
action_history
previous_responses
profile
legal_action_space
```

Reglas:

1. No se utilizan probabilidades marginales sin declarar el nodo y las condiciones.
2. Las probabilidades deben corresponder a acciones legales en ese nodo.
3. La distribución de respuestas debe sumar uno dentro de su espacio de acciones válido.
4. Si existe una acción no modelada, el resultado debe declararlo; no se redistribuye silenciosamente su masa.
5. La respuesta de un rival puede depender de las respuestas anteriores de otros.
6. Si se asume independencia entre respuestas, se etiqueta como hipótesis.
7. La correlación de respuestas requiere un modelo conjunto o condicional explícito.
8. Un jugador folded no vuelve a actuar.
9. Un jugador all-in no recibe una respuesta normal de fold/call/raise.
10. El rango de un jugador all-in debe modelar la distribución de manos compatible con su acción.
11. Sin un modelo de respuesta suficiente no existe EV completo de una agresión.
12. Una predicción de respuesta no es una observación de lo que el rival hará realmente.

---

## 9. `MultiwayActionEV`

**Definición:** valor esperado de una acción del héroe bajo una distribución conjunta de manos, un modelo de respuesta y un árbol de juego declarado.

```text
MultiwayActionEV:
    action
    decision_node
    ev
    unit
    reference_state
    method
    joint_range_model
    response_model
    action_tree
    tree_depth
    terminal_conditions
    pot_structure
    side_pots
    n_samples
    seed
    ci_low
    ci_high
    coverage_by_player
    joint_coverage
    model_assumptions
    version
```

Reglas:

1. El EV requiere creencias válidas para los rivales relevantes.
2. El EV de una agresión requiere modelos de respuesta suficientes para las ramas materiales.
3. El cálculo debe modelar las respuestas secuenciales y las dependencias relevantes.
4. `FieldEquity` no sustituye al árbol de decisiones.
5. La equity puede ser un componente del EV, pero no contiene por sí sola fold equity ni decisiones posteriores.
6. Los importes ya comprometidos se tratan como costes hundidos respecto al nodo actual.
7. El EV de fold suele ser cero respecto al nodo, pero no significa que se recupere lo invertido.
8. El EV de call incluye el coste adicional y la distribución de resultados de los botes elegibles.
9. El EV de raise modela folds, calls, nuevas subidas y demás respuestas legales relevantes.
10. El EV de check puede requerir modelar calles posteriores.
11. Un jugador all-in no vuelve a responder en el árbol.
12. Los side pots y las condiciones de elegibilidad se recalculan según las contribuciones de cada rama.
13. Si el árbol está truncado, se declara `tree_depth` y el método de valoración de hojas.
14. Un árbol truncado no se presenta como solución completa.
15. La unidad del EV y el nodo de referencia son obligatorios.
16. No se compara un EV con otro si cambian de forma no controlada el modelo de rangos, respuestas, bote o condiciones terminales.
17. Un EV con cobertura insuficiente se marca `unsupported` o `provisional`, según la política declarada.
18. No se devuelve `0` como sustituto de un cálculo que no pudo realizarse.
19. No se elige una acción multiway por una sola simulación.
20. Un EV calculado no demuestra por sí solo que la política sea estratégicamente correcta.

---

## 10. Interfaces propuestas

```text
build_field_state(hand, street, hero, rules)
    -> FieldState

estimate_villain_beliefs(field_state, models)
    -> MultiwayRangeSet

build_joint_distribution(range_set, joint_policy, model)
    -> JointDistribution

sample_joint(range_set, joint_distribution, n, seed)
    -> SamplingResult

build_pot_eligibility(field_state)
    -> [PotEligibility]

field_equity(field_state, range_set, joint_distribution, method, n, seed)
    -> FieldEquity

field_response(field_state, villain, action, model)
    -> FieldResponse

multiway_action_ev(
    field_state,
    action,
    range_set,
    joint_distribution,
    response_models,
    action_tree,
    n,
    seed
)
    -> MultiwayActionEV
```

### 10.1 Contratos de las interfaces

`build_field_state`:

- Construye el estado a partir de información disponible.
- No decide ni consulta modelos estratégicos.
- No inventa posiciones, cartas, contribuciones u orden.
- Devuelve un estado explícitamente incompleto si faltan datos esenciales.

`estimate_villain_beliefs`:

- Produce una creencia individual por rival.
- No usa información posterior al instante de decisión.
- Conserva procedencia y cobertura.
- No convierte ausencia de datos en rango uniforme.

`build_joint_distribution`:

- Define la distribución conjunta objetivo.
- Declara cómo combina rangos individuales.
- Aplica restricciones compartidas de cartas.
- No utiliza `union()`.

`sample_joint`:

- Muestrea de la distribución conjunta declarada.
- No modifica `range_set`.
- Conserva pesos y diagnósticos.
- Falla explícitamente si no puede generar muestras suficientes.

`build_pot_eligibility`:

- Construye botes y elegibilidad desde contribuciones reconciliadas.
- Conserva aportaciones de jugadores folded.
- Respeta all-ins, devoluciones y side pots.

`field_equity`:

- Calcula resultados sobre asignaciones conjuntas y runouts.
- No utiliza equity HU como sustituto.
- No devuelve cero ante rango vacío o cobertura no utilizable.

`field_response`:

- Modela únicamente acciones legales del rival en el nodo correspondiente.
- No se ejecuta para folded o all-in como si fueran jugadores activos.
- Declara supuestos, cobertura y versión.

`multiway_action_ev`:

- Necesita estado, creencias, distribución conjunta y respuestas suficientes.
- Evalúa un árbol de acciones y pagos.
- Falla explícitamente si faltan componentes materiales.
- No devuelve una acción recomendada ni modifica la decisión live.

Los nombres son interfaces conceptuales. Antes de implementar deben contrastarse con las estructuras reales del repositorio y con los contratos de rango, equity y EV.

---

## 11. Cobertura e incertidumbre

La cobertura se reporta por rival y para la distribución conjunta.

```text
MultiwayCoverage:
    coverage_by_player
    joint_coverage
    missing_beliefs
    unsupported_beliefs
    fallback_sources
    correlation_status
    response_coverage
    pot_accounting_status
    calculation_status
```

Reglas:

1. No se promedian coberturas diferentes para presentar una cobertura global aparentemente alta.
2. Un rival con rango no utilizable no desaparece del cálculo sin justificación.
3. Un prior se identifica como prior.
4. Un fallback se identifica como fallback.
5. Un rango individual válido no demuestra que la distribución conjunta esté bien especificada.
6. Una distribución conjunta válida no demuestra que el modelo de respuesta esté calibrado.
7. La cobertura de rangos, respuestas y contabilidad de botes se reporta por separado.
8. El intervalo de MC no representa la incertidumbre de los rangos ni la del modelo de correlación.
9. La incertidumbre de muestreo y la incertidumbre de modelo no se mezclan en un único número.
10. Si una pieza necesaria no está disponible, el resultado no se presenta como equity o EV completo.

Estados de cálculo:

```text
exact
estimated
provisional
unknown
unsupported
failed
```

Estos estados describen el resultado del cálculo, no una recomendación de póker.

---

## 12. Integración en sombra

`MULTIWAY_SOPORTADO` permanece `False`.

La ruta experimental podrá diseñarse para construir `FieldState`, creencias, distribución conjunta y cálculos de equity/EV sin afectar la decisión live.

Restricciones:

1. No cambia la recomendación.
2. No sustituye la ruta HU.
3. No activa UI multiway.
4. No escribe en `data/`.
5. No modifica artefactos de producción.
6. No modifica `MULTIWAY_SOPORTADO`.
7. No utiliza el resultado experimental como etiqueta automática de entrenamiento.
8. No promueve automáticamente un cálculo provisional a exacto.
9. No activa escritores reales.
10. Debe poder desactivarse sin alterar la ruta live.

### 12.1 `MWShadowReport`

```text
MWShadowReport:
    hand_id
    decision_id
    state_status
    range_coverage_by_player
    joint_policy
    joint_model_version
    sampling_method
    n_samples
    seed
    effective_sample_size
    rejection_rate
    equity_by_pot
    side_pots
    tie_results
    response_coverage
    ev_status
    calculation_status
    assumptions
    comparison_metadata
    data_snapshot_hash
    model_versions
```

Reglas:

- El informe identifica la versión de datos y modelos utilizada.
- Distingue cálculos exactos, estimados, provisionales y fallidos.
- No presenta la unión histórica de rangos como equity multiway.
- Una comparación con HU o con `union()` es un diagnóstico de diferencias, no una comparación entre dos métodos equivalentes.
- No se escribe en `data/` ni en datos de entrenamiento.
- El almacenamiento persistente requiere un destino expresamente autorizado y separado de los datos de aprendizaje.
- La ausencia de almacenamiento no se resuelve escribiendo silenciosamente en otra ubicación.
- El informe no contiene una recomendación para la UI.

---

## 13. Dependencias y riesgos

| Dependencia | Riesgo | Mitigación |
|---|---|---|
| `EstimatedRange` | Rangos vacíos o mal calibrados | Cobertura y procedencia explícitas |
| `GenericPrior` | Prior presentado como observación | `source_kind` obligatorio |
| `joint_distribution` | Producto de marginales confundido con distribución real | Política conjunta formalizada |
| `JointSampler` | Sesgo por muestreo o rechazo | Distribución objetivo y ponderación verificables |
| Blockers | Colisiones o asignaciones ilegales | Validación conjunta |
| Correlación | Independencia presentada como verdad | Baseline etiquetado y modelos comparables |
| `FieldResponse` | Respuestas marginales insuficientes | Árbol condicional y cobertura explícita |
| `contributions` | Side pots incorrectos | Reconciliación y tests de elegibilidad |
| All-ins | Jugador all-in tratado como folded o activo | Separar actuación y elegibilidad |
| Ties | Repartos incorrectos | Reglas de empate y odd chips |
| Cobertura | Un agregado oculta un rival sin datos | Reporte por rival y cobertura conjunta |
| EV | Equity confundida con valor de acción | Árbol de respuestas y pagos |
| Sombra | Resultado experimental llega a serving | Aislamiento y flag desactivado |

---

## 14. Criterios de aceptación

### 14.1 Estado y cartas

1. Todos los jugadores relevantes conservan identidad y estado.
2. Folded y all-in se distinguen.
3. All-in conserva elegibilidad según contribuciones.
4. Las cartas conocidas no se duplican.
5. El estado incompleto no se presenta como válido.
6. Las contribuciones y los botes pueden reconciliarse.

### 14.2 Distribución conjunta

1. Ningún camino MW usa `union()` como equity de campo.
2. Cada rival conserva su propia creencia.
3. La política conjunta es obligatoria.
4. Independencia condicionada se etiqueta `independence_baseline`.
5. La distribución conjunta tiene una definición matemática verificable.
6. El muestreo respeta esa distribución.
7. Las muestras inválidas se rechazan completas.
8. La ponderación se conserva cuando corresponde.
9. Mismo seed y mismas entradas producen muestras reproducibles.
10. No se corrigen rangos de forma silenciosa para reducir rechazos.

### 14.3 Equity y botes

1. Blockers se aplican a asignaciones completas.
2. Equity se calcula con runouts futuros.
3. No se suman equities HU para producir equity de campo.
4. Side pots tienen elegibilidad propia.
5. Folded no gana botes.
6. All-in conserva elegibilidad.
7. Ties y odd chips siguen reglas deterministas.
8. Rango vacío produce `unknown` o `unsupported`, nunca cero.
9. `n_joint_assignments`, `n_runouts` y `n_samples` no se intercambian.
10. La incertidumbre de muestreo no se confunde con incertidumbre de modelo.

### 14.4 Respuesta y EV

1. EV de agresión sin modelo de respuesta suficiente es inválido.
2. Las respuestas se condicionan al nodo y al historial.
3. Las acciones no legales no reciben probabilidad.
4. Los jugadores folded y all-in no responden como activos.
5. El árbol declara profundidad y condiciones terminales.
6. Los side pots se recalculan en las ramas pertinentes.
7. El EV declara unidad y nodo de referencia.
8. Los cálculos incompletos no devuelven cero como sustituto.

### 14.5 Sombra

1. `MULTIWAY_SOPORTADO=False`.
2. La UI no cambia.
3. La ruta live no cambia.
4. No se escriben datos de entrenamiento.
5. No se activan escritores reales.
6. El informe sombra no se presenta como recomendación.
7. Los resultados conservan hashes, versiones, cobertura y supuestos.
8. La ruta experimental se puede desactivar sin alterar la ruta HU.

---

## 15. Límites de esta fase

Este documento no autoriza:

- Implementar interfaces o modelos.
- Cambiar `motor/`.
- Cambiar `data/`.
- Modificar registros históricos.
- Regenerar rangos, perfiles o tablas.
- Modificar la ruta live.
- Cambiar `rules.py` para permitir MW.
- Activar UI multiway.
- Cambiar `MULTIWAY_SOPORTADO`.
- Ejecutar escritores reales.
- Declarar validación estratégica.
- Presentar el baseline de independencia como modelo calibrado.

**Principio final:** multiway exige una distribución conjunta de manos, un tratamiento compartido de blockers, una estructura de botes y, para EV, un modelo de respuestas y un árbol de acciones. Ninguna unión de rangos individuales sustituye esas piezas. El cálculo en sombra no equivale a soporte estratégico ni autoriza una recomendación live.