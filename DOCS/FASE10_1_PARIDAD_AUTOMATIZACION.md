# Fase 10.1 — Paridad funcional y automatización del asistente HU

Estado: **implementación experimental, sin piloto real y sin escritura en
`data/` por defecto**.

Esta fase continúa sobre `286801b`. No modifica `motor/asistente_live.py`,
`motor/asistente_live_gui.py`, el recorder original, OCR, captura original ni
el dataset histórico.

## 1. Qué se implementó

### 1.1 Capa separada `motor/hu_parity/`

La Fase 10 se mantiene aislada en `motor/hu_experimental/`. La paridad vive en
un paquete separado para que el paquete aislado no importe el motor live.

| Archivo | Función |
|---|---|
| `motor/hu_parity/parity.py` | Adaptador real sobre `asistente_live.Asistente` + `LiveRecorder`, puerta HU y predicción/resultado. |
| `motor/hu_parity/automation.py` | Polling periódico con parada cooperativa y eventos para la GUI. |
| `motor/hu_parity/comparison.py` | Comparación de reconstrucción de estado: recorder live vs intérprete HU. |
| `motor/hu_parity/gui_parity.py` | GUI experimental de paridad, reutilizando la GUI de Fase 10. |
| `motor/hu_experimental_parity_gui.py` | Entrada: `python -m motor.hu_experimental_parity_gui`. |
| `motor/test_hu_parity.py` | 10 tests de paridad, polling, comparación y seguridad. |

### 1.2 Reutilización real del motor live

`LiveParityAssistant`:

1. Aplica la puerta HU con `interpret_state` **antes** de llamar al motor live.
2. Instancia el `Asistente` original con `build_models`.
3. Sustituye su `DecisionLog` por un `SnapshotCollector` en memoria. Así usa el
   snapshot exacto que el motor live genera antes de recomendar, sin escribir
   `data/decisions.jsonl`.
4. Sustituye su `LiveRecorder` por uno con salida aislada
   (`trabajo/hu_experimental/hands_parity.jsonl` por defecto).
5. Llama a `Asistente.step(...)` con la imagen y la PIL originales, para
   conservar la detección de turno del motor live.
6. Persiste la predicción en el registro prospectivo aislado.
7. Observa acciones posteriores en `rec.hand` y registra un `HU_OUTCOME`
   separado. Si la mano termina, registra resultado final en otro evento.

La recomendación live se guarda como `provisional_selected_action`. Nunca se
convierte automáticamente en `selected_action` ni en decisión demostrada.

### 1.3 Automatización

- `LiveParityAssistant.poll_once()` captura, interpreta, comprueba HU, analiza
  y persiste si aparece una oportunidad nueva.
- `HUPollingController` ejecuta ciclos periódicos en un hilo daemon.
- La GUI de paridad drena eventos con `root.after`, sin bloquear tkinter.
- Un `RLock` en `LiveParityAssistant` serializa análisis, registro y polling
  dentro de un mismo proceso, para que el botón manual y el auto no muten la
  misma mano a la vez.
- La GUI no tiene botones de fold/call/raise/all-in.
- El polling se detiene al cerrar la ventana o con «Detener auto».

### 1.4 Detección de oportunidad y resultado

- La predicción se construye con el snapshot del motor live y se persiste
  antes de observar la acción posterior.
- La acción posterior se detecta comparando las acciones ya vistas en el
  snapshot con las acciones actuales del `LiveRecorder`.
- Si no se detecta una acción concreta, la predicción queda pendiente hasta
  que el recorder finalice la mano; entonces se registra el resultado final.
- El resultado es un evento `HU_OUTCOME` distinto, con `observed_at`,
  `observed_action`, `new_information` y/o `result`.

## 2. Cómo se usa

### GUI de paridad

```powershell
python -m motor.hu_experimental_parity_gui
```

Flujo manual:

1. «Capturar estado»: captura e interpreta.
2. «Analizar»: usa el motor live y muestra la recomendación provisional.
3. «Registrar predicción»: persiste exactamente la predicción congelada.

Flujo automático:

1. «Iniciar auto».
2. El polling captura y persiste predicciones nuevas.
3. «Detener auto» para parar.

### Uso programático

```python
from motor.hu_parity.parity import LiveParityAssistant

assistant = LiveParityAssistant()
analysis = assistant.analyze()
registration = assistant.register_analysis(analysis)
print(registration.prediction_id)
```

## 3. Comparación original vs experimental

`compare_frame_state(state)` alimenta el mismo frame sintético a:

- el `LiveRecorder` original, y
- `interpret_state` de la capa HU.

Compara asientos activos, posiciones, cartas, board, bote, calle, stacks y
apuestas. Las diferencias se devuelven como `discrepancies`, no se normalizan.

Resultado conocido con un frame HU por defecto:

```text
field: hero_position
experimental: SB
live: BTN
code: position_mapping_btn_vs_sb
```

El intérprete HU asigna SB al botón en heads-up. El recorder live, por defecto,
asigna BTN/BB en esa mesa. La GUI y la predicción muestran ambos valores y
declaran `position_mapping_live_btn_vs_hu_sb`.

### Modos de posición

| Modo | Comportamiento |
|---|---|
| `live_default` | Paridad con el defecto live (normalmente BTN/BB). Declara la discrepancia. |
| `hu_sb_bb` | Fuerza SB/BB en HU con `MANUAL_POSITIONS`, usando el mismo motor live. Corrige la posición; no es paridad exacta con el defecto live. |

El modo se configura en `ExperimentalConfig.parity_position_mode`.

Con `manual_positions={'hero': 'SB', 'p1': 'BB'}`, la comparación sintética
pasa a `matches=True`: cartas, stacks, bote, calle y posiciones coinciden.

## 4. Seguridad de datos

Por defecto:

- `parity_hands_path = trabajo/hu_experimental/hands_parity.jsonl`.
- `data/decisions.jsonl` no se escribe: el `DecisionLog` se sustituye por un
  colector en memoria.
- `data/hands_db.jsonl` no se escribe.
- Los shadow logs live están desactivados.
- El registro prospectivo sigue en `trabajo/hu_experimental/`.
- La GUI no ejecuta acciones de póker.

Para apuntar el recorder de paridad a `data/hands_db.jsonl` se exige
explícitamente:

```python
ExperimentalConfig.default().with_paths(
    parity_hands_path='data/hands_db.jsonl',
    parity_allow_historical_hand_db=True,
)
```

Eso **no está autorizado todavía**. Tampoco se ha iniciado F9-B ni se han
registrado manos reales.

## 5. Pruebas ejecutadas

```text
motor/test_hu_parity.py                          10 passed
motor/test_hu_experimental.py                    17 passed
Suite HU (pytest motor -k hu)                    164 passed, 1 skipped
```

Nota: `pytest` completo del repositorio no colecta limpiamente por pruebas
preexistentes que leen `stdin` o requieren fixtures ausentes
(`tools/test_live.py`, `tools/test_mano6.py`) y por una aserción de módulo en
`tests/test_ausente.py`. Esas fallas no provienen de esta fase; la suite HU sí
queda verde.

Los tests de paridad cubren:

- uso real del motor live con snapshot en memoria;
- recomendación provisional, nunca demostrada;
- persistencia y deduplicación;
- resultado posterior como evento separado;
- modo `hu_sb_bb` y tabla `OR_SB`;
- abstención con tres jugadores activos sin construir el motor;
- comparación de estado y discrepancia BTN/SB;
- polling y errores del controlador;
- conservación de PIL para detección de turno;
- rechazo de `data/hands_db.jsonl` sin autorización;
- hash del `hands_db` histórico sin cambios.

## 6. Límites y riesgos abiertos

1. **Paridad no es corrección estratégica.** `live_default` replica el defecto
   BTN/BB del recorder. `hu_sb_bb` corrige posiciones, pero cambia la
   recomendación respecto al live por defecto. La diferencia está declarada.
2. **Preflop live muestrea frecuencias.** No hay equity preflop exacta; se
   declara `preflop_action_is_sampled` y `preflop_equity_not_computed`.
3. **Postflop no se ha validado con capturas reales.** El motor live se
   reutiliza, pero no hay evidencia prospectiva postflop ni medición de OCR.
4. **Detección de resultados depende del recorder.** Si el recorder no detecta
   una acción por delta de stack/bet, el outcome puede llegar recién al
   finalizar la mano.
5. **Concurrencia no resuelta.** La GUI de paridad y el asistente original no
   deben capturar/escribir a la vez. `hu_sb_bb` modifica `MANUAL_POSITIONS`
   global durante un `step` y lo restaura; no es seguro entre procesos.
6. **Manuscrito de integridad.** Cualquier escritura futura a
   `data/hands_db.jsonl` cambiará su SHA-256 e invalidará el manifiesto de
   `motor/learn.py` hasta una redeclaración versionada.
7. **Rendimiento real no medido.** No se afirma el presupuesto de 8 segundos
   ni el comportamiento de la GUI sobre una mesa real.
8. **El piloto real sigue bloqueado.** Se requiere autorización explícita para
   F9-B, captura real, observaciones reales o validación estratégica.

## 7. Criterios de aceptación de Fase 10.1

- [x] Adaptador real sobre `asistente_live`, sin modificarlo.
- [x] Puerta HU antes del motor live.
- [x] Captura manual y polling automático.
- [x] Predicción persistida antes del resultado.
- [x] Resultado posterior como evento separado.
- [x] GUI experimental independiente.
- [x] Comparación original vs experimental con discrepancias visibles.
- [x] Tests de abstención, ambigüedad y no escritura en `data/`.
- [ ] Prueba con capturas reales y medición de OCR/rendimiento.
- [ ] Demostración de equivalencia postflop con modelos reales.
- [ ] Política de concurrencia y escritor único.
- [ ] Decisión sobre `data/hands_db.jsonl`, sidecars y manifiesto de hash.

## 8. Decisión pendiente

Antes de un piloto real hay que decidir y documentar:

1. Si se autoriza escribir en `data/hands_db.jsonl` y con qué procedimiento de
   redeclaración de hash/manifiesto.
2. Si se permite `data/decisions.jsonl`, `shadow_hierarchy.jsonl` o capturas de
   ambigüedad fuera del directorio aislado.
3. Si la captura será manual o automática durante el piloto.
4. Si se usará `live_default` o `hu_sb_bb` como modo operativo.
5. La política de escritor único entre el asistente original y el de paridad.
6. La autorización explícita para iniciar F9-B.
