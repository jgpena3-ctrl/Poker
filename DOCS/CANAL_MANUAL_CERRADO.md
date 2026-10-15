# CANAL MANUAL CERRADO — `hands_db.jsonl`

**Estado:** vigente.
**Fecha:** 2026-10-14
**Commit del estado canónico:** `5c41b23`
**SHA-256:** `202a1f548fc60bac3d0d4b7a225429083e22298d97a5f6f38cb28d24435b0634`
**Líneas:** 1258
**Vigila:** `motor/test_canal_manual.py`

---

## 1. Qué significa «cerrado»

> **`data/hands_db.jsonl` solo se modifica con un script versionado en
> `tools/`. Nunca a mano, nunca con un editor, nunca copiando y pegando.**

No es una intención. `motor/test_canal_manual.py` falla si:

| | |
|---|---|
| 1 | el fichero tiene cambios **sin commitear** |
| 2 | su `sha256` **no es** `learn.HANDS_DB_SHA256` |
| 3 | el número de manos **no es** `learn.HANDS_DB_LINEAS` |
| 4 | este documento **no menciona** el hash y el commit vigentes |
| 5 | el commit declarado **no existe** o **no tiene** ese hash |

Las cinco se leen juntas porque cada una sola se puede esquivar. Un hash
declarado sin documento es una afirmación sin respaldo; un documento sin
hash es una descripción de otra base.

## 2. Por qué, y no es una norma de estilo

En este mismo bloque, `aplicar_reinterpretacion.py --apply` sobrescribió
**928 líneas** que el mantenedor había escrito a mano: 74 manos modificadas y
22 borradas. Se restauraron enteras y no se perdió nada, pero el agujero era
real: el script comparaba con **su propia salida** y no con la del fichero
que tenía delante.

Lo que faltaba no era que el script fuera cuidadoso. Era **que nadie pudiera
hacerlo por error**.

> El fallo no fue ejecutar `--apply`. Fue que el script no tenía la
> garantía de «no sobrescribo lo que no es mío». Ahora sí, y además hay un
> test que falla si el fichero se sale del estado declarado.

`--apply --descartar-cambios` sigue existiendo, y es una **salvaguarda, no
una recuperación**: si se autoriza, el fichero ajeno se reemplaza. Por eso el
backup se verifica por hash antes de escribir y el rollback es automático si
la verificación posterior falla.

## 3. Los estados que se reconocen

`aplicar_reinterpretacion.py::estado_del_fichero_actual()` clasifica el
fichero en tres:

| estado | sha256 | qué es |
|---|---|---|
| `referencia` | `bb46fec0…` | `e314f74`, el punto de partida: CM-001, CM-003 y la ventana de 877 |
| `salida_de_este_script` | `173a7274…` | lo que produce `aplicar_reinterpretacion.py` |
| **`ajeno`** | cualquier otra cosa | alguien lo editó |

Con `ajeno`, `--apply` se niega y dice cuántas líneas se perderían. En
`dry-run` lo informa pero no falla: **informar no es escribir**.

## 4. El estado vigente tiene 68 cambios sin declarar

Este es el punto abierto, y por eso el estado canónico no es la salida del
script. Lo que sigue sale de `python tools/reconciliar.py`, que es **solo
lectura**:

- `5c41b23` tiene **1258** líneas. La referencia `e314f74` tenía **1280**.
- **22 manos borradas**, **70 modificadas** sobre la referencia.
- De esas 70, **24** son los 23 de CM-004 más `H_0350`, con motivo
  identificable.
- **46 no tienen motivo escrito en ninguna parte.**
- De esas 46, **8** son las reversiones que `02fc641` deshizo y que volvieron
  a aplicarse.

### 4.1 La base está CONGELADA

> **Mientras haya revisión manual en curso, `hands_db.jsonl` no se modifica:
> ni a mano, ni con script.**

`learn.REVISION_PENDIENTE = True`. El mantenedor va revisando las manos una a
una —lleva **1014** de ~1200— y las decisiones que dependen de eso se toman al
final. Editar la base mientras se revisa invalidaría la revisión.

Se hace cumplir con tests, no con una nota:

| | |
|---|---|
| `test_la_base_no_cambia_mientras_hay_revision_manual` | falla si el sha256 cambia |
| `aplicar_reinterpretacion.py --apply` | se niega y devuelve **4** |

`--descartar-cambios` **no salta** el congelamiento. Saltarlo significa
terminar la revisión, no escribir más rápido.

### 4.2 Decisión vigente

**Documentar y aplazar.** No se declaran los 46, no se revierten las 8
reaplicadas, no se restauran las 22 borradas. Se dejan escritas y se deciden
cuando la revisión llegue al final. Ver `DECISION_CM004.md` §0-ter.

## 5. Cómo se cambia la base a partir de ahora

```bash
# 1. el script, con su dry-run primero
python tools/aplicar_reinterpretacion.py
python tools/aplicar_reinterpretacion.py --apply

# 2. si el fichero actual NO es suyo, hay que decirlo a sabiendas
python tools/aplicar_reinterpretacion.py --apply --descartar-cambios

# 3. actualizar el estado canonico: las DOS constantes, con motivo
#      learn.HANDS_DB_SHA256
#      learn.HANDS_DB_LINEAS
#      learn.HANDS_DB_COMMIT
#    y este documento

# 4. regenerar los derivados, si el cambio afecta a la ventana
python tools/reconstruir_derivados.py regen

# 5. suite
python -m pytest motor recorder tests -q
```

**Actualizar el hash sin escribir el motivo en este documento es editar a
mano con más pasos.** Es la misma falta de trazabilidad, con más pasos.

## 6. `aplicar_correcciones.py` todavía no declara su salida

Es el otro script que escribe este fichero, y **no declara el sha256 de lo
que produce**. Mientras sea así, su salida es indistinguible de una edición
manual, que es justo el problema que se quiere cerrar.

Hay un test que lo dice (`test_los_dos_scripts_de_escritura_declaran_a_que_script_se_debe`).
Está pendiente de resolverse: o se le declara el SHA de salida, o se declara
que ya no se usa.

## 7. Lo que este documento NO dice

- No dice que la base actual sea **correcta**. Dice que es **conocida**:
  tiene un hash, un commit y una lista de lo que no está declarado.
- No dice que las 22 manos borradas estuvieran mal. Dice que **se borraron**,
  y que la evidencia que lo autoriza está sin escribir. Ver
  `DOCS/HALLZGOS_H0001_H1014.md` §5.