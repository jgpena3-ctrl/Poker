# FASE 10.5 — Puente de snapshot del recorder

## Estado

Implementación técnica en el árbol de trabajo, **sin declarar Fase 10.5
aceptada ni certificada**. No se inició F9-B, no se capturó una mesa real, no
se registraron manos reales y no hubo commit ni push.

Antes de modificar código se confirmó:

- HEAD `00b1f9186f14598ca37797d21f13daf8f62f90f1`, en `main`; `origin/main`
  apunta al mismo commit.
- Commits recientes: `00b1f91` (HU live parity/polling/auditoría), `286801b`
  (asistente HU experimental y reporte de paridad), `eaeac11` (contratos de
  rangos HU y escenarios HU-P5).
- `00b1f91` fue creado por Jorgito el 16-11-2026 y es el HEAD recibido; no se
  reescribió ni se hizo checkout/reset.
- El trabajo Fase 10.4 y los demás cambios previos del usuario se conservaron.
  `data/decisions.jsonl` mantiene 11 eventos manuales `H_1375` (5 decisiones y
  5 resoluciones del 17-11, más 1 decisión del 18-11) producidos por una
  ejecución manual del asistente original; no se revirtieron, no se
  incorporaron a esta implementación y no se commitean.

## Flujo implementado

1. `HUCaptureAdapter` produce un `CapturedFrame` usando el punto de captura
   original.
2. Frames rechazados por frescura/secuencia conservan un snapshot diagnóstico
   no procesado y no mutan el recorder.
3. Para cada frame aceptado, `SnapshotLiveRecorder.process_frame()` delega una
   sola vez al `LiveRecorder.process_frame()` original, con una copia de nivel
   superior del estado para aislar sus mutaciones internas.
4. Se congela un `RecorderSnapshot` con hash de estado/imagen, timestamp y
   origen, estado bruto y copia entregada al recorder, mano/acciones, cartas
   OCR y reconstruidas, botón/posiciones, activos/folded/inactivos/all-in,
   stacks/apuestas, contribuciones por jugador y calle, bote leído/calculado,
   `to_call`, ambigüedades, contradicciones y campos ausentes.
5. `interpret_recorder_snapshot()` construye `HUState` exclusivamente desde
   `RecorderSnapshot.decision_view` (`DecisionStateView`). El motor original
   continúa recibiendo el estado bruto, sin que la vista HU lo reemplace.
6. La puerta HU se evalúa después del snapshot. Si no hay exactamente dos
   jugadores o existen contradicciones/datos bloqueantes, no se llama al motor
   para producir una recomendación.
7. Si la puerta permite analizar, `Asistente.step()` recibe el estado bruto;
   su llamada interna a `process_frame()` queda suprimida. Las pruebas
   distinguen una ejecución real y una invocación interna no ejecutada: por
   ciclo aceptado, `process_frame_executions == 1`.

La extensión mínima frente al acoplamiento `Asistente.step()`/recorder es el
context manager `SnapshotLiveRecorder.suppress_processing()`. No se copió ni
modificó un método completo del motor original.

## Aislamiento de persistencia

En modo diagnóstico, la instancia del recorder:

- intercepta guardado de frames, evidencias de ambigüedad y resultados de
  sesión;
- redirige la escritura de finalización a `os.devnull`, conserva el hand
  finalizado en memoria y no propaga callbacks externos de guardado;
- no conecta un `DecisionLog` secundario: `SnapshotCollector` opera solo en
  memoria y `engine.shadow` queda desactivado;
- no convierte finalizaciones/acciones reales en eventos `HU_OUTCOME`
  automáticos. Los eventos posteriores requieren `record_outcome()` explícito.

El registro prospectivo de predicciones permanece separado del hand DB
histórico. Las pruebas guardan las escrituras bajo `data/` y verifican hashes;
finalizar una mano sintética no crea `hands_bridge.jsonl`, `decisions_parity`
ni directorios de evidencia.

## Pruebas ejecutadas

- `python -m pytest motor/test_hu_recorder_bridge.py motor/test_hu_parity.py motor/test_hu_experimental.py -q`:
  **83 passed**.
- `python -m pytest motor -q -k "hu"`: **220 passed, 1 skipped**.
- `python -m compileall -q` sobre los módulos modificados: correcto.
- `motor/hu_parity/testdata/stored_frame.json` es un estado sintético guardado;
  no se encontró una captura real almacenada apta para reproducir el caso de
  referencia.

Las pruebas cubren ejecución única/supresión del segundo procesamiento,
estado bruto sin mutar, snapshot inmutable, timestamp/hash de frame, posiciones,
acciones y contribuciones por calle, `to_call` conocido/desconocido, discrepancia
OCR-recorder de cartas y bote, botón fuera de jugadores activos, board
incompleto, abstención sin recomendación, finalización no persistente, registro
posterior explícito, cero de contribución postflop derivado del ledger de
acciones (con procedencia y sin pisar apuestas OCR) y normalización del board
acumulado de turn/river en la copia de mano que consume el motor.

## Estado de archivos protegidos

No se modificaron `motor/asistente_live.py`, `motor/asistente_live_gui.py`,
`recorder/recorder_live.py` ni `tools/capture_live.py`. `data/hands_db.jsonl`
permanece intacto. `data/decisions.jsonl` ya estaba modificado antes de esta
fase por una ejecución manual del asistente original (11 eventos `H_1375`) y
sigue sin commitear; este trabajo no lo tocó. Hashes del árbol de trabajo:

| Archivo | SHA-256 |
|---|---|
| `data/hands_db.jsonl` | `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E` |
| `data/decisions.jsonl` | `122C71F28B1952DB371322D0C36D051800F73FC85958C72BD6CB690C94A3EAAD` |
| `motor/asistente_live.py` | `0524A29CDC2A71C1E237D31C2D46158390D12FA5084115B13D6F4C6EC5C7A788` |
| `motor/asistente_live_gui.py` | `7B65DF5E9DA8EF1E548987FC77438072F64CBB962122B5BB955A45442D7F53EF` |
| `tools/capture_live.py` | `26EF5B006DAF35967A26FEE9B4A8AE88D8A2A0FBE96A9CAB8E3277ADEFA4E72B` |
| `recorder/recorder_live.py` | `7AAAED26A73D8EA130950D0E1CB255920CD3E3BAD27CE9E49C0933C31F28386E` |

## GUI compacta y flujo operativo

La GUI de paridad (`motor/hu_parity/gui_parity.py`, entrada
`python -m motor.hu_experimental_parity_gui`) se rehizo como panel compacto:

- Ventana sin bordes de 367×719 px anclada al borde derecho
  (`x = screen_width - 367`, `y = 0`). Cabe en el espacio libre de 368×719 y
  no cubre los ROIs de captura (el ROI más a la derecha termina en x=998).
  `HU_GUI_WIDTH`, `HU_GUI_HEIGHT`, `HU_GUI_X`, `HU_GUI_Y`,
  `HU_GUI_BORDERLESS` y `HU_GUI_TOPMOST` permiten ajustarla; el título se
  puede arrastrar y `✕` cierra.
- Un único flujo: `Iniciar` prepara lectores y motor en un hilo, adquiere la
  guardia de sesión y arranca el polling. `Detener` lo para y libera la
  guardia cuando el ciclo en curso termina. `Capturar ahora` hace una sola
  captura manual.
- Panel "Mesa": calle, mano, posiciones, cartas, board, bote, `to_call`,
  stacks y apuestas. Panel "Recomendación": acción provisional y equity/estado.
  Panel "Necesito de ti": motivos de bloqueo en lenguaje operativo y registro
  de la acción observada del rival. Pestañas "Detalle" (estado bruto,
  snapshot, contradicciones) y "Avanzado" (control manual, integridad, backup).
- La GUI no corrige el estado, no reemplaza el snapshot y no ejecuta acciones.

### Uso

1. Abrir con `python -m motor.hu_experimental_parity_gui`.
2. La ventana arranca sola ~1 s después de abrirse; si no, pulsar `Iniciar`.
3. Jugar la mano: la GUI muestra la lectura y la recomendación sin pedir nada.
4. Si aparece una pregunta en "Necesito de ti", resolverla antes de seguir. Para
   un resultado pendiente: elegir la predicción (muestra mano/calle/acción),
   marcar la acción observada del rival con los botones rápidos o el
   desplegable y pulsar `Registrar`. `unknown` y la exclusión de la pestaña
   "Avanzado" son registros explícitos, no inferencias.
5. `Detener` termina el polling; `✕` cierra. El título se puede arrastrar para
   mover la ventana; `HU_GUI_X`/`HU_GUI_Y` fijan otra posición.

La preparación pesada corre fuera del hilo de Tk; los resultados del worker se
entregan por una cola drenada con `after` (no se llama `after` desde otros
hilos). Un `Detener` durante la preparación cancela el arranque pendiente y no
deja el lock de captura tomado.

### Reconciliación de resultados

El asistente bloquea el reinicio si hay predicciones previas sin outcome. La
GUI consulta `LiveParityAssistant.pending_outcome_ids()` y `pending_outcomes()`
(solo lectura), muestra la mano/calle/acción de cada pendiente en "Necesito de
ti" y exige que el operador marque la acción observada y pulse `Registrar`.
`record_outcome()` escribe el evento explícito y descuenta la predicción de la
lista de reconciliación; cuando no quedan pendientes, el polling se reanuda.
No se crean outcomes automáticos ni se asocian manos por tiempo.

## Modo operativo 6-max con situación HU

La mesa del operador es siempre 6-max. La condición operativa no es "mesa HU"
sino **exactamente 2 jugadores activos en la mano**. El modo por defecto es
`hu_in_6max`:

- usa las posiciones y el orden 6-max del motor original, sin `MANUAL_POSITIONS`
  ni corrección SB/BB;
- exige 2 activos, cartas del hero, `to_call` trazable (OCR o ledger de
  acciones del recorder) y ausencia de contradicciones bloqueantes;
- deja que `Asistente.step(require_turn=True)` decida el turno con el orden
  6-max; no aplica la puerta de orden postflop HU de `hu_sb_bb`;
- persiste la predicción y permite `record_outcome()` explícito.

`hu_sb_bb` sigue disponible para una mesa realmente HU (SB/BB y orden postflop
HU) y `live_default` sigue siendo diagnóstico, no persistente. La diferencia
entre la posición HU y la live se declara en la predicción
(`position_mode`, `position_correction=none_live_6max_positions`,
`position_mapping_live_btn_vs_hu_sb`); no se corrige el estado en silencio.

### Evidencia H_1374 (replayer 6-max)

Las 8 capturas `capturas/juego/H_1374` se reprodujeron en secuencia (26→33) con
el lector original y `LiveParityAssistant(parity_position_mode='hu_in_6max')`:

| Captura | Activos | Resultado |
|---|---|---|
| 26 | hero,p3,p4,p5 | `not_heads_up:4_active`, sin recomendación |
| 27 | hero,p3,p4 | `not_heads_up:3_active`, sin recomendación |
| 28 | hero,p3 | **recomendación live `subir`** (frecuencias 0.75 subir / 0.25 igualar) |
| 29 | hero,p3 | flop; `to_call=0.0`; aún no es el turno del héroe (p3 actúa primero) |
| 30 | hero,p3 | flop; p3 apuesta `6.7`; `to_call=6.7`; **recomendación live `call`** |
| 31 | hero,p3 | turn; `to_call=0.0`; aún no es el turno del héroe (p3 actúa primero) |
| 32 | hero,p3 | turn; p3 apuesta `18.1`; `to_call=18.1`; **recomendación live `call`** |
| 33 | p3 | `hand_finalized_during_capture_cycle` |

La captura 28 es el momento HU dentro de la mano 6-max: el motor original
recomienda con las posiciones live (`hero=BTN`) y la puerta no fuerza SB/BB.

En flop/turn el OCR no observa una apuesta del héroe (`hero_bet=None`). El
snapshot no convierte ese campo ausente en cero. Lo que se usa es el **ledger de
acciones del recorder**: si la mano grabada existe, el héroe está activo, no
está all-in, no tiene ninguna acción en la calle actual (o solo checks), el OCR
no observó una apuesta suya y no hay contradicción, entonces su contribución
postflop es `0.0`. Esa contribución se marca con procedencia
`recorder_action_ledger_zero` y el `to_call` con
`recorder_action_ledger`; el `raw_state['hero_bet']` sigue siendo `None`. Si
falta la mano/ledger, hay un call/raise sin contribución, una apuesta OCR
observada o un all-in, no se aplica el cero y la puerta se abstiene como antes.

La reproducción secuencial también muestra que el bote queda dentro de
tolerancia (captura 30: lectura 28.5 / calculado 28.4; captura 32: 53.3 / 53.2).
La contradicción `pot_read_vs_calculated` que aparecía al reproducir solo las
capturas 29–32 era un artefacto de empezar a mitad de mano, sin el preflop que
aporta las contribuciones previas; la mesa live siempre entrega la secuencia
completa. Si el bote real difiere más allá de la tolerancia, la puerta sigue
absteniendo.

Al habilitar el turn apareció además un fallo del motor original ajeno a la
paridad: `_villain_postflop_actions()` lee `streets[street]['board']`, pero el
recorder guarda solo la carta nueva en turn/river. Con 2 cartas del héroe + 1
carta de board, `hand_evaluator.evaluate_n_batch` recibía `n=3` y lanzaba
`KeyError: 3`; el motor devolvía `error: 3` y no había recomendación. El bridge
normaliza **solo la copia de mano que consume el motor**, completando el board
acumulado de turn/river (`flop + turn`, `flop + turn + river`); no modifica
`motor/asistente_live.py`, `recorder/recorder_live.py` ni el estado OCR crudo.
Con esa normalización la captura 32 recomienda `call` (EV call 21.96, fold 0.0,
raise 5.98, all-in -8.02).

La mano canónica `H_1374` de la DB sigue con turn `2s` y `Pippocho` inactivo,
mientras las capturas muestran turn `5c` y `Rafaaa13` inactivo. Esa
contradicción no se corrigió: escribir en `data/` requiere autorización. La
reproducción no escribió en `data/`, `trabajo/`, registro ni plantillas: usó un
runtime y un directorio `unknown` temporales.

## Diagnóstico de la lectura OCR (H_1372)

Las 8 capturas `capturas/juego/H_1372/Captura de pantalla (17..24).png` no son
comparables con las referencias calibradas: el contenido de la mesa está
comprimido ~1.9% en vertical y los glifos miden 11 px frente a los 12 px de las
plantillas. El lector no está roto: sobre `capturas/juego/mano1 (0..5).png`
sigue leyendo cartas y board correctamente. Los errores observados en H_1372
(`Js,3s` por `Jh,6h`, `181/182` por `101`, `5→9`, `0→8`) se explican por ese
desfase de renderizado y por ROIs absolutos que recortan filas del glifo.

No se modificó el lector ni se recalibraron plantillas. En operación normal la
lectura actual es correcta; si el renderizado vuelve a cambiar, la puerta HU
abstiene por contradicción OCR-recorder en lugar de recomendar con datos
dudosos. H_1372 es una mano 6-max con más de 2 jugadores activos en las
capturas; la puerta abstiene por `not_heads_up`, no por ser 6-max. Si esa mano
llega a 2 activos, `hu_in_6max` recomienda usando las posiciones y el orden de la
mesa, con la misma exigencia de `to_call` derivable de forma trazable (OCR
observado o ledger de acciones del recorder, nunca un cero inventado).

## Limitaciones pendientes

- La certificación OCR con capturas reales alineadas sigue pendiente: las
  capturas `H_1372` aportadas están desplazadas y no permiten validar la
  generalización del lector. El caso de referencia (cartas `Jh,6h`, bote
  `4.0`, `to_call=2.5`) está confirmado contra la DB y las imágenes, pero no
  se usa para forzar una recomendación.
- La operación real de la GUI compacta en mesa (posición exacta, foco, DPI y
  no interferencia con la captura) no está validada; solo se comprobó el
  layout 367×719 y el flujo con asistentes simulados.
- Latencia real, operación GUI en mesa, paridad postflop real y política de
  conservación de evidencia no están validadas.
- La colección completa del repositorio sigue afectada por los bloqueos
  preexistentes documentados en el inventario Fase 10.5.

Por estas limitaciones la entrega es una implementación aislada con pruebas
sintéticas, no una aceptación operativa o estratégica de Fase 10.5.
