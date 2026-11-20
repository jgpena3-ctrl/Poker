# FASE 10.5 — Inventario del pipeline original y diseño de integración HU

## 0. Estado de esta entrega

- Esta entrega es **auditoría y diseño**. No se ha modificado ningún archivo de
  código, matriz, perfil, manifiesto ni artefacto estratégico.
- No se ha capturado la pantalla, no se ha iniciado F9-B, no se han registrado
  manos reales y no se ha ejecutado un piloto.
- No hay commits ni push.
- El único artefacto nuevo de esta fase es este documento.
- HEAD: `00b1f91` (`00b1f9186f14598ca37797d21f13daf8f62f90f1`).
- Los cambios de Fase 10.4 siguen en el árbol de trabajo sin commit:
  `motor/hu_experimental/capture.py`, `motor/hu_experimental/gui.py`,
  `motor/hu_experimental/assistant.py`, `motor/hu_parity/parity.py`,
  `motor/test_hu_experimental.py`, `motor/test_hu_parity.py`.
  `data/decisions.jsonl` contiene 10 líneas añadidas por una ejecución manual
  del asistente original; no forman parte de esta fase y no deben incluirse en
  un commit.

### Hashes de referencia (antes de esta fase)

| Archivo | SHA-256 |
|---|---|---|
| `data/hands_db.jsonl` | `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E` |
| `data/decisions.jsonl` | `AC660859FBEFD2306706335B9A1BAD9842B49688C1B21217921982129E5C6C13` |
| `motor/asistente_live.py` | `0524A29CDC2A71C1E237D31C2D46158390D12FA5084115B13D6F4C6EC5C7A788` |
| `motor/asistente_live_gui.py` | `7B65DF5E9DA8EF1E548987FC77438072F64CBB962122B5BB955A45442D7F53EF` |
| `tools/capture_live.py` | `26EF5B006DAF35967A26FEE9B4A8AE88D8A2A0FBE96A9CAB8E3277ADEFA4E72B` |

---

## 1. Inventario del pipeline original

### 1.1 Captura de pantalla y OCR

Punto de entrada: `tools/capture_live.py::capture()`.

Orden exacto:

1. `ImageGrab.grab()` obtiene un `PIL.Image` de la pantalla completa.
2. Se convierte a `numpy.ndarray` RGB.
3. `StateReader.read_all(pil)` lee el estado numérico y los asientos.
4. `CardReader.read_all(img_arr)` lee las cartas del héroe y las comunitarias.
5. `capture()` copia `cards['hero']` a `state['hero_cards']`.
6. `capture()` copia `cards['community']` a `state['community']`.
7. Devuelve `(state, img_arr, pil)`.

No se separan los tiempos de screenshot y OCR. `capture_live` no expone
confianza por campo ni el estado bruto intermedio de cada lector.

#### `StateReader.read_all()` — `tools/lector_estado.py`

| Campo | Origen | Transformación | Salida |
|---|---|---|---|
| `pot` | ROI `calib['pot']` | escala de grises, `_strip_left_label`, `DigitOCR.read(pool='digits')` | `float` o `None` |
| `{pid}_stake` | ROI `calib['player_stacks'][pid]` | escala de grises, `DigitOCR.read(pool='stacks')` | `float` o `None` |
| `btn` | `calib['dealer_button']` por asiento | media RGB del ROI; máximo > 80; protección especial de `p3` | pid (`hero`/`p1`…`p5`) o `None` |
| `{pid}_state` | ROI de botón por asiento + fila de estrella | `StateMatcher.read()`; si no hay botón, estrella; fallback a brillo | `'activo'` o `'inactivo'` |
| `{pid}_bet` | `BET_ROIS[pid]` | `DigitOCR` y/o `BinaryMatcher`; `p3` invierte el orden | `float` o `None` |

Notas:

- `pot_wide` no lo produce `capture_live`; el recorder lo acepta como respaldo
  histórico, pero en el camino live normal no existe.
- Los estados de asiento se reducen a `activo`/`inactivo`; no se conserva el
  texto original del botón (`igualar`, `subir`, `retirarse`, etc.).
- Los `stake` se leen del stack visible. No se corrige el stack por apuestas ya
  comprometidas.
- Los `bet` se anulan para asientos en estado inactivo/fuera.

#### `CardReader.read_all()` — `tools/lector_unificado.py`

| Campo | Origen | Transformación | Salida |
|---|---|---|---|
| `community` | `COM_COORDS` (5 slots) + `COM_RANK`/`COM_PALO` | plantillas de gradiente para rango; clúster de color/forma para palo | lista de 5 `{'rank', 'suit'}` |
| `hero` | `HERO_REGION = (96, 146, 117, 165)` | mitad izquierda/derecha; mitad superior para rango; píxeles absolutos para palo | lista de 2 códigos o `None` |

Notas:

- `HERO_REGION` está hardcodeado y no usa `calib['hero_cards']`. En
  `data/calib_1365.json` existen coordenadas `hero_cards`, pero el lector de
  cartas no las consulta. Es una duplicidad de fuentes de calibración, no una
  prueba de error por sí misma.
- El palo del héroe se decide con píxeles absolutos:
  `(100,157)`, `(98,159)`, `(113,157)`, `(111,159)`. Si la mesa se mueve,
  cambia de tamaño o el recorte no coincide, el fallback puede convertir un
  palo rojo en `s` (spade).
- El lector no expone puntuación de confianza. Un resultado dudoso se devuelve
  igualmente como carta, salvo que el recorte esté vacío.

### 1.2 Contrato del estado bruto

El estado que consume el motor y el recorder es un `dict` plano. Claves
relevantes:

```text
pot
hero_stake, p1_stake, ..., p5_stake
hero_bet,  p1_bet,  ..., p5_bet
hero_state, p1_state, ..., p5_state
btn
hero_cards
community
```

No contiene:

- `to_call`
- contribuciones por calle
- acciones
- posiciones
- street lógico
- confianza por campo
- procedencia de cada valor

Todo eso lo construye, o lo intenta construir, el recorder.

### 1.3 Recorder original — `recorder/recorder_live.py`

Punto de entrada: `LiveRecorder.process_frame(state, img_arr, log)`.

Flujo:

1. Guarda el frame causal para evidencias de ambigüedad.
2. Actualiza `hand['max_pot']` con el `pot` leído.
3. Si no hay mano:
   - `_can_start_hand()` exige botón válido, asiento de botón con stack visible
     y al menos dos stacks visibles.
   - `_awaiting_new_hand` y `_is_new_deal()` evitan reutilizar una mano
     terminada.
   - Si no puede empezar, guarda `last_state`/`last_img` y termina.
4. Si detecta mano nueva (`_is_new_hand`):
   - finaliza la mano anterior si existe;
   - `_assign_cards_by_name(state)`;
   - `start_hand(state)`.
5. `start_hand()` construye el contrato de mano:
   - `hand_id`, `date`, `btn_idx`, `btn_player`;
   - `players[]` con `active`, `name`, `pos`, `stack`, `cards`, `_id`;
   - `comunitarias`;
   - `streets` con `actions` y `board` para preflop/flop/turn/river;
   - `current_street`, `max_pot`, `final_pot`, `showdown`.
6. `_reconstruct_preflop()` reconstruye ciegas y acciones preflop a partir de
   posiciones, estados y apuestas visibles.
7. En cada frame con mano:
   - aplica inactivos manuales;
   - detecta inactivos;
   - detecta salto/cambio de calle;
   - detecta acciones y labels;
   - audita el bote con `_audit_live_pot()`;
   - detecta fin de mano y llama `finalize_hand()`.
8. Actualiza `last_state` y `last_img`.

#### Datos derivados que produce el recorder

| Dato | Fuente | Método |
|---|---|---|
| Posiciones | botón + asientos sentados + overrides manuales | `_assign_positions()` / `_hand_positions` |
| Mapa pid→posición | posiciones de la mano o asignación actual | `_get_pid_map()` |
| Mapa posición→pid | inverso | `_get_pos_map()` |
| Contribución por calle y posición | acciones `p/b/c/r` con importe absoluto | `_street_contributions()` |
| Bote calculado | contribuciones, devoluciones y rake | `_pot_breakdown()` |
| Bote live calculado | contribuciones con devoluciones | `_pot_breakdown()['pot_live_calculated']` |
| Ambigüedad bote/apuesta | lectura OCR vs contribuciones registradas | `_audit_live_pot()` |
| Folds | acciones `f` en `hand['streets']` | `_folded_positions` / acciones |
| All-in | estado y apuestas | `_allin_players` |
| Calle actual | board y transiciones | `hand['current_street']` |
| Cartas congeladas | `{pid}_cards` al iniciar la mano | `hand['players'][].cards` |

#### Contrato de mano finalizado

`finalize_hand()` calcula y escribe:

- `final_pot` y desglose de bote;
- `showdown` y ganador, si existe;
- `players[].cards` (las cartas conocidas al inicio);
- `streets` completas;
- evidencias de ambigüedad.

#### Efectos secundarios del recorder

- `output_path`: escribe la mano finalizada. En el adaptador experimental está
  aislado en `trabajo/hu_experimental/hands_parity.jsonl`.
- `ambiguity_capture_dir`: guarda PNG/JSON de ambigüedad, siempre activo. En el
  adaptador experimental está aislado en
  `trabajo/hu_experimental/ambiguedades/`.
- `capture_dir`: si se configura, guarda todos los frames. En paridad está en
  `None`, por lo que no se guarda cada frame.
- `on_hand_finalized`: callback que usa el registro prospectivo.
- Estado global de módulo: `MANUAL_POSITIONS`, `MANUAL_CARDS`,
  `MANUAL_INACTIVE`, `PLAYER_NAMES`. El adaptador debe guardar y restaurar lo
  que modifique.
- El recorder **no es thread-safe**. El adaptador ya serializa captura y
  análisis con locks.

### 1.4 Motor original — `motor/asistente_live.py`

Punto de entrada: `Asistente.step(state, img_arr, pil, ...)`.

Orden:

1. `self.rec.process_frame(state, img_arr, log=log)`.
2. `self._observe_stacks(state)`.
3. `_hero_act(state, pil)` o `_hu_next_to_act` en modo HU.
4. Si toca actuar: `recomendacion(state)` o `recomendaciones(state)`.
5. `DecisionLog.record_decision(snapshot)` antes de `on_reco`.
6. `on_reco(texto, evs, sit, label)`.

Qué consume el motor:

- `state['pot']` para el bote de la situación;
- `state[f'{hero}_bet']` y `_max_bet(state)` para `to_call`;
- `state[f'{pid}_stake']` para stacks;
- `state['hero_cards']` o `{hero_pid}_cards` para cartas;
- `state['community']` para board;
- `rec.hand` para posiciones, cartas congeladas, folds, secuencia preflop y
  evidencia postflop.

Consecuencia importante: el motor usa una mezcla de **OCR bruto** (pot, bets,
stacks, board, cards) y **estado derivado del recorder** (posiciones, folds,
cartas congeladas, acciones). No consume un contrato único y normalizado.

### 1.5 Punto de integración real

El punto donde el pipeline original ya ha ejecutado todas sus detecciones es:

```text
LiveRecorder.process_frame()
  -> hand / _hand_positions / _pot_breakdown / _street_contributions /
     _folded_positions / _inactive_players / _allin_players /
     _hand_ambiguities / last_state
```

Ese es el estado que debe consumir la capa HU. No es `capture_live.capture()`:
ese es solo la entrada visual.

---

## 2. Qué recibe y qué descarta hoy el adaptador experimental

### 2.1 Camino actual

```text
HUCaptureAdapter.capture()
  -> CapturedFrame.state (dict bruto de capture_live)
  -> interpret_state(frame.state) -> HUState
  -> puertas temporales / secuencia
  -> engine.step(frame.state, frame.image, frame.pil)
       -> rec.process_frame() (recorder completo)
       -> recomendacion()
       -> SnapshotCollector
  -> ParityAnalysis(state=HUState bruto, snapshot=DecisionLog)
```

El recorder **sí se ejecuta**, pero su resultado se descarta para la
interpretación HU. La GUI muestra `analysis.state`, construido antes de
`engine.step`, no el estado procesado por el recorder.

### 2.2 Pérdidas concretas

| Campo HU | Hoy sale de | Se descarta | Riesgo |
|---|---|---|---|
| `hero_cards` | `state['hero_cards']` | `rec.hand.players[hero].cards`, `{hero_pid}_cards`, procedencia | Una lectura OCR dudosa se muestra como verdad; no se compara con las cartas congeladas al inicio |
| `board` | `state['community']` | board registrado por calle, `hand['streets'][street]['board']` | Board OCR y board registrado pueden discrepar sin señal |
| `street` | longitud del board | `hand['current_street']`, transiciones | Un board incompleto puede cambiar la calle lógica |
| `pot` | `state['pot']` | `_pot_breakdown()['pot_live_calculated']`, `_audit_live_pot()` | No se detecta bote duplicado/incompleto; no hay abstención por contradicción |
| `to_call` | `max(villain_bet - hero_bet, 0)` si ambos existen | contribuciones por calle, acciones, `_preflop_current_bet` | Si falta una apuesta, queda `None` aunque el recorder pueda demostrar la contribución; si ambas están mal, el resultado se acepta |
| `hero_stack` | `state['hero_stake']` | stack de inicio de mano y evolución | `None` si el OCR falla; no se inventa, pero tampoco se explica |
| `villain_stack` | `state[villain_stake]` | ídem | ídem |
| `hero_bet` / `villain_bet` | `state[..._bet]` | contribución registrada y auditoría de apuesta | No se distingue apuesta total de contribución de calle |
| posiciones | `state['btn']` + asientos activos | `rec._hand_positions` | Si el botón no se detecta, quedan `None` aunque la mano tenga posiciones |
| asientos activos | `{pid}_state` | folds registrados, inactivos manuales, jugadores de la mano | Un asiento puede aparecer activo tras un fold |
| secuencia | no existe en `HUState` | `hand['streets'][street]['actions']` con `observed/inferred/ambiguous` | La capa HU no puede reconstruir la secuencia y no debe inventarla |

### 2.3 Sobre el caso de referencia

Estado reportado:

```text
Asientos activos: ('hero', 'p1')
Cartas hero: ('Js', '3s') | board: () | calle: preflop
Pot: 8.0 | to_call: None | stacks: None/38.8 | bets: None/7.5
```

Valores reales confirmados por el usuario:

```text
Cartas hero: Jh, 6h
Pot actual: 4.0
To call: 2.5
```

Lo que puede afirmarse con la evidencia actual:

1. `Js/3s` y `8.0` son valores **brutos** de OCR. La capa HU no los inventa:
   `interpret_state()` los copia de `state['hero_cards']` y `state['pot']`.
2. `to_call=None` es una abstención de la capa HU porque `hero_bet` es `None`:
   la fórmula actual solo calcula si ambas apuestas están presentes.
3. `hero_stack=None` impide además que `HUState` llegue a `ready`; el estado
   queda `unresolved` y no debería producir una predicción registrable.
4. La captura que produjo exactamente ese estado no está identificada en el
   repositorio. Se revisaron 129 imágenes candidatas; solo 4 tenían
   `('hero','p1')` activos y ninguna coincidía con pot 8.0, P1 bet 7.5,
   P1 stack 38.8 y cartas Js/3s. Sin la imagen y el estado bruto de esa captura
   no se puede demostrar la causa raíz de cartas y bote.

Hipótesis que deben probarse con la captura de referencia, no asumirse:

- desplazamiento/redimensionado de la mesa: `HERO_REGION` y los píxeles de palo
  son absolutos; un cambio de geometría afecta a cartas y a todos los ROI;
- error de OCR en el rango derecho (6→3) y fallback de palo a `s` por píxeles
  que no cumplen ni blanco ni rojo;
- lectura del bote en una región que contiene otra cantidad de la mesa, o
  escala distinta de la calibración;
- contribuciones del recorder derivadas de las mismas apuestas erróneas, por
  lo que no son una verdad independiente.

No se aplicará división por dos, corrección constante ni sustitución de cartas
sin demostrar el origen.

---

## 3. Diseño de integración propuesto

### 3.1 Principios

1. **Un solo dueño de la detección**: el recorder original.
2. **La capa HU no vuelve a detectar** píxeles, cartas, botones, botes ni
   apuestas.
3. **Procedencia explícita**: cada campo declara `ocr`, `recorder`,
   `derived`, `manual` o `unknown`.
4. **Desconocido sigue desconocido**: no se convierte `None` en 0.
5. **Contradicción ⇒ abstención**: si OCR y recorder discrepan más allá de una
   tolerancia declarada, el estado queda `unresolved` y no se predice.
6. **Aislamiento**: ningún camino escribe en `data/`.
7. **Sin F9-B, sin manos reales, sin piloto** en esta fase.

### 3.2 Componentes nuevos (diseño, no implementados)

#### `RecorderSnapshot`

`dataclass(frozen=True)` construido después de `process_frame()`. Debe
conservar, sin reinterpretar:

```text
frame_id / captured_at / frame_sha256
raw_state                         # dict bruto de capture_live
hand_id / hand                    # contrato del recorder
street / board_recorded
button_seat
players: [
  pid, seat, position, active, folded, allin,
  stack_read, stack_start, bet_read, contribution_street,
  cards_frozen, cards_read, card_source
]
pot_read / pot_calculated / pot_live_calculated / pot_audit
to_call_derived / to_call_raw / to_call_source
actions_by_street                # observed/inferred/ambiguous
ambiguities
observed_fields / unknown_fields / contradictions
```

`RecorderSnapshot` no decide; solo congela evidencia.

#### `SnapshotLiveRecorder`

Subclase experimental de `LiveRecorder`:

```text
class SnapshotLiveRecorder(LiveRecorder):
    def process_frame(self, state, img_arr, log=print):
        super().process_frame(state, img_arr, log=log)
        self.last_snapshot = build_snapshot(self, state, img_arr)
```

No se modifica `recorder_live.py`. La subclase se inyecta como
`engine.rec`, igual que ya hace `LiveParityAssistant.ensure_engine()`.

Ventaja: el motor original sigue llamando a `self.rec.process_frame()` una sola
vez. No hay doble procesamiento.

Alternativa si se necesita bloquear la recomendación antes de calcularla:

- llamar `rec.process_frame()` explícitamente;
- construir el snapshot y la puerta HU;
- llamar `engine.step()` con un flag `_skip_process_once` en la subclase para
  que no vuelva a procesar el frame;
- restaurar el flag en `finally`.

Se documenta como opción B. La opción A (hook post-`process_frame`) es la
recomendada porque conserva exactamente el orden del motor original.

#### `interpret_recorder_snapshot(snapshot) -> HUState`

Sustituye a `interpret_state(raw_state)` en el camino de paridad. Debe producir
un `HUState` extendido con:

- `provenance: Mapping[str, str]`
- `unknown_fields: Tuple[str, ...]`
- `contradictions: Tuple[str, ...]`
- `sequence_status` y `actions` (o una estructura separada)

Reglas por campo:

| Campo | Prioridad | Regla |
|---|---|---|
| `hero_cards` | `hand.players[hero].cards` → `state[f'{hero}_cards']` → `state['hero_cards']` | Si dos fuentes difieren: `cards_contradiction` y `unresolved`. No sustituir. |
| `board` | `hand.streets[street].board` → `state['community']` | Si difieren: `board_contradiction`. La calle sale del recorder, no solo del conteo. |
| `pot` | `pot_read` y `pot_live_calculated` | Si ambos existen y `abs(diff) > max(0.5, 0.05*pot_read)`: `pot_contradiction` y abstención. Si solo hay uno, se usa con `provenance`. |
| `to_call` | contribuciones de la calle actual | `max(opponent_contrib - hero_contrib, 0)` si ambas existen. Si falta una: `unknown`. Si `bet` bruto y contribución discrepan: `to_call_contradiction`. |
| `hero_stack` | `state['hero_stake']` | Se conserva el valor; si `None`, desconocido. No se suma la apuesta. |
| `villain_stack` | `state[villain_stake]` | Ídem. |
| `positions` | `rec._hand_positions` con `hand` activo | Si no hay mano: `rec._assign_positions(state)` solo si el botón es válido. Si no hay botón: desconocido. |
| `button_seat` | `hand.btn_player` → `state['btn']` | Debe pertenecer a los asientos activos. Si no: `button_not_in_hand`. |
| `active_seats` | `hand.players` + `state` + folds registrados | Exactamente dos activos. Si el OCR y el recorder discrepan: `active_count_contradiction`. |
| `street` | `hand.current_street` | Verificar que el board registrado sea compatible. Si no: `street_contradiction`. |
| `sequence` | `hand.streets[street].actions` | Copiar con `observed/inferred/ambiguous`; no reconstruir en la capa HU. |

#### `DecisionStateView`

Vista normalizada para el motor original. Solo se construye si la puerta HU
pasa y no hay contradicciones bloqueantes.

Debe conservar:

- `pot` con procedencia;
- `bets` con procedencia;
- `stacks` con procedencia;
- `hero_cards` y `board` con procedencia;
- `positions` y `button` del recorder;
- `actions` del recorder.

Si un campo es contradictorio, no se “elige el más bonito”: se bloquea la
predicción con un motivo inspeccionable.

### 3.3 Flujo de una captura

```text
1. capture_live.capture()                     # una sola vez
2. SnapshotLiveRecorder.process_frame()       # una sola vez
3. build_snapshot()                           # congela OCR + recorder
4. interpret_recorder_snapshot()              # HUState + procedencia
5. puerta HU:
   - exactamente 2 activos
   - hero y rival identificados
   - botón dentro de los activos
   - cartas 2 y board válido
   - calle coherente
   - pot/to_call no contradictorios
6. si pasa: DecisionStateView -> motor original -> predicción provisional
   si no pasa: abstención con motivo; no se invoca recomendación
7. persistencia aislada solo si el operador lo pide
```

### 3.4 Política de posiciones HU

- `live_default`: usar las posiciones del recorder tal cual. Es diagnóstico,
  no paridad HU.
- `hu_sb_bb`: exigir botón identificado y dentro de los dos activos. Asignar
  botón = SB y el otro = BB. No forzar posiciones si el botón falta o está
  fuera.
- No inferir el botón por stack, nombre ni orden de asientos.
- La puerta de turno debe usar `_hu_next_to_act`/`_hu_hero_act`, no el orden
  6-max del recorder.
- Si el recorder ya tiene `_hand_positions`, esa es la fuente; si no, y hay
  botón válido, usar `_assign_positions`. Si no hay ninguna, desconocido.

### 3.5 Política de bote y `to_call`

Bote:

- `pot_read` es OCR; `pot_live_calculated` es derivado de acciones.
- No se suman contribuciones dos veces: `_street_contributions()` ya devuelve
  importes absolutos por posición y `_pot_breakdown()` ya aplica devoluciones.
- Si `pot_read` y `pot_live_calculated` difieren más de la tolerancia, no se
  corrige: se marca `pot_contradiction` y se abstiene.
- No se divide por dos ni se aplica una constante.

`to_call`:

- Es exclusivamente el importe adicional que el héroe necesita aportar para
  igualar la apuesta vigente.
- Se calcula con contribuciones absolutas de la calle actual:
  `max(contrib_opponent - contrib_hero, 0)`.
- Si falta la contribución del héroe o del rival, `None`.
- Si las apuestas brutas y las contribuciones discrepan, `to_call_contradiction`.
- No se usa el tamaño del bote ni la apuesta total del rival como `to_call`.

### 3.6 Política de cartas

- Prioridad: cartas congeladas en `hand['players'][hero].cards`.
- Respaldo: `state[f'{hero_pid}_cards']`, luego `state['hero_cards']`.
- Si las fuentes discrepan, `cards_contradiction` y `unresolved`.
- No se sustituyen cartas dudosas por otras.
- Si no hay confianza, se declara `confidence=unknown`; no se inventa.
- El board se trata igual, con prioridad al board registrado por calle.

### 3.7 Aislamiento y efectos secundarios

- `parity_hands_path` permanece dentro de `runtime_dir`; `data/hands_db.jsonl`
  siempre se rechaza.
- `ambiguity_capture_dir` en `runtime_dir/ambiguedades`.
- Diagnóstico de cartas/regiones en `runtime_dir/diagnostico/<frame_id>/`, con
  `frame_sha256`, recortes y estado bruto. No se mezcla con manos reales.
- `capture_dir=None`: no se guardan todos los frames.
- No se escribe en `data/decisions.jsonl`; `SnapshotCollector` retiene el
  snapshot en memoria y, si se habilita, escribe en
  `runtime_dir/decisions_parity.jsonl`.
- `on_hand_finalized` sigue siendo experimental. Si se quiere modo
  “sin registro de manos”, el `output_path` del recorder debe apuntar a un
  archivo de diagnóstico aislado o desactivarse; no a `data/`.
- Guardar/restaurar `MANUAL_POSITIONS`, `MANUAL_CARDS`, `MANUAL_INACTIVE` y
  `PLAYER_NAMES` alrededor de cada frame.
- Mantener los locks: el recorder y el motor no son thread-safe.

---

## 4. Plan de pruebas (diseño)

### 4.1 Unitarias, sin captura real

- Snapshot con estado bruto + mano sintética: extracción de cada campo.
- Cartas correctas, cartas de asiento equivocado, palo incorrecto.
- Bote duplicado, bote incompleto, bote solo OCR, bote solo calculado.
- `to_call` correcto, `to_call` desconocido, contribución ausente.
- Botón fuera de los activos, botón ausente, posiciones desconocidas.
- Asientos vacíos, más de dos activos, estado incompleto.
- Contradicción OCR vs recorder: abstención, no corrección.
- `hu_sb_bb` vs `live_default`: posiciones y turno.
- Garantía de no escritura en `data/`.

### 4.2 Integración secuencial

Con una captura almacenada y autorizada:

1. Ejecutar el camino original sobre el frame.
2. Congelar `rec.hand`, `last_state`, `_hand_positions`, `_pot_breakdown`,
   `_street_contributions`.
3. Ejecutar el camino experimental sobre el **mismo** frame almacenado.
4. Comparar campo por campo con `compare_frame_state`.
5. No capturar la pantalla simultáneamente con dos asistentes.

### 4.3 Criterios de aceptación

- Mismo frame ⇒ mismo snapshot ⇒ mismo `HUState` (determinista).
- Ningún campo desconocido se convierte en cero.
- Toda contradicción produce abstención con motivo.
- `data/` permanece con hash idéntico.
- Los archivos originales conservan su hash.
- No se activa F9-B ni se registran manos reales.

---

## 5. Decisiones pendientes antes de implementar

1. **Fork de aplicación vs copia literal**: se recomienda mantener el fork de
   aplicación y añadir `SnapshotLiveRecorder` + `interpret_recorder_snapshot`.
   Copiar las 2.255 líneas del motor crearía dos verdades divergentes.
2. **Persistencia de manos experimentales**: definir si el recorder debe
   finalizar y escribir manos en `runtime_dir` o si se desactiva por completo
   en modo diagnóstico. Recomendación: modo diagnóstico con escritura aislada
   y sin registro real.
3. **Recomendación con estado normalizado**: definir si el motor original debe
   recibir `DecisionStateView` (recomendado, con contradicciones bloqueantes) o
   seguir recibiendo el estado bruto y usar el snapshot solo para visualización.
4. **Captura de referencia**: hace falta la imagen y el estado bruto exactos del
   caso `Js,3s / pot 8.0 / to_call 2.5` para demostrar la causa raíz de cartas y
   bote. Sin ella no se puede certificar la corrección.
5. **Autorización de implementación**: no se implementa nada hasta recibir
   instrucción explícita.

---

## 6. Limitaciones abiertas

- No se ha reproducido el caso de referencia desde una imagen del repositorio.
- No se ha medido latencia real de captura/OCR en la mesa del usuario.
- No se ha validado paridad postflop real.
- No se ha demostrado que la exclusión del asistente original sea enforceable;
  sigue siendo una política operativa, no una garantía técnica.
- La política de datos históricos (`hands_db`, sidecars, manifiesto) sigue sin
  resolverse.
- `data/decisions.jsonl` contiene 10 eventos `H_1375` de una ejecución manual
  del asistente original; no se revirtieron y no deben incluirse en un commit
  de esta fase.

---

## 7. Conclusión

La reutilización correcta no es “usar `capture_live.capture()` y luego
interpretar el dict bruto”. Es **dejar que el recorder original construya su
estado completo y hacer que la capa HU consuma ese estado con procedencia y
abstención**.

La implementación propuesta no añade un segundo OCR ni un segundo recorder:
añade un snapshot congelado y un adaptador de interpretación. El motor original
sigue siendo el único que detecta y recomienda.

No se declara superada la fase: cartas, bote y `to_call` no se han reproducido
todavía desde la captura de referencia.
