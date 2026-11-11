# Auditoría de contratos de consumo de los siete derivados

**Estado:** investigación y documentación cerradas. Esta fase no autoriza
regeneración, reanclaje, cambio de motor, B2 ni sesiones reales.

**Fecha:** 2026-11-11

**Base canónica:** `data/hands_db.jsonl`, 1344 líneas,
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`,
commit de blob `8594ed5`.

**Derivados auditados:** `preflop_stats.json`, `player_stats.json`,
`profiles.json`, `profile_ranges.json`, `postflop_ranges.json`,
`observations.json` y `behavior.json`.

**Verificador de integridad:** `tools/verificar_adopcion_1344.py` (solo
lectura; 12 comprobaciones; sale con código distinto de cero si falla).

---

## 0. Resumen ejecutivo

1. **Ningún módulo de producción lee los siete derivados como entrada.**
   `motor/asistente_live.py::build_models()` reconstruye perfiles, rangos,
   `Oracle` y modelo postflop desde `data/hands_db.jsonl`; no abre los JSON
   históricos (`motor/asistente_live.py:476-499`).

2. **Solo `profile_ranges.json` y `postflop_ranges.json` tienen lectores
   semánticos en el repositorio:** `tools/range_lab_gui.py` y
   `tools/diagnosticar_56_154.py`. El primero puede influir en una estimación
   estratégica experimental; el segundo es un diagnóstico histórico.

3. **Los otros cinco derivados no tienen lector semántico.** Son informes
   agregados o volcados de observaciones, no contratos de entrada. Además,
   `behavior.json` no es una serialización de ida y vuelta: `Oracle` no puede
   consumirlo tal como está escrito; falla con `ValueError`.

4. **`postflop_ranges.json` no es autosuficiente.** `PostflopRangeModel.load()`
   no restaura el `Oracle` que usa como prior ni los contadores de procedencia.
   Si se usa sin reinyectar el prior, `p_action()` cambia de forma silenciosa.
   Medido: 580 probabilidades comparadas, diferencia absoluta media `0.0621`
   y máxima `0.2504` frente a un modelo reconstruido desde la ventana actual de
   877.

5. **Hay un camino mixto concreto, pero está en el laboratorio, no en el
   asistente live.** `tools/range_lab_gui.py::load_models()` carga rangos
   históricos y, para el postflop, reconstruye el `Oracle` con la ventana
   actual de 877 manos. No verifica que ambos artefactos compartan base, ventana
   ni etiquetas.

6. **No hay una ruta de producción que combine las 1344 manos con estos
   derivados de legado.** El asistente live ni siquiera usa las 1344: llama a
   `load_hands(reliable_only=True)` y trabaja con 877 manos. Esa selección de
   ventana es silenciosa respecto de la base canónica, pero no es una mezcla
   con los JSON históricos.

7. **No se puede afirmar que los derivados sean reproducibles ni que
   correspondan a la base actual.** Declaran la ventana de 877 y algunos
   contadores, pero no incluyen hash de la base, hash de las líneas de entrada,
   hash de etiquetas ni versión de los límites de campo. Dos de ellos declaran
   `arbol_sucio=True`.

8. **Conclusión operativa:** los siete pueden seguir consultándose únicamente
   como artefactos históricos de solo lectura. Ninguno debe presentarse como
   cálculo sobre las 1344. `profile_ranges.json` y `postflop_ranges.json`
   requieren un contrato nuevo antes de cualquier regeneración o uso como
   modelos de decisión. Los otros cinco requieren contrato nuevo solo si se
   quieren convertir en entradas; hoy no lo son.

---

## 1. Alcance, método y límites

### 1.1 Qué se auditó

Se buscaron lectores de los siete nombres en todo el código Python del
repositorio, incluidas rutas construidas con `os.path.join`, `Path(...) /` y
listas de nombres. Después se revisó cada coincidencia para separar:

- lectores semánticos: abren el JSON y usan sus campos;
- lectores de integridad: solo calculan hashes, tamaños o copian bytes;
- generadores: escriben el JSON, no lo leen;
- reconstrucciones en memoria: llaman a `from_hands`, `Oracle(build(...))`,
  `Profiles.from_hands`, etc., sin abrir el derivado;
- referencias muertas o históricas: código que nombra una API que ya no
  existe, o documentación.

No se instrumentó el runtime de la GUI ni del asistente. La evidencia es
revisión estática más ejecuciones de solo lectura. No cubre consumidores
externos al repositorio, cuadernos o procesos manuales fuera de `git`.

### 1.2 Qué no se hizo

- No se modificó `data/`.
- No se regeneró ningún derivado.
- No se reanclaron hashes, pines ni manifiestos.
- No se cambiaron rangos, calibración, lógica estratégica ni
  `MULTIWAY_SOPORTADO=False`.
- No se inició B2 ni se ejecutaron sesiones reales.
- No se intentó poner verdes los fallos históricos anclados a 1253.

Las comparaciones en memoria de este informe (`from_hands`) construyen objetos
temporales para medir contratos; no escriben ficheros.

---

## 2. Inventario de los artefactos

Los siete ficheros están en `data/` y son los hashes canónicos registrados en
`data/calibration_window.json`.

| Derivado | Forma y claves principales | Manos / muestra | Metadatos de procedencia | Lector semántico |
|---|---|---:|---|---|
| `preflop_stats.json` | `hands`, `denoms`, `cats`, `known_denoms`, `denoms_pos`, `cats_pos` | `hands=877` | Solo `hands`; sin base, commit ni ventana | Ninguno |
| `player_stats.json` | 139 jugadores → `{hero, stats{b3,b4,bar,cbet,f2bar,f2cb,pfr,vpip,wsd,wtsd}}` | 139 jugadores | Ninguno | Ninguno |
| `profiles.json` | 139 jugadores → `{player, hero, n, stats, bins, label, subtype, stack_mean, confidence, reliability}` | 139 jugadores | Ninguno | Ninguno |
| `profile_ranges.json` | `meta`, `perfil` (139), `opp` (6), `cnt` (21), `omega` (139) | `hands_input=877`, `hands_used=866` | `meta` con ventana, commit, `arbol_sucio`, `built_at`; sin hash de base ni de líneas | `range_lab_gui`, `diagnosticar_56_154` |
| `postflop_ranges.json` | `meta`, `labels` (139), `opp` (116), `cnt` (197) | `hands_input=877`, `hands_used=866` | Igual que el anterior; sin `Oracle` serializado | `range_lab_gui`, `diagnosticar_56_154` |
| `observations.json` | Lista de 8742 observaciones; incluye `hand_id`, `street`, `player`, `kind`, `pos`, `action`, `amount`, `sizing`, `pot_before`, `stack_effective`, `spr`, `pot_type`, `players_active`, `board`, `texture_class`, `facing`, `raised_before`, `preflop_sequence`, `hand_known`, `cards` | 877 manos, 139 jugadores | Ninguno | Ninguno |
| `behavior.json` | `hands` (877), `observaciones` (8742), `profiles` (139), `granular` (111), `por_facing` (32) | 877 manos, 8742 observaciones | Solo contadores; sin base, commit ni ventana | Ninguno |

Tamaños y hashes completos: anexo A.

### 2.1 “1253” no es el número de manos de los derivados

Los derivados **no contienen 1253 manos**. Contienen la ventana de **877**.
“1253” identifica la base histórica que el registro de adopción les asigna;
“877” es la ventana efectiva de todos los artefactos.

Evidencia:

- `preflop_stats.hands = 877`;
- `behavior.hands = 877`, `behavior.observaciones = 8742`;
- `profile_ranges.meta.hands_input = 877`, `hands_used = 866`;
- `postflop_ranges.meta.hands_input = 877`, `hands_used = 866`;
- `observations.json` contiene exactamente 877 `hand_id` distintos;
- `profiles.json` y `player_stats.json` contienen 139 jugadores.

`profile_ranges.meta` y `postflop_ranges.meta` también declaran
`hands_window="reliable_only"`, `code_commit="0fcceed"`,
`arbol_sucio=true` y `built_at` del 2026-10-25. Ese sello **no es un
fingerprint de la base**: `hands_window` se deduce del número de manos
recibidas, no de un hash de las líneas. El propio módulo
`motor/_procedencia.py` documenta esa limitación.

### 2.2 Cobertura actual frente a los artefactos

Medido con la base canónica actual y los artefactos:

| Ámbito | Manos | Nombres de jugador |
|---|---:|---:|
| Base canónica completa (`load_hands(reliable_only=False)`) | 1344 | 192 |
| Ventana fiable (`load_hands(reliable_only=True)`) | 877 | 147 |
| `profiles.json` / `player_stats.json` | — | 139 |
| `observations.json` | 877 | 139 |

La ventana fiable son las primeras 900 líneas físicas menos las 23 exclusiones
CM-004. Por tanto, de las 1344 quedan fuera **467**: 444 posteriores a la línea
900 y 23 exclusiones. El asistente live usa esas 877, no las 1344.

Cincuenta y tres nombres de la base completa no aparecen en `profiles.json`;
ocho nombres de la ventana tampoco. El fichero no declara la regla de inclusión
(número mínimo de oportunidades, filtros de puesto, etc.), así que no se puede
distinguir “sin muestra suficiente” de “fuera de la ventana” leyendo el
artefacto. No se interpreta como un defecto de datos: es una **falta de
contrato de cobertura**.

Además, comparando por `hand_id` el commit histórico `51a6fb9` con la base
actual `8594ed5`:

- 91 IDs nuevos;
- 127 IDs comunes con contenido distinto;
- **106 de los 877 IDs de la ventana actual tienen contenido distinto**.

Eso no demuestra qué contenido usó cada derivado —no hay hash de líneas de
entrada—, pero sí demuestra que la ventana actual no es la misma que la base
histórica registrada. Un derivado de 877 no queda automáticamente alineado con
la base actual por coincidir en el número de manos.

---

## 3. Quién consume qué

### 3.1 Matriz de consumidores

Leyenda: **L** = lee semánticamente el JSON; **H** = solo integridad: hash,
tamaño, copia de bytes o contadores/metadatos; **G** = genera/escribe;
**T** = prueba con fichero temporal, no canónico; **R** = reconstruye en memoria
desde las manos, sin abrir el JSON; **I** = recibe un objeto inyectado, sin
comprobar su procedencia; **—** = no lo usa.

| Consumidor | `preflop_stats` | `player_stats` | `profiles` | `profile_ranges` | `postflop_ranges` | `observations` | `behavior` | Clase |
|---|---|---|---|---|---|---|---|---|
| `motor/asistente_live.py` | — | — | R | R | R | R | R | Reconstrucción actual sobre 877, no consumo de JSON |
| `motor/recommend_loop.py` | — | — | — | I | I | — | — | Acepta modelos sin validar procedencia |
| `motor/decision.py::OracleResponse` | — | — | — | — | — | — | I | Usa un `Oracle` inyectado |
| `tools/range_lab_gui.py` | — | — | — | L | L | — | — | **Inseguro/no verificable** para base actual; histórico si solo se inspecciona |
| `tools/diagnosticar_56_154.py` | — | — | — | L | L | — | — | Diagnóstico histórico |
| `tools/reconstruir_derivados.py` | H/G | H/G | H/G | H/L/G | H/L/G | H/G | H/G | Utilidad de reconstrucción; `regen` bloqueado |
| `tools/verificar_adopcion_1344.py` | H | H | H | H | H | H | H | Verificador de solo lectura |
| `motor/test_player_ranges.py` | — | — | — | T | — | — | — | Prueba de round-trip con fichero temporal |
| `motor/test_postflop_ranges.py` | — | — | — | — | T | — | — | Prueba de round-trip con fichero temporal |
| `tools/auditar_equity_observable.py` | — | — | — | R | — | — | — | Referencia muerta a `PostflopModel`; no consume JSON |
| `tools/equity_de_mano.py` | — | — | — | R | — | — | — | Referencia muerta a `PostflopModel`; no consume JSON |

### 3.2 El camino de producción

`motor/asistente_live.py::build_models()` hace exactamente esto:

```python
hands = load_hands(reliable_only=True)          # 877 de 1344
profs = Profiles.from_hands(hands)
labels = {name: p.label for name, p in profs.profiles.items()}
range_model = ProfileRangeModel.from_hands(hands, labels=labels)
oracle = Oracle(build(hands, labels=labels))
postflop_model = PostflopRangeModel.from_hands(hands, labels=labels)
postflop_model._oracle = oracle
```

No hay `json.load` de los siete derivados. El asistente construye un estado
coherente **de la ventana de 877**, no de las 1344 y no de los JSON históricos.
Después usa `range_model` para el rango preflop
(`motor/asistente_live.py:1176-1189`, `1575-1590`) y `OracleResponse` para la
respuesta del rival (`motor/asistente_live.py:1599-1603`).

Consecuencias:

- **No hay mezcla de las 1344 con los derivados históricos en producción.**
- **Sí hay una omisión silenciosa de 467 manos canónicas**: la ventana fiable
  es 877 y ningún mensaje de la interfaz la presenta como subconjunto de 1344.
- Si alguien cambiara los generadores para usar `load_hands()` sin
  `reliable_only`, produciría artefactos de otra ventana sin cambiar el
  contrato de producción. Eso sería una divergencia nueva, no una
  actualización automática.

### 3.3 `tools/range_lab_gui.py`: el camino mixto real

`load_models()` (`tools/range_lab_gui.py:47-89`) hace:

```python
pre = pr_mod.ProfileRangeModel.load()           # profile_ranges.json histórico
post = pf_mod.PostflopRangeModel.load()         # postflop_ranges.json histórico
if getattr(post, '_oracle', None) is None:
    hands = load_hands(reliable_only=True)      # ventana actual de 877
    post._oracle = Oracle(build(hands, labels=dict(post.labels)))
```

Esto mezcla generaciones:

- los rangos preflop y postflop vienen del JSON histórico;
- las etiquetas del `Oracle` vienen de `post.labels` histórico;
- las observaciones con las que se construye ese `Oracle` vienen de la ventana
  actual de 877;
- no se comprueba que `profile_ranges.meta` y `postflop_ranges.meta` sean de la
  misma base, ni que las etiquetas históricas coincidan con las actuales.

El resultado se usa en `run_pipeline()` y en la GUI para estimar equity y
actualizar rangos. Es una herramienta experimental, no el asistente live, pero
produce información estratégica y no tiene guardia de procedencia. Su
clasificación es **inseguro/no verificable** para la base canónica actual.

Si los JSON no existen o fallan con `FileNotFoundError`, `ValueError` o
`KeyError`, el código reconstruye desde la ventana actual. Si existen, no hay
aviso de que sean legado. El fallback silencioso y la carga silenciosa son
comportamientos distintos y no se distingue cuál ocurrió.

### 3.4 `tools/diagnosticar_56_154.py`: lector histórico

Este script abre `data/_snapshot_pre_rebuild_1b14c18/*.json` y los
`profile_ranges.json` / `postflop_ranges.json` actuales. Lee `perfil`, `opp` y
`cnt`; no valida `meta` ni la base. Solo imprime una comparación de cobertura y
masa. No influye en recomendaciones. Clase: **artefacto histórico**.

### 3.5 `tools/reconstruir_derivados.py`: lector y escritor potencial

- `DERIVADOS` contiene los siete nombres (`tools/reconstruir_derivados.py:26-28`).
- `cmd_backup()` copia los siete y registra hashes.
- `_metricas()` lee `profile_ranges.json` y `postflop_ranges.json` para contar
  claves y bytes; no lee los otros cinco semánticamente.
- `cmd_regen()` ejecuta los siete CLIs oficiales y **sobrescribe** los siete.
- `cmd_comparar()` compara métricas antes/después.

Como consumidor, no valida base ni ventana; como herramienta de regeneración,
está bloqueada por esta fase. No se ejecutó `regen`.

### 3.6 `tools/verificar_adopcion_1344.py`: lector de integridad

- `check_derivatives()` compara los siete hashes con
  `data/calibration_window.json`.
- `check_derivative_legacy_metadata()` lee `preflop_stats.json`,
  `behavior.json`, `observations.json`, `profile_ranges.json` y
  `postflop_ranges.json` para comprobar contadores y la etiqueta de legado.
- No interpreta rangos, no construye modelos y no recomienda. Es el lector de
  integridad de referencia.

### 3.7 Referencias que no son consumidores

`tools/auditar_equity_observable.py:90` y `tools/equity_de_mano.py:439`
intentan `postflop_ranges.PostflopModel()`. Esa clase **no existe** en
`motor/postflop_ranges.py`; el `try/except` la convierte en `None` y la
herramienta sigue sin modelo postflop. No leen el JSON ni deben contarse como
consumidores.

`tools/clasifica_data.py` solo menciona nombres de ficheros para clasificar
escritores; no los lee.

---

## 4. Análisis por derivado

### 4.1 `preflop_stats.json`

- **Generador:** `python -m motor.learn --json`
  (`motor/learn.py:738-748`), sobre `load_hands(reliable_only=True)`.
- **Campos:** `hands`, `denoms`, `cats`, `known_denoms`, `denoms_pos`,
  `cats_pos`. Son contadores agregados por jugador, denominador, categoría y
  posición.
- **Consumidores en código:** ninguno. No hay `from_json`, `load` ni lectura
  semántica.
- **Dependencias si se usara como entrada:** nombres de jugador, posiciones,
  categorías de `learn.preflop_events`, reglas de denominador y clasificación.
- **Si está desactualizado:** un informe manual o un consumidor externo puede
  presentar cifras de 877 como si fueran de 1344. El motor no se entera.
- **Impacto estratégico:** ninguno en el repositorio actual.
- **Clasificación:** **compatible solo como artefacto histórico**; no es una
  entrada del motor.
- **Contrato que falta:** metadata de base/ventana, hash de líneas de entrada,
  versión de esquema y loader si se quiere convertir en entrada.

### 4.2 `player_stats.json`

- **Generador:** `python -m motor.stats --json` (`motor/stats.py:260-271`),
  sobre la ventana fiable.
- **Campos:** 139 jugadores → `{hero, stats{...}}`. No guarda denominadores ni
  conteos, solo frecuencias.
- **Consumidores en código:** ninguno. No hay loader.
- **Dependencias:** contadores de transición por jugador; reglas de showdown,
  c-bet, barriles y denominadores.
- **Si está desactualizado:** no se puede auditar una frecuencia sin el
  denominador; el fichero no permite reconstruir si el `n` era suficiente.
- **Impacto estratégico:** ninguno en el repositorio actual.
- **Clasificación:** **compatible solo como artefacto histórico**.
- **Contrato que falta:** conteos/denominadores, metadata de base/ventana,
  versión de esquema y loader si se convierte en entrada.

### 4.3 `profiles.json`

- **Generador:** `python -m motor.profile --json`
  (`motor/profile.py:340-359`), sobre la ventana fiable.
- **Campos:** 139 jugadores → `{player, hero, n, stats, bins, label, subtype,
  stack_mean, confidence, reliability}`. No guarda `counts`; por tanto no
  permite recalcular bins, confianza ni etiqueta desde el fichero.
- **Consumidores en código:** ninguno. `Profiles` no tiene `load`; el motor
  construye `Profiles.from_hands`, no lee el JSON.
- **Dependencias:** estadísticas de transición, stacks y matrices para
  `omega`; la etiqueta PEZ/TIBURON se usa indirectamente en
  `asistente_live`, pero se recalcula desde las manos.
- **Si está desactualizado:** un consumidor externo puede leer etiquetas de 877
  y creer que son de 1344. El motor no las lee.
- **Impacto estratégico:** ninguno en el repositorio actual; sí podría tenerlo
  si alguien usara el fichero como fuente de etiquetas.
- **Clasificación:** **compatible solo como artefacto histórico**.
- **Contrato que falta:** `counts`, regla de inclusión de jugadores, hash del
  mapa de etiquetas, metadata de base/ventana y loader si se convierte en
  entrada.

### 4.4 `observations.json`

- **Generador:** `python -m motor.observations --json`
  (`motor/observations.py:267-286`), sobre la ventana fiable.
- **Campos:** lista de 8742 observaciones con `hand_id`, calle, jugador, tipo
  (`hero`/`villain`), posición, acción, importe, sizing, bote previo, stack
  efectivo, SPR, tipo de bote, jugadores activos, board, textura, `facing`,
  secuencia preflop, `hand_known` y cartas.
- **Consumidores en código:** ninguno. No hay `from_dict`, `load` ni esquema
  versionado.
- **Dependencias:** IDs de mano, jugadores, posiciones, acciones, boards,
  cartas, botes, stacks y reglas de extracción. Es el único derivado con
  referencias a manos concretas.
- **Si está desactualizado:** reutilizarlo mezclaría observaciones de manos que
  ya cambiaron. La comparación `51a6fb9` → `8594ed5` muestra 106 IDs de la
  ventana actual con contenido distinto; el fichero no guarda hash de entrada.
- **Impacto estratégico:** ninguno por sí solo, pero es la materia prima de
  `behavior` y `postflop_ranges`; usarlo como entrada sin contrato sería un
  riesgo alto.
- **Clasificación:** **compatible solo como artefacto histórico**; el de mayor
  riesgo de reutilización manual por contener IDs de mano.
- **Contrato que falta:** envoltorio con metadata, versión de esquema, hash de
  IDs de origen, versión de límites de campo y loader/validador.

### 4.5 `behavior.json`

- **Generador:** `python -m motor.behavior --json`
  (`motor/behavior.py:262-293`), sobre la ventana fiable.
- **Campos:** `hands=877`, `observaciones=8742`, `profiles{139}`,
  `granular{111}` y `por_facing{32}`. Las claves de las tablas se serializan
  como cadenas `"perfil|calle|textura|facing"` o
  `"perfil|calle|facing"`.
- **Consumidores en código:** ninguno.
- **No es ida y vuelta:** `Oracle` espera claves tupla. Al pasarle el JSON
  cargado, `p_action` falla:
  `ValueError: too many values to unpack (expected 3)`.
  El fichero es un informe, no una serialización del `Oracle`.
- **Dependencias:** etiquetas de perfil, observaciones, `min_n`, textura y
  `facing`.
- **Si está desactualizado:** las tablas son de 877; no hay metadata de base ni
  hash de observaciones. No se puede saber si las etiquetas y observaciones
  corresponden a la misma ventana.
- **Impacto estratégico:** el motor usa `Oracle(build(hands, ...))` en memoria;
  no usa el JSON. Un consumidor externo no puede cargarlo directamente.
- **Clasificación:** **compatible solo como artefacto histórico**; **no es un
  contrato de serialización**.
- **Contrato que falta:** codec de claves (o listas de componentes),
  metadata, `min_n`, hashes de etiquetas/observaciones y loader; o declaración
  explícita de “solo informe”.

### 4.6 `profile_ranges.json`

- **Generador:** `python -m motor.player_ranges --json`
  (`motor/player_ranges.py:419-429`), sobre la ventana fiable.
- **Campos:** `meta` (alpha, origen, ventana, `hands_input=877`,
  `hands_used=866`, `code_commit="0fcceed"`, `arbol_sucio=true`, `built_at`),
  `perfil` (139 jugadores), `opp` (6 claves), `cnt` (21 claves) y `omega`
  (139 jugadores).
- **Consumidores semánticos:** `tools/range_lab_gui.py` y
  `tools/diagnosticar_56_154.py`.
- **Loader:** `ProfileRangeModel.load()` (`motor/player_ranges.py:375-388`)
  solo usa `meta['alpha']`; no valida ni conserva el resto de `meta`
  (`hands_input`, `hands_used`, `code_commit`, `arbol_sucio`, `built_at`,
  `hands_window`). Lee `perfil`, `opp`, `cnt` y `omega`, pero no restaura
  `profiles`; deja `n_hands_input` y `n_hands_used` en `None`.
  `player_omega()` funciona por la caché `_omega`, pero el modelo cargado no
  puede auditar su procedencia.
- **Dependencias:** etiquetas/perfil, `omega` (que depende de `Profiles` y
  matrices), eventos preflop, `preflop_matrices.json`, posición, spot y acción.
  El prior se lee de `preflop_matrices.json`, cuya versión no está en `meta`.
- **Si está desactualizado:** el modelo se carga sin aviso y se puede usar con
  manos o etiquetas actuales. No hay comprobación de base, ventana, hash de
  líneas ni hash de etiquetas.
- **Impacto estratégico:** sí, si se usa en `recommend_loop`, en el laboratorio
  o en cualquier cálculo de equity. En producción actual no se carga; se
  reconstruye.
- **Clasificación:** **compatible solo como artefacto histórico**. Como modelo
  cargado para la base actual es **inseguro/no verificable**.
- **Contrato que falta:** hash de base, hash de líneas seleccionadas, hash de
  `preflop_matrices`, hash del mapa de etiquetas, versión de límites de campo,
  restauración de contadores y validación que falle cerrada.

### 4.7 `postflop_ranges.json`

- **Generador:** `python -m motor.postflop_ranges --json`
  (`motor/postflop_ranges.py:293-306`), sobre la ventana fiable.
- **Campos:** `meta` (alpha, `n_buckets=5`, origen, ventana, `hands_input=877`,
  `hands_used=866`, `code_commit="0fcceed"`, `arbol_sucio=true`, `built_at`),
  `labels` (139), `opp` (116) y `cnt` (197). No incluye el `Oracle` ni un hash
  de sus tablas.
- **Consumidores semánticos:** `tools/range_lab_gui.py` y
  `tools/diagnosticar_56_154.py`.
- **Loader:** `PostflopRangeModel.load()` (`motor/postflop_ranges.py:275-290`)
  solo usa `meta['alpha']` y `meta['n_buckets']`; lee `labels`, `opp` y `cnt`,
  pero:
  - no restaura `_oracle`;
  - no restaura `n_hands_input` ni `n_hands_used`;
  - no valida el resto de `meta`, la base, la ventana ni el commit.
- **Consecuencia medida:** en un modelo cargado sin reinyectar Oracle,
  `p_action()` usa un prior plano `0.2` para celdas con `opp > 0` y devuelve
  `0.0` para celdas sin `opp`. Frente a un modelo reconstruido desde la ventana
  actual de 877, sobre 116 celdas y 580 probabilidades:
  - diferencia absoluta media: `0.0621`;
  - diferencia absoluta máxima: `0.2504`.
  `tools/range_lab_gui.py` reinyecta un Oracle para evitar el prior plano, pero
  lo construye con etiquetas históricas y observaciones actuales.
- **Dependencias:** observaciones postflop, etiquetas, algoritmo de buckets
  (`hand_evaluator`), Oracle/`behavior`, `alpha`, `n_buckets` y límites de
  campo.
- **Si está desactualizado:** el modelo se carga sin aviso y actualiza rangos
  con probabilidades de 877 y un prior que puede no corresponder. No hay
  fingerprint.
- **Impacto estratégico:** alto; es el modelo que actualiza el rango rival en
  cada calle.
- **Clasificación:** **inseguro/no verificable como modelo autónomo**;
  **compatible solo como artefacto histórico de lectura**.
- **Contrato que falta:** serializar el Oracle o su hash/priors, restaurarlo en
  `load`, validar base/ventana/etiquetas/observaciones, versionar el algoritmo
  de buckets y fallar cerrado si falta el prior.

---

## 5. Contratos que faltan para regenerar de forma segura

### 5.1 Contrato mínimo común

Todo derivado que aspire a ser entrada —no solo informe— debería declarar:

```text
schema_version
generator
command
code_commit
arbol_sucio
built_at

source_base:
  commit
  sha256
  lines
  window_rule
  window_limit
  selected_ids_sha256
  excluded_ids_sha256
  field_limits_version

counts:
  hands_input
  hands_valid
  hands_used
  observations
  players

cross_artifact:
  labels_sha256
  observations_sha256
  preflop_matrices_sha256
```

Y el loader debe:

- comprobar todos los fingerprints contra la base y los artefactos que declara;
- rechazar una combinación que no coincida;
- no sustituir un fallo por un prior plano, una etiqueta `?` o un fallback
  silencioso;
- distinguir “informe histórico” de “modelo cargado”.

### 5.2 Qué falta por derivado

| Derivado | Falta para ser entrada segura |
|---|---|
| `preflop_stats.json` | Metadata de base/ventana, hash de líneas, esquema y loader; decidir si es solo informe |
| `player_stats.json` | Denominadores/conteos, metadata, esquema y loader |
| `profiles.json` | `counts`, regla de inclusión, hash de etiquetas, metadata y loader |
| `observations.json` | Envoltorio con metadata, esquema, hash de IDs de origen, versión de límites y validador |
| `behavior.json` | Codec de claves, `min_n`, hashes de etiquetas/observaciones, metadata y loader; o declarar “solo informe” |
| `profile_ranges.json` | Hash de base/líneas/matrices/etiquetas, restauración de contadores, validación de `meta` y fallo cerrado |
| `postflop_ranges.json` | Oracle serializado o prior verificable, hashes de etiquetas/observaciones, versión de buckets, contadores y fallo cerrado |

### 5.3 Dependencias: no todos se regeneran juntos

La dependencia real no es una cadena única. Es aproximadamente:

```text
base + ventana + límites de campo
├── preflop_stats          (learn.preflop_events)
├── player_stats           (stats.TransitionStats)
│   └── profiles           (TransitionStats + preflop_matrices)
│       ├── labels
│       ├── profile_ranges (preflop_events + labels + profiles/omega + matrices)
│       └── behavior       (observations + labels)
├── observations           (extract_hands)
│   └── behavior
│       └── postflop_ranges (observations + labels + Oracle + buckets)
```

Matices importantes:

- `profiles.json` **no** se construye leyendo `player_stats.json`; ambos
  consumen `TransitionStats` en memoria. Un contrato que los trate como cadena
  de ficheros sería incorrecto.
- `behavior.json` **no** se construye leyendo `observations.json`; llama a
  `extract_hands` en memoria. El contrato de ficheros tendría que decidir si
  quiere conservar esa independencia o convertir observaciones en fuente.
- `postflop_ranges.json` necesita el `Oracle`, pero el `Oracle` no está
  serializado. No basta con regenerar `opp`/`cnt`.
- `preflop_stats.json` y `player_stats.json` son independientes entre sí;
  podrían actualizarse sin tocar rangos, siempre que se declare la misma
  ventana.

### 5.4 Regeneración y ventana

Los siete CLIs actuales usan `load_hands(reliable_only=True)`:

- `motor/learn.py:742`
- `motor/stats.py:264`
- `motor/profile.py:349`
- `motor/player_ranges.py:423`
- `motor/postflop_ranges.py:300`
- `motor/observations.py:276`
- `motor/behavior.py:278`

Por tanto, ejecutar `python tools/reconstruir_derivados.py regen` hoy **no**
produciría artefactos de 1344: produciría otra vez la ventana de 877. Cualquier
regeneración futura debe decidir explícitamente:

1. si la fuente es la ventana fiable de 877 o la base completa de 1344;
2. si se mantienen las 23 exclusiones CM-004;
3. qué límites de campo se aplican;
4. si el asistente live también cambia de ventana;
5. cómo se evita que un artefacto de una ventana se mezcle con un modelo de
   otra.

Esa decisión no está tomada y no se toma en esta fase.

---

## 6. Matriz de compatibilidad y conclusión

### 6.1 Compatibilidad por derivado

| Derivado | ¿Puede seguir consumiéndose? | Restricción | ¿Afecta a recomendaciones? | ¿Contrato nuevo antes de regenerar? |
|---|---|---|---|---|
| `preflop_stats.json` | Sí, como informe histórico de solo lectura | No presentarlo como 1344; no usarlo como entrada | No en el repositorio | Sí, si se convierte en entrada |
| `player_stats.json` | Sí, como informe histórico | No presentarlo como 1344; faltan denominadores | No en el repositorio | Sí, si se convierte en entrada |
| `profiles.json` | Sí, como informe histórico | No presentarlo como 1344; no usarlo como fuente de etiquetas sin contrato | No en el repositorio | Sí, si se convierte en entrada |
| `observations.json` | Sí, como volcado histórico de solo lectura | No reutilizar IDs/acciones sin comprobar la base; no es esquema estable | No por sí solo; alto riesgo como materia prima | Sí |
| `behavior.json` | Sí, como informe histórico | No alimentar `Oracle` directamente; no es round-trip | No en el repositorio | Sí, si se convierte en entrada |
| `profile_ranges.json` | Solo lectura histórica; no como modelo actual | Sin fingerprint de base/ventana/etiquetas; `load` solo usa `meta['alpha']` y no valida procedencia | Sí, si se inyecta en `recommend_loop` o en el laboratorio | Sí |
| `postflop_ranges.json` | Solo lectura histórica; no como modelo autónomo | `load` pierde Oracle; sin fingerprint; labels históricas | Sí, si se inyecta en `recommend_loop` o en el laboratorio | Sí |

**Ninguno de los siete es “compatible con la base canónica de 1344” como
cálculo actual.** Los cinco informes pueden conservarse; los dos modelos de
rango solo pueden conservarse como legado verificable, no como modelos
vigentes.

### 6.2 Respuesta a la pregunta de mezcla

- **En producción:** no hay mezcla de 1344 con los JSON históricos, porque
  producción no lee los JSON. Sí hay una selección silenciosa de 877 de 1344.
- **En el laboratorio:** sí hay una mezcla concreta. `range_lab_gui` carga
  rangos históricos y reconstruye el Oracle postflop con la ventana actual de
  877, sin comprobar que compartan base, ventana o etiquetas.
- **En la API:** `recommend_loop.recommend()` acepta `range_model` y
  `postflop_model` sin ningún parámetro de procedencia. Cualquier llamador
  puede inyectar un modelo cargado de disco. Es un hueco de contrato, aunque
  el llamador actual (`asistente_live`) construya modelos frescos.
- **No se encontró** un camino de producción que use las 1344 completas junto
  con los derivados históricos.

### 6.3 Conclusión explícita

1. **Pueden seguir consumiéndose sin cambios** los cinco informes
   (`preflop_stats`, `player_stats`, `profiles`, `observations`, `behavior`)
   **solo como documentación histórica de solo lectura**. No son entradas del
   motor y no deben presentarse como cálculos sobre 1344.

2. **`profile_ranges.json` y `postflop_ranges.json`** pueden seguir
   consultándose en contextos forenses o de diagnóstico, pero **no deben usarse
   como modelos vigentes** ni regenerarse sin un contrato que declare y valide
   base, ventana, etiquetas, matrices, límites de campo y —en postflop— el
   Oracle.

3. **`behavior.json` no es un formato de intercambio**: es un informe. Si se
   quiere usar como entrada, necesita codec de claves y loader; hoy falla.

4. **`postflop_ranges.json` es el caso más urgente**: su loader no restaura el
   prior y el archivo no lo contiene. Un consumidor que no reinyecte el Oracle
   obtiene probabilidades distintas sin ningún aviso.

5. **No se autoriza regenerar, reanclar ni cambiar la ventana.** La fase
   termina aquí.

---

## 7. Evidencia reproducible

### 7.1 Integridad de la adopción

```powershell
python tools/verificar_adopcion_1344.py
```

Resultado: `OK` en las 12 comprobaciones; base
`3f0e7e5e...` / 1344 líneas / 2.070.355 bytes; 7/7 hashes de derivados;
ventana 877; `MULTIWAY_SOPORTADO=False`.

```powershell
python tools/verificar_ventana_calibracion.py
```

Resultado: ventana provisional de 877, hash de líneas seleccionadas
`ea99bae6...`, 23 exclusiones.

### 7.2 Pruebas de los loaders de rango

```powershell
python -m pytest motor/test_player_ranges.py motor/test_postflop_ranges.py -q
```

Resultado: `36 passed`. Estas pruebas usan ficheros temporales; no validan la
procedencia de los JSON canónicos ni la restauración del Oracle.

### 7.3 Búsqueda de lectores

```powershell
Get-ChildItem -Recurse -File -Filter *.py |
  Where-Object { $_.FullName -notmatch '__pycache__' } |
  Select-String -Pattern 'preflop_stats|player_stats|profiles\.json|profile_ranges|postflop_ranges|observations\.json|behavior\.json'
```

La revisión de las 45 coincidencias deja:

- lectores semánticos: `tools/range_lab_gui.py`,
  `tools/diagnosticar_56_154.py`;
- lectores de integridad/copia: `tools/reconstruir_derivados.py`,
  `tools/verificar_adopcion_1344.py`;
- generadores y comentarios: el resto;
- pruebas de round-trip: `motor/test_player_ranges.py`,
  `motor/test_postflop_ranges.py` (ficheros temporales).

### 7.4 Comprobaciones de contrato

- `behavior.json` cargado en `Oracle` y consultado con `p_action`: falla con
  `ValueError: too many values to unpack (expected 3)`.
- `PostflopRangeModel.load()`: `_oracle is None`, `n_hands_input is None`,
  `n_hands_used is None`; 116 celdas y 580 probabilidades frente a un modelo
  fresco de 877: diferencia media `0.0621`, máxima `0.2504`.
- `ProfileRangeModel.load()`: `profiles is None`, `n_hands_input is None`,
  `n_hands_used is None`; `_omega` se conserva.
- Comparación `51a6fb9` → `8594ed5` por `hand_id`: 91 IDs nuevos, 127 IDs
  comunes cambiados, 106 de los 877 IDs de la ventana actual cambiados.

### 7.5 Límites de esta evidencia

- Es una búsqueda estática; no cubre consumidores externos ni código generado
  en tiempo de ejecución.
- No se ejecutó `reconstruir_derivados.py regen` ni ningún CLI que escriba
  derivados.
- No se ejecutó la suite completa ni se declara verde. Los pines históricos de
  1253 siguen fuera de alcance y no se reanclaron.
- No se declara reproducibilidad de la base ni calibración validada.

---

## Anexo A. Hashes y tamaños de los siete derivados

Registrados en `data/calibration_window.json` y comprobados por
`tools/verificar_adopcion_1344.py`.

| Derivado | Bytes | SHA-256 |
|---|---:|---|
| `preflop_stats.json` | 147.632 | `53fae60a515382146c76477f8cb92cc2fb42de0ae180e7aba90efce362987749` |
| `player_stats.json` | 85.652 | `ae6babbcbf94d018f5ba4590c7cc9143ca244836a14cf5370c55f56d55306e44` |
| `profiles.json` | 75.553 | `24037cc5ba0dd97afe208abe1498fed4db5cf935f5254b838641efb2f0ab110b` |
| `profile_ranges.json` | 90.334 | `add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa` |
| `postflop_ranges.json` | 13.709 | `1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c` |
| `observations.json` | 4.738.786 | `86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3` |
| `behavior.json` | 27.908 | `efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae` |

## Anexo B. Referencias de código

| Tema | Referencia |
|---|---|
| Carga de la ventana fiable | `motor/learn.py:236-274` |
| Generación de `preflop_stats` | `motor/learn.py:646-748` |
| Generación de `player_stats` | `motor/stats.py:260-271` |
| Generación de `profiles` | `motor/profile.py:244-279`, `340-359` |
| Generación de `observations` | `motor/observations.py:267-286` |
| Generación de `behavior` | `motor/behavior.py:191-205`, `262-293` |
| `Oracle` | `motor/behavior.py:71-144` |
| `ProfileRangeModel.load` | `motor/player_ranges.py:375-388` |
| `PostflopRangeModel.load` | `motor/postflop_ranges.py:275-290` |
| Modelos del asistente live | `motor/asistente_live.py:476-499` |
| Uso de rangos en el asistente | `motor/asistente_live.py:1176-1189`, `1575-1590` |
| `OracleResponse` | `motor/decision.py:84-140` |
| Inyección en `recommend_loop` | `motor/recommend_loop.py:256-280`, `384-392` |
| Laboratorio mixto | `tools/range_lab_gui.py:47-89` |
| Diagnóstico histórico | `tools/diagnosticar_56_154.py:19-24`, `45-113` |
| Reconstrucción de derivados | `tools/reconstruir_derivados.py:26-28`, `98-191` |
| Verificador de adopción | `tools/verificar_adopcion_1344.py:57-72`, `160-177`, `224-270` |
| Referencia muerta a `PostflopModel` | `tools/auditar_equity_observable.py:90`; `tools/equity_de_mano.py:439` |
