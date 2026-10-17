# LOS CINCO BLOQUEOS, Y DE QUIÉN ES CADA UNO

> R1 pide, como criterio de su tarea 6, que INC-004 esté «en la lista de lo
> que queda bloqueado y no es mío». Y R2 dice por qué esa lista importa:
>
> > Lo que hace que un proyecto se pueda retomar: no «queda esto», sino «queda
> > esto y es de este».
>
> Esa lista no existía en ningún fichero. Vivía en los mensajes de commit y
> en el informe de cada bloque, que es donde deja de estar cuando el commit
> se deja de leer.
>
> **Los cinco están declarados y ninguno está resuelto.** Este documento no
> resuelve ninguno: los nombra, dice qué haría falta y dice de quién es la
> decisión.

## La lista

| # | el bloqueo | qué haría falta | de quién es |
|---|---|---|---|
| 1 | **`H_1196` tiene una `BB b` mal ordenada** (INC-004) | una decisión, y es de dos caras | del dueño de `data/` **y** `motor/` |
| 2 | **qué significa `matrix`** | la intención del generador del fichero | de quien generó el fichero |
| 3 | **las 5 manos con board divergente** | un bloque de instrumentación | de quien pueda abrir un bloque |
| 4 | **la vía preflop del motor** | un bloque en `motor/`, con contrato antes | del dueño de `motor/` |
| 5 | **ponderar la predicción por rival** | decidir si se pondera, y con qué pesos | de quien decida el objetivo |

Y hay un sexto que no es un bloqueo sino una **decisión cerrada**:

| | |
|---|---|
| **`DEFAULT_ALPHA`** | **2,0.** No se calibra, y no porque las métricas no lo digan, sino porque AUC mide orden y `alpha` es una escala. No es un bloqueo: está decidido. Ver [`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md) |

## 1. INC-004 — `H_1196`, y por qué no es un fallo de este bloque

[`INC-004_H_1196.md`](INC-004_H_1196.md) dice **ESTADO: ABIERTO**, y el fallo
sigue visible a proposito:

```
FAILED motor/test_cm004.py::test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega
AssertionError: manos con una `BB b` mal ordenada otra vez: ['H_1196']
```

Ni `xfail`, ni `skip`. Y `tools/test_inc004_sigue_abierto.py` comprueba que
siga asi, para que no se pueda cerrar por cansancio.

**La decisión es de dos caras y no se puede elegir sin abrir una**, así que
no se abre aquí:

- si el **registro** de `H_1196` es lo que está mal, el arreglo es de `data/`,
  y el invariante CM-004 sigue siendo correcto;
- si el **invariante** CM-004 es lo que está mal, el arreglo es de `motor/` y
  el registro puede quedarse como está.

Las dos caras son de la misma persona porque tocan las dos capas. Y por eso no
es un arreglo: es una decisión, y las decisiones tienen dueño.

## 2. `matrix` — declarado, no resuelto

[`QUE_ES_MATRIX.md`](QUE_ES_MATRIX.md) tiene una cota medida y una pregunta
abierta para quien generó el fichero. Lo que se sabe y lo que no está en sus
§«Se sabe» y §«No se sabe, y no se puede saber con datos».

Y aquí está el punto que hace que no se pueda cerrar desde dentro: **la
semántica no está en los datos**. Un fichero puede ser cualquier cosa y
producir los mismos números. Asumir la semántica sería inventarla, que es
exactamente el error que este bloque lleva cuatro rondas corrigiendo en otro
sitio.

## 3. Las 5 manos con board divergente

`tablero()` lee `comunitarias`; `villain_hasta_corte()` lee `streets.*.board`.
En 5 de las 877 manos no coinciden.

**No se corrigen aquí**, y el motivo es concreto: corregirlo cambia la
instrumentación, y por lo tanto **mueve las cifras**. Un AUC que se publica
no se mueve como efecto secundario de una limpieza. Hace falta un bloque, con
su medición antes y después.

Está medido y escrito en
[`QUE_REPRESENTA_LA_PREDICCION.md`](QUE_REPRESENTA_LA_PREDICCION.md) §2.3.

## 4. La vía preflop del motor

El motor **no tiene camino de equity preflop**: `situation` declara board de 3
a 5 cartas. Por eso la única vía preflop que hay es una enumeración contra las
cartas **reales** del rival, que va marcada `observable: False` y que el propio
código dice que **no** es la equity de una decisión.

Añadirla es un bloque en `motor/`, y por la regla del proyecto **un contrato
antes de tocar `motor/`**. Los dos contratos que hay, `CONTRATO_PREFLOP.md` y
`CONTRATO_L_SEC.md`, están firmados y no se tocan.

## 5. Ponderar la predicción por rival

Con 415 de 877 cortes con más de un rival vivo, «la equity del héroe» no es un
número: es una lista. El AUC usa la **mediana**, sin ponderar.

Medido: para este AUC la elección **no importa** —recorrido 0,0333 contra una
amplitud de IC de 0,5667—. Pero eso es lo que se ha medido: **cuánto mueve**,
no si es lo correcto. Que la mediana sea la reducción correcta es una
cuestión de poker, y si lo es, ponderar por bote puede no ser lo mismo.

## Lo que este documento NO hace

- **No resuelve ninguno.** Los cinco necesitan una decisión de alguien.
- **No los baja de categoría.** Un bloqueo con dueño es una cosa sana; un
  bloqueo sin dueño es deuda.
- **No los mezcla.** Que los cinco aparezcan juntos en una tabla no los hace
  del mismo tipo: dos son decisiones de datos, dos son instrumentación, y uno
  es semántica. La lista los ordena por de quién es, que es lo único que
  tienen en común.