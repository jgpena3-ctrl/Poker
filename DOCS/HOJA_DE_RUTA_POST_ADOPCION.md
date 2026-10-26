# Hoja de ruta post-adopción

**Fecha:** 2026-10-25
**Base canónica:** `data/hands_db.jsonl` — **adoptada y reparada**
**SHA-256:** `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`
**Líneas:** 1253
**Commit de la base:** `51a6fb9`

Este documento sustituye, para el trabajo inmediato, al estado pre-adopción de
`DOCS/PLAN_ACCION.md`, `DOCS/PROYECTO.md` y `DOCS/ESTADO_DEL_TRABAJO.md`.
La base ya está adoptada; lo que sigue es re-anclar las cifras y corregir los
defectos de motor que la adopción dejó visibles.

## 1. Lo que la adopción dejó hecho

- `trabajo/hands_db_edicion.jsonl` pasó a ser la fuente canónica por copia
  verificada, con el original en `data/hands_db.jsonl.bak`
  (SHA `5ae2abd7…`, 1258 líneas).
- Se retiraron `H_0028`, `H_0072`, `H_0146`, `H_1123` y `H_1188`.
- El motor reconoce 1253 ciegas y las doce categorías del contrato de
  adopción (`trabajo/control_categorias_adopcion.json`).
- Los siete derivados se regeneraron en el mismo commit.
- La base normalizada añade las postas `p`, corrige posiciones efectivas
  (por ejemplo `UTG` → `MP` cuando el asiento del botón está vacío) y arregla
  la mano `H_0846`.

## 2. El contrato de asientos: reparado

`winner`, `allin` y `btn_player` son **ids de asiento** (`hero`, `p1`..`p5`)
que se resuelven como índice en `players[]`. El contrato exige seis asientos,
siempre en el orden de `motor.multiway.PLAYER_IDS`; lo comprueba
`motor.multiway.contrato_orden_ok`.

La normalización compactó `players[]` en 60 manos. `tools/reparar_asientos.py`
reconstruyó esos 60 arrays desde la referencia de 1258, colocando cada jugador
en su asiento antiguo y rellenando los huecos. No escribió la base canónica:
generó una candidata y un informe, y la adopción se hizo por copia verificada.

| | antes | después |
|---|---|---|
| manos con menos de 6 asientos | 60 (53 de 5, 7 de 4) | **0** |
| ids `btn_player` fuera de rango | 11 | **0** |
| ids `winner` fuera de rango | 10 | **0** |
| `contrato_orden_ok` con problemas | 60 | **0** |
| `posiciones_allin` sin resolver | 60 | **0** |

Artefactos: `trabajo/hands_db_reparada.jsonl`, `trabajo/reparacion_asientos.json`.
Los 67 asientos restaurados tienen `pos` vacío: no crean posiciones
duplicadas ni cambian las categorías. La ventana fiable sigue en 877.

## 3. Contrato que queda escrito

1. `players[]` tiene **siempre** seis posiciones, en el orden
   `('hero','p1','p2','p3','p4','p5')`.
2. `winner`, `allin` y `btn_player` son ids de asiento y se resuelven con
   `motor.multiway.posicion_de_id`, no con `int(id[1:])`.
3. `btn_player` es el asiento **físico** del botón. Cuando ese asiento está
   inactivo, el botón efectivo es el siguiente asiento ocupado; por eso
   `players[btn_idx].pos` puede no ser `BTN`. No es un defecto.
4. `players[].pos` es la posición **efectiva** (salta asientos inactivos).
5. Si `contrato_orden_ok` es falso, las herramientas deben **fallar o
   declarar el hueco**, nunca suponer un índice.

## 4. Pruebas: estado tras la reparación

- `motor/test_multiway.py::test_orden_players_se_verifica_en_la_ventana_fiable`
  pasa; `contrato_orden_ok` da 0 problemas.
- Los 23 pins de `motor/test_auditar_origen.py` y
  `motor/test_diagnostico_grabador.py` están re-baselinados con las cifras
  medidas, no solo con números nuevos: se reescribieron los casos obsoletos
  (`H_0357`, `H_0058`, `H_0546`) en vez de relajar sus invariantes.
- `tools/test_reparar_asientos.py`: 7 tests.
- `motor/test_auditar_origen.py`: 29 tests. `motor/test_diagnostico_grabador.py`:
  39 tests.
- Suite `motor recorder tests`: **927 passed, 1 skipped, 5 xfailed** en 5 min
  24 s. Los `tools/test_live.py` y `tools/test_mano6.py` no son suite: piden
  entrada por teclado o una captura que no está en el repo.

## 5. Lo que sigue abierto

1. **Unificar el resolvedor de ids.** `tools/auditar_rango.py::pos_de_pid` y
   `tools/calibrar.py::id_a_pos` deben usar `multiway.posicion_de_id` y
   rechazar la mano si el contrato no se cumple. Añadir test de regresión.
2. **Re-anclar la Fase D** (`DOCS/FASE_D_PLAN.md`) con el SHA y las ventanas
   nuevas, y solo entonces calibrar. La tabla de `DOCS/RANGO_VIGENTE.md` §4
   sigue medida sobre la base de 1258.
3. **Arreglar H4** (limp corto contado como subida) y re-derivar sus cifras.
   Su condición ya se cumple: las cifras están re-derivadas contra la base
   adoptada.
4. **Revisar la codificación `p` en las auditorías.** 45 manos tienen una `p`
   en posición distinta de SB/BB con importe 1.0: es un limp codificado como
   posta, no un ante. Hay que decidir si se recodifica a `c` antes de
   calibrar, y corregir los textos de `tools/auditar_origen.py` que aún hablan
   de `BB b`.
5. **Revisar las tres ciegas dobles.** `H_0357`, `H_0475` y `H_0738` tienen una
   `BB b` después de la `BB p`. `_es_ciega_bb` marca las dos como ciega porque
   no hay acción voluntaria entre medias, así que el motor se come la segunda
   acción. Está declarado en `motor/test_ciega_bb.py`, no arreglado: toca
   decidir si es dato o motor, y si se arregla, regenerar derivados.
6. **Actualizar la documentación obsoleta:** `DOCS/PROYECTO.md`,
   `DOCS/PLAN_ACCION.md`, `DOCS/ESTADO_DEL_TRABAJO.md` e
   `INDICE_DEFECTOS.md`.

## 6. Comandos

```powershell
python tools/reparar_asientos.py
python -m pytest tools/test_reparar_asientos.py -q
python -m pytest motor/test_multiway.py -q
python -m pytest motor/test_learn.py -q
python -m pytest motor/test_auditar_origen.py motor/test_diagnostico_grabador.py -q
```

Comprobación estructural sobre la base canónica:

```powershell
python -c "import sys; sys.path.insert(0,'.'); import motor.learn as L; from motor.multiway import contrato_orden_ok; hs=L.load_hands(); print(sum(1 for h in hs if not contrato_orden_ok(h)))"
```

Resultado esperado: `0`.

## 7. Lo que no se hace

- No calibrar mientras la tabla de la ventana no esté re-anclada a la base de
  1253.
- No escribir `data/hands_db.jsonl` desde un script: el canal manual está
  cerrado (`DOCS/CANAL_MANUAL_CERRADO.md`).
- No actualizar los pins a ciegas para poner la suite en verde.
- No dar por neutra la normalización: cambia posiciones efectivas, añade las
  postas `p` y codifica limps como `p` en 45 manos, aunque las categorías
  medidas sean idénticas.
