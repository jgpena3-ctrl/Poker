# Diseño técnico MW: interfaces y semántica (2026-11-13)

**Estado:** diseño. `MULTIWAY_SOPORTADO=False` se mantiene. No se implementa,
no se activa UI, no se modifica `motor/`, no se escriben datos.

**Objetivo:** definir las piezas mínimas para que multiway pueda calcularse en
sombra con semántica correcta, sin presentar una unión de rangos como si fuera
una equity de campo.

**Base actual:** `recommend_loop._build_multiway_range` construye una unión de
`RangeState`; `rules.py` bloquea MW; `situation.equity_vs_range` es HU. La
unión no modela blockers compartidos, correlación de acciones, orden, ties ni
side pots.

## 1. Principios

1. **Un campo no es un rango.** No existe “el rango del campo” como un único
   vector normalizado.
2. **Cada rival conserva su creencia.** `MultiwayRangeSet` es una colección de
   creencias, no una unión.
3. **La correlación es explícita.** La independencia es un baseline, no la
   verdad.
4. **Los blockers son conjuntos.** Se aplican a la asignación conjunta, no a
   cada rango por separado y luego se suman.
5. **El orden y los botes se calculan.** Ties, all-ins y side pots no son
   detalles de presentación.
6. **Sombra primero.** Calcular y registrar no es recomendar.

## 2. Tipos

### 2.1 `FieldState`

```
FieldState:
  hand_id
  street
  board
  hero
  hero_hand
  players: [FieldPlayer]
  active_players: [player_id]
  folded_players: [player_id]
  all_in_players: [player_id]
  dead_cards
  pot
  bets
  contributions
  current_actor
  last_aggressor
  action_history
  blinds
  stacks
  rules
  data_snapshot
```

`FieldPlayer`:

```
player_id
pos
stack
committed
is_hero
is_active
is_all_in
is_folded
profile
```

Reglas:

- `active_players` excluye folded y all-in para acción, pero los all-in
  conservan elegibilidad de bote.
- `contributions` es la fuente de side pots; `pot` no basta.
- `dead_cards` incluye board, descartes conocidos y cartas quemadas si el
  formato las declara.
- `hero_hand` es exacto; no se muestrea.

### 2.2 `VillainBelief`

```
VillainBelief:
  player_id
  pos
  range: EstimatedRange | GenericPrior
  reach
  profile
  n_obs
  coverage
  model_version
  data_snapshot
  source_kind: observed | estimated | prior
```

Reglas:

- Un `VillainBelief` vacío es válido como ausencia; no produce equity.
- `coverage` viaja con la creencia; no se eleva al agregarla.
- `source_kind` impide presentar un prior como observación.

### 2.3 `MultiwayRangeSet`

```
MultiwayRangeSet:
  beliefs: {player_id: VillainBelief}
  hero_hand
  board
  dead_cards
  joint_policy: independent | correlated | conditional
  correlation_model
  coverage_by_player
```

Reglas:

- No tiene un método `union()` como salida de campo.
- No se normaliza el conjunto de creencias a un único vector.
- `joint_policy` es obligatorio; no hay default silencioso.
- `coverage_by_player` se reporta por rival.

### 2.4 `JointSampler`

```
JointSampler:
  range_set
  policy
  seed
  max_rejections
  sample(n) -> [JointSample]
  diagnostics -> SampleDiagnostics
```

`JointSample`:

```
assignments: {player_id: combo}
hero_hand
board
valid
rejection_reason
weight
```

`SampleDiagnostics`:

```
requested
accepted
rejected
rejection_rate
blocker_collisions
invalid_range
method
seed
```

Reglas:

- Un sample es válido solo si todas las cartas de todos los jugadores son
  distintas y compatibles con board/dead.
- Un rechazo no se “arregla” borrando una carta de un rango y dejando los
  demás inconsistentes.
- `rejection_rate` se reporta; si es alta, la estimación es frágil.
- Mismo seed + mismas entradas → mismos samples.

### 2.5 `FieldEquity`

```
FieldEquity:
  hero_hand
  board
  range_set
  method: exact | monte_carlo
  n_runouts
  n_samples
  seed
  win / tie / lose
  side_pots: [PotResult]
  ci_low / ci_high
  coverage_by_player
  diagnostics
```

Reglas:

- Es una distribución de resultados, no un único número.
- `win/tie/lose` se reporta por bote cuando hay side pots.
- Un rango vacío → `unknown`, no 0.
- `n_runouts` y `n_samples` no se intercambian.
- La equity de campo no se obtiene sumando equities HU.

### 2.6 `FieldResponse`

```
FieldResponse:
  player_id
  action_space
  model
  fold_prob
  call_prob
  raise_prob
  raise_size_distribution
  conditional_on: hand, board, pot, stack, history, profile
  correlation_model
  coverage
  version
```

Reglas:

- Sin `FieldResponse` no hay EV de una agresión multiway.
- La respuesta se condiciona a la mano del rival y al estado; no se usa una
  probabilidad marginal sin declararlo.
- Las respuestas de rivales pueden correlacionarse por un factor de campo;
  esa correlación se declara.
- Un rival all-in no “responde” con fold/call normal; se modela su rango de
  all-in.
- Un rival folded no vuelve a actuar.

### 2.7 `MultiwayActionEV`

```
MultiwayActionEV:
  action
  ev
  method
  n_samples
  seed
  ci_low / ci_high
  tree_depth
  response_model
  range_set
  side_pots
  coverage_by_player
  version
```

Reglas:

- El EV usa `FieldEquity` + `FieldResponse` + botes.
- El EV de fold es una convención del nodo, no una probabilidad.
- Un árbol truncado se declara con `tree_depth`.
- Un EV con cobertura insuficiente no se compara con uno completo.
- No se elige una acción MW por EV de una sola simulación ni por una muestra
  sin intervalo.

## 3. Blockers y correlación

### 3.1 Blockers conjuntos

Orden correcto:

1. Fijar `hero_hand`, board y dead cards.
2. Muestrear una asignación conjunta de todos los rivales.
3. Rechazar si hay cartas repetidas.
4. Renormalizar **la distribución conjunta aceptada**, no cada rango por
   separado.

Incorrecto:

- quitar del rango de A una carta y no actualizar B;
- muestrear A, luego B “sin la carta de A”, y sumar;
- normalizar cada rango después de quitar blockers y multiplicar.

### 3.2 Independencia

`joint_policy=independent`:

- cada rival se muestrea de su creencia;
- se rechazan colisiones;
- se etiqueta `independence_baseline`;
- sirve como baseline, no como modelo calibrado.

### 3.3 Correlación

`joint_policy=correlated`:

- factor latente compartido (por ejemplo, agresividad de mesa);
- o muestreo condicional secuencial con dependencia declarada;
- `correlation_model` obligatorio;
- diagnóstico de colisiones y de diversidad;
- no se declara calibrado sin evaluación.

`conditional`:

- se condiciona a las acciones ya observadas;
- no se vuelve a condicionar dos veces por la misma acción;
- la historia usada debe ser la disponible en la decisión.

## 4. Orden, ties, all-ins y side pots

### 4.1 Orden

- El orden de actuación sale de `action_order`/posición efectiva, no de una
  lista fija.
- El orden de desempate de odd chips se declara en `rules`.
- El orden de elegibilidad de side pots sale de `contributions`, no de la
  posición.

### 4.2 Ties

- Se reparte el bote entre ganadores empatados.
- Odd chips: regla determinista declarada (por ejemplo, primer asiento tras
  el botón); nunca aleatoria silenciosa.
- `win/tie/lose` se reportan por separado.

### 4.3 All-in

- Un all-in no se trata como fold.
- Su contribución queda en el bote; su elegibilidad se mantiene.
- Un call corto crea side pot.
- Un raise por debajo del mínimo se resuelve según reglas del formato; no se
  inventa.

### 4.4 Side pots

- Se calculan por niveles de contribución.
- Un jugador folded no gana ningún bote.
- El exceso no igualado se devuelve.
- Cada `PotResult` declara elegibles, contribución, ganador(es) y odd chips.
- La equity total es la suma de resultados por bote, no una equity única
  aplicada al bote total.

## 5. Interfaces

```
build_field_state(hand, street, hero, rules) -> FieldState
estimate_villain_beliefs(field, models) -> MultiwayRangeSet
sample_joint(range_set, policy, n, seed) -> (samples, diagnostics)
field_equity(range_set, board, method, n, seed) -> FieldEquity
field_response(field, villain, action, model) -> FieldResponse
multiway_action_ev(field, action, ranges, response_model, n, seed)
    -> MultiwayActionEV
```

Contratos:

- `build_field_state` no decide y no consulta modelos.
- `estimate_villain_beliefs` no usa información posterior a la decisión.
- `sample_joint` no modifica `range_set`.
- `field_equity` no usa `union()`.
- `field_response` no se ejecuta para folded/all-in como si fueran activos
  normales.
- `multiway_action_ev` falla de forma explícita si falta respuesta o hay
  cobertura insuficiente; no devuelve 0.

## 6. Integración en sombra

- `MULTIWAY_SOPORTADO` sigue `False`.
- La ruta experimental puede construir `FieldState` y calcular piezas, pero:
  - no cambia la recomendación;
  - no escribe en `data/` por defecto;
  - registra un `MWShadowReport`;
  - se puede desactivar por configuración.
- `MWShadowReport` incluye: cobertura por rival, método, `n`, seed, rechazos,
  side pots, ties, versión y diferencias con HU/union.
- La UI no recibe una recomendación MW.

## 7. Dependencias y riesgos

| Dependencia | Riesgo | Mitigación |
|---|---|---|
| `EstimatedRange` | rangos vacíos o mal calibrados | cobertura explícita; no equity si vacío |
| `PlayerRangeModel` | perfiles escasos | `UNKNOWN`/prior declarado |
| `FieldResponse` | modelo de respuesta inexistente | sin EV de agresión |
| `contributions` | side pots mal calculados | tests de botes y all-ins |
| blockers | rechazo alto / sesgo | diagnóstico y sensibilidad |
| correlación | independencia presentada como verdad | etiqueta baseline |
| orden | ties/odd chips incorrectos | regla determinista y test |
| cobertura | se agrega como si fuera exacta | reporte por rival |

## 8. Criterios de aceptación

1. Ningún camino MW usa `union()` como equity de campo.
2. Un joint sample inválido por blockers se rechaza; no se repara a medias.
3. `rejection_rate` y `coverage_by_player` son visibles.
4. Independencia se etiqueta `independence_baseline`.
5. Ties, all-ins y side pots tienen tests propios.
6. Rango vacío → `unknown`; no 0.
7. EV de agresión sin `FieldResponse` es inválido.
8. `MULTIWAY_SOPORTADO=False` y la UI no cambia.
9. Mismo seed → mismos samples y misma equity.
10. Un `MWShadowReport` no se presenta como recomendación.
