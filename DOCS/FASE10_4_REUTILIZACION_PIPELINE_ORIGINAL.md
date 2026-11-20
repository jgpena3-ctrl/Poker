# Fase 10.4 — Reutilización del pipeline original y diagnóstico de `capture_delay`

Fecha: 2026-11-17
Estado: implementación técnica y validación sintética. **Sin captura real, sin
piloto F9-B, sin registro de manos reales y sin escritura en `data/` por parte
del asistente experimental.**

## 1. Decisión de arquitectura

Se adopta un **fork de aplicación**, no una segunda copia del motor:

- Se reutiliza sin modificar `tools/capture_live.py` para screenshot, OCR de
  estado, OCR de cartas, botón y comunidad.
- Se reutiliza sin modificar `motor/asistente_live.py::Asistente` como motor de
  recomendación.
- Se reutiliza sin modificar `recorder/recorder_live.py` para la semántica de
  mano, asientos, posiciones y apuestas, pero con una instancia y una ruta de
  salida aisladas.
- La capa experimental (`motor/hu_experimental` + `motor/hu_parity`) aporta
  interpretación HU, abstención, predicción prospectiva, outcomes separados y
  GUI independiente.

No se duplican las ~2.255 líneas de `asistente_live.py` porque el motor original
ya se compone sin cambios. Duplicarlo crearía dos verdades y rompería la
paridad que se quiere medir. El fork es de la aplicación: captura original +
motor original + persistencia experimental aislada.

## 2. Auditoría de reutilización

| Componente | Archivo original | Función | Efectos laterales | Uso experimental |
|---|---|---|---|---|
| Captura | `tools/capture_live.py` | `capture()`: `ImageGrab.grab()`, `StateReader.read_all()`, `CardReader.read_all()`, cartas por asiento y comunidad | Ninguno sobre archivos; sí estado global de lectores | `HUCaptureAdapter` delega en `capture_live.capture()` |
| Lectores | `tools/lector_estado.py`, `tools/lector_unificado.py` | OCR de pot, stacks, bets, estados, botón, cartas | Inicialización pesada (~5-6 s) | Se inicializan con `capture_live.init_reader()` en `prepare()` |
| Motor | `motor/asistente_live.py` | `Asistente.step()`: recorder, situación, EV, recomendación | Escribe si se dejan sus salidas por defecto | Se instancia el original y se sustituyen `rec` y `decision_log` antes de usarlo |
| Recorder | `recorder/recorder_live.py` | Manos, posiciones, apuestas, evidencia de ambigüedad | Escribe `hands_db.jsonl` y capturas de ambigüedad | Instancia aislada en `runtime_dir`; nunca `data/` |
| Decision log | `motor/decision_log.py` | Decisiones/resoluciones | Escribe `data/decisions.jsonl` por defecto | `SnapshotCollector` en memoria; sidecar solo si se habilita y dentro de `runtime_dir` |
| GUI | `motor/asistente_live_gui.py` | Flujo manual/automático, captura, estado, recomendación | Escribe manos/decisiones en `data/` | GUI experimental independiente; no importa la GUI original |

Puntos de aislamiento ya presentes en `LiveParityAssistant.ensure_engine()`:

1. `LiveRecorder(output_path=runtime/hands_parity.jsonl,
   ambiguity_capture_dir=runtime/ambiguedades)`.
2. `DecisionLog` secundario solo dentro de `runtime_dir` y solo si
   `parity_enable_live_decision_log=True`.
3. `engine.shadow = False`; `parity_enable_shadow_logs=True` está prohibido.
4. `ExperimentalConfig` rechaza `data/hands_db.jsonl` y cualquier ruta fuera de
   `runtime_dir`.
5. `SnapshotCollector` sustituye al `DecisionLog` del motor antes de ejecutar
   `step()`.

## 3. Diagnóstico de `capture_delay: 6857.1 ms`

### 3.1 Medición

Sobre una captura almacenada (`capturas/Captura de pantalla (166).png`), sin
capturar la pantalla:

| Fase | Tiempo |
|---|---:|
| `StateReader()` (arranque de plantillas OCR) | 5.022,4 ms |
| `CardReader()` | 722,9 ms |
| `StateReader.read_all()` | 264,2 ms |
| `CardReader.read_all()` | 8,7 ms |
| Lectura total por frame, ya inicializado | ~272,8 ms |
| `capture_live.init_reader()` (arranque conjunto, proceso frío) | 6.005,1–8.449,2 ms |

### 3.2 Causa

El adaptador experimental anterior creaba `StateReader` y `CardReader` de forma
perezosa **dentro** de la primera captura. Por eso el primer `capture_ms`
incluía el arranque de plantillas (~5,7 s) más la lectura (~0,27 s), y superaba
el límite de 5.000 ms. El asistente original no mostraba ese problema porque
`Asistente.__init__()` llama a `capture_live.get_readers()` antes de la primera
captura.

No era un frame viejo ni un timestamp mal puesto: era **coste de arranque
imputado al frame**. La captura almacenada sí se leía correctamente: 19 claves
de estado, `p1` y `p2` activos, `pot=7.3`, `btn=p2`.

### 3.3 Por qué la GUI mostraba un estado vacío

Al rechazar por tiempo, `LiveParityAssistant._analyze()` pasaba `hu=None` a
`_blocked_analysis()`. La GUI mostraba entonces el `HUState` vacío por defecto:
sin asientos, sin cartas, sin pot y sin campos observados. El estado capturado
no estaba vacío; el diagnóstico lo ocultaba.

### 3.4 Corrección

- `HUCaptureAdapter.prepare()` inicializa los lectores **antes** del screenshot
  y fuera de `capture_ms`.
- La captura real delega exactamente en `capture_live.capture()`.
- El timestamp se toma inmediatamente antes de la captura.
- `capture_ms` mide solo captura + OCR; `setup_ms` se informa por separado.
- No se inventa `ocr_ms`: `capture_live` no separa screenshot de OCR.
- `_analyze()` interpreta el estado **antes** de los filtros temporales y lo
  conserva en el análisis bloqueado. La causa del rechazo ya no borra lo
  observado.
- La GUI añade el botón **Preparar lectores**, muestra `setup` y captura por
  separado, y registra exactamente el análisis mostrado (`register_analysis`)
  en lugar de volver a analizar el frame.

## 4. Cambios realizados

| Archivo | Cambio |
|---|---|
| `motor/hu_experimental/capture.py` | Delegación en `capture_live.capture()`; `prepare()`; `setup_ms`; advertencias `state_empty`/`state_keys_missing`; sin OCR inventado |
| `motor/hu_parity/parity.py` | `prepare()`; interpretación previa al filtro temporal; estado observado conservado en rechazos; captura serializada con lock |
| `motor/hu_experimental/assistant.py` | `prepare()` para la GUI base |
| `motor/hu_experimental/gui.py` | Botón **Preparar lectores + motor**; visualización de setup/captura; registro del análisis congelado |
| `motor/test_hu_parity.py` | Pruebas de delegación en `capture_live`, orden setup→timestamp→captura, `prepare()` y diagnóstico conservado |
| `motor/test_hu_experimental.py` | El invariante de imports permite únicamente `capture_live` en `capture.py`; sigue prohibiendo motor/recorder/GUI originales |

## 5. Validación ejecutada

```text
python -m pytest motor/test_hu_parity.py motor/test_hu_experimental.py -q
60 passed

python -m pytest motor -q -k "hu"
197 passed, 1 skipped, 1241 deselected
```

`data/hands_db.jsonl` conservó su SHA-256
`3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
antes y después de la suite. La suite se ejecutó con
`POKER_DECISIONS_PATH` redirigido a un archivo temporal.

La lectura offline de una captura almacenada produjo:

```text
states = {'hero_state': 'inactivo', 'p1_state': 'activo',
          'p2_state': 'activo', 'p3_state': 'inactivo',
          'p4_state': 'inactivo', 'p5_state': 'inactivo'}
pot = 7.3
btn = p2
```

Ese frame es de una mesa de 6 jugadores con dos activos, no una mesa HU. El
asistente debe abstenerse por identidad/posiciones, no por “no detectar nada”.

## 6. Límites y pendientes

- No se ha realizado captura real ni sesión de observación.
- No se ha medido la latencia real de screenshot/OCR en la pantalla del
  operador; la cifra de ~273 ms es lectura offline sobre una imagen almacenada.
- No se ha certificado paridad campo a campo contra el asistente original sobre
  el mismo frame real. La validación de paridad debe hacerse secuencialmente:
  capturar con uno, detenerlo, y alimentar el mismo estado/imagen al otro; nunca
  capturar la pantalla simultáneamente.
- La exclusión frente a `asistente_live` sigue siendo best-effort si el proceso
  original no puede verificarse.
- El registro `data/decisions.jsonl` contiene eventos nuevos de `H_1375`
  (15:23–15:25 UTC) compatibles con una ejecución manual del asistente original.
  No fueron generados por el asistente experimental y no se modificaron ni
  revirtieron en esta fase.
- F9-B, el piloto real y cualquier registro de manos reales siguen sin
  autorización.

## 7. Uso recomendado

1. Abrir la GUI experimental.
2. Pulsar **Preparar lectores + motor** una vez y esperar a que termine
   (lectores ~5-8 s; modelos aparte).
3. Pulsar **Capturar estado**.
4. Revisar **OBSERVADO**; si el frame no es HU, debe abstenerse con un motivo
   explícito.
5. Pulsar **Analizar** y, si procede, **Registrar prediccion**.
6. Registrar el resultado como evento posterior separado.

No usar esta aplicación como verdad estratégica ni ejecutar acciones de poker
desde ella.
