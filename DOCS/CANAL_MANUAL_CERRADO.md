# CANAL MANUAL CERRADO — `hands_db.jsonl`

**Estado:** vigente.
**Fecha:** 2026-10-15
**Commit del estado canónico:** `9b5905a`
**SHA-256:** `36dce9fecac77356c19181be1bba06b9fe52b6f11db811b5fa4a9d991926b481`
**Líneas:** 1258
**Vigila:** `motor/test_canal_manual.py` — 12 tests

---

## 1. Qué significa «cerrado»

> **Ningún SCRIPT escribe `data/hands_db.jsonl`. Nunca a mano, nunca con un
> editor, nunca copiando y pegado.**
>
> El mantenedor **sí** la edita a mano: eso es la revisión. Lo que está cerrado
> es el canal por el que se cuela una escritura sin que nadie la decida. Ver §4.1.

No es una intención. `motor/test_canal_manual.py` falla si:

| | |
|---|---|
| 1 | el fichero tiene cambios **sin commitear** |
| 2 | su `sha256` **no es** `learn.HANDS_DB_SHA256` |
| 3 | el número de manos **no es** `learn.HANDS_DB_LINEAS` |
| 4 | este documento **no menciona** el hash y el commit vigentes |
| 5 | el commit declarado **no existe** o **no tiene** ese hash |
| 6 | el blob de git y el fichero en disco **no coinciden** byte a byte |
| 7 | `aplicar_reinterpretacion.py` **no** comprueba la revisión en curso |
| 8 | el mensaje de revisión vuelve a decir «BASE CONGELADA» |

Las ocho se leen juntas porque cada una sola se puede esquivar. Un hash
declarado sin documento es una afirmación sin respaldo; un documento sin hash
es una descripción de otra base.

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

El estado vigente (`9b5905a`) es `ajeno`, y con razón: es la revisión manual.

## 4. El estado vigente: 63 manos revisadas, y medida

`9b5905a` cambió **63** manos sobre `5c41b23`. No es un cambio único, son
cuatro familias de corrección, todas sobre manos que el mantenedor estaba
revisando una a una (de `H_1014` a `H_1029`).

Lo que se comprobó, contra el fichero anterior y no contra una impresión:

| | `5c41b23` | `9b5905a` |
|---|---|---|
| manos con una `BB b` mal ordenada (**el invariante de CM-004**) | 2 · `H_0103`, `H_0236` | **0** |
| manos sin ganador declarado | 1 | **0** |
| `winner` con 2+ ganadores, dentro de las 63 tocadas | 14 | **1** |
| jugadores `active:false` que conservan `pos` | 29 | **20** |
| cartas del hero corregidas por OCR | — | 3 manos |
| líneas del fichero | 1258 | 1258 |

| familia | cuántas | qué es |
|---|---|---|
| orden de la ciega del BB | 20 con preflop tocado | `BB x inferred` colocado donde el motor lo reconoce como ciega, acciones fantasma retiradas |
| `winner` | 17 | listas de 2 a 6 ganadores reducidas a uno; la mano sin ganador recuperada |
| `active` / `pos` | ~20 | jugadores que ya habían folderado con `active:false` y `pos` todavía puesta, o al revés |
| OCR | 3 | cartas del hero corregidas |

**La decisión es aceptar el estado y declararlo**, que es lo contrario de
revertirlo: revertir devolvería dos violaciones del invariante de CM-004 y
perdería trabajo real. Se llama Opción A en `revision_1`.

### 4.1 La revisión en curso NO congela la base

> **Mientras haya revisión manual en curso, ningún SCRIPT escribe
> `hands_db.jsonl`.**

`learn.REVISION_EN_CURSO = True`. El mantenedor va revisando las manos una a
una —lleva **1029** de ~1200— y eso, por definición, es editar el fichero.

**Lo que esta frase ya NO dice**, y antes sí:

> ~~`hands_db.jsonl` no se modifica: ni a mano, ni con script.~~

Las dos mitades eran verdad y juntas eran una contradicción: *revisar las
manos una a una es cambiarlas*. El congelamiento prohibía exactamente la
actividad de la revisión. Medido: `9b5905a` cambió 63 manos —legítimas, y con
mejora medida— y el guard falló, que es lo único que el guard podía hacer.
Volvería a fallar en el siguiente commit de la revisión. Eso no es un guard: es
una bomba de relojería, y obligaba a apagar el mecanismo entero para poder
seguir revisando.

| | antes | ahora |
|---|---|---|
| el mantenedor edita a mano | **prohibido** | **es la revisión** |
| un script escribe | prohibido | prohibido |
| el manifiesto se redeclara | imposible mientras dure la revisión | en cada avance, con su motivo |

Lo que protege las ediciones del mantenedor no es un congelamiento: es
`test_el_hash_de_la_base_es_el_declarado`. Obliga a que cada cambio de la
base lleve su hash, su commit y su motivo escrito. Dos guards del mismo
invariante no son más seguridad, son dos sitios donde el invariante puede
estar mal.

`--descartar-cambios` **no salta** el bloqueo de scripts. Saltarlo significa
terminar la revisión, no escribir más rápido.

### 4.2 Decisión vigente

**Declarar y continuar.** Las 22 borradas, las 70 de `5c41b23` y las 63 de
`9b5905a` **se aceptan** y quedan escritas, con el hash y el motivo aquí. Ya no
hay un «pendiente» que resolver: un pendiente que nadie puede resolver no es un
estado defendible en un repositorio.

Lo que **sigue abierto** no es el estado de la base, sino estas decisiones, que
son de calibración y no de datos:

| | |
|---|---|
| [APARCADO_DB.md](APARCADO_DB.md) | lo que queda aparcado, con su estado medido |
| [RANGO_VIGENTE.md](RANGO_VIGENTE.md) | si las manos excluidas vuelven a la ventana de calibración |

## 5. Cómo se cambia la base a partir de ahora

```bash
# 1. el script, con su dry-run primero
python tools/aplicar_reinterpretacion.py
python tools/aplicar_reinterpretacion.py --apply

# 2. si el fichero actual NO es suyo, hay que decirlo a sabiendas
python tools/aplicar_reinterpretacion.py --apply --descartar-cambios

# 3. actualizar el estado canonico: las TRES constantes, con motivo
#      learn.HANDS_DB_SHA256
#      learn.HANDS_DB_LINEAS
#      learn.HANDS_DB_COMMIT
#    y este documento

# 4. si el cambio afecta a la ventana, recalcular las cifras publicadas
python tools/auditar_solapamiento_multiway.py     # §5 de CONTRATO_F72A.md

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

- No dice que la base actual sea **correcta**. Dice que es **conocida**: tiene
  un hash, un commit y una lista de lo que se hizo y por qué.
- No dice que las 22 manos borradas de `5c41b23` estuvieran mal. Dice que **se
  borraron**, y que la evidencia que lo autoriza está sin escribir. Ver
  `DOCS/HALLZGOS_H0001_H1014.md` §5.
- No dice que `9b5905a` esté completo. Dice que las 63 manos que tocó están
  medidas y declaradas, y que la revisión sigue en `H_1029` de ~1200.