# Fase 10.3 — Certificación automatizada HU

**Resultado: certificación incompleta; piloto no autorizado.** Se ampliaron las
pruebas y barreras automatizadas en el entorno experimental. El requisito de
exclusión fiable frente al asistente original no se puede demostrar sin que el
original coopere o sin controlar obligatoriamente su lanzamiento. No se cambió
el asistente original para intentar sortear esa limitación.

No se creó commit ni se hizo push. No se inició F9-B, no hubo manos/capturas
reales y no se tocaron datos históricos, matrices, perfiles ni manifiestos.

## Evaluación de criterios

| Criterio | Resultado | Evidencia/limitación |
|---|---|---|
| Exclusión fiable entre dos instancias experimentales | **Cumplido** | Lock atómico; segunda instancia bloqueada. |
| Exclusión fiable frente a `asistente_live` original | **No certificable** | Se detecta por proceso cuando es reconocible y se revisa periódicamente, pero el original no consulta el lock; existe una ventana de carrera. |
| Rechazo de capturas viejas/fuera de orden | **Cumplido sintéticamente** | Límite de edad, timestamp del screenshot antes de OCR, timestamp duplicado/colisión y secuencia decreciente. |
| Cambio de mano sin asociar outcomes a otra mano | **Cumplido sintéticamente** | Se requiere `hand_id`; pendientes de otra mano se excluyen, nunca se unen a acciones de la mano nueva. |
| Ausencia de predicciones duplicadas | **Cumplido en escenarios probados** | Deduplicación en polling y por `decision_key` ya persistida; reinicio con predicciones previas sin outcome falla cerrado. |
| Predicción persistida antes de acciones/resultados posteriores | **Cumplido sintéticamente** | Prueba integral prediction→finalización→outcome en eventos separados y en ese orden. |
| Abstención ante ambigüedad | **Cumplido en escenarios probados** | HU, turno, frescura, identidad de mano, persistencia e integridad del ledger son puertas de rechazo. |
| GUI recuperable ante errores | **Cumplido en lógica sintética** | Se prueba error→recuperación y que un worker activo conserva el lock al cerrar. No es certificación visual de Tk en una mesa. |
| Medición de latencia | **Medida sintéticamente; requisito real pendiente** | Ver §6; OCR/captura real no están incluidos. |

Por tanto, Fase 10.3 **no cumple todos los criterios de aceptación** y no
certifica uso automatizado prospectivo real.

## 1. Concurrencia: hallazgo y decisión técnica

`CaptureSessionGuard` ya bloquea instancias experimentales duplicadas. La
sonda busca procesos Python del asistente original al adquirir el lock y cada
5 s mientras se captura; un conflicto aborta, el resultado desconocido falla
cerrado y la GUI informa el error. No mata procesos. Se mejoró el cierre del
polling para que la GUI no libere el lock si el hilo todavía está capturando o
procesando.

La inspección de `motor/asistente_live.py`, `motor/asistente_live_gui.py` y
`recorder/recorder_live.py` confirma que el original no consulta
`capture_session.lock` ni participa en un protocolo de lease. La captura
original puede iniciarse directamente. Por ello:

- La sonda de procesos es una detección de mejor esfuerzo, no una exclusión
  mutua. Puede haber una carrera entre la comprobación y una captura; también
  puede omitirse un proceso iniciado por una ruta de lanzamiento no reconocida.
- Un lock externo que el original no adquiere no puede impedir que capture.
- Un supervisor solo garantizaría exclusión entre procesos lanzados a través
  de ese supervisor; el lanzamiento directo seguiría siendo un bypass. No se
  implementa como garantía.

Se mantiene la prohibición operativa de ejecutar ambos asistentes a la vez.
Para obtener exclusión técnicamente garantizada haría falta autorizar cambios
cooperativos al original o imponer una política externa de lanzamiento/acceso
que no pueda evitarse. Ninguna de esas dos cosas está autorizada/demostrada en
esta fase.

## 2. Frescura, duplicados y asociación a mano

- El timestamp de la captura de pantalla se toma inmediatamente después de
  `ImageGrab.grab()` y **antes** de conversión/OCR. No se usa el final del OCR
  como si fuera el instante de captura.
- Se conservan los límites de 5 s para edad total y captura, y 3 s para OCR.
  Un frame con timestamp repetido, timestamp en colisión o anterior al último
  aceptado se rechaza antes de mutar el recorder. Frames iguales con timestamps
  nuevos pueden seguir alimentando el recorder para su detección de estabilidad;
  el estado de decisión no vuelve a registrarse.
- La `decision_key` persiste como clave idempotente: si ya aparece en el ledger,
  no se agrega otro evento de predicción.
- Al reiniciar, un ledger ilegible o con integridad inválida bloquea la captura.
  También se bloquea si hay predicciones de la sesión previa sin outcome; deben
  reconciliarse antes de capturar para no unirlas a otra mano.
- Toda predicción requiere identidad de mano. Si cambia el `hand_id` antes de
  observar su acción, se registra una exclusión (`hand_id_changed_before_outcome`)
  con ambos IDs; no se atribuye la acción de la mano nueva.

Estos controles detectan timestamps antiguos y secuencias fuera de orden, pero
no pueden determinar por sí solos que un screenshot recién tomado represente
visualmente la mano correcta si el OCR produce una lectura plausible pero falsa.
Eso requiere capturas/validación de campo aún no autorizadas.

## 3. Prueba integral reproducible

Se añadió una prueba sintética del flujo completo:

1. Un frame HU válido y con turno genera `HU_PREDICTION`.
2. Se verifica que el ledger contiene solo ese evento.
3. Se finaliza la mano en el recorder aislado; el callback únicamente encola el
   resultado.
4. En un ciclo posterior se persiste `HU_OUTCOME`, referenciando la predicción
   anterior y con resultado final.
5. Se verifica el orden prediction→outcome y la integridad del ledger.

También se prueban reinicio con predicción pendiente, deduplicación después de
reconciliar, cambio de `hand_id`, frame fuera de orden, timestamp duplicado,
errores recuperables de GUI, persistencia fallida y parada del polling sin
liberación prematura del lock. Todas las salidas usan directorios temporales.

## 4. GUI y observabilidad

`PollEvent` informa duración total y fases de análisis/captura, persistencia de
predicción y observación/persistencia posterior. La GUI presenta duración por
ciclo, muestra errores y permite que un ciclo posterior vuelva a estado activo.
El worker no se reemplaza mientras un ciclo anterior siga vivo. Si el cierre
vence el timeout de parada, el lock se conserva y un watcher lo libera cuando
el worker termina; si el proceso cae inesperadamente, se recupera por PID
obsoleto.

Las pruebas usan controles/variables sintéticos, no una ventana real ni una
captura de mesa. Por tanto, la operación visual de Tk no queda certificada.

## 5. Pruebas

```text
python -m pytest motor/test_hu_parity.py motor/test_hu_experimental.py -q
58 passed

python -m pytest motor -q -k "hu"
195 passed, 1 skipped, 1241 deselected
```

La suite no modifica pruebas ajenas al alcance y no ejecuta manos reales.

## 6. Medición sintética de latencia

Medición reproducible con 30 ciclos `poll_once`, estados inyectados que varían
el bote para provocar decisiones distintas, `SimpleNamespace(oracle=None)` y
persistencia en un directorio temporal. Incluye interpretación, recorder,
motor, ledger/integridad y manejo del ciclo; **excluye** screenshot real y OCR.

```text
Plataforma: Windows-10-10.0.26200-SP0
n=30
p50 = 8.005 ms
p95 = 11.762 ms
Máximo observado = 266.146 ms
```

El máximo incluye el arranque frío/importación del motor. No es una medida de
captura/OCR ni acredita el presupuesto original de 8 segundos en una mesa real.
El requisito de latencia de campo sigue pendiente.

## 7. Estado final

- Fase 10.1: implementada, sin commit.
- Fase 10.2: auditoría aceptada, sin commit.
- Fase 10.3: endurecimiento y pruebas sintéticas implementados; **certificación
  incompleta por concurrencia con el original y falta de medición de campo**.
- F9-B: no iniciado; piloto no autorizado.
- HEAD permanece en `286801bc8e678a5688109d9bb502f70f3adb2a45`.
- Sin commit ni push.

Los cambios previos de Fase 10.1 y 10.2 se conservaron. No se modificaron el
asistente/GUI originales, el recorder original, `data/`, artefactos históricos
ni manifiestos.
