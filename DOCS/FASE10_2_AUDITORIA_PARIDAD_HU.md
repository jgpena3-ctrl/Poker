# Fase 10.2 — Auditoría de paridad HU y preparación operativa

**Estado:** auditoría sintética completada; cambios sin commit ni push. No se
hicieron capturas reales, no se registraron manos reales y F9-B no se inició.

## Veredicto

**No está listo ni autorizado para un piloto en mesa real.** La implementación
queda apta para continuar pruebas sintéticas aisladas. El modo operativo es
`hu_sb_bb`; se abstiene cuando no puede demostrar turno HU u orden postflop.
`live_default` queda como diagnóstico y no permite persistir predicciones.

No hay mediciones reales de captura/OCR, el asistente original no coopera con
el lock de exclusión, el recorder puede reconstruir acciones ambiguas y el
adaptador se abstiene postflop cuando falta evidencia de orden. No se afirma
paridad estratégica ni un presupuesto de latencia.

## 1. Posiciones, ciegas, stacks y orden HU

### Hallazgos

- En HU, el botón es SB y el otro jugador es BB.
- `interpret_state()` ya asignaba SB al asiento `btn` y BB al contrario.
- `LiveRecorder._assign_positions()` asigna `BTN` al botón y `BB` al único
  rival restante; no produce SB. Esto explica `position_mapping_btn_vs_sb`.
- `MANUAL_POSITIONS` se aplica después del mapeo automático y las posiciones se
  fijan al iniciar la mano. El override temporal se restaura después de cada
  llamada del adapter.
- La secuencia HU correcta es SB→BB preflop y BB→SB postflop.
- `LiveRecorder` representa el stack como `stake visible + apuesta visible`;
  la comparación resta la apuesta para obtener el stack detrás.

### Correcciones y límites

- `ExperimentalConfig` usa `hu_sb_bb` por defecto. El adapter aplica SB/BB y
  configura el orden correcto solo en la instancia experimental del recorder.
- La instancia experimental de `Asistente` usa una comprobación HU estricta de
  jugador al turno, independiente del orden 6-max original. No se modifican
  `motor/asistente_live.py` ni `recorder/recorder_live.py`.
- El helper estratégico live `_hero_oop` usa la primera acción del flop como
  evidencia; sin ella recurre al orden 6-max. En `hu_sb_bb`, una predicción
  postflop se rechaza si esa acción falta, no es de BB o es inferida/ambigua.
- `live_default` sigue disponible solo como referencia diagnóstica; el ledger
  rechaza su persistencia.
- La predicción declara `position_mode_hu_correction_not_exact_live_parity`,
  posición live predeterminada y corrección aplicada. No se declara paridad
  exacta con el comportamiento live predeterminado.

## 2. Comparación de estados

`compare_frame_state()` clasifica cada campo como:

- `exact`: valores iguales sin normalización semántica.
- `semantic`: equivalencia con normalización documentada.
- `discrepancy`: diferencia relevante.
- `not_comparable`: falta evidencia; desconocido no se transforma en cero ni
  en equivalencia.

Se comparan número e identidad de jugadores, identidad/posiciones de héroe y
rival, cartas privadas reconocidas, board/calle/estado de mano, stacks, bote,
apuestas, contribuciones, acción pendiente y jugador al que corresponde actuar.
Normalizaciones de cartas y stacks aparecen en el resultado.

Fixtures sintéticas: `preflop_sb_to_act`, `preflop_bb_option`,
`flop_bb_first_checked`, `turn_hero_facing_bet` y `river_no_bet`.

Evidencia:

- Sin override, el botón aparece como BTN en live y SB en HU: discrepancia
  `position_mapping_btn_vs_sb`.
- Con `{'hero': 'SB', 'p1': 'BB'}`, las posiciones coinciden y los stacks son
  equivalencia semántica por la normalización de apuesta.
- Board/calle se reconstruyen desde las calles del recorder. Sin evidencia de
  cartas privadas, contribuciones o turno, el resultado queda
  `not_comparable`.
- Si el recorder HU no persiste el botón (posiciones SB/BB), el comparador no
  trata el fallback del mismo frame como corroboración independiente del botón.
- Un frame aislado no siempre contiene historial suficiente para determinar
  contribuciones o turno; no se oculta esa limitación.

## 3. Aislamiento de persistencia

| Salida | Ruta autorizada |
|---|---|
| Ledger prospectivo HU | `trabajo/hu_experimental/registro_prospectivo.jsonl` |
| Manos del recorder de paridad | `trabajo/hu_experimental/hands_parity.jsonl` |
| Ambigüedades e índice | `trabajo/hu_experimental/ambiguedades/` |
| Lock de captura | `trabajo/hu_experimental/capture_session.lock` |
| Sidecar live opcional | `trabajo/hu_experimental/decisions_parity.jsonl` (desactivado) |

La configuración rechaza rutas de manos fuera de `runtime_dir`, incluida
`data/hands_db.jsonl` incluso con el antiguo flag de autorización. Los shadow
logs están prohibidos. `SnapshotCollector` reemplaza al `DecisionLog` live;
el recorder no recibe `capture_dir` ni `session_dir` y sus salidas apuntan al
directorio experimental.

La prueba de aislamiento intercepta escrituras en `data/`, ejecuta análisis,
registro y finalización sintética del recorder, y verifica hashes antes/después
de `hands_db.jsonl`, `decisions.jsonl`, matrices, perfiles y shadow log. También
verifica que ledger y salidas del recorder quedan bajo el directorio temporal
autorizado. No se modificaron datos ni manifiestos.

Las capturas de ambigüedad solo pueden guardarse en
`trabajo/hu_experimental/ambiguedades/`. El recorder no define retención
automática: la retención es **indefinida hasta revisión/eliminación manual
autorizada**. No se generó evidencia real.

Si falla el append prospectivo, el error se propaga y el polling no devuelve
`registration`; no se afirma que la predicción esté persistida. El ledger usa
lock exclusivo por append.

## 4. Orden temporal y antigüedad

Secuencia de polling probada:

1. Captura `CapturedFrame`.
2. Rechaza estado incompleto/ambiguo y exige HU exacto. El `step` comprueba el
   turno con la regla HU adaptada antes de recomendar.
3. Calcula y congela la predicción.
4. Persiste `HU_PREDICTION`.
5. Solo después observa acciones/resultados posteriores y persiste
   `HU_OUTCOME` separado.

El callback de finalización solo encola la mano; los outcomes se procesan
después del registro prospectivo. La frescura se valida también al registrar
una predicción manual.

Límites configurados (no son mediciones): frame 5 s, captura 5 s, OCR 3 s.
Timestamp inválido/futuro, estado antiguo, captura/OCR lenta o análisis expirado
impiden generar o registrar. Las pruebas cubren captura duplicada sin segundo
evento, cambio sintético de apuesta/acción posterior, antigüedad y retraso OCR.
No prueban cambios de pantalla ni latencia OCR en una mesa real.

## 5. Concurrencia y escritor único

- La GUI toma un lock atómico `capture_session.lock`; otra instancia
  experimental recibe error y no inicia polling.
- Se busca `asistente_live` con `psutil` o consulta CIM de solo lectura en
  Windows. Conflicto detectado aborta sin matar procesos. Si no se puede
  verificar el proceso original, el inicio es fail-closed. La comprobación se
  repite cada 5 s durante una sesión.
- En esta auditoría la sonda Windows devolvió `[]`. Las pruebas simulan proceso
  original ocupado, sonda desconocida y lock experimental duplicado; la GUI
  informa el error y no inicia el controlador.
- El ledger prospectivo tiene también lock exclusivo por append.

**Límite residual:** `asistente_live` no participa en el protocolo de lock. La
sonda no hace atómica la exclusión entre programas independientes ni detecta
un proceso que arranque inmediatamente después de una comprobación. Sigue
prohibido ejecutarlos a la vez: el operador debe cerrar el original antes de
abrir la GUI experimental. No se mata ni reconfigura el asistente original.

## 6. Seguridad y abstenciones

- `selected_action` sigue en `None`; la recomendación solo es
  `provisional_selected_action`, rotulada como no demostrada.
- No hay controles ni integración para ejecutar acciones de póker.
- `motor.rules.MULTIWAY_SOPORTADO` sigue en `False`. Solo se predice con dos
  asientos activos explícitamente conocidos; menos/más de dos o estados
  desconocidos/incompletos bloquean la predicción.
- El valor multiway del snapshot live queda solo como auditoría. La predicción
  fuerza `multiway=False` y `multiway_soportado=False`.
- `live_default`, turno no demostrado, frame antiguo, persistencia fallida u
  orden postflop incierto no producen una predicción registrada.

## 7. Pruebas ejecutadas

```text
python -m pytest motor/test_hu_parity.py motor/test_hu_experimental.py -q
50 passed

python -m pytest motor -q -k "hu"
187 passed, 1 skipped, 1241 deselected

git diff --check
sin errores
```

La suite incluye posiciones, ciegas/stacks/turno, fixtures y clasificaciones,
aislamiento de escritura, fallo de persistencia, orden temporal, stale/OCR,
duplicados, escritor único, lock de captura, polling e integración GUI
sintética. No se ejecutaron pruebas de campo ni la suite completa del repo.

## 8. Restricciones, Git y hashes

- HEAD: `286801bc8e678a5688109d9bb502f70f3adb2a45` (sin commit nuevo).
- No se hizo commit ni push.
- No se modificaron `motor/asistente_live.py`,
  `motor/asistente_live_gui.py`, recorder original, configuración live, `data/`,
  matrices, perfiles ni manifiestos.
- `data/hands_db.jsonl` conserva el hash de referencia.

SHA-256 al finalizar:

```text
3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E  data/hands_db.jsonl
C6F8A18DB358F3071FAB7D5C4A17D3E1FDD88D17C54CE345592AF9B5DD7AB841  data/decisions.jsonl
075BAE3AA9DE8F6141C5DB016A397A9B34D727FFBED4B6A5512D108C27F0E5C1  data/preflop_matrices.json
24037CC5BA0DD97AFE208ABE1498FED4DB5CF935F5254B838641EFB2F0AB110B  data/profiles.json
ADD0E8999CB713E2C739369BACCDDCDED9164EF69D55B01C8240419648B620AA  data/profile_ranges.json
273FEA66A92A4D85B1821C3A6A82F739FD6CF5A5AEB3B386619B3A5FBE90E973  data/shadow_hierarchy.jsonl
9F1201ED5EFFDDA1019BE74DD0EB0B90C87B9BCEF6B2707F09BC200785E60C89  motor/learn.py
```

El árbol ya contenía cambios Fase 10.1 sin commit antes de esta auditoría; se
conservaron. El `git status --short` final se entrega en la respuesta de cierre.
