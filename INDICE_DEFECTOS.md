# ÍNDICE DE DEFECTOS Y CASOS — BASE HISTÓRICA DE 1258 REGISTROS

> ⚠️ **Índice histórico.** Se midió sobre la base de 1258 (`35727961…`). La
> base canónica es ahora de **1253** líneas (`c3172a14…`, commit `51a6fb9`) y
> estos recuentos no se han vuelto a medir. El estado operativo está en
> [`DOCS/HOJA_DE_RUTA_POST_ADOPCION.md`](DOCS/HOJA_DE_RUTA_POST_ADOPCION.md).

**Respuesta corta: no existe ese documento.** El problema de cada grupo está
repartido por **58 ficheros en `DOCS/`**, y **la mayoría siguen hablando de 1280
manos** — la base antes de la retirada de 22.

Este fichero es el índice. **No sustituye a los documentos de origen**: los
señala y dice en qué estado real están, medido hoy contra los 1258.

- **SHA base:** `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`
- **Medición de este índice:** `python tools/auditar_rango.py` sobre **H_0001..H_1014**
  (991 manos), contra la base de hoy.

---

## 1. Grupos con defecto, verificados hoy

| grupo | manos **[C] hoy** | dónde se explica | qué pide | acción |
|---|---:|---|---|---|
| **`IMPORTE_SUBIDA`** | **30** | `DOCS/DEFECTO_45.md` | una subida que no supera la apuesta viva | **manual + grabación** |
| **`SHOWDOWN_SIN_WINNER`** | **15** | ⚠️ **sin documento propio** | `showdown` cita a quien no ganó | **manual + grabación** |
| **`WINNER_FOLDEO`** | **3** | `DOCS/DEFECTO_214.md` | `winner` incluye a quien foldeó | **manual + grabación** |
| **`ACCION_FANTASMA`** | **2** | `DOCS/DEFECTO_FANTASMA.md` | acción de una posición no sentada | **manual + grabación** |
| **`ACCION_DESPUES_FOLD`** | **0** | `DOCS/DEFECTO_8.md` | acción tras fold | **nada: ya no ocurre** |
| **`SIN_RESPUESTA_BB`** | **0** | `DOCS/DEFECTO_652.md` | el BB no responde tras la subida | **nada: ya no ocurre** |

**Total a editar a mano: 50 manos, cero solapamientos.**
IDs en `PLAN_EDICION_DB.md` § 4.

> ⚠️ **`SHOWDOWN_SIN_WINNER` no tiene documento.** Es la clase más grande sin
> cobertura escrita: 15 manos que `auditar_rango.py` detecta y que nadie ha
> escrito. Es el hueco más visible de esta lista.

---

## 2. Correcciones CM — todas aplicadas salvo CM-002

| id | qué es | documento | **[C] estado hoy** |
|---|---|---|---|
| **CM-001** | `H_0141` importe `27.0` → `2.7` | `CORRECCIONES_MANUALES.md`, `MIGRACION_CM001_CM003.md` | **aplicada** — la acción vale `2.7` |
| **CM-002** | `H_0350` `cards: "-"` | `CORRECCIONES_MANUALES.md` | **pendiente y NO verificable** sin el pantallazo |
| **CM-003** | 26 checks del BB con `inferred:true` | `CORRECCIONES_MANUALES.md`, `MIGRACION_CM001_CM003.md` | **aplicada** — quedan 23 marcas |
| **CM-004** | ciega del BB tras acciones voluntarias (23 manos) | `CORRECCIONES_MANUALES.md`, `CM004_REINTERPRETACION.md`, `DECISION_CM004.md`, `EXCLUSION_CM004.md`, `RECONSTRUCCIONES_CM004.md` | **aplicada — quedan 0 mal ordenadas** |

> 🔴 **Aviso de desfase.** `CORRECCIONES_MANUALES.md` marca **CM-004 como
> «abierta»** y `RECONSTRUCCIONES_CM004.md` como «cerrado». **El primero está
> desfasado**: la corrección está hecha. Si alguien lo lee y lo «arregla» otra
> vez, rompe 23 manos ya reparadas.

---

## 3. Casos aislados

| caso | manos | dónde se explica | **[C] estado** |
|---|---:|---|---|
| **`H_1196`** | 1 | `DOCS/INC-004_H_1196.md` | **el rojo intencional.** El test `test_cm004.py` sigue fallando con él |
| **`SIN_ALLIN`** | **73** (`H_0001`–`H_0073`) | `DOCS/APARCADO_DB.md`, `HALLZGOS_H0001_H1014.md` | **no es un defecto.** Es la huella del grabador antiguo |
| **Las 22 retiradas** | 22 registros / 21 contenidos | `DOCS/PROYECTO.md` § 6.3 (línea 733) | retiradas en `75bbdb7` sin criterio establecido |
| **`H_1015`** | 1 | `DOCS/PROYECTO.md` (no figura en su lista) | retirada **sin ninguna lista** que la mencione |
| **`H_0350`** | 1 | `CORRECCIONES_MANUALES.md` | `cards: "-"`, solo si aparece el pantallazo |

> ⚠️ **`SIN_ALLIN` no se «corrige».** Añadir `allin: []` a las 73 destruye la
> única huella que distingue el grabador de julio. Ver `PLAN_EDICION_DB.md` § 3.

---

## 4. Los documentos y cuál está desfasado

**[C]** 12 de 58 mencionan 1258. El resto **no**.

| desfasado (habla de 1280) | veces que dice «1280» |
|---|---:|
| `PROYECTO.md` | **22** |
| `DECISION_CM004.md`, `CM004_REINTERPRETACION.md`, `DIAGNOSTICO_CALIBRACION.md` | 6 cada uno |
| `HALLZGOS_H0001_H1014.md`, `RESUMEN_SECCION.md` | 5 / 3 |
| `CORRECCIONES_MANUALES.md`, `RECONSTRUCCIONES_CM004.md`, `DEFECTO_652.md`, `MIGRACION_CM001_CM003.md` | 1–3 |

**[D]** Los documentos que **sí** están al día con 1258:
`APARCADO_DB.md`, `APUESTAS_DELTA.md`, `AUDITORIA_ORIGEN.md`,
`CANAL_MANUAL_CERRADO.md`, `HALLZGOS_H0001_H1014.md`, `INC-004_H_1196.md`,
`RANGO_VIGENTE.md`, `REVISION_TECNICA_AUDITORIA.md`, `SANEAMIENTO.md`.

**[D]** `PROYECTO.md` es el documento de referencia del proyecto y es el **más
desfasado**: su § 6.3 dice que hay que eliminar 20 manos que **ya están
eliminadas**, y su § 6.4 habla de 1280 en todo el análisis de la ventana.

---

## 5. Los documentos que NO son de datos

**[D]** Para no buscarlos donde no están: de los 58 ficheros en `DOCS/`, unos 40
son de **motor** (`CONTRATOS_*`, `FASE_D_*`, `L_SEC_*`, `AUC_*`,
`CALIBRACION_*`), no de la base de manos. El índice de arriba cubre los que sí
son de datos.

---

## 6. Resumen operativo

| pregunta | respuesta |
|---|---|
| ¿cuántas manos hay que editar a mano? | **50** |
| ¿hay lote viable? | **no** — las 4 clases necesitan la grabación original |
| ¿qué está ya aplicado? | CM-001, CM-003, CM-004 |
| ¿qué queda sin poder corregir? | CM-002, sin pantallazo |
| ¿qué NO es un defecto? | `SIN_ALLIN` (73), DEFECTO_8 (0), DEFECTO_652 (0) |
| ¿qué es una decisión, no una corrección? | las 22 retiradas y `H_1015` |
| ¿qué no está escrito en ningún sitio? | **`SHOWDOWN_SIN_WINNER`, 15 manos** |

**[P]** Plan de edición y procedimiento manual: `PLAN_EDICION_DB.md`.
**[P]** Copia de trabajo y editor: `trabajo/ABRIR_EDITOR_COPIA.py`.