# Auditoría del pipeline de modelos live

**De `data/hands_db.jsonl` a `motor/asistente_live.py::build_models()` y sus recomendaciones**

- **Fecha:** 2026-11-11
- **HEAD auditado:** `c4fd70b` (local, sin push)
- **Base canónica:** `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`, 2.070.355 bytes, 1.344 líneas
- **Ventana live:** 877 manos (`H_0001..H_0926`, con huecos), línea física 900 = `H_0926`; línea 901 = `H_0927`
- **Naturaleza:** auditoría de solo lectura. **No** es calibración ni validación estratégica.
- **Entregable:** este documento. No se modificaron datos, derivados, hashes, manifiestos, pines, rangos, estrategia, `build_models()`, la selección 877, `MULTIWAY_SOPORTADO=False`, ni se ejecutaron sesiones reales ni B2.

> **Advertencia de interpretación.** Esta auditoría separa cuatro cosas que suelen mezclarse:
> 1. **integridad mecánica** (¿el pipeline lee lo que dice leer, sin derivados viejos ni fallbacks silenciosos?);
> 2. **procedencia y aptitud del dato** (¿la base y la ventana son reproducibles y representativas?);
> 3. **validez matemática** (¿los conteos, priors, shrinkage y agregaciones sostienen lo que se afirma?);
> 4. **calidad estratégica de la recomendación** (¿la recomendación mejora EV en mesas reales?).
>
> El pipeline puede ser mecánicamente limpio y, a la vez, alimentar modelos con campos defectuosos y con un mapeo de acciones distinto entre entrenamiento y serving. Ninguna conclusión de este documento autoriza a usar las recomendaciones como evidencia de mejora estratégica.

---

## 1. Resumen ejecutivo

### 1.1 Lo que está bien

1. **No hay contaminación directa por los siete derivados históricos** en el camino de producción. `build_models()` llama a `load_hands(reliable_only=True)` y reconstruye `Profiles`, `ProfileRangeModel`, `Oracle` y `PostflopRangeModel` desde la base actual. Ningún módulo de producción abre `profiles.json`, `player_stats.json`, `preflop_stats.json`, `profile_ranges.json`, `postflop_ranges.json`, `observations.json` ni `behavior.json`.
2. **La ventana 877 es reproducible mecánicamente:** primeras 900 líneas físicas, todas JSON válido con `players` y `streets`, menos 23 IDs CM-004. Resultado exacto: 877 manos.
3. **No hay fallback silencioso a datos viejos** dentro de `build_models()`. Si falta la base o una tabla estática, el comportamiento es error, tabla plana/cobertura declarada o valor 0 con warning; no se carga un JSON histórico.
4. **El verificador de adopción pasa sus 12 comprobaciones de integridad** (hash de base, bytes, líneas, manifiesto, hashes de los siete derivados, snapshot de calibración, ventana 877, metadata legacy, hash de `preflop_matrices.json`, `MULTIWAY_SOPORTADO=False`). Eso prueba integridad de artefactos, **no** aptitud de los modelos.
5. **Los tests dirigidos de los dos modelos de rango pasan:** `36 passed` en `motor/test_player_ranges.py` y `motor/test_postflop_ranges.py`. No hay afirmación de suite completa verde.

### 1.2 Hallazgos que impiden tratar los modelos como “listos”

1. **P0 — El mapeo preflop de serving no coincide con el de entrenamiento.**
   - `learn.classify_first_action()` clasifica `b` y `r` **por contexto**: con `raises_before=0`, tanto `b` como `r` pueden ser `open`/`rol`; con `raises_before=1`, pueden ser `3bet`/`squeeze`.
   - `asistente_live._preflop_spot()` hace un mapeo plano: `b -> open`, `r -> 3bet`, `c -> call_open`, `x -> limp`, sin mirar `raises_before` ni `limps_before`.
   - `asistente_live._preflop_raises()` solo cuenta `r`; ignora por completo `b`.
   - En la ventana 877 hay **162 acciones preflop `b` con importe > 1 BB**. El entrenamiento las usa según contexto; el serving las interpreta como `open` (rango rival) o las ignora (héroe).
   - Consecuencia: una apertura grabada como `r` —la codificación dominante— es leída por el rango rival como **3bet**; un check de BB grabado como `x` es leído como **limp**; un call en bote limpeado grabado como `c` es leído como **call_open**. No hay test de paridad entre ambos parsers.
2. **P0 — No se aplica ninguna restricción por campo defectuoso.** Las 877 manos entran completas. En concreto:
   - 10 manos con restricción de acciones (`H_0005`, `H_0059`, `H_0214`, `H_0226`, `H_0327`, `H_0357`, `H_0832`, `H_0834`, `H_0925`, `H_0926`) aportan 16 eventos preflop conocidos, 20 observaciones postflop usadas y **126 observaciones al `Oracle`**.
   - `H_0926` contiene un `SB x` imposible después del fold de flop y aun así entra en el `Oracle`; `H_0832` contiene un limp corto grabado como `b`.
   - 9 manos con restricción de tablero: 8 observaciones postflop se pierden por tablero ausente, pero las 9 manos siguen en el resto de modelos.
   - El defecto de `showdown` de `H_0798` solo afecta W$SD; no debe excluir la mano de rangos.
3. **P0 — El perfil histórico y el perfil live no usan la misma regla.**
   - Histórico: `simple_label(stack_mean, vpip, pfr)`; si el stack medio es alto pero VPIP > 32 % y PFR < 10 %, el jugador es **PEZ**.
   - Live: `_perfil_for()` solo mira stack medio de la sesión/stack actual; sin información devuelve **TIBURON**. No reproduce el fallback VPIP/PFR.
   - **22 de los 78 PEZ históricos (28,2 %)** son PEZ por el fallback VPIP/PFR con stack medio ≥ 50 BB. Live los clasificaría TIBURON con el mismo stack. Ejemplos: `Sp1609` (1 mano, VPIP 100 %, PFR 0 %), `Franco1603` (52 manos, VPIP 82,7 %, PFR 1,9 %), `Silvio` (30 manos, VPIP 90 %, PFR 6,7 %).
   - El modelo no usa `prob_vec_player()`/omega individual en producción; el live es un modelo **por etiqueta de perfil**, no por jugador.
4. **P0 — `PostflopRangeModel.n_hands_used = 864` es engañoso.** El metadato cuenta manos con cartas conocidas, no manos que aportan postflop. Las manos que realmente contribuyen son **339**; 525 son solo preflop. El modelo tiene 1.388 observaciones postflop, 116 celdas, 47 con `n < 5` y 74 con `n < 10`. En el punto de decisión no se expone `n`.
5. **P1 — La selección 877 omite el 36,8 % de las acciones de la base.** Las 877 manos representan el 63,2 % de las acciones de las 1.344; la cola de 444 manos aporta el 34,9 % y las 23 CM-004 el 1,8 %; ambas quedan fuera. La cola añadiría, en un contrafactual no autorizado, 45 perfiles, 4.876 observaciones y 209 manos postflop contribuyentes, pero solo 5 celdas postflop nuevas y **ningún** evento nuevo en `PEZ/facing_3bet` (sigue en 5). Más datos no arreglan uniformemente las celdas débiles.
6. **P1 — La ventana 877 incluye 106 manos que cambiaron respecto de `51a6fb9`.** Hay 76 campos de acciones de calle distintos (15 preflop, 25 flop, 19 turn, 17 river), 44 cambios de texto de showdown, 5 cambios de `active`, 1 cambio de identidad de jugador y 1 cambio de nombre de ganador. No hay cambios de stack/posición/tablero/`final_pot` entre esas 106. Algunas ediciones quitaron checks fantasma; otras insertaron checks, y una (`H_0926`) insertó un check en una secuencia que sigue siendo imposible.
7. **P1 — La procedencia de `data/preflop_matrices.json` es opaca.** Es el modelo real de preflop del héroe (117 tablas, fuera de `build_models`), no tiene bloque de procedencia, y su hash está pinneado (`075bae...`) pero no se liga a una base/ventana. La auditoría de cobertura reporta 107 tablas exactas, 1 alias, 2 ausencias intencionales y 30 huecos posibles; las tablas `SQUEEZE` (6) y `Over_Call` (3) no son consultadas por `_recom_preflop`.
8. **P1 — `tools/range_lab_gui.py` puede mezclar rangos históricos con Oracle actual.** Carga `profile_ranges.json`/`postflop_ranges.json` si existen; luego reconstruye el `Oracle` con las 877 actuales y las etiquetas del artefacto histórico. `PostflopRangeModel.load()` pierde `_oracle` por diseño. No hay guardia de procedencia ni comparación de hashes. Es una ruta auxiliar, pero puede producir evidencia aparentemente “actual” sobre modelos viejos.
9. **P2 — `tools/diagnosticar_56_154.py` no es evidencia del estado actual.** Compara el snapshot histórico `data/_snapshot_pre_rebuild_1b14c18` con JSON legacy; sirve para diagnosticar aquel corte, no para afirmar qué hacen los modelos live de hoy.
10. **P2 — Erratum de la auditoría previa:** `player_stats.json` **sí** guarda denominadores, como pares `[opp, act]`. El que guarda frecuencias sin conteos es `profiles.json`. La afirmación anterior estaba invertida.

### 1.3 Veredicto por eje

| Eje | Veredicto | Motivo |
|---|---|---|
| Integridad mecánica | **Pasa con reservas** | Rebuild determinista desde la base; sin derivados en producción; 36 tests dirigidos verdes; pero sin sello de procedencia y sin suite completa. |
| Procedencia / aptitud del dato | **No apta para uso irrestricto** | Ventana 877 provisional; 23 CM-004 con motivo desactualizado; 444 manos fuera; 106 manos editadas; defectos de campo sin restringir. |
| Validez matemática | **Provisional / no validada** | Conteos pequeños, `alpha=2`, prior plano, `min_n=3`, `fade_n=20`, metadato postflop incorrecto, sin intervalos ni validación out-of-sample. |
| Calidad estratégica | **No establecida** | Mismatch de parser preflop, etiquetas live vs históricas, modelo por perfil sin omega individual, sin sesiones reales ni medición de EV. |

---

## 2. Alcance, método y límites

### 2.1 Alcance

Se auditó la cadena completa:

1. `data/hands_db.jsonl` y `motor/learn.py::load_hands()`.
2. La selección de 877 manos y las 23 exclusiones CM-004.
3. `motor/profile.py::Profiles.from_hands()` y `motor/stats.py::TransitionStats`.
4. `motor/player_ranges.py::ProfileRangeModel`.
5. `motor/observations.py::extract_hand(s)` y `motor/behavior.py::Oracle`.
6. `motor/postflop_ranges.py::PostflopRangeModel`.
7. `motor/preflop.py` y `data/preflop_matrices.json` (modelo real de preflop del héroe, fuera de `build_models`).
8. `motor/asistente_live.py`: `build_models()`, `_perfil_for()`, `_preflop_spot()`, `_preflop_raises()`, `_rango_main()`, `_recom_preflop()`, `_recomendacion_para()`.
9. `motor/decision.py::OracleResponse` y el consumo de EV/incertidumbre.
10. Herramientas auxiliares: `tools/range_lab_gui.py`, `tools/diagnosticar_56_154.py`, `tools/verificar_adopcion_1344.py`.

### 2.2 No objetivos

- No se regeneraron derivados ni se actualizaron hashes/manifiestos/pines.
- No se cambiaron rangos, priors, umbrales, selección 877, `build_models()` ni `MULTIWAY_SOPORTADO=False`.
- No se ejecutó B2, ni sesiones reales, ni calibración.
- No se reanclaron los tests históricos de 1.253 manos.
- No se propone aquí una estrategia nueva; solo contratos y correcciones de pipeline.

### 2.3 Método

- Lectura de código y de artefactos con scripts de solo lectura en Python.
- Reproducción de `load_hands(reliable_only=False)` y `load_hands(reliable_only=True)`.
- Reconstrucción en memoria de los modelos actuales, sin escribir artefactos.
- Diff contra `git show 51a6fb9:data/hands_db.jsonl` limitado a las 877 IDs actuales; evidencia serializada en `C:\Users\Jorgito\AppData\Local\Temp\opencode\diff_877_51a6fb9.json`.
- Conteos de modelos en `C:\Users\Jorgito\AppData\Local\Temp\opencode\models_summary.json`.
- Verificación de integridad con `python tools/verificar_adopcion_1344.py`.
- Tests dirigidos con `python -m pytest motor\test_player_ranges.py motor\test_postflop_ranges.py -q` (**36 passed, 2 warnings**; no suite completa).

---

## 3. Base, ventana y flujo real

### 3.1 La base

| Propiedad | Valor |
|---|---|
| Archivo | `data/hands_db.jsonl` |
| SHA-256 | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| Bytes | 2.070.355 |
| Líneas físicas | 1.344 |
| Manos válidas con `load_hands()` | 1.344 (`H_0001..H_1374`) |
| Manos con `reliable_only=True` | 877 (`H_0001..H_0926`, con huecos) |
| Commit que introdujo la base | `8594ed5` |
| Estado del manifiesto | Declara la base, pero el snapshot de procedencia quedó marcado no reproducible en B1; no se usa como prueba de origen. |

La base no es “la base original”: es una base adoptada y editada. El verificador confirma que el archivo actual coincide con el hash canónico y con el manifiesto, pero **no** demuestra que cada línea sea fiel a su mano original. La propia ventana de calibración está marcada `provisional` y sus derivados `stale/not adopted`.

### 3.2 `load_hands()` exactamente

`motor/learn.py::load_hands(path=None, *, max_hands=None, reliable_only=False)`:

- Lee líneas físicas en orden.
- Si `reliable_only=True`, corta en `RELIABLE_HANDS = 900` líneas físicas.
- Descarta JSON inválido, sin `players` o sin `streets`.
- Aplica `EXCLUSIONES_VENTANA_FABLE` (23 IDs CM-004).
- No rellena, no imputa y no cae a otro archivo.

Resultado reproducido:

```text
load_hands(reliable_only=False) -> 1344 manos, H_0001..H_1374
load_hands(reliable_only=True)  ->  877 manos, H_0001..H_0926
```

Las primeras 900 líneas físicas son **900 manos válidas** (`invalid_lines = []`). La línea 901 es `H_0927`. Por tanto “900 válidas” no significa “900 aptas”: es un corte mecánico de líneas, seguido de 23 exclusiones.

### 3.3 Diagrama de flujo real

```text
data/hands_db.jsonl  (1344 líneas; SHA-256 3f0e...; base adoptada)
        │
        │  load_hands(reliable_only=True)
        │  = primeras 900 líneas físicas
        │    - JSON inválido / sin players / sin streets
        │    - 23 IDs CM-004
        ▼
   877 manos  (H_0001..H_0926, con huecos; línea 900 = H_0926)
        │
        ├──────────────────────────────────────────────────────────────┐
        │                                                              │
        ▼                                                              ▼
  Profiles.from_hands()                                      extract_hands()
  ├─ TransitionStats (conteos opp/act)                        8.657 observaciones
  ├─ mean_stack_by_player()                                          │
  ├─ simple_label(stack_mean, vpip, pfr)                             ├─ behavior_table(min_n=3)
  └─ 138 perfiles (78 PEZ / 60 TIBURON)                              ▼
        │                                                        Oracle
        │                                                  111 celdas granular
        │                                                  32 celdas por_facing
        │                                                  P(A|perfil, calle, facing, textura)
        │                                                              │
        ├──────────────────────────────┐                               │
        ▼                              ▼                               │
ProfileRangeModel.from_hands()   PostflopRangeModel.from_hands()       │
├─ 864 manos con evento conocido ├─ 339 manos postflop reales          │
├─ 1.168 eventos preflop          ├─ 1.388 observaciones               │
├─ 6 celdas opp + 21 cnt          ├─ 116 celdas                        │
└─ + preflop_matrices.json        └─ _oracle = Oracle  ◄───────────────┘
   (117 tablas; estático)             (inyectado por build_models)
        │                              │
        └──────────────┬───────────────┘
                       ▼
              AsistenteLive / recomendación
              ├─ _perfil_for(): stack live -> PEZ/TIBURON
              ├─ _recom_preflop(): preflop_matrices.json (héroe; NO 877)
              ├─ _preflop_spot(): clasificación plana b/r/c/x
              │      -> range_model.prob_vec(perfil, spot, acción)
              ├─ acciones postflop observadas
              │      -> postflop_model.prob_vec(perfil, calle, facing, board, acción)
              └─ OracleResponse(oracle, label, contexto, fade_n=20)
                     -> EV / decisión
```

Rutas que **no** son producción:

```text
data/profiles.json, player_stats.json, preflop_stats.json,
profile_ranges.json, postflop_ranges.json, observations.json, behavior.json
        │
        ├─ tools/range_lab_gui.py  (auxiliar; puede mezclar con Oracle actual)
        ├─ tools/diagnosticar_56_154.py (diagnóstico histórico)
        └─ ProfileRangeModel.load() / PostflopRangeModel.load()
              (pérdida de metadatos; PostflopRangeModel.load() pierde _oracle)
```

### 3.4 Inventario de constructores

| Componente | Constructor / entrada | Salida | Consumido por |
|---|---|---|---|
| `TransitionStats` | `motor/stats.py`, `from_hands(hands)` | Contadores `[opp, act]` por jugador | `Profiles`; no va directo a live |
| `Profiles` | `motor/profile.py::Profiles.from_hands(hands)` | 138 perfiles, etiquetas PEZ/TIBURON, `stack_mean`, `n`, frecuencias | `build_models`, etiquetas de rango/Oracle/postflop |
| `PlayerProfile.omega` | `Profile` + `preflop_matrices` | Ajuste individual opcional | No usado por `asistente_live` |
| `ProfileRangeModel` | `motor/player_ranges.py::from_hands(hands, labels)` | `P(A|H, spot, perfil)`; 864/1.168; 6 opp + 21 cnt | `_rango_main`, `_recomendacion_para` |
| `extract_hand(s)` | `motor/observations.py` | 8.657 `Observation` | `Oracle`, `PostflopRangeModel` |
| `Oracle` | `motor/behavior.py::build(hands, labels, min_n=3)` | 111 granular + 32 por_facing | `OracleResponse`; prior de `PostflopRangeModel` |
| `PostflopRangeModel` | `motor/postflop_ranges.py::from_hands(hands, labels)` | 116 celdas, 1.388 obs, 339 manos reales; `alpha=2` | `_rango_main`, `_recomendacion_para` |
| `preflop_matrices` | `motor/preflop.py::load_tables()` + `lookup_table()` | 117 tablas de probabilidad | `_recom_preflop` (héroe); no `build_models` |
| `OracleResponse` | `motor/decision.py` | Mezcla perfil + heurística con `fade_n=20` | Decisión/EV |
| `AsistenteLive` | `motor/asistente_live.py` | Recomendación live | Producción |
| `recommend_loop.recommend` | `motor/recommend_loop.py` | Demo/recomendación con modelos inyectables | No es el camino live actual |

---

## 4. Auditoría exacta de las 877 manos

### 4.1 900 válidas → 877

La regla declarada en `data/calibration_window.json`:

```text
rule: "first 900 physical lines of data/hands_db.jsonl;
       keep valid JSON with players+streets; drop CM-004 exclusions"
reliable_hands_limit: 900
physical_lines_considered: 900
valid_hands: 900
invalid_lines: []
excluded_count: 23
selected_count: 877
selected_lines_sha256: ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed
```

La selección no es un holdout aleatorio ni un corte temporal “hasta una fecha”: es un corte por orden físico de registro. No hay garantía de que las primeras 900 manos sean representativas de la población posterior. La cola de 444 manos contiene 45 jugadores nuevos y 29 que ya aparecen en la ventana; es una muestra distinta, no una extensión neutra.

### 4.2 Las 23 exclusiones CM-004

IDs exactos:

```text
H_0031 H_0037 H_0039 H_0051 H_0067 H_0078 H_0104 H_0107 H_0109
H_0127 H_0143 H_0147 H_0161 H_0170 H_0183 H_0210 H_0215 H_0248
H_0262 H_0263 H_0279 H_0294 H_0722
```

Contenido agregado de las 23:

- 303 acciones totales; 22 con showdown; 23 con cartas de héroe.
- 16 manos con flop, 10 con turn, 5 con river.
- 38 nombres de jugadores.
- Líneas físicas 30–696; todas dentro de las primeras 900.
- 2,6 % de las manos de la ventana; 1,8 % de las acciones de la base completa.

| Mano | Línea | Acciones | Pre/Flop/Turn/River | Showdown | Bote final |
|---|---:|---:|---|---|---:|
| H_0031 | 30 | 7 | 7/0/0/0 | sí | 6.0 |
| H_0037 | 36 | 15 | 10/5/0/0 | sí | 31.5 |
| H_0039 | 38 | 16 | 12/2/2/0 | sí | 36.6 |
| H_0051 | 50 | 8 | 8/0/0/0 | sí | 6.0 |
| H_0067 | 66 | 11 | 8/3/0/0 | sí | 6.35 |
| H_0078 | 76 | 15 | 10/5/0/0 | sí | 40.7 |
| H_0104 | 102 | 15 | 12/3/0/0 | sí | 19.4 |
| H_0107 | 105 | 14 | 11/3/0/0 | sí | 20.0 |
| H_0109 | 107 | 9 | 9/0/0/0 | sí | 4.0 |
| H_0127 | 125 | 10 | 10/0/0/0 | sí | 16.5 |
| H_0143 | 141 | 17 | 9/3/3/2 | sí | 36.425 |
| H_0147 | 144 | 18 | 9/3/3/3 | sí | 44.365 |
| H_0161 | 158 | 18 | 10/4/2/2 | sí | 44.965 |
| H_0170 | 165 | 13 | 9/2/2/0 | sí | 21.425 |
| H_0183 | 178 | 16 | 10/4/2/0 | sí | 31.4 |
| H_0210 | 205 | 15 | 9/2/3/1 | sí | 56.4 |
| H_0215 | 210 | 18 | 12/4/2/0 | sí | 52.27 |
| H_0248 | 243 | 9 | 9/0/0/0 | sí | 9.0 |
| H_0262 | 257 | 8 | 8/0/0/0 | sí | 6.0 |
| H_0263 | 258 | 13 | 10/3/0/0 | sí | 9.3 |
| H_0279 | 274 | 7 | 7/0/0/0 | sí | 6.0 |
| H_0294 | 289 | 11 | 7/2/2/0 | sí | 8.7 |
| H_0722 | 696 | 20 | 9/3/5/3 | no | 15.2 |

**Erratum CM-004.** El texto histórico conservado en `data/calibration_window.json` dice que se excluyen porque “la ciega del BB después de acciones voluntarias se lee como una subida que pudo no ocurrir”. Ese defecto de orden ya no existe: la base actual tiene cero violaciones del invariante según el comentario vigente de `motor/learn.py` (el último caso, `BB r` de `H_1196`, es posterior a la ventana). El motivo vigente no es el defecto original: las 23 manos fueron reescritas a mano y **no conservan originales**, por lo que no se puede reconstruir con fidelidad su campo original. La decisión de mantenerlas fuera sigue abierta; este documento no la cambia. No debe citarse el texto viejo como justificación técnica actual.

Esto **no** autoriza a excluir manos de las 877 por falta de procedencia. Dentro de la ventana no hay un defecto de procedencia por mano que justifique eliminar la mano completa; las 23 CM-004 son una decisión histórica aparte. Las restricciones que propone este informe son por campo: acciones, tablero, stack, asiento, showdown.

**Qué elimina la exclusión.** A nivel de modelos, pasar de 900 a 877 produce:

| Métrica | 900 (con CM-004) | 877 (ventana live) | Diferencia |
|---|---:|---:|---:|
| Manos | 900 | 877 | −23 |
| Perfiles | 139 | 138 | −1 (`P5` desaparece) |
| Rango: manos usadas | 887 | 864 | −23 |
| Rango: eventos preflop | 1.199 | 1.168 | −31 |
| Oracle: observaciones | 8.908 | 8.657 | −251 |
| Postflop: observaciones | 1.407 | 1.388 | −19 |
| Postflop: celdas | 116 | 116 | 0 |
| `PEZ no_raise/facing_open/facing_3bet` | 132/55/5 | 128/55/5 | −4/0/0 |
| `TIBURON no_raise/facing_open/facing_3bet` | 679/312/16 | 652/312/16 | −27/0/0 |

La exclusión no toca las celdas más débiles (`PEZ/facing_3bet=5`, `TIBURON/facing_3bet=16`). Sí cambia una etiqueta: **`Valentina22` pasa de TIBURON a PEZ** al quitar las 23 manos, porque su stack medio baja de 50,3 a 48,8 BB con solo 2–3 manos. Es un ejemplo directo de etiqueta inestable por umbral.

### 4.3 La cola de 444 manos

Contenido de las 444 manos fuera de la ventana (líneas 901–1344):

- 5.758 acciones; 34,9 % de las acciones de la base completa (16.486).
- 143 showdowns; 444 manos con cartas de héroe.
- 317 manos con flop, 242 con turn, 174 con river.
- 74 jugadores: 45 nuevos, 29 ya presentes en la ventana.

Contrafactual de información **no autorizado y no ajustado por calidad**: construir los mismos modelos con 1.321 manos = 877 + 444, manteniendo fuera las 23 CM-004. No es una propuesta de adopción; solo cuantifica lo que hoy no se usa.

| Métrica | 877 | 1.321 (877+444) | Añadiría |
|---|---:|---:|---:|
| Perfiles | 138 | 183 | +45 |
| Rango: manos usadas | 864 | 1.301 | +437 |
| Rango: eventos preflop | 1.168 | 1.796 | +628 |
| Postflop: observaciones | 1.388 | 2.334 | +946 |
| Postflop: manos contribuyentes | 339 | 548 | +209 |
| Oracle: observaciones | 8.657 | 13.533 | +4.876 |
| Postflop: celdas | 116 | 121 | +5 |
| Oracle: celdas granular | 111 | 118 | +7 |
| `PEZ no_raise/facing_open/facing_3bet` | 128/55/5 | 193/96/5 | +65/+41/0 |
| `TIBURON no_raise/facing_open/facing_3bet` | 652/312/16 | 1.024/453/25 | +372/+141/+9 |

Lectura: la cola añade mucho volumen y 45 perfiles nuevos, pero **no añade ni un solo evento a `PEZ/facing_3bet`** y solo 5 celdas postflop. La mejora no es uniforme; agregar manos no garantiza cubrir los huecos que hoy importan. Tampoco se ha evaluado si esas 444 manos son más o menos limpias que las 877.

### 4.4 Qué cambió respecto de `51a6fb9`

`51a6fb9` es una base histórica de 1.253 líneas (`H_0001..H_1282`, SHA-256 `c3172a14...`). El diff limitado a las 877 IDs actuales encuentra:

- **106 de las 877 manos actuales cambiaron** respecto de `51a6fb9`.
- Campos afectados (una mano puede tener varios):
  - `actions_preflop`: 15 manos.
  - `actions_flop`: 25.
  - `actions_turn`: 19.
  - `actions_river`: 17.
  - `top_showdown`: 44.
  - `player_active`: 5.
  - `players_set` / `players_count`: 1 (`H_0060`, identidad `HERO -> Jeffer30bog`).
  - `top_winner`: 1 (`H_0058`, `Juanmabm -> Arquejandro`).
- **No** hay cambios de `stack`, posición, tablero ni `final_pot` entre esas 106.
- En las diferencias de acciones se observan 93 checks (`x`) eliminados y 8 insertados. La mayoría de las eliminaciones son checks fantasma; no todas las inserciones son válidas:
  - `H_0926` inserta un `BB x` en el turn, pero la mano sigue conteniendo un `SB x` imposible después del fold de flop.
  - `H_0188` inserta `SB x` en turn y river.
  - `H_0486`, `H_0614`, `H_0715`, `H_0852` insertan checks de flop; `H_0855` de river.
- Los cambios de `showdown` son en su mayoría texto/formato; solo `H_0058` cambia el nombre del ganador real. `H_0798` sigue con un reparto incompleto (`showdown.winner1` no cubre el bote), que afecta W$SD, no rangos.
- Los cambios de `active` (`H_0058`, `H_0059`, `H_0061`, `H_0063`, `H_0064`) afectan el campo `active`/`players_active`, no una acción de un jugador activo en los modelos actuales. No se pierden acciones no-`p`; el efecto actual es de metadata.
- `H_0060` cambia una identidad de jugador y, por tanto, la clave de perfil de esa mano.

**Lectura correcta del diff.** Que una mano haya cambiado no implica que hoy esté defectuosa, y que no haya cambiado no implica que esté limpia. El diff prueba que la ventana actual no es la base histórica; no sustituye la restricción por campo. En particular, las manos con defectos actuales (`H_0926`, `H_0832`, `H_0798`, etc.) pueden haber cambiado o no; lo relevante es el campo defectuoso de hoy.

Lista exacta de las 106 manos cambiadas (para reproducibilidad):

```text
H_0018 H_0029 H_0038 H_0048 H_0050 H_0055 H_0058 H_0059 H_0060 H_0061
H_0063 H_0064 H_0065 H_0069 H_0071 H_0088 H_0092 H_0098 H_0099 H_0117
H_0118 H_0120 H_0123 H_0125 H_0130 H_0133 H_0134 H_0136 H_0137 H_0138
H_0140 H_0144 H_0148 H_0153 H_0171 H_0172 H_0174 H_0179 H_0186 H_0188
H_0194 H_0201 H_0203 H_0205 H_0211 H_0213 H_0224 H_0228 H_0240 H_0241
H_0257 H_0259 H_0261 H_0265 H_0266 H_0268 H_0269 H_0270 H_0271 H_0272
H_0274 H_0276 H_0281 H_0282 H_0300 H_0301 H_0306 H_0312 H_0315 H_0319
H_0322 H_0323 H_0325 H_0326 H_0327 H_0331 H_0337 H_0376 H_0415 H_0430
H_0445 H_0486 H_0527 H_0589 H_0614 H_0617 H_0640 H_0650 H_0662 H_0677
H_0691 H_0708 H_0711 H_0713 H_0715 H_0773 H_0826 H_0832 H_0841 H_0847
H_0852 H_0855 H_0886 H_0889 H_0918 H_0926
```

---

## 5. Matriz de procedencia

Principio: **un hash de archivo no es procedencia de modelo**. El pipeline actual puede reconstruir desde la base y, aun así, no dejar rastro de qué base, qué ventana, qué IDs excluidos y qué versión de código produjeron las probabilidades que se usaron en una recomendación.

| Artefacto / modelo | Universo declarado | n real | Campos / metadatos | Procedencia verificable | ¿Producción? |
|---|---|---:|---|---|---|
| `data/hands_db.jsonl` | 1.344 líneas | 1.344 | Base adoptada; IDs `H_0001..H_1374` | SHA-256 canónico; manifiesto; origen original no reproducible | Fuente única |
| `data/calibration_window.json` | Ventana 877 | 877 | `selected_lines_sha256=ea99...`; 23 IDs; `excluded_line_hashes` | Hash de selección y de líneas excluidas; estado `provisional` | Define la ventana |
| `Profiles` en memoria | 877 | 138 perfiles; 147 nombres | Etiquetas, `stack_mean`, `n`, frecuencias; sin conteos serializados | **Ninguna**: no hay hash de base/ventana/commit en el objeto | Sí |
| `TransitionStats` en memoria | 877 | 138 perfiles con eventos | Contadores `[opp, act]` | **Ninguna** | Sí, vía `Profiles` |
| `ProfileRangeModel` en memoria | 877 | 864 manos usadas; 1.168 eventos; 6 opp + 21 cnt | `alpha=2`; `n_hands_input=877`, `n_hands_used=864` | **Ninguna** en el objeto; `save()` legacy no incluye base/ventana | Sí |
| `Oracle` en memoria | 877 | 8.657 obs; 111 granular + 32 por_facing | `min_n=3`; etiquetas de 138 perfiles | **Ninguna** | Sí |
| `PostflopRangeModel` en memoria | 877 | 339 manos reales; 1.388 obs; 116 celdas | `n_hands_used=864` (engañoso); `alpha=2`; `_oracle` inyectado | **Ninguna** | Sí |
| `data/preflop_matrices.json` | 117 tablas | n/d (curated/assumed) | Solo clave `tables`; sin bloque de procedencia | SHA-256 `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1`; no ligado a base/ventana | Sí, para preflop héroe |
| `profile_ranges.json` (legacy) | 877 / 866 | 877/866; 866 usadas; 1.170 opp | `code_commit=0fcceed`; `arbol_sucio=true`; `ventana=877`; sin hash de base ni de líneas | Hash de archivo; metadata legacy; **no base** | No |
| `postflop_ranges.json` (legacy) | 877 / 866 | 877/866; 1.453 opp; 139 perfiles | Igual metadata legacy | Hash de archivo; **no base** | No |
| `observations.json` (legacy) | 877 | 8.742 obs | Metadata legacy | Hash de archivo; **no base** | No |
| `behavior.json` (legacy) | 877 | 8.742 obs; 139 perfiles | Sin loader de vuelta a `Oracle` | Hash de archivo; **no base** | No |
| `profiles.json` (legacy) | 877 | 139 perfiles | **Frecuencias sin conteos** | Hash de archivo; **no base** | No |
| `player_stats.json` (legacy) | 877 | 139 perfiles | **Pares `[opp, act]`** | Hash de archivo; **no base** | No |
| `preflop_stats.json` (legacy) | 877 | n/d | JSON legacy; sin lector de producción | Hash de archivo; **no base** | No |

**Conclusión de procedencia.** La producción actual es reproducible *mecánicamente* desde la base, pero **no es auditable hacia atrás**: un modelo guardado no dice de qué base salió, qué 877 IDs usó, qué 23 excluyó, ni qué commit lo construyó. Los siete derivados legacy sí declaran `877/866` y `code_commit=0fcceed`, pero no declaran hash de base ni de líneas seleccionadas; además están desactualizados respecto de la reconstrucción actual (139 perfiles vs 138; 8.742 vs 8.657 observaciones; 866 vs 864 manos de rango; 1.453 vs 1.388 observaciones postflop). Ningún módulo de producción los lee.

### 5.1 Erratum sobre `player_stats.json` y `profiles.json`

La auditoría anterior afirmó que `player_stats.json` guarda frecuencias sin denominadores. Es incorrecto. El estado real es:

- `data/player_stats.json`: guarda **pares `[opp, act]`**; por tanto sí conserva denominadores y permite recalcular frecuencias y `n`.
- `data/profiles.json`: guarda **frecuencias** (VPIP/PFR/WTSD/W$SD) y metadatos de etiqueta, **sin conteos**. No permite reconstruir la incertidumbre de esas frecuencias.
- `ProfileRangeModel`/`PostflopRangeModel` serializados guardan `opp`/`cnt`, pero `ProfileRangeModel.load()` pierde `profiles`, `n_hands_input` y `n_hands_used`; `PostflopRangeModel.load()` pierde `_oracle`, `n_hands_input` y `n_hands_used`.

Este erratum importa porque una revisión de confiabilidad no puede usar `profiles.json` como si tuviera denominadores; debe usar `player_stats.json` o reconstruir desde la base.

---

## 6. Matriz de defectos de campo y restricciones

La regla correcta es **restringir el campo defectuoso**, no eliminar la mano entera por procedencia dudosa. La tabla siguiente cruza el inventario `DOCS/B1_EXCEPCION_INVENTARIO.json` con la ventana 877 y con lo que cada modelo consume realmente.

### 6.1 Defectos en la ventana 877

| Clave / defecto | Manos en 877 | Campo real | ¿Afecta a los modelos live? | Detalle |
|---|---:|---|---|---|
| `secuencia_acciones` (hard sequence) | 9 + `H_0832` = **10** | `streets.*.actions` | Sí, preflop y postflop | IDs: `H_0005 H_0059 H_0214 H_0226 H_0327 H_0357 H_0832 H_0834 H_0925 H_0926`. Contribuyen 16 eventos preflop conocidos, 20 obs postflop usadas y **126 obs al Oracle**. |
| `frecuencias_preflop` | 10 | `preflop.actions` | Sí | Mismo conjunto; afecta `TransitionStats`, `ProfileRangeModel`, `Oracle`. |
| `frecuencias_postflop` | 9 | `flop/turn/river.actions` | Sí | Excluye `H_0832`; incluye `H_0926`. Las 9 aportan observaciones postflop y al Oracle. |
| `tablero_equity` (unión) | **9** | `streets.*.board` / `comunitarias` | Sí, vía observaciones postflop | IDs: `H_0093 H_0297 H_0372 H_0587 H_0590 H_0812 H_0909 H_0915 H_0921`. |
| `board_contradiction` | 5 | `streets.*.board` vs `comunitarias` | Indirecto | `H_0093 H_0297 H_0812 H_0915 H_0921`. `observations` usa `streets.*.board`, así que la contradicción de `comunitarias` no cambia el board live; sí indica inconsistencia de fuente. |
| `board_missing` | 4 | `streets.*.board` ausente | **Sí** | `H_0372 H_0587 H_0590 H_0909`. Causan 8 observaciones postflop descartadas; el resto de la mano sigue. |
| `showdown_ganador` | 1 | `showdown.winner1` | Solo W$SD / stats | `H_0798`: reparto incompleto; no afecta rangos ni Oracle. No excluir la mano de esos modelos. |
| `stack` (`active_null_stack`) | **17** | `players[].stack` | Etiquetas | `H_0016 H_0022 H_0061 H_0198 H_0415 H_0421 H_0430 H_0515 H_0526 H_0547 H_0557 H_0697 H_0824 H_0834 H_0853 H_0863 H_0906`. `mean_stack_by_player` los omite; la etiqueta puede quedar indeterminada o cambiar. |
| `allin` | 18 | `players[].allin` | No en los modelos actuales | Ningún modelo live usa `allin`. No es motivo para excluir de rangos/Oracle; sí para futuros cálculos de EV/SPR. |
| `asientos` (`active_no_position`) | **51** | `asientos` / `pos` | No pierde acciones; sí `players_active` | 484 entradas de acción no-`p` no se pierden; 18 nombres siguen sin posición. `Observations`/rangos usan posición de la acción, no `players_active`. No excluir la mano por este campo. |
| `bote` | **0** en 877 | `final_pot`/bote interno | No | Las 17 `active_null_stack` no son defectos de bote. No hay defecto de bote en la ventana. |
| `comunitarias` truncadas | **30** | `comunitarias` | No en live actual | `observations` usa `streets.*.board`; `comunitarias` no alimenta Oracle/postflop. No excluir por este campo. |
| `calibracion_877` | 6 | ventana provisional | No es un campo de mano | `H_0926 H_0832 H_0430 H_0589 H_0662 H_0847`; combina acción imposible, limp, comunitarias truncadas y bote limitado. |
| `registro_procedencia` | 0 | metadata | No | No hay manos excluibles por “falta de procedencia” dentro de 877; la procedencia es una propiedad de la base/ventana, no de una mano individual. |
| `derivados` | 0 | JSON legacy | No | No hay lectores de producción. |

### 6.2 Listas exactas que importan

**Acciones restringidas (10):**

```text
H_0005 H_0059 H_0214 H_0226 H_0327 H_0357 H_0832 H_0834 H_0925 H_0926
```

**Tablero/equity restringido (9):**

```text
H_0093 H_0297 H_0372 H_0587 H_0590 H_0812 H_0909 H_0915 H_0921
```

**Tablero ausente que descarta observaciones (4):**

```text
H_0372 H_0587 H_0590 H_0909
```

**Stack nulo (17):**

```text
H_0016 H_0022 H_0061 H_0198 H_0415 H_0421 H_0430 H_0515 H_0526
H_0547 H_0557 H_0697 H_0824 H_0834 H_0853 H_0863 H_0906
```

**Showdown defectuoso (1):** `H_0798`.

**Calibración/ventana (6):** `H_0926 H_0832 H_0430 H_0589 H_0662 H_0847`.

### 6.3 Consecuencia por modelo y restricción que falta

| Modelo | Campos que consume | Restricción que debería aplicar | ¿Se aplica hoy? | Fuga actual |
|---|---|---|---|---|
| `TransitionStats` / `Profiles` | acciones, cartas, stacks, showdown, active | Excluir/aislar acciones de las 10; no usar stack nulo para media; W$SD de `H_0798`; no inferir posición de `players_active` | **No** | Stats y etiquetas se calculan con las 10; 17 stacks omitidos sin flag; W$SD con reparto incompleto. |
| `ProfileRangeModel` | acciones preflop, posición, cartas conocidas, etiqueta | Excluir eventos de acciones inválidas; tratar `H_0832` como limp corto; no contar `SB x` de `H_0926` | **No** | 16 eventos conocidos de las 10; `H_0832` entra como `limp`; `H_0926` entra donde el parser lo permita. |
| `Oracle` | etiqueta, calle, `facing`, textura, acción; **no** cartas | Excluir acciones inválidas; no agrupar tablero inválido como `None`; separar `por_facing` de observaciones sin board válido | **No** | 126 obs de las 10; 8 obs de board ausente quedan en `por_facing` y pueden alimentar el fallback; 5 contradicciones no cambian el board live pero revelan fuente inconsistente. |
| `PostflopRangeModel` | cartas conocidas, board de `streets`, etiqueta, acción, `facing` | Excluir acciones inválidas; board válido obligatorio; no usar etiqueta de stack nulo sin flag | **No** | 20 obs usadas de las 10; 8 obs descartadas por board; 30 obs usadas de las 9 con tablero restringido; 339 manos reales, no 864. |
| Héroe preflop (`preflop_matrices`) | acciones preflop del héroe y previas | Unificar codificación `b/r/c/x`; no inferir limp solo de `c`; no ignorar `b` | **No** | 162 `b>1BB` en 877; `_preflop_raises` solo `r`; un open `b` no se ve; un limp corto `b` no se ve. |
| Etiqueta live | stack de sesión/actual | Reproducir `simple_label` o declarar que es otra regla; no default ciego a TIBURON | **No** | 22/78 PEZ históricos por VPIP/PFR no reproducibles; `Valentina22` cambia de etiqueta al excluir 23 manos. |
| `range_lab_gui` | JSON legacy + Oracle actual | Exigir misma base/ventana/etiquetas o separar modos | **No** | Mezcla posible; ver §10. |
| `recommend_loop` | modelos inyectables / `opening_range` | No inyectar modelos live en demo sin sello; no usar omega ausente | **No (latente)** | Puede combinar `prob_vec_player` con modelos sin procedencia. |

**Regla de granularidad.** Para `H_0926` no se excluye la mano completa: se invalida la observación/acción imposible. Para `H_0832` no se excluye la mano: se corrige/etiqueta el campo `b` corto. Para `H_0798` no se excluye de rangos: se restringe W$SD. Para las 4 manos sin board no se excluye el preflop: se descartan solo las observaciones postflop sin board. Para las 51 sin asiento no se excluye nada de rangos: se corrige `players_active` si se usa.

---

## 7. Auditoría modelo por modelo

### 7.1 `TransitionStats` y `Profiles`

**Constructor:** `motor/profile.py::Profiles.from_hands()` (`profile.py:245`) sobre `motor/stats.py::TransitionStats.from_hands()`. También calcula `mean_stack_by_player()` (`profile.py:72`) y `simple_label()` (`profile.py:96`).

**Entrada:** 877 manos completas; `players`, `streets.*.actions`, cartas, `stack`, `showdown`, `active`, `final_pot` (este último no para los modelos live).

**Salida:** 138 perfiles, 78 PEZ / 60 TIBURON; 147 nombres con actividad; 9 nombres sin perfil (`HERO`, `MuckeDB`, `P1`–`P5`, `p4`, `p5`). El nombre `Jarduan` (héroe) concentra 864 manos; los otros perfiles tienen muchos menos.

**Campos usados:**

- `TransitionStats`: acciones por calle, posición, cartas conocidas, `showdown` (WTSD/W$SD), `active` no se usa para decidir el conteo de acciones.
- `Profiles`: `mean_stack_by_player` usa `players[].name` y `players[].stack`; ignora `None`/no numérico y conserva 0 real.
- `simple_label`: primero stack medio `< STACK_FISH_BB (50)` → PEZ; si no, VPIP > 32 % y PFR < 10 % → PEZ; si no, TIBURON. Sin stack ni stats → TIBURON por defecto.

**Defectos y comportamiento:**

- 17 manos con stack nulo: se omiten del promedio sin warning. La etiqueta de un jugador puede quedar basada en muy pocas manos.
- 51 manos con `active` sin posición: no se pierden acciones no-`p`; el campo `players_active` queda inexacto, pero no es clave de `Oracle`/postflop.
- `H_0798`: W$SD con reparto incompleto; no afecta rangos.
- `Valentina22`: 3 manos en 900, 2 en 877; su stack medio cruza 50 BB y cambia de TIBURON a PEZ.
- **22 de 78 PEZ (28,2 %)** son PEZ por VPIP/PFR con stack ≥ 50 BB. La regla live no reproduce ese fallback. Ejemplos con `n` y frecuencias: `Sp1609` (n=1; VPIP 100 %, PFR 0 %), `Ocampo99` (n=2; 100/0), `Nnn1` (n=2; 50/0), `Franco1603` (n=52; 82,7/1,9), `Silvio` (n=30; 90/6,7), `Woons` (n=39; 71,8/2,6), `Elyessi27` (n=81; 44,4/6,2).
- El campo `confidence` de `PlayerProfile` no se propaga a los modelos ni a la recomendación. Una etiqueta con n=1 pesa igual que una con n=81 en la celda de perfil.
- `Profiles.to_dict()`/`profiles.json` guarda frecuencias, no conteos; `player_stats.json` sí guarda `[opp, act]`, pero no se usa en producción.

**Dependencia estática:** `Profiles.from_hands()` carga `preflop_matrices.json` para `PlayerProfile.omega`/base rates. No hay verificación de hash en el constructor; el archivo se lee de disco y se cachea en proceso.

### 7.2 `ProfileRangeModel` (preflop rival)

**Constructor:** `motor/player_ranges.py::ProfileRangeModel.from_hands(hands, labels)` (`player_ranges.py:128`).

**Entrada real:** 877 manos; 138 etiquetas; `learn.preflop_events(hand)` con primera decisión conocida; `preflop_matrices.json` como prior.

**Salida:** 864 manos contribuyentes; 1.168 eventos preflop conocidos; 6 celdas `opp` y 21 celdas `cnt`. 13 manos no aportan ningún evento preflop con cartas conocidas.

**Conteos exactos por perfil/denominador:**

| Perfil | Denominador | n | Categorías (conteo) |
|---|---|---:|---|
| PEZ | `no_raise` | 128 | limp 47, rol 11, bb_check 27, open 21, call_limp 22 |
| PEZ | `facing_open` | 55 | call_open 47, 3bet 4, squeeze 1, fold_vs_open 3 |
| PEZ | `facing_3bet` | 5 | call_3bet 5 |
| TIBURON | `no_raise` | 652 | open 161, fold 323, bb_check 54, call_limp 28, rol 75, limp 11 |
| TIBURON | `facing_open` | 312 | call_open 83, fold_vs_open 201, 3bet 22, squeeze 6 |
| TIBURON | `facing_3bet` | 16 | fold_vs_3bet 16 |

**Transformación matemática:**

- Para una acción `A` y un spot, `p_matrix` combina el prior (`_prior_grid(action, pos, villain_pos)`) con los conteos empíricos `cnt[(perfil, denom, A)]` y `opp[(perfil, denom)]`.
- `alpha=2`; para `PEZ/facing_3bet` con n=5, el prior pesa `2/(5+2)=28,6 %`. No hay intervalo ni flag de baja muestra.
- Los conteos empíricos están **pooled por perfil+denominador**, no por posición. La posición solo modula el prior; no hay celda empírica “PEZ en BB vs CO”.
- `_prior_grid` elige: (1) tabla exacta por posición simple (`OR_UTG`, etc.); (2) tabla exacta por par de posiciones (`3B_BB_vs_CO`, etc.); (3) `FLAT_PRIOR=0.15` con `RuntimeWarning`. No elige “la primera tabla de la acción”.
- `CAT_TABLE` mapea `limp` y `call_limp` a tablas `LIMP...` que **no existen** en `preflop_matrices.json`; no tiene entrada para `bb_check`. `rol` tampoco se consulta en el camino live. Por eso 217 de 1.168 eventos (18,6 %) pertenecen a categorías que el serving no vuelve a consultar como tales: `bb_check` 81, `rol` 86, `call_limp` 50.

**Fallos de serving asociados (no del constructor, pero del consumo):**

- `_preflop_spot()` clasifica por la **última acción**, no por la primera decisión del villano:
  - `b -> open`
  - `r -> 3bet`
  - `c -> call_open`
  - `x -> limp`
  - sin acción -> `open`
- Eso no coincide con `classify_first_action()`. En particular:
  - una apertura grabada como `r` (hay 567 acciones `r` preflop en 877, no todas aperturas) se consulta como `3bet`;
  - un check de BB `x` se consulta como `limp`;
  - un call en bote limpeado `c` se consulta como `call_open`;
  - un `b>1` se consulta como `open` aunque el entrenamiento lo pueda llamar `rol`/`3bet`/`squeeze` según contexto;
  - un `b<=1` (15 casos en 877) se consulta como `open`, pero el entrenamiento lo llama `limp`.
- `bb_check`, `rol` y `call_limp` no se consultan nunca con su propia celda. La tabla de entrenamiento y la consulta live no están alineadas.
- Si `pos='BB'` y la acción es `open`, no existe `OR_BB` ni par `OR_BB_vs_*`; `_prior_grid` cae a `FLAT_PRIOR=0.15` (con warning). No es un fallback a datos viejos, pero sí un prior plano silencioso en la práctica.
- No hay comparación entre `ProfileRangeModel.load()` y el modelo reconstruido. `load()` no restaura `profiles`, `n_hands_input` ni `n_hands_used`; `prob_vec_player()` puede quedar con omega 1.0. El `save()` posterior puede escribir metadata incompleta.

**Riesgo de contaminación:** el modelo actual no lee `profile_ranges.json`; el riesgo es de **datos actuales defectuosos** (10 manos de acción) y de **mapeo de serving**, no de derivado histórico.

### 7.3 `Observation` y `Oracle`

**Constructor:** `motor/observations.py::extract_hand(s)` y `motor/behavior.py::build(hands, labels, min_n=3)` (`behavior.py:191`); `Oracle` en `behavior.py:71`.

**Entrada:** 877 manos; 138 etiquetas; acciones de todas las calles; board de `streets.*.board`; `facing` precomputado; textura; cartas conocidas; `players_active`.

**Salida:** 8.657 observaciones. `Oracle` materializa 111 celdas `granular` (con textura) y 32 celdas `por_facing` (sin textura). `min_n=3` descarta 28 observaciones de la tabla granular. Las celdas `por_facing` conservan el total.

**Campos usados:**

- Etiqueta del jugador que actúa.
- Calle (`flop`, `turn`, `river`).
- `facing` (lo que enfrenta: bet/raise/check/etc.).
- Textura del board (`_texture_class`), derivada de `streets.*.board`.
- Acción (`x`, `b`, `c`, `f`, `r`) y `sizing`.
- No usa `final_pot`, `stack`, `allin`, `players_active` como clave; `players_active` queda como metadata y no entra en la celda.
- No exige cartas conocidas: el `Oracle` agrega acciones de jugadores sin cartas. Eso es intencional para P(A|C), pero significa que las restricciones de acciones no se pueden sustituir por “solo manos con cartas”.

**Comportamiento con datos faltantes / poca muestra:**

- Board ausente: `_texture_class` devuelve `None`; la observación no se descarta del `Oracle`. Las 8 observaciones de las 4 manos sin board quedan en celdas de textura inválida (`'-'`) y en `por_facing`; no son alcanzables por una consulta live con textura válida, pero **sí pueden influir en `por_facing` cuando una celda granular no llega a `min_n=3`**.
- Board contradictorio: `observations` usa `streets.*.board`, no `comunitarias`; por eso las 5 contradicciones no cambian la textura live. Siguen siendo una señal de fuente inconsistente.
- `min_n=3`: celdas con 1–2 observaciones no se materializan en granular; la consulta cae a `por_facing` o a una población/etiqueta inferior. No hay corrección por multiplicidad ni intervalo.
- En la grilla de consultas live enumerada (2 etiquetas × 3 calles × facings válidos × texturas válidas) hay 98 combinaciones: 59 resuelven a `granular`, 39 a `por_facing`, y **36 tienen `n<20`**. Ninguna combinación válida cae a “población” en la enumeración actual; eso no elimina el riesgo de celdas con 3–10 observaciones.
- `OracleResponse` (`decision.py:84`) usa `fade_n=20`: mezcla la distribución del perfil con la heurística `default_response` con peso `1 - n/20`. Con n=5, el 75 % es heurística; con n=3, el 85 %. El `n` se usa internamente, pero no se presenta como incertidumbre al usuario.
- `Oracle` no tiene hash de base/ventana/commit. Un `behavior.json` guardado no se puede recargar en un `Oracle` (no hay loader inverso); el JSON no es un artefacto de producción.

**Riesgo de contaminación:** el `Oracle` actual se construye con la base actual, pero incluye 126 observaciones de las 10 manos con acciones restringidas y 8 observaciones con board ausente en `por_facing`. No hay derivado histórico en producción.

### 7.4 `PostflopRangeModel`

**Constructor:** `motor/postflop_ranges.py::PostflopRangeModel.from_hands(hands, labels)` (`postflop_ranges.py:126`).

**Entrada:** 877 manos; etiquetas; `extract_hand`; cartas conocidas; board de `streets.*.board`; `facing`; acciones. El board solo se usa para el **bucket de fuerza** de la mano; la celda es `(perfil, calle, facing, bucket)` con 5 buckets.

`from_hands()` ya construye un `Oracle` interno con las etiquetas recibidas; `build_models()` lo reemplaza por el `Oracle` compartido. En producción no hay discrepancia de etiquetas, pero se duplica trabajo y un uso directo de `from_hands()` sin inyección puede quedar con un Oracle distinto del que usa el resto del asistente.

**Salida real:**

- `n_hands_input=877`.
- `n_hands_used=864` **no es postflop**: cuenta manos con cartas conocidas, aunque solo tengan preflop.
- Manos que realmente aportan al menos una observación postflop: **339**.
- 525 manos son preflop-only para este modelo.
- 1.388 observaciones postflop usadas; 1.396 observaciones conocidas menos 8 descartadas por board ausente.
- 116 celdas; 47 con `n<5`; 74 con `n<10`; 18 con `n>=20`.
- De 70 consultas live válidas por bucket, 67 tienen datos y 3 caen a prior-only (`PEZ` turn donk bet1/bet2; `PEZ` turn bet2). Esas 3 no son un fallback histórico: usan el prior del `Oracle`.

**Transformación:**

- `alpha=2`; el prior es `Oracle.p_action(perfil, street, facing)` **sin textura** (por tanto `por_facing` o inferior). No hay prior granular de textura dentro de `PostflopRangeModel`.
- `p_action` devuelve probabilidades por acción; no devuelve `n`, `source` ni intervalo al punto de decisión.
- Si `_oracle is None`: con `opp>0` usa `FLAT_PRIOR=0.2`; con `opp=0` devuelve 0.0. No hay warning. En producción `build_models()` inyecta `postflop_model._oracle = oracle`; en un `load()` esa inyección se pierde y el modelo queda parcialmente inicializado.
- `load()` no restaura `_oracle`, `n_hands_input` ni `n_hands_used`; `save()` posterior puede escribir metadata incompleta.
- `_scores_cache` cachea buckets por board; no hay invalidación entre bases, pero el objeto se reconstruye por proceso.

**Defectos que lo afectan:**

- 20 observaciones de las 10 manos con acciones restringidas siguen entrando.
- Ejemplo exacto: `H_0926` aporta 10 observaciones al `Oracle` (incluida la `SB x` imposible), 3 eventos preflop conocidos y 7 observaciones postflop conocidas. `PostflopRangeModel` descarta la acción sin cartas por falta de cartas, no por invalidación de la secuencia; por eso el modelo sigue usando 7 observaciones de esa mano.
- 8 observaciones se pierden por board ausente; las 4 manos siguen en preflop.
- 30 observaciones usadas provienen de las 9 manos con tablero restringido (16 de contradicción + 14 de manos con board válido pero `comunitarias`/tablero restringido); el board live de `observations` puede ser válido en parte de ellas.
- La etiqueta histórica puede venir de un stack nulo; el modelo no recibe un flag de etiqueta dudosa.

**Riesgo de contaminación:** no hay lectura de `postflop_ranges.json` en producción. El riesgo es de **metadato falso** (`864` vs `339`), **prior plano/`Oracle` actual** y **mezcla en `load()`/`range_lab`**, no de derivado histórico directo.

### 7.5 Preflop del héroe: `preflop_matrices.json`

**Constructor:** `motor/preflop.py::load_tables()` y `lookup_table()`; consumo en `asistente_live._recom_preflop()` (`asistente_live.py:1328`). **No** pasa por `build_models()` y **no** se reconstruye desde las 877.

**Entrada:** acciones preflop del héroe y de los rivales; posición; tabla estática `data/preflop_matrices.json`.

**Salida:** probabilidades de `fold/call/raise` por table; recomendación.

**Cobertura:**

- 117 tablas: `OR` 5, `ROL` 5, `3B` 15, `4B` 15, `5B` 15, `Call_OR` 8, `Call_3B` 15, `Call_4B` 15, `Call_5B` 15, `SQUEEZE` 6, `Over_Call` 3.
- La auditoría de cobertura reporta 107 exactas, 1 alias, 2 ausencias intencionales y 30 huecos posibles; no se listan aquí todas las combinaciones.
- `SQUEEZE` y `Over_Call` no son consultadas por `_recom_preflop`; son tablas presentes pero no usadas en el camino live.
- No hay bloque de procedencia: solo `tables`. No se puede saber si se derivaron de 877, de 1.253, de otra base o de curaduría manual. El hash `075bae...` pinnea el archivo, no su origen.

**Comportamiento con tablas faltantes:**

- `lookup_table` hace exacta y alias; `_pf_table_lookup` puede hacer un fallback explícito a “otra posición vs” (`fallback_other_vs`) para el héroe.
- Si falta `OR` para una posición, `_recom_preflop` devuelve `None`/sin recomendación.
- Si falta una componente de raise/call, `_pf_freq` devuelve `0.0` con warning de cobertura; el resultado puede ser “0 % raise / 100 % fold”, que es una **decisión**, no un dato observado.
- `f_r or 0.0` y similares confunden un 0 % real con una tabla ausente. La UI puede mostrar cobertura, pero el motor no distingue “no hay dato” de “el dato es 0”.
- No hay `n` por tabla; son probabilidades asumidas/curadas, no conteos con denominador.

**Defectos de parser en el camino héroe:**

- `_preflop_raises()` (`asistente_live.py:376`) cuenta solo `r`; ignora `b`.
- `_recom_preflop()` detecta limps solo como `c`; un limp corto `b<=1BB` o un open `b` no se ve.
- En 877 hay **162 acciones preflop `b` con importe >1 BB** y **15 con importe <=1 BB**. El entrenamiento las clasifica por contexto; el héroe no.
- Si la mesa actual graba las aperturas como `r` (lo esperable con el recorder que mapea “subir” a `r`), el héroe las maneja; si las graba como `b`, las ignora. No hay test de paridad ni normalización única.

### 7.6 Camino live y etiquetas

**`_perfil_for()`** (`asistente_live.py:671`):

1. media de stacks de la sesión para ese `player_id`;
2. si no hay historial, `state[f'{player_id}_stake']`;
3. si no hay nada, `TIBURON`;
4. PEZ si la media/stack `< 50`, si no TIBURON.

No usa VPIP/PFR, no usa `self.models.labels` y no busca el nombre histórico. Por eso no reproduce los 22 PEZ por fallback. Un jugador con stack actual alto y VPIP/PFR de PEZ histórico se consulta como TIBURON.

**`_rango_main()`** (`asistente_live.py:1118`):

- Calcula `perfil = _perfil_for(pid, state)`.
- Llama `_preflop_spot(self.rec.hand, main_pos)`.
- Consulta `self.models.range_model.prob_vec(perfil, spot, action, pos=main_pos, villain_pos=_pf_rival_pos(...))`.
- Aplica las acciones postflop observadas con `self.models.postflop_model.prob_vec(...)`.
- No usa `prob_vec_player()` ni omega individual. El rango es de **perfil**, no del jugador histórico.

**`_recomendacion_para()`** (`asistente_live.py:1536`):

- Selecciona rivales activos; usa `OracleResponse` con `fade_n=20`.
- No propaga `n`, `source` ni confianza de celda a la recomendación visible.
- `MULTIWAY_SOPORTADO=False`; no se audita multiway ni se cambia.

**Caches / fallbacks:**

- `_TABLES` de `preflop.py` y `_base_rates` de `profile.py` son caches de proceso; no verifican hash en cada build. Si el archivo cambia en caliente, el proceso puede quedar con una versión anterior.
- `Oracle._poblacion` cachea población por calle; no se invalida.
- `PostflopRangeModel._scores_cache` cachea buckets por board; no se invalida.
- `ProfileRangeModel.load()` y `PostflopRangeModel.load()` degradan metadata; `PostflopRangeModel.load()` pierde `_oracle`.
- `range_lab_gui` hace fallback de JSON a reconstrucción actual sin sello; ver §10.
- `build_models()` no tiene fallback a datos viejos; si falla la base, falla el build.

---

## 8. Riesgos de contaminación

### 8.1 Lo que **no** ocurre

- `build_models()` no lee `profiles.json`, `player_stats.json`, `preflop_stats.json`, `profile_ranges.json`, `postflop_ranges.json`, `observations.json` ni `behavior.json`.
- No hay `if FileNotFoundError: cargar JSON viejo`.
- No hay `load()` de rangos dentro de `build_models()`.
- No hay `PostflopRangeModel` cargado desde disco en producción; se construye desde manos y se le inyecta el `Oracle` actual.
- Los siete derivados legacy declaran 877/866 y `code_commit=0fcceed`, `arbol_sucio=true`; no declaran base ni líneas. Están desactualizados y **no se usan**.

Esto es importante: la contaminación principal **no** es “el modelo live está leyendo un JSON de 1.253/877”. Es más sutil y más difícil de ver.

### 8.2 Lo que sí ocurre

| Riesgo | Dónde | ¿Producción? | Severidad | Evidencia |
|---|---|---|---|---|
| Defectos de campo actuales entran sin restricción | `build_models` -> todos los modelos | **Sí** | **Alta** | 10 manos de acción -> 16 eventos rango, 20 obs postflop, 126 obs Oracle; 8 obs board ausente; `H_0926`/`H_0832` |
| Mapeo preflop training vs serving | `_preflop_spot`, `_preflop_raises` | **Sí** | **Alta** | `r` open -> `3bet`; `x` -> `limp`; `c` limped -> `call_open`; 162 `b>1`; 15 `b<=1`; `bb_check`/`rol`/`call_limp` no consultados |
| Etiqueta histórica vs etiqueta live | `simple_label` vs `_perfil_for` | **Sí** | **Alta** | 22/78 PEZ por VPIP/PFR no reproducibles; default TIBURON; `Valentina22` flip |
| `preflop_matrices` sin procedencia | héroe preflop | **Sí** | Media-alta | 117 tablas; sin metadata; 30 gaps; hash no ligado a base |
| `PostflopRangeModel.n_hands_used=864` | metadato live | **Sí** | **Alta** | 339 manos reales; 525 preflop-only; no `n` en decisión |
| `PostflopRangeModel.load()` pierde `_oracle` | `load()`/lab | No en build; sí en lab | Alta si se usa | `load()` no restaura Oracle; `p_action` puede devolver 0.0/0.2 |
| `range_lab_gui` mezcla legacy + Oracle actual | herramienta | Auxiliar | Alta si se cita como producción | JSON legacy + Oracle 877 actual + etiquetas legacy; sin guardia |
| `recommend_loop` inyección latente | demo | No camino live | Media | Puede recibir modelos sin sello y usar `prob_vec_player`/omega |
| `diagnosticar_56_154` histórico | herramienta | No | Media de interpretación | Snapshot `_snapshot_pre_rebuild_1b14c18`, no base actual |
| Selección 877 / cola 444 / 23 CM-004 | datos | **Sí** | Alta para representatividad | 877 = 63,2 % acciones; 444 = 34,9 %; 23 = 1,8 %; no holdout |
| 106 manos cambiadas vs `51a6fb9` | datos | **Sí** | Media | 76 campos de acción; `H_0926` inserta check inválido; sin stack/board/pot changes |
| Sin sello de modelo | `build_models`/recomendación | **Sí** | Alta para reproducibilidad | No hay base/window/commit/labels digest en el objeto live |
| Erratum `player_stats`/`profiles` | documentación | No | Baja | Contadores vs frecuencias |

### 8.3 Contaminación por derivados históricos: riesgo indirecto, no directo

El riesgo real de los legacy es **humano/auxiliar**:

- `range_lab_gui` puede cargar `profile_ranges.json`/`postflop_ranges.json` (877/866, 139 perfiles, 8.742 obs) y luego reconstruir el `Oracle` con las 877 actuales y las etiquetas del JSON legacy. Eso produce una combinación que no existió en ningún build: rangos viejos + Oracle nuevo + etiquetas viejas.
- `PostflopRangeModel.load()` no restaura `_oracle`; si la herramienta no lo reconstruye, el modelo queda con prior plano o 0 y puede parecer “débil” por una inicialización incompleta, no por los datos.
- `ProfileRangeModel.load()` no restaura `profiles`/`n_hands_input`/`n_hands_used`; `prob_vec_player()` puede quedar con omega 1.0.
- `behavior.json` no tiene loader; no se puede reconstruir un `Oracle` equivalente desde él. Citarlo como “el Oracle actual” sería incorrecto.
- `diagnosticar_56_154.py` compara el snapshot histórico `data/_snapshot_pre_rebuild_1b14c18` con JSON legacy; no mide la base actual ni los modelos actuales. Su salida puede confundirse con evidencia de producción si no se rotula.

**Propuesta de aislamiento (no implementada).** Ver §10.3. La idea es que la herramienta auxiliar no pueda producir una mezcla silenciosa: o todo histórico con su Oracle histórico, o todo actual con su Oracle actual.

---

## 9. Evaluación de incertidumbre

### 9.1 Incertidumbre por modelo

| Modelo | n efectivo | Punto más débil | Qué se propaga a la decisión |
|---|---:|---|---|
| `Profiles` | 138 perfiles; 147 nombres; 9 sin perfil | 22/78 PEZ por VPIP/PFR; `n=1` (`Sp1609`); `Valentina22` 2–3 manos | Etiqueta sin `n` ni confianza; default TIBURON |
| `ProfileRangeModel` | 864 manos; 1.168 eventos | `PEZ/facing_3bet=5`; `TIBURON/facing_3bet=16`; `PEZ/facing_open=55` | Probabilidad con `alpha=2`; sin `n`/source; prior plano 0.15 posible |
| `Oracle` | 8.657 obs; 111 granular + 32 por_facing | 36/98 consultas live con `n<20`; 28 obs granular descartadas por `min_n=3` | `OracleResponse` con `fade_n=20`; no muestra `n` como incertidumbre |
| `PostflopRangeModel` | 339 manos reales; 1.388 obs; 116 celdas | 47 celdas `n<5`; 74 `n<10`; 3 consultas prior-only; metadata dice 864 | Probabilidad con `alpha=2`; no `n`/source; `load()` sin Oracle |
| `preflop_matrices` | 117 tablas; 30 gaps | 2 ausencias intencionales; componentes faltantes -> 0 | Tabla asumida; sin `n`; `SQUEEZE`/`Over_Call` no consultadas |
| Etiqueta live | 1 stack de sesión | Sin historial -> TIBURON; 22 PEZ no reproducibles | Etiqueta usada para seleccionar celdas de perfil |
| Selección 877 | 877/1.344 manos | 444 cola (34,9 % acciones); 45 jugadores nuevos; 23 CM-004 | Representatividad no estimada; no holdout |

### 9.2 Incertidumbre de la selección

- **23 CM-004:** 303 acciones, 22 showdowns, 38 jugadores; 900→877 quita 251 obs, 31 eventos de rango y 19 obs postflop; cambia `Valentina22` de TIBURON a PEZ; no cambia las celdas más débiles. La exclusión es una decisión de procedencia, no una restricción de campo.
- **444 cola:** 5.758 acciones; 45 jugadores nuevos; 1.321 contrafactual añade 45 perfiles, 4.876 obs, 209 manos postflop y solo 5 celdas postflop; `PEZ/facing_3bet` sigue en 5. Es información perdida, pero no uniformemente útil.
- **106 cambiadas vs `51a6fb9`:** 76 campos de acción; 44 showdown; 5 active; 1 identidad; 1 ganador; sin stack/board/pot. No es una muestra aleatoria de correcciones; algunas insertan defectos.
- **No hay holdout temporal ni por jugador.** El corte es por orden físico; la cola contiene jugadores nuevos y una distribución distinta. Cualquier métrica in-sample de las 877 no estima el rendimiento out-of-sample.

### 9.3 Falsa precisión: ejemplos concretos

1. **`n_hands_used=864` vs 339 reales.** Un consumidor que lea el metadato cree que hay 864 manos postflop; hay 339. La diferencia de 525 es el 61 % del valor declarado.
2. **`PEZ/facing_3bet=5`.** El prior pesa 28,6 %; no hay flag. La probabilidad final puede parecer una estimación estable.
3. **`Oracle` con `n=3` y `fade_n=20`.** El 85 % de la respuesta es heurística; la UI no lo dice.
4. **`PostflopRangeModel` con `n=1`.** `alpha=2` suaviza hacia el prior; no hay `n` de celda en la decisión.
5. **Etiqueta con `n=1`.** `Sp1609` es PEZ con 1 mano (VPIP 100 %, PFR 0 %); `Ocampo99`/`Nnn1` con 2. La etiqueta se propaga a todos los modelos.
6. **`preflop_matrices` sin `n`.** Una tabla ausente se convierte en 0 % raise / 100 % fold con warning; el usuario puede leerlo como recomendación fuerte.
7. **`_preflop_spot` sin contexto.** Una apertura `r` se convierte en `3bet`; el rango se vuelve más estrecho sin que el `n` lo delate.

---

## 10. Diferencias entre herramientas auxiliares y producción

| Ruta | Qué lee | Uso previsto | ¿Producción? | Diferencia / riesgo |
|---|---|---|---|---|
| `asistente_live.build_models()` | base actual, 877 | Modelos live | **Sí** | Rebuild actual; sin sello de base/ventana/commit |
| `asistente_live._recom_preflop()` | `preflop_matrices.json` | Héroe preflop | **Sí** | Estático; sin procedencia; parser `b/r` incompleto |
| `range_lab_gui.load_models()` | `profile_ranges.json`, `postflop_ranges.json`; si fallan, base 877; Oracle actual | Laboratorio | **No** | Puede mezclar legacy + actual; `oracle_rebuild` no cambia etiquetas; sin guardia |
| `recommend_loop.recommend()` | modelos inyectables/`opening_range` | Demo | **No** | Puede usar `prob_vec_player`/omega y modelos sin sello; latente |
| `diagnosticar_56_154.py` | snapshot `_snapshot_pre_rebuild_1b14c18` + JSON legacy | Diagnóstico histórico | **No** | No es base actual; no debe citarse como producción |
| `verificar_adopcion_1344.py` | hashes/manifiesto | Integridad | **No** | Prueba artefactos, no modelos ni estrategia |
| `ProfileRangeModel.load()` | `profile_ranges.json` | Persistencia/lab | **No** | Pierde `profiles`, `n_hands_input`, `n_hands_used`; omega puede quedar 1.0 |
| `PostflopRangeModel.load()` | `postflop_ranges.json` | Persistencia/lab | **No** | Pierde `_oracle`, `n_hands_input`, `n_hands_used`; prior plano/0 |
| `behavior.json` | JSON legacy | Inspección | **No** | Sin loader inverso a `Oracle`; no es evidencia live |
| `preflop_matrices.json` | tablas estáticas | Héroe preflop | **Sí**, indirecto | 117 tablas; sin metadata; 30 gaps; hash sin base |

### 10.1 `range_lab_gui`: por qué es peligroso

El flujo problemático es:

```text
ProfileRangeModel.load()      -> rangos 877/866, 139 perfiles, code_commit=0fcceed
PostflopRangeModel.load()     -> celdas 877/866, 139 perfiles, sin _oracle
        +
hands = load_hands(reliable_only=True)  -> 877 actuales
Oracle = build(hands, post.labels)      -> 8.657 obs actuales
        +
postflop_model._oracle = oracle
```

No hay una comprobación de que el `post.labels` legacy corresponda a las 877 actuales. Un perfil del JSON puede no tener observaciones actuales; uno actual puede no existir en el JSON. La herramienta puede mostrar una probabilidad que mezcla:

- priors/empíricos de 866 manos viejas;
- etiquetas de 139 perfiles viejas;
- un `Oracle` de 8.657 observaciones actuales;
- un `PostflopRangeModel` sin `n` real.

El resultado no es ni el modelo live actual ni el modelo histórico coherente. Es un **tercer objeto** sin procedencia.

### 10.2 `diagnosticar_56_154.py`

El script compara el snapshot histórico `data/_snapshot_pre_rebuild_1b14c18` con JSON legacy para diagnosticar una diferencia de 56/154 (según el caso). No lee la base actual ni reconstruye los modelos live. Su salida es evidencia de un corte histórico; si se cita como “estado actual” se comete un error de procedencia. Debe llevar un banner de “diagnóstico histórico, no producción” y la base/commit del snapshot.

### 10.3 Propuesta de aislamiento de `range_lab_gui` (no implementada)

**Objetivo:** impedir mezclas silenciosas sin cambiar el comportamiento de producción.

1. **Envelope de procedencia obligatorio** en `profile_ranges.json` y `postflop_ranges.json`:
   - `base_sha256`, `selected_lines_sha256`, `window_count`, `excluded_ids_sha256`, `code_commit`, `dirty`, `labels_sha256`, `oracle_sha256` (si aplica), `created_at`, `schema_version`.
2. **Modo explícito** en la herramienta: `historical` o `current`. En `historical`, cargar todo del mismo envelope, incluido un `Oracle` persistido o reconstruido del mismo snapshot. En `current`, reconstruir todo desde `load_hands(reliable_only=True)` y no cargar JSON legacy.
3. **Rechazo de mezcla:** si `pre` y `post` tienen distinto `base_sha256`/`window_count`/`labels_sha256`, abortar con mensaje; no hay fallback automático a “lo que haya”.
4. **Oracle coherente:** si el `PostflopRangeModel` cargado no tiene `_oracle` y no hay un `oracle_sha256` que corresponda, deshabilitar el modo postflop o reconstruir el Oracle **solo** desde la misma base/etiquetas; nunca inyectar el Oracle actual en un modelo legacy.
5. **Sello visible:** banner en UI y en cualquier export: `AUXILIAR / HISTÓRICO / NO PRODUCCIÓN`, con hashes y conteos. Si el usuario pide “actual”, mostrar 877/138/8.657/339 y no 139/8.742/864.
6. **`PostflopRangeModel.load()`:** persistir `_oracle` o su procedencia; no permitir `p_action` con `_oracle=None` en modo postflop sin un warning visible. `ProfileRangeModel.load()`: restaurar o declarar `n_hands_input`/`n_hands_used`/`profiles`.
7. **`recommend_loop`:** no aceptar modelos inyectados sin envelope; si se usa `prob_vec_player`, exigir omega con `n` y base. No es producción, pero debe ser imposible confundirlo.
8. **`diagnosticar_56_154.py`:** banner fijo “histórico”, snapshot/commit en la salida; no usar la palabra “actual” para el snapshot.

---

## 11. Contratos y correcciones priorizadas

Ninguna de estas correcciones se implementa en esta auditoría. Se ordenan por riesgo para la recomendación live.

### P0 — Antes de usar los modelos para decisiones estratégicas

| ID | Contrato | Evidencia | Criterio de aceptación |
|---|---|---|---|
| P0-1 | **Normalización preflop única** entre `learn.classify_first_action()` y el serving | `_preflop_spot` mapea `r->3bet`, `x->limp`, `c->call_open`; `_preflop_raises` ignora `b`; 162 `b>1`, 15 `b<=1` en 877 | Un solo clasificador con `raises_before`, `limps_before`, `callers`, importe y `bb`; tests de paridad para `b/r/c/x/f`, limp corto, open, 3bet, 4bet; ninguna categoría consultada sin haber sido entrenada |
| P0-2 | **Restricción por campo defectuoso, no por mano** | 10 acciones, 9 tablero, 1 showdown, 17 stack, 51 asiento; `H_0926`/`H_0832` en modelos | Tabla de campos restringidos aplicada en cada constructor; conteos antes/después; `H_0926` no entra al Oracle por la acción imposible; `H_0832` se trata como limp corto; `H_0798` solo restringe W$SD; las 4 sin board solo pierden postflop; no se excluye por procedencia |
| P0-3 | **`PostflopRangeModel` debe reportar su muestra real y su incertidumbre** | `n_hands_used=864`, real 339; 47 celdas `n<5`; 3 consultas prior-only | `n_hands_used` = manos con al menos una obs postflop; `p_action`/`prob_vec` devuelven o registran `n` y `source`; la UI/registro muestra `n`; `load()` restaura o invalida `n`; tests con celdas vacías/prior-only |
| P0-4 | **Envelope de procedencia y prohibición de mezcla** | `build_models` sin base/window/commit; `range_lab` legacy + actual; `load()` pierde metadata | Todo modelo guardado declara base, líneas seleccionadas, ventana, IDs excluidos, commit, labels/oracle digest; `range_lab` rechaza mezcla; `PostflopRangeModel.load()` sin Oracle no simula producción |
| P0-5 | **Paridad de etiqueta histórica vs live** | 22/78 PEZ por VPIP/PFR no reproducibles; default TIBURON; `Valentina22` flip | `_perfil_for` usa la misma regla o declara explícitamente una regla distinta; fallback VPIP/PFR implementado o etiqueta desconocida; `n`/confianza propagados; tests con los 22 casos y con stack nulo |

### P1 — Antes de considerar los modelos “calibrados” o “listos”

| ID | Contrato | Evidencia | Criterio de aceptación |
|---|---|---|---|
| P1-1 | **Procedencia de `preflop_matrices.json`** | 117 tablas; solo `tables`; 30 gaps; hash sin base | Bloque de procedencia (fuente, base/ventana, fecha, autor, método); validación de hash; documentar 107/1/2/30; marcar `SQUEEZE`/`Over_Call` no usadas; no presentar tablas como conteos |
| P1-2 | **Tablero inválido y `Oracle`** | 8 obs sin board en `por_facing`; 5 contradicciones; `min_n=3` | Observaciones con board inválido en celda separada/no consultable; `por_facing` no las mezcla si se usa textura; `n` y source por consulta; tests de board ausente/contradictorio |
| P1-3 | **Alineación de categorías y priors en `ProfileRangeModel`** | `bb_check`/`rol`/`call_limp` no consultadas; `LIMP` inexistente; 30 gaps; flat 0.15 | `CAT_TABLE` cubre todas las categorías consultadas; no hay acción sin tabla o se declara prior plano; `bb_check`/`rol`/`call_limp` tienen consulta propia; tests de cobertura |
| P1-4 | **Sello de build live** | `build_models` no registra base/ventana/commit/conteos | `build_models` devuelve/loguea un `build_id` con hashes, 877, 23, 138, 864, 8.657, 339; la recomendación incluye `build_id`; imposible comparar sesiones sin él |
| P1-5 | **Decisión sobre 23 CM-004 y cola 444** | 23 sin originales; 444 fuera; 45 jugadores nuevos; `PEZ/facing_3bet` no crece | Documento de decisión explícito: mantener/restaurar 23 con criterio de campo; holdout temporal/por jugador para la cola; no adoptar por volumen; no reanclear tests hasta decidir |
| P1-6 | **Etiquetas de baja muestra** | `Sp1609` n=1; `Ocampo99`/`Nnn1` n=2; 22 fallback | Etiqueta “desconocida” o intervalo cuando `n` < umbral; no asignar PEZ/TIBURON con una mano; tests de estabilidad al quitar manos |

### P2 — Higiene y documentación

| ID | Contrato | Evidencia | Criterio de aceptación |
|---|---|---|---|
| P2-1 | **Derivados legacy** | 7 JSON 877/866; 139 perfiles; 8.742 obs; sin base; no producción | Marcar `LEGACY/NO USAR`; no regenerar sin autorización; si se regeneran, incluir base/líneas/commit; no confundir con live |
| P2-2 | **`range_lab_gui` y `diagnosticar`** | Mezcla; snapshot histórico | Aplicar §10.3; banner y guardias; no citar como producción |
| P2-3 | **`behavior.json` sin loader** | No round-trip a Oracle | O documentar que es solo inspección o añadir loader con formato explícito; no usarlo como fuente live |
| P2-4 | **Erratum `player_stats`/`profiles`** | Contadores vs frecuencias | Corregir documentación previa; usar `player_stats` para `n`; no usar `profiles.json` para confianza |
| P2-5 | **`recommend_loop` latente** | `prob_vec_player`/omega; modelos inyectables | Guardia de procedencia; no camino live; tests de que no se mezcla con `asistente_live` |
| P2-6 | **Suite completa** | 36 tests dirigidos verdes; tests históricos 1.253 rojos, no reanclados | No afirmar “suite verde”; decidir reanclaje en una fase separada, con autorización |

---

## 12. Evidencia reproducible

### 12.1 Integridad de artefactos

```text
$ python tools/verificar_adopcion_1344.py
...
OK base.sha256                  3f0e7e5e...
OK base.bytes                   2070355 bytes
OK base.lines                   1344 lineas fisicas, 1344 no vacias
OK manifest.learn               commit 8594ed5, sha256 3f0e...
OK manifest.commit_blob         blob 093281fb39ac = disco; ultimo commit 8594ed55c49b
OK derivatives.hashes           7/7 hashes coinciden con el snapshot
OK calibration.snapshot_sha256  7f2453f4...
OK calibration.window           base 3f0e..., ventana 877, excluidas 23, hash ea99...
OK calibration.provisional      status provisional; derivados stale/not adopted
OK derivatives.legacy_metadata  legado 51a6fb9/1253, ventana 877; observaciones 8742; hands_used 866
OK preflop_matrices.sha256      075bae3a...
OK rules.multiway               MULTIWAY_SOPORTADO=False
RESULTADO: OK (12/12)
```

Este resultado prueba **integridad de archivos**, no que los 877 sean una muestra limpia ni que los modelos estén calibrados.

### 12.2 Conteos de la ventana y de los modelos

```python
from motor.learn import load_hands
from motor.profile import Profiles
from motor.player_ranges import ProfileRangeModel
from motor.postflop_ranges import PostflopRangeModel
from motor.behavior import build

hands = load_hands(reliable_only=True)
assert len(load_hands(reliable_only=False)) == 1344
assert len(hands) == 877
labels = {n: p.label for n, p in Profiles.from_hands(hands).profiles.items()}
rm = ProfileRangeModel.from_hands(hands, labels=labels)
pm = PostflopRangeModel.from_hands(hands, labels=labels)
be = build(hands, labels=labels)

print(len(labels))                    # 138
print(rm.n_hands_input, rm.n_hands_used)  # 877 864
print(sum(v.sum() for v in rm.opp.values()))  # 1168
print(be['observaciones'])            # 8657
print(len(be['granular']), len(be['por_facing']))  # 111 32
print(pm.n_hands_used)                # 864 (metadata; real 339)
print(sum(pm.opp.values()), len(pm.opp))  # 1388 116
```

Conteos por perfil/denominador:

```text
PEZ     no_raise 128 / facing_open 55 / facing_3bet 5
TIBURON no_raise 652 / facing_open 312 / facing_3bet 16
```

Conteo real de manos postflop contribuyentes:

```text
1.396 observaciones postflop conocidas
-   8 por board ausente
= 1.388 usadas
339 manos contribuyentes
525 manos preflop-only
```

### 12.3 Diff contra `51a6fb9`

Evidencia serializada: `C:\Users\Jorgito\AppData\Local\Temp\opencode\diff_877_51a6fb9.json`.

```json
{
  "window_count": 877,
  "changed": ["...106 IDs..."],
  "fields": {
    "top_showdown": 44,
    "actions_preflop": 15,
    "player_active": 5,
    "top_winner": 1,
    "players_set": 1,
    "players_count": 1,
    "actions_river": 17,
    "actions_turn": 19,
    "actions_flop": 25
  }
}
```

La lista completa de 106 IDs está en §4.4. No hay campos de stack/posición/tablero/`final_pot` en el diff; eso no implica que la base actual no tenga defectos en esos campos, solo que no cambiaron entre ambas bases para esas 106 manos.

### 12.4 Contrafactual de la cola

```text
877        -> 138 perfiles, 864 rango, 1168 eventos, 1388 postflop, 8657 obs
1321 (877+444, sin CM-004)
           -> 183 perfiles, 1301 rango, 1796 eventos, 2334 postflop, 13533 obs
delta      -> +45 perfiles, +437 rango, +628 eventos, +946 postflop, +4876 obs
postflop   -> +209 manos contribuyentes; +5 celdas
PEZ/facing_3bet: 5 -> 5
```

Este contrafactual **no** es una propuesta de adopción ni una validación de calidad. Incluye las 444 manos tal como están, con sus defectos, y no aplica restricciones por campo.

### 12.5 Tests

```text
$ python -m pytest motor\test_player_ranges.py motor\test_postflop_ranges.py -q
36 passed, 2 warnings in 7.31s
```

Warnings observados:

```text
_prior_grid: sin tabla para action='open' pos='' villain_pos='';
usando FLAT_PRIOR=0.15
```

Ese warning es evidencia de que el prior plano es parte del comportamiento real, no una hipótesis.

No se ejecutó la suite completa. Los tests históricos anclados a 1.253 manos siguen rojos y no fueron reanclados; no se afirma “suite verde”.

### 12.6 Estado de archivos

- No se modificó `data/`, ningún derivado, hash, manifiesto ni pin.
- No se cambió `build_models()`, la selección 877, rangos, estrategia ni `MULTIWAY_SOPORTADO`.
- No se ejecutaron sesiones reales, B2 ni calibración.
- El único archivo nuevo es este informe: `DOCS/AUDITORIA_PIPELINE_MODELOS_LIVE.md`.

---

## 13. Conclusiones

1. **El pipeline live es mecánicamente reconstruible y no lee los derivados históricos.** Esa parte está bien y debe preservarse.
2. **La ventana 877 no es un dataset limpio por el hecho de ser la ventana canónica.** Contiene 10 manos con acciones restringidas, 9 con tablero restringido, 1 con showdown incompleto, 17 con stack nulo y 51 con asiento incompleto. La restricción correcta es por campo, no por mano ni por procedencia.
3. **El riesgo más grave no es un JSON viejo: es el desalineamiento training/serving de preflop.** `_preflop_spot` y `_preflop_raises` no comparten el clasificador de `learn.classify_first_action`; una apertura `r` puede consultarse como 3bet, un check de BB como limp y un call limpeado como call_open. Esto invalida la interpretación directa del rango rival y del spot del héroe.
4. **La etiqueta live no reproduce la etiqueta histórica.** 22/78 PEZ dependen de VPIP/PFR y no se pueden reconstruir con `_perfil_for`; además, la etiqueta es de perfil, no de jugador, y omega no se usa en producción.
5. **`PostflopRangeModel` declara una muestra que no tiene.** 864 metadato vs 339 reales; 47 celdas con `n<5`; no expone `n`. El modelo no es “calibrado” por tener 1.388 observaciones agregadas.
6. **La selección 877 es una decisión de compromiso, no una validación.** 444 manos de cola y 23 CM-004 quedan fuera; la cola añade 45 perfiles y 4.876 observaciones, pero no mueve `PEZ/facing_3bet` y solo añade 5 celdas postflop. Las 23 CM-004 siguen fuera por falta de originales, no por el defecto de orden original, y la decisión sigue abierta.
7. **`range_lab_gui` y `diagnosticar_56_154.py` no son producción.** El primero puede mezclar rangos históricos con Oracle actual; el segundo es un diagnóstico de snapshot histórico. Deben aislarse y rotularse antes de que alguien los cite como evidencia actual.
8. **No hay evidencia de mejora estratégica.** Esta auditoría no es calibración, no mide EV, no ejecuta sesiones y no autoriza B2. Cualquier afirmación de “mejor recomendación” requiere una fase separada, con holdout y restricciones por campo.

**Estado final:** auditoría entregada; no se implementó ninguna corrección. Cualquier cambio en datos, derivados, hashes, pines, `build_models()`, rangos, estrategia, `MULTIWAY_SOPORTADO`, calibración, B2 o sesiones reales requiere autorización separada.

---

## Apéndice A. Reproducción mínima de la ventana

```python
import json
from motor.learn import load_hands

all_hands = load_hands(reliable_only=False)
win = load_hands(reliable_only=True)

assert len(all_hands) == 1344
assert len(win) == 877
assert win[0]['hand_id'] == 'H_0001'
assert win[-1]['hand_id'] == 'H_0926'

cal = json.load(open('data/calibration_window.json', encoding='utf-8'))
assert cal['window']['selected_count'] == 877
assert cal['window']['excluded_count'] == 23
assert cal['window']['valid_hands'] == 900
assert cal['window']['invalid_lines'] == []
```

## Apéndice B. Resumen de cifras clave

```text
Base:                    1344 manos; 2070355 bytes; sha256 3f0e...
Ventana live:             877 manos; H_0001..H_0926; línea 900
Excluidas CM-004:          23; 303 acciones; 22 showdowns; 38 jugadores
Cola fuera:               444; 5758 acciones; 143 showdowns; 45 jugadores nuevos
Perfiles:                 138 (78 PEZ / 60 TIBURON); 147 nombres; 9 sin perfil
Rango:                    864/877; 1168 eventos
                          PEZ no_raise/facing_open/facing_3bet = 128/55/5
                          TIBURON no_raise/facing_open/facing_3bet = 652/312/16
Oracle:                   8657 obs; 111 granular; 32 por_facing; min_n=3
Postflop:                 339 manos reales; 1388 obs; 116 celdas; metadata 864
Postflop celdas:          47 n<5; 74 n<10; 18 n>=20; 3 prior-only de 70
Diff 51a6fb9:             106 manos; 76 campos de acción; 44 showdown; 5 active
Contrafactual 1321:       +45 perfiles; +4876 obs; +209 manos postflop; +5 celdas
PEZ/facing_3bet:          5 -> 5 (la cola no añade eventos)
Preflop b>1:              162 en 877; b<=1: 15; r: 567; c: 1151
Preflop tablas:           117; 107 exactas; 1 alias; 2 intencionales; 30 gaps
Tests dirigidos:          36 passed, 2 warnings; suite completa no ejecutada
```

## Apéndice C. Archivos y líneas de referencia

| Archivo | Punto clave |
|---|---|
| `motor/learn.py` | `RELIABLE_HANDS=900` (línea 53); `load_hands` (236); `EXCLUSIONES_VENTANA_FABLE` (206); `preflop_events` (469); `classify_first_action` (~317) |
| `motor/profile.py` | `mean_stack_by_player` (72); `simple_label` (96); `Profiles.from_hands` (245) |
| `motor/player_ranges.py` | `from_hands` (128); `_prior_grid` (169); `prob_vec` (253); `prob_vec_player` (347); `load` (376) |
| `motor/postflop_ranges.py` | `from_hands` (126); `p_action` (203); `prob_vec` (~220); `load` (~276) |
| `motor/behavior.py` | `Oracle` (71); `build` (191); `behavior_table` |
| `motor/observations.py` | `extract_hand` (110); `extract_hands` (228) |
| `motor/preflop.py` | `lookup_table` (108) |
| `motor/decision.py` | `OracleResponse` (84); `fade_n=20` |
| `motor/asistente_live.py` | `_preflop_spot` (138); `_preflop_raises` (376); `build_models` (476); `_perfil_for` (671); `_rango_main` (1118); `_recom_preflop` (1328); `_recomendacion_para` (1536) |
| `motor/recommend_loop.py` | `recommend` (256); no camino live |
| `tools/range_lab_gui.py` | `load_models`; mezcla legacy/actual |
| `tools/diagnosticar_56_154.py` | snapshot histórico; no producción |
| `data/calibration_window.json` | 877; 23 IDs; hash de selección; `provisional` |
| `data/preflop_matrices.json` | 117 tablas; sin procedencia; hash `075bae...` |

---

**Fin del informe.**
