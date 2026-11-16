# Fase 10 — Informe separado: paridad funcional con `asistente_live`

Fecha: 2026-11-16

Estado: **informe técnico, sin implementación**. No se ejecutó captura real, no
se inició F9-B y no se modificó `data/`.

Hash de `data/hands_db.jsonl` al emitir este informe:

```text
3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E
```

Este documento responde a la solicitud de que el asistente experimental
funcione **tal como funciona `asistente_live`**, con solo los cambios necesarios
para cubrir los requisitos de las pruebas, y permitiendo que las manos sigan
registrándose en `data/hands_db.jsonl`.

---

## 1. Resumen ejecutivo

1. La implementación actual de Fase 10 **no es paridad con `asistente_live`**:
   usa un prior plano, no usa el modelo de perfiles PEZ/TIBURON, no modela la
   respuesta del rival y no mantiene el estado de mano del recorder.
2. La paridad es técnicamente posible **sin modificar**
   `motor/asistente_live.py`, `motor/asistente_live_gui.py`, el recorder ni el
   OCR originales. Se puede construir un adaptador nuevo que instancie y use el
   motor original.
3. El obstáculo central es que **el motor live está acoplado al recorder**:
   `Asistente.recomendacion()` lee `self.rec.hand` para resolver el spot
   preflop, las acciones postflop, las posiciones y el contexto de la mano. No
   alcanza con reutilizar los modelos: hay que ejecutar también el seguimiento
   de mano del recorder.
4. Como el recorder original escribe en `data/hands_db.jsonl` al finalizar una
   mano, aceptar “las manos siguen en el hand_db” implica aceptar que el hash
   declarado cambiará y que habrá que actualizar el manifiesto de integridad
   mediante un procedimiento versionado. No se puede mantener a la vez la regla
   actual de hash inmutable y la escritura de manos nuevas.
5. La recomendación técnica es un **adaptador de paridad con puerta HU**
   (opción A), no copiar el motor ni sustituir sus modelos. La alternativa de
   solo observar `decisions.jsonl` (opción B) es más barata y exacta, pero no
   garantiza por sí sola el bloqueo HU ni la persistencia prospectiva antes de
   la acción posterior.

No se ha implementado ninguna de estas opciones en este informe.

---

## 2. Qué significa “tal cual `asistente_live`”

Para este informe, paridad significa:

- misma captura/OCR y mismo estado observado;
- mismos modelos PEZ/TIBURON construidos desde `data/hands_db.jsonl`;
- misma resolución preflop por matrices y mismo muestreo ponderado;
- mismo rango postflop, misma respuesta del rival vía `OracleResponse`, mismas
  reglas y mismo cálculo de EV;
- mismo seguimiento de mano y mismo registro en `data/hands_db.jsonl`;
- misma GUI operativa: inicializar, capturar, nombres, cartas manuales,
  posiciones, inactivos, ganador, guardar mano y cancelar mano;
- mismas deducciones de turno y de cambio de mano que usa el asistente live.

No significa necesariamente:

- ejecutar el mismo archivo de GUI sin cambios;
- mezclar el registro prospectivo experimental con `hands_db`;
- convertir automáticamente la recomendación live en una decisión
  `demonstrated` del registro HU;
- activar multiway;
- usar serving, `recommend_loop` o ejecutar acciones de poker.

### 2.1. Paridad de salida no es paridad de estatus probatorio

`asistente_live` produce una **recomendación operativa**. El registro
prospectivo certificado distingue entre:

- `selected_action`: decisión `demonstrated` según el contrato de evaluación;
- `provisional_selected_action`: selección no demostrada.

Aunque el motor live sea el mismo, su recomendación **no debe etiquetarse como
`demonstrated`** solo por provenir de `asistente_live`. La forma conservadora de
mapearla es:

- mostrar la recomendación live como recomendación operativa;
- persistirla como `provisional_selected_action`;
- dejar `selected_action = None` salvo que además pase el contrato certificado
  de Fase 8.

Esto preserva la paridad visible sin falsear el registro.

---

## 3. Hecho central: el motor live depende del recorder

La inspección de `motor/asistente_live.py` muestra que:

- `Asistente.__init__` crea `LiveRecorder()` y `DecisionLog()`;
- `Asistente.step()` primero llama a `self.rec.process_frame(...)`;
- `Asistente.recomendacion()` obtiene el héroe, el rival y el board, pero
  después `_recomendacion_para()` usa `self.rec.hand` para:
  - resolver el spot preflop (`_preflop_spot`);
  - obtener las acciones postflop del rival;
  - conocer posiciones y acciones previas;
  - calcular la iniciativa y el contexto de la mano;
- `LiveRecorder.finalize_hand()` es quien agrega la mano a
  `data/hands_db.jsonl`.

Consecuencia: **no se puede obtener paridad real llamando solo a
`Asistente.recomendacion()` con un estado suelto**. Sin el estado de mano del
recorder, el spot preflop y el rango postflop pueden quedar distintos. La
paridad exige ejecutar `step()` o reproducir su secuencia de recorder + motor.

Esto también explica por qué “las manos siguen en el hand_db” no es un agregado
externo: es una consecuencia natural de usar el motor live.

---

## 4. Comparación entre Fase 10 actual y `asistente_live`

| Capacidad | Fase 10 actual | `asistente_live` | Qué se requiere para paridad |
|---|---|---|---|
| Captura/OCR | Adaptador aislado; una captura manual | `capture_live.capture()` y lectores originales | Mantener captura y estado; conservar también la imagen PIL para detección de turno |
| Modelos | Prior plano uniforme | `build_models()`: perfiles PEZ/TIBURON, `ProfileRangeModel`, `Oracle`, `PostflopRangeModel` | Usar `build_models()` o un snapshot equivalente |
| Preflop | `preflop_canonical` si hay acciones; sin recomendación completa | Matrices preflop, cobertura, muestreo ponderado, auditoría de tablas | Llamar al camino preflop original a través de `step()` |
| Postflop | Prior plano, sin respuesta del rival, EV simplificado | Rango del rival + `OracleResponse` + `rules_plan` + `compute_evs` | Usar `_recomendacion_para()` original |
| Estado de mano | No se mantiene | `LiveRecorder.process_frame()` | Ejecutar el recorder original en cada frame capturado |
| `hands_db` | No se escribe | `LiveRecorder.finalize_hand()` agrega a `data/hands_db.jsonl` | Permitir escritura y gobernarla |
| Decisiones | Registro prospectivo propio | `DecisionLog` escribe `data/decisions.jsonl` antes del resultado | Decidir si se permite ese sidecar o se redirige/desactiva |
| Shadow logs | No se usan | `ShadowLog` puede escribir `data/shadow_hierarchy.jsonl` | Decidir si se permite o se desactiva con `asistente.shadow = False` |
| Detección de turno | No se usa | `_hero_act(state, pil)` y estado de mano | Conservar `pil` y ejecutar `step()` con `require_turn` correcto |
| Deduplicación | Manual | `last_reco_key` y `force_reco` | Reutilizar la deduplicación o añadir una clave de registro propia |
| GUI | Observación y registro prospectivo | Jugadores, cartas, posiciones, inactivos, ganador, guardar/cancelar mano, auto/manual | Añadir esos controles a la GUI experimental, sin botones de acción |
| Polling | Manual, sin automático | `Asistente.run()` con polling | Añadir modo automático si se quiere registro continuo de manos |
| Multiway | Bloqueado por `interpret_state` | El motor live puede operar multiway según su política | Mantener la puerta HU antes de llamar al motor live |
| Predicción | Persistencia manual posterior al análisis | `DecisionLog` persiste el snapshot al recomendar | Persistir el snapshot antes de la acción posterior; idealmente en el callback `on_reco` |
| Resultado | Evento prospectivo separado | `DecisionLog.resolve_hand()` al finalizar la mano | Componer ambos flujos sin duplicar ni contaminar la predicción |
| Pruebas de aislamiento | Prohíben importar `asistente_live` y recorder | No aplica | Separar pruebas de “modo aislado” y “modo paridad” |

---

## 5. Opciones de arquitectura

### Opción A — Adaptador de paridad con puerta HU (recomendada)

Nuevo módulo, por ejemplo `motor/hu_experimental/parity.py`, que:

1. importa `Asistente` y `build_models` del motor original;
2. valida primero el estado con `interpret_state`;
3. si no hay exactamente dos asientos activos, héroe activo y datos mínimos,
   **no llama al motor live** y registra el motivo;
4. si es HU, llama a `Asistente.step(state, img_arr, pil, ...)`;
5. captura el `EvTable` y la `Situation` mediante el callback `on_reco`;
6. mapea esa salida a un `HUPrediction` y la persiste en el registro
   prospectivo;
7. deja el resultado posterior como `HUOutcome` separado.

Ventajas:

- paridad real con el motor live;
- puerta HU explícita y fallo seguro;
- registro prospectivo integrado;
- no modifica los archivos originales.

Costes y riesgos:

- el adaptador queda acoplado a la API interna de `Asistente` (método `step`,
  callback `on_reco`, `EvTable`, `Situation`);
- el recorder original escribe `hands_db` y posibles capturas de ambigüedad;
- hay que gestionar concurrencia y snapshots de modelos;
- las pruebas actuales de “cero imports live” dejan de aplicar en modo paridad.

### Opción B — Observador de `decisions.jsonl` (mínimo cambio)

Ejecutar `asistente_live`/`asistente_live_gui` sin cambios y añadir un proceso
separado que lea `data/decisions.jsonl`:

- cada evento `decision` se convierte en `HUPrediction`;
- cada evento `resolution` se convierte en `HUOutcome`;
- se conserva el `recorded_at` original y se registra el `decision_id`.

Ventajas:

- paridad exacta por definición, porque no se reimplementa nada;
- no hay que tocar el motor ni el recorder;
- el `DecisionLog` ya escribe antes de la resolución.

Límites:

- el observador no puede impedir que el asistente live recomiende en multiway;
- no hay puerta HU en tiempo real, solo filtrado posterior;
- la predicción se importa después, aunque su `recorded_at` sea anterior;
- la GUI experimental no sería el asistente operativo, sino una capa de
  auditoría.

Esta opción sirve para **auditar** el asistente live, no para sustituirlo por
un asistente experimental HU con fallo seguro.

### Opción C — Mantener el prototipo actual

Ventajas:

- máximo aislamiento;
- no escribe `data/`;
- ya está probado.

Límites:

- no es paridad con `asistente_live`;
- no registra manos en `hands_db`;
- no usaría perfiles ni respuesta del rival.

No cumple la solicitud actual si se exige paridad funcional.

### Recomendación

Si el objetivo es un **asistente experimental HU que se comporte como el live y
además tenga puerta HU y registro prospectivo**, usar la opción A.

Si el objetivo es únicamente **auditar exactamente lo que ya hace el live**,
usar la opción B.

---

## 6. Trabajo mínimo requerido para la opción A

### 6.1. Adaptador de motor

Archivo nuevo propuesto: `motor/hu_experimental/parity.py`.

Responsabilidades:

- construir o recibir los modelos una sola vez;
- instanciar `Asistente` con `verbose=False`;
- no reemplazar el recorder por uno que no escriba manos;
- configurar el recorder antes del primer frame;
- validar HU antes de llamar a `step`;
- ejecutar `step` con `require_turn=False, force_reco=True` en modo manual,
  igual que la captura manual de la GUI live;
- ejecutar `step` con `require_turn=True` si se usa polling automático;
- capturar `on_reco(text, evs, sit, label)`;
- mapear `evs`/`sit` a `HUPrediction`;
- persistir la predicción antes de que el operador registre la acción
  posterior;
- deduplicar para que un doble clic no genere dos predicciones idénticas.

Pseudocódigo mínimo:

```python
class LiveParityEngine:
    def __init__(self, ...):
        self.models = build_models(verbose=False)
        self.asistente = Asistente(models=self.models, verbose=False)
        self.asistente.shadow = False   # solo si no se permiten shadow logs

    def analyze(self, frame):
        hu = interpret_state(frame.state)
        if hu.status != 'ready' or len(hu.active_seats) != 2:
            return blocked(hu)
        pending = None
        def on_reco(text, evs, sit, label):
            nonlocal pending
            pending = (evs, sit, label)
        result = self.asistente.step(
            frame.state, frame.image, frame.pil,
            require_turn=False, force_reco=True, on_reco=on_reco,
        )
        return build_prediction(result, pending, self.asistente.rec.hand)
```

No se debe implementar este pseudocódigo sin resolver antes los puntos de
datos, concurrencia y mapeo de estatus.

### 6.2. Captura y PIL

La captura actual devuelve `state`, `image` (numpy) y tiempos, pero no conserva
la imagen PIL que usa `_hero_act`. Para paridad hay que:

- añadir `pil` a `CapturedFrame`, o
- llamar a `capture_live.capture()` dentro del adaptador de paridad y conservar
  la tupla completa `(state, img_arr, pil)`.

Sin `pil`, la detección de turno del motor live no se reproduce.

### 6.3. Mapeo de la recomendación a `HUPrediction`

Campos mínimos:

| Campo de `HUPrediction` | Origen en el motor live |
|---|---|
| `hero_position` | `sit.position` o `_pos_of(hero_pid)` |
| `canonical_status` | Vista canónica si está disponible; si no, `not_evaluated` |
| `coverage_state` | Auditoría preflop o `unknown` |
| `sequence_status` | `preflop_table_audit`/contrato si está disponible |
| `range_kind` | `profile_range` postflop; `preflop_matrix` en preflop |
| `range_source` | `ProfileRangeModel`/`PostflopRangeModel` y snapshot de decisión |
| `range_provenance` | `evs.model_evidence`, auditoría preflop y snapshot |
| `response_distribution` | `evs.model_evidence.oracle_response` si existe |
| `equity` | `sit.equity` postflop; `None` preflop |
| `equity_scenario` | `showdown_vs_profile_range` postflop; `None` preflop |
| `action_ev` | `evs.ev`; en preflop son frecuencias, no EV |
| `selected_action` | `None` salvo evaluación certificada |
| `provisional_selected_action` | `evs.chosen` |
| `legal_actions` | `evs.candidate_actions` |
| `uncertainty_reasons` | Warnings de OCR, cobertura y respuesta no disponible |
| `pot`, `to_call`, `hero_stack`, `villain_stack` | Estado observado |
| `board`, `hero_cards` | `sit` o `cards_known` del snapshot |
| `prior_actions` | `actions_before_decision` del snapshot |
| `code_version` | Versión del adaptador + versión del motor live |
| `data_snapshot_id` | SHA-256 del snapshot de `hands_db` usado por los modelos |
| `metadata` | `decision_id`, `hand_id`, `engine=asistente_live`, `label`, `action_values_kind` |

Reglas:

- En preflop, `evs.preflop = True` y `evs.ev` contiene **frecuencias**, no EV.
  Hay que persistir `action_values_kind='frequency'`.
- En preflop, `equity` debe quedar `None`; el motor live tampoco calcula equity
  exacta ahí.
- En postflop, `evs.ev` contiene EV y `sit.equity` contiene la equity contra el
  rango del rival.
- `evs.chosen` en preflop es una acción muestreada; hay que persistir
  `evs.preflop_sampling` (semilla, distribución y candidatos).
- `evs.chosen` en postflop es la acción elegida por reglas/EV; no es
  automáticamente `demonstrated` para el registro.

### 6.4. Persistencia antes de la información posterior

El `DecisionLog` original ya persiste un snapshot antes de la resolución. Para
el registro prospectivo hay dos variantes:

- **Automática (recomendada)**: persistir `HUPrediction` dentro de `on_reco`,
  antes de devolver el control a la GUI. Así la predicción queda registrada
  antes de cualquier acción posterior.
- **Manual controlada**: guardar un snapshot congelado en `on_reco` y persistirlo
  solo cuando el operador pulse “Registrar predicción”. Es aceptable si el
  operador no observa la acción posterior antes de pulsar, pero es más frágil.

La variante automática es la única que garantiza el requisito temporal sin
depender del operador.

### 6.5. Deduplicación

`Asistente.step(force_reco=True)` recomputa en cada captura manual. Para no
crear predicciones duplicadas:

- clave propuesta: `hand_id + street + actions_seen_count + hash(estado
  relevante) + versión del motor`;
- guardar la clave en `metadata`;
- si la clave ya existe y no cambió el estado, actualizar la vista pero no
  registrar otra predicción;
- si el operador fuerza una nueva consulta, permitir una nueva predicción con
  un `prediction_id` nuevo y dejar constancia de que es una repetición.

---

## 7. Registro de manos en `data/hands_db.jsonl`

### 7.1. Qué se reutiliza

Se reutiliza `LiveRecorder` sin modificarlo:

- `OUTPUT_PATH` por defecto:
  `data/hands_db.jsonl`;
- `process_frame()` mantiene la mano en memoria;
- `finalize_hand()` agrega una línea JSON al final;
- `on_hand_finalized` resuelve el `DecisionLog`;
- las capturas de ambigüedad pueden escribirse en
  `pruebas/recorder/sesiones/ambiguedades/capturas`.

No se reescriben manos históricas ni se migra el archivo.

### 7.2. Consecuencias obligatorias

1. **El hash cambiará.** El manifiesto de `motor/learn.py`
   (`HANDS_DB_SHA256`, `HANDS_DB_LINEAS`) quedará obsoleto. Hay que actualizarlo
   con el procedimiento versionado que corresponda; no editarlo a mano.
2. **Las pruebas de integridad pueden fallar.** En particular, la prueba que
   compara el hash declarado con el archivo real. Hay que separar:
   - pruebas que verifican que el modo aislado no escribe;
   - pruebas que verifican el modo paridad con un archivo temporal;
   - prueba de sesión real con backup y redeclaración.
3. **Backup previo.** Antes de la primera escritura real: copia de
   `data/hands_db.jsonl`, hash y número de líneas.
4. **Append-only.** No editar, truncar ni reordenar líneas históricas.
5. **Un solo writer.** `LiveRecorder` no tiene bloqueo entre procesos. Si la GUI
   original y la experimental escriben a la vez, pueden duplicar `hand_id` o
   intercalar líneas. Debe haber una regla operativa de un solo asistente
   abierto, o un bloqueo de sesión externo que ambas respeten. El bloqueo del
   adaptador no protege a la GUI original si esta no lo usa.
6. **Cierre de manos.** Para que una mano se guarde hay que ejecutar
   `process_frame` suficientes veces y llegar a `finalize_hand`, o pulsar
   “Guardar mano”. Una captura manual aislada no garantiza el registro
   continuo. Si se quiere “seguir registrando como el live”, hace falta el modo
   automático o capturas manuales sistemáticas.

### 7.3. Sidecars que también escriben

Además de `hands_db`, el motor live puede escribir:

- `data/decisions.jsonl` mediante `DecisionLog`;
- `data/shadow_hierarchy.jsonl` mediante `ShadowLog`;
- `pruebas/recorder/sesiones/ambiguedades/capturas` mediante el recorder.

Si no se autorizan, hay que desactivar o redirigir explícitamente:

- `asistente.shadow = False` desactiva los shadow logs de jerarquía/preflop;
- `POKER_DECISIONS_PATH` permite cambiar la ruta del `DecisionLog` antes de
  construir `Asistente`;
- el recorder de ambigüedades se puede configurar con `ambiguity_capture_dir`
  si se reemplaza el recorder por uno creado con parámetros, pero eso ya no es
  exactamente el `Asistente` por defecto.

Estas decisiones deben tomarse antes de la primera captura.

---

## 8. Modelos y fuga de información

`build_models()` lee `data/hands_db.jsonl` con `load_hands(reliable_only=True)`.
Si el asistente se inicia antes de la sesión y no se reinicia, los modelos
quedan congelados en memoria. Eso es aceptable.

El riesgo aparece si:

- se reinicia el asistente durante la misma sesión, o
- se reconstruyen los modelos después de haber agregado manos de la sesión.

En ese caso, los modelos podrían incluir información posterior a algunas
predicciones.

Requisitos:

- construir modelos una sola vez al inicio de la sesión;
- registrar el SHA-256 y el número de líneas de `hands_db` en
  `data_snapshot_id`;
- no reconstruir modelos durante la sesión;
- si hay que reiniciar, usar una copia congelada de `hands_db` o un builder
  equivalente que acepte una ruta de snapshot;
- documentar el snapshot en cada predicción.

`build_models()` no acepta una ruta por parámetro. Para un snapshot congelado
hay dos alternativas:

1. mantener una sola sesión sin reinicio y usar el archivo real; o
2. añadir un builder nuevo en el paquete experimental que replique las pocas
   líneas de `build_models` usando `load_hands(path=snapshot)` y los mismos
   modelos, con una prueba de equivalencia contra `build_models()`.

No se recomienda modificar `motor/learn.py` ni `build_models()` para esto.

---

## 9. GUI: qué se necesita para que funcione “tal cual”

La GUI experimental actual es de observación. Para paridad operativa debe
incorporar, como mínimo:

- botón “Inicializar lector + modelos”;
- botón “Capturar”;
- selector auto/manual;
- campos de nombre, cartas manuales, posición e inactivo por asiento;
- override de ganador;
- botón “Guardar mano”;
- botón “Cancelar mano”;
- visualización de la mano en curso;
- salida/registro de `hands_db`;
- estado del registro prospectivo y de la integridad.

No debe incorporar:

- botones de fold/call/raise/all-in;
- ejecución automática de acciones;
- conexión a serving o `recommend_loop`.

La GUI original tampoco tiene botones de acción: solo inicia/detiene, captura,
guarda y cancela. La diferencia es que la experimental debe añadir la capa de
registro prospectivo y la puerta HU.

### 9.1. Modo automático

Si se quiere que las manos se registren de forma continua, hay que reutilizar
`Asistente.run()` o un bucle equivalente:

- `step` periódico con `require_turn=True`;
- botón de detención;
- captura exclusiva;
- cierre ordenado que finalice la mano en curso;
- persistencia prospectiva en el callback de recomendación.

Esto cambia el requisito previo de “sin polling automático”. Es una decisión
explícita, no un detalle de implementación.

---

## 10. Pruebas y criterios de aceptación

### 10.1. Pruebas unitarias y sintéticas

1. **Paridad de recomendación**: para un estado sintético y un snapshot de
   modelos fijo, el adaptador produce la misma acción, EVs/frecuencias y
   metadatos que `Asistente.recomendacion()` llamado directamente.
2. **Preflop determinista**: con semilla fija, misma acción muestreada y mismo
   `preflop_sampling`.
3. **Postflop determinista**: con `runout=False` o semilla fija, mismos EVs.
4. **Puerta HU**: 3+ asientos activos, héroe inactivo, cartas ausentes o board
   inválido no llaman al motor live y producen un motivo explícito.
5. **Predicción antes del resultado**: la predicción se persiste antes de que
   exista un `HUOutcome` y no contiene datos posteriores.
6. **Resultado separado**: el `HUOutcome` referencia el `prediction_id` y no
   modifica la predicción.
7. **Deduplicación**: dos capturas idénticas no crean dos predicciones
   idénticas; una repetición forzada queda marcada.
8. **Mapeo de estatus**: la recomendación live queda como `provisional`, nunca
   como `demonstrated` por defecto.
9. **Preflop**: `equity=None` y `action_values_kind='frequency'`; no se inventa
   equity exacta.
10. **Hand DB en temporal**: el modo de prueba escribe en un archivo temporal,
    no en `data/hands_db.jsonl`.
11. **Modo aislado**: el paquete aislado sigue sin importar live/recorder y no
    escribe `data/`.
12. **Sin cambios en originales**: `git diff` no toca
    `motor/asistente_live.py`, `motor/asistente_live_gui.py`, recorder, OCR ni
    serving.
13. **Multiway**: `MULTIWAY_SOPORTADO` sigue en `False`.
14. **GUI**: no hay botones de acción y la captura es explícita o con stop.

### 10.2. Pruebas de sesión real (solo con autorización)

1. Backup y hash previo de `hands_db`.
2. Una sesión HU controlada, sin dinero real.
3. Medición de captura/OCR + motor completo.
4. Verificación de que cada predicción precede a su outcome.
5. Verificación de que las manos se agregaron al final y con esquema válido.
6. Hash posterior y actualización versionada del manifiesto.
7. Restauración desde backup en un entorno de prueba.

### 10.3. Criterios de aceptación

- La misma entrada sintética produce la misma recomendación observable que el
  motor live, con las tolerancias documentadas.
- La predicción se persiste antes de la acción posterior.
- El outcome es un evento separado.
- El modo HU bloquea cualquier estado que no sea exactamente dos asientos.
- Las manos se registran en `hands_db` solo en modo paridad autorizado.
- No se modifica ningún archivo original ni artefacto histórico.
- No se afirma el presupuesto de 8 s sin medición real.

---

## 11. Riesgos y límites

1. **Acoplamiento a API interna.** El adaptador usa `step`, `on_reco`,
   `EvTable`, `Situation` y `rec.hand`. Un cambio futuro en el motor live puede
   romper la paridad; hay que fijar la versión y probar la equivalencia.
2. **Doble writer.** `LiveRecorder` no tiene bloqueo entre procesos. Dos GUI
   abiertas pueden corromper la numeración o intercalar líneas.
3. **Hash y manifiesto.** Escribir manos invalida el hash declarado y puede
   romper pruebas de integridad hasta que se redeclare.
4. **Fuga de información por reinicio.** Reconstruir modelos tras agregar manos
   de la sesión puede introducir información posterior.
5. **Multiway.** El motor live puede calcular multiway; la puerta HU debe
   impedir la llamada, no confiar en la política interna.
6. **Aleatoriedad preflop.** La acción preflop se muestrea. Sin semilla, dos
   capturas del mismo estado pueden diferir; hay que registrar la semilla y no
   presentar la acción como determinista.
7. **Rendimiento.** El motor completo postflop puede tardar más que el prior
   plano; no se conoce el tiempo real con captura/OCR. No se puede afirmar el
   presupuesto de 8 s sin medición.
8. **OCR.** La confianza por carta no está cuantificada; la puerta HU no
   convierte una lectura dudosa en una certeza.
9. **Sidecars.** `decisions.jsonl`, `shadow_hierarchy.jsonl` y las capturas de
   ambigüedad son escrituras adicionales que deben autorizarse o desactivarse.
10. **Estatus probatorio.** La recomendación live no es automáticamente una
    decisión demostrada del registro prospectivo.

---

## 12. Decisiones pendientes del usuario

Para implementar la opción A hace falta autorización explícita sobre:

1. **Importar y usar `motor/asistente_live.py`** desde un adaptador nuevo, sin
   modificarlo.
2. **Permitir que el recorder original escriba** en
   `data/hands_db.jsonl`.
3. **Aceptar que el hash cambiará** y autorizar el procedimiento versionado de
   redeclaración del manifiesto.
4. **Definir sidecars**: permitir o desactivar `data/decisions.jsonl`,
   `data/shadow_hierarchy.jsonl` y capturas de ambigüedad.
5. **Definir modo de captura**: manual, automático o ambos. Sin modo automático
   no se garantiza el registro continuo de manos.
6. **Definir persistencia prospectiva**: automática en `on_reco` (recomendada)
   o manual con snapshot congelado.
7. **Definir concurrencia**: un solo asistente abierto o bloqueo de sesión
   respetado por ambos.
8. **Actualizar las pruebas** para separar modo aislado y modo paridad, y para
   usar archivos temporales en las pruebas de escritura.
9. **Autorizar o no F9-B**. La implementación y las pruebas sintéticas no
   equivalen a un piloto real.

Sin esas decisiones, el cambio no debe implementarse, porque afectaría datos
protegidos y el contrato de auditoría.

---

## 13. Conclusión

La paridad con `asistente_live` no se logra “cambiando solo el modelo” dentro
del prototipo actual. El motor live depende del recorder para construir el
contexto de la mano, y el recorder es el que escribe `hands_db`. Por eso la
paridad exige un adaptador que ejecute el motor original con su estado de mano,
una puerta HU delante y un mapeo conservador hacia el registro prospectivo.

Es técnicamente viable y no requiere modificar los archivos originales. Pero
implica aceptar escrituras en `data/`, cambiar el hash de `hands_db`, coordinar
un solo writer y revisar las pruebas de aislamiento. Nada de eso se ha hecho en
este informe.
