# Fase 10 — Asistente HU experimental aislado

Fecha: 2026-11-15

## 1. Alcance y resultado

Se ha creado un asistente experimental HU independiente que:

- reutiliza captura/OCR mediante adaptadores aislados;
- interpreta el estado observado sin completar campos ausentes;
- construye una prediccion experimental usando los contratos HU;
- persiste la prediccion en el registro prospectivo aislado;
- permite registrar resultados posteriores como eventos separados;
- incluye una GUI propia, sin botones que ejecuten acciones de poker.

No se ha iniciado F9-B ni se ha registrado ninguna observacion real.

## 2. Arquitectura

```
Pantalla
  |
  v
HUCaptureAdapter (adaptador aislado)
  |-- StateReader  (tools/lector_estado.py)
  |-- CardReader   (tools/lector_unificado.py)
  |-- ImageGrab    (PIL)
  |
  v
interpret_state (motor/hu_experimental/state.py)
  |
  v
HUExperimentalAssistant (motor/hu_experimental/assistant.py)
  |-- hu_range_contracts (prior plano, KnownCards, EstimatedRange, equity)
  |-- hu_ev              (EV puro)
  |-- hu_evaluation      (si hay secuencia preflop canonica)
  |-- preflop_canonical  (solo si se aportan acciones preflop)
  |
  v
ProspectiveHURegistry (motor/hu_prospective.py)
  |
  v
trabajo/hu_experimental/registro_prospectivo.jsonl
```

El sistema original (`motor/asistente_live.py`, `motor/asistente_live_gui.py`)
no se importa, no se modifica y no comparte estado mutable ni writers.

## 3. Inventario y clasificacion de componentes

| Componente | Clasificacion | Uso |
|---|---|---|
| `tools/lector_estado.py` | Reutilizable mediante adaptador | Lectura de pot, stacks, bets y estados de asiento |
| `tools/lector_unificado.py` | Reutilizable mediante adaptador | Lectura de cartas hero y community |
| `PIL.ImageGrab` | Reutilizable directamente | Captura explicita de pantalla |
| `motor/preflop_contract.py` | Reutilizable directamente | Contratos preflop |
| `motor/preflop_coverage.py` | Reutilizable directamente | Cobertura estricta |
| `motor/preflop_canonical.py` | Reutilizable directamente | Vista canonica preflop |
| `motor/hu_range_contracts.py` | Reutilizable directamente | Prior, rango estimado, equity |
| `motor/hu_ev.py` | Reutilizable directamente | EV por accion |
| `motor/hu_evaluation.py` | Reutilizable directamente | Seleccion demostrada/provisional |
| `motor/hu_prospective.py` | Reutilizable directamente | Registro append-only, integridad y backup |
| `motor/asistente_live.py` | No reutilizable | Motor live original; prohibido modificar |
| `motor/asistente_live_gui.py` | No reutilizable | GUI original; prohibido modificar |
| `recommend_loop`, serving, recorder | Descartados | Fuera del alcance y con efectos live |
| Writers historicos | Descartados | No se escriben datos ni artefactos |

## 4. Archivos nuevos

- `motor/hu_experimental/__init__.py`
- `motor/hu_experimental/config.py`
- `motor/hu_experimental/capture.py`
- `motor/hu_experimental/state.py`
- `motor/hu_experimental/assistant.py`
- `motor/hu_experimental/gui.py`
- `motor/hu_experimental_assistant.py`
- `motor/hu_experimental_gui.py`
- `motor/test_hu_experimental.py`
- `DOCS/FASE10_ASISTENTE_HU_EXPERIMENTAL.md`

No se modifico ningun archivo existente del asistente original ni de datos.

## 5. Flujo temporal de prediccion

1. El operador pulsa manualmente **Capturar estado**.
2. El adaptador ejecuta una unica captura y una unica pasada de OCR.
3. `interpret_state` valida:
   - exactamente dos asientos activos;
   - hero activo;
   - boton/posiciones;
   - cartas y board sin duplicados;
   - pot, stacks, bets y `to_call` cuando estan disponibles.
4. El motor construye la prediccion con el estado disponible.
5. La prediccion se persiste antes de que el operador registre la accion
   posterior.
6. El resultado se registra como `HU_OUTCOME` separado, con su propio
   `observed_at`.
7. No se permite incorporar resultados, acciones posteriores, cartas de
   showdown ni datos finales dentro de la prediccion.

La persistencia no se dispara automaticamente desde la captura: el operador
debe pulsar **Registrar prediccion**. Esto evita declarar como valida una
prediccion que no fue persistida antes de la accion posterior.

## 6. Rutas de configuracion y persistencia

- Directorio de ejecucion: `trabajo/hu_experimental/`
- Registro: `trabajo/hu_experimental/registro_prospectivo.jsonl`
- Backups: `trabajo/hu_experimental/backups/`
- El registro rechaza rutas dentro de `data/` y nombres de artefactos
  protegidos.
- La GUI no usa la configuracion del asistente original.

## 7. GUI experimental

`motor/hu_experimental_gui.py` es una implementacion independiente, no una
copia de `asistente_live_gui.py`.

Muestra:

- estado de captura y OCR, con warnings;
- asientos, posiciones, cartas, board, pot, stacks y bets;
- estado canonico de decision;
- cobertura y procedencia del rango;
- equity, metodo e incertidumbre;
- EV por accion y supuestos;
- accion demostrada o accion provisional claramente etiquetada;
- estado del registro y confirmacion de persistencia;
- separacion textual entre observado, inferido, desconocido, prediccion y
  resultado posterior.

No contiene botones de fold, call, raise, all-in ni ningun control que ejecute
acciones de poker. Tampoco hace polling automatico.

## 8. Garantias de aislamiento

Verificado por pruebas e inspeccion de imports:

- `motor/asistente_live.py` no se modifica.
- `motor/asistente_live_gui.py` no se modifica.
- El paquete experimental no importa `asistente_live`,
  `asistente_live_gui`, `recommend_loop`, serving, recorder ni writers
  historicos.
- No se escribe en `data/`.
- No se comparten writers con el sistema original.
- No se activa multiway; `MULTIWAY_SOPORTADO` permanece `False`.
- No se ejecutan acciones ni clics.
- No se inicia el piloto real.

La captura de pantalla es un recurso potencialmente exclusivo. El adaptador
realiza una captura manual por llamada, sin hilo de polling. Si el asistente
original y el experimental capturan simultaneamente, el comportamiento de la
plataforma no esta garantizado; se documenta como restriccion operativa.

## 9. Interpretacion y fallo seguro

`interpret_state` devuelve estados explicitos:

- `ready`: informacion suficiente para construir una prediccion;
- `unresolved`: falta informacion critica;
- `no_decision`: no es HU, el hero no esta activo, hay cartas duplicadas,
  board invalido o estado estructuralmente inconsistente.

Los errores de OCR no se convierten en cartas, apuestas o stacks inventados.
Los campos ausentes quedan `None` y generan motivos de incertidumbre.

## 10. Contratos y evaluation

- La equity postflop se calcula contra un `GenericPrior` plano a traves de
  `build_estimated_range` y `equity_to_showdown`.
- El EV se calcula con `hu_ev.calculate_ev`.
- Si hay acciones preflop explicitas, se usa `preflop_canonical` y
  `hu_evaluation.evaluate_hu`.
- El prior plano nunca produce una decision `demonstrated`; la seleccion queda
  como `provisional` o ausente.
- La respuesta del rival no se modela. Las apuestas quedan `unknown`.
- La equity preflop exacta no se ejecuta desde la GUI: el contrato disponible
  enumera runouts y tarda decenas de segundos incluso con pocos combos. Se
  declara `preflop_equity_not_computed_without_fast_contract` en lugar de
  inventar una aproximacion.

## 11. Pruebas ejecutadas

`python -m pytest motor/test_hu_experimental.py -q`

Resultado: **17 passed**.

Cobertura de las pruebas nuevas:

- captura inyectada sin escritura;
- rechazo de captura malformada;
- interpretacion HU con posiciones y `to_call`;
- rechazo de tres jugadores activos;
- cartas ausentes;
- board invalido;
- cartas duplicadas;
- preflop sin equity inventada;
- postflop con prior y seleccion nunca demostrada;
- uso de vista canonica preflop cuando hay acciones;
- persistencia antes del resultado;
- inmutabilidad de la prediccion original;
- rechazo de IDs duplicados;
- conservacion de observaciones no evaluables;
- rechazo de datos posteriores en metadata;
- ausencia de imports live/recorder;
- ausencia de botones de accion;
- hash de `data/hands_db.jsonl` sin cambios.

Suite HU completa:

`python -m pytest motor/test_hu_experimental.py motor/test_hu_prospective.py motor/test_hu_evaluation.py motor/test_hu_ev.py motor/test_hu_preflop_contract.py motor/test_hu_range_contracts.py motor/test_hu_scenarios.py motor/test_preflop_contract.py -q`

Resultado: **159 passed, 1 skipped, 1 xfailed**.

## 12. Rendimiento medido

Mediciones sinteticas en Windows, sin captura real de pantalla:

| Etapa | Mediana |
|---|---:|
| Captura inyectada | 0.012 ms |
| Analisis HU postflop (prior plano, equity MC) | 109.19 ms |
| Persistencia en registro | 3.63 ms |

No se midio captura real ni OCR real porque no se ejecuto una sesion real y no
se dispone de una pantalla controlada en las pruebas. Por tanto **no se afirma**
que el presupuesto total de 8 segundos este cumplido. Solo se afirma que la
capa HU medida esta muy por debajo de ese presupuesto en el escenario
sintetico.

## 13. Limitaciones conocidas

1. El lector de cartas existente usa heuristicas de palo; el adaptador no
   dispone de una confianza cuantificada por carta.
2. La equity preflop exacta es demasiado lenta para la GUI; queda unknown.
3. El rango del rival es un prior plano, no una estimacion especifica.
4. No hay modelo de respuesta del rival; las apuestas quedan unknown.
5. No hay deteccion automatica de acciones ni de cambios de mano; el operador
   captura manualmente.
6. No hay prueba automatizada de la GUI con pantalla real.
7. La atomicidad y el bloqueo dependen de las garantias del registro y del
   sistema de archivos ya documentadas en Fase 7.
8. No hay autenticidad criptografica de los eventos.
9. La captura concurrente con el asistente original no esta coordinada.

## 14. Instrucciones de ejecucion y cierre

Ejecutar:

```
python -m motor.hu_experimental_gui
```

Uso manual:

1. Confirmar que la ruta del registro esta fuera de `data/`.
2. Pulsar **Verificar integridad**.
3. Pulsar **Capturar estado**.
4. Revisar warnings de OCR e incertidumbre.
5. Pulsar **Registrar prediccion** antes de observar la accion posterior.
6. Registrar el resultado en el campo de resultado posterior.
7. Al cerrar, verificar integridad y crear backup.

La GUI no se inicia automaticamente y no captura en segundo plano.

## 15. Recuperacion

1. Ante corrupcion, detener nuevas escrituras.
2. No truncar ni reparar automaticamente el registro.
3. Verificar el backup con `verify_backup`.
4. Restaurar a una ubicacion nueva siempre que sea posible.
5. Si se restaura sobre el registro activo, se exige `overwrite=True` y se
   conserva el original como `.pre_restore`.
6. Verificar el registro restaurado antes de usarlo.
7. Registrar toda intervencion manual.

## 16. Evidencia de que no se inicio el piloto real

- No se ejecuto ninguna captura real de pantalla.
- No se registro ninguna observacion real.
- Todas las pruebas usan estados sinteticos y directorios temporales.
- La GUI no se inicio contra una mesa real.
- El registro por defecto esta en `trabajo/hu_experimental/`, no en `data/`.
- `data/hands_db.jsonl` conserva su SHA-256.

## 17. Matriz de aceptacion

| Criterio | Estado | Evidencia |
|---|---|---|
| Asistente experimental ejecutable | CERTIFICADO | Import y tests del paquete |
| Captura/OCR reutilizados de forma aislada | CERTIFICADO | Adaptador inyectable y lectores existentes |
| GUI experimental independiente | CERTIFICADO | `motor/hu_experimental_gui.py` |
| Prediccion antes de informacion posterior | CERTIFICADO | Persistencia manual y test de orden |
| Registro prospectivo conserva garantias | CERTIFICADO | Suite de `hu_prospective` incluida |
| Casos inciertos fallan de forma segura | CERTIFICADO | Tests de estado no HU, cartas, board |
| Asistente original intacto | CERTIFICADO | Sin cambios en Git ni imports |
| Datos historicos y artefactos intactos | CERTIFICADO | SHA-256 y rutas protegidas |
| Pruebas respaldan garantias | CERTIFICADO_CON_LIMITACIONES | 17 tests; GUI real no probada |
| Piloto real no iniciado | CERTIFICADO | Sin observaciones reales |

## 18. Verificacion final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl` antes y despues:
  `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- `py_compile`: OK.
- `git diff --check`: OK.
- Sin commits.
- Sin cambios en live, serving, recorder, OCR original, datos, artefactos,
  pines, ledgers, PR-03, F0, PR-02B ni G2.
- `MULTIWAY_SOPORTADO=False`.

## 19. Recomendacion

La Fase 10 queda tecnicamente preparada como prototipo experimental aislado.
No autoriza ni inicia F9-B. Antes de un piloto real deben resolverse, como
minimo:

- confianza y estabilidad temporal del OCR;
- equity preflop rapida o asincrona;
- modelo de respuesta del rival;
- deteccion de cambios de mano;
- prueba de la GUI en el entorno real de captura;
- coordinacion de captura con el asistente original.

Hasta entonces, las predicciones son experimentales y no deben usarse como
verdad estrategica ni para jugar dinero real.
