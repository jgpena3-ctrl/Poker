# AUDITORIA DEL ESTADO DE LOS JUGADORES

> **Estado:** medicion cerrada; las 53 manos de estado quedan en cuarentena.
> **Fuente:** `trabajo/hands_db_edicion.jsonl` (1258) y la copia filtrada
> previa a esta cuarentena (1109). Tras apartar las 53 manos de estado, la
> copia filtrada vigente tiene 1056.
> **No cambia** ninguna cifra publicada ni la base canonica.

## 1. Que se mira

Cuatro formas que no tenian detector propio:

| clase | pregunta |
|---|---|
| `ACTIVO_SIN_POSICION` | un jugador `active: true`, ¿tiene `pos`? |
| `ACTIVO_SIN_ACCION` | un activo con `pos`, ¿actuo alguna vez, foldo o esta all-in? |
| `ACTIVO_SIN_ACCION_CALLE` | en una calle con acciones, ¿desaparecio alguien que no foldo ni estaba all-in? |
| `INACTIVO_CON_POSICION` | un jugador `active: false`, ¿conserva `pos`? (metrica) |

El cuarto caso de la lista original —inactivo con acciones— ya lo cubre
`INACTIVO_QUE_ACTUA`.

## 2. Medido

Sobre la copia completa y sobre la copia filtrada previa (1109):

| clase | copia (1258) | filtrada previa (1109) |
|---|---:|---:|
| `ACTIVO_SIN_POSICION` | 81 manos | 67 manos |
| `ACTIVO_SIN_ACCION` | 39 manos | 31 manos |
| `ACTIVO_SIN_ACCION_CALLE` | 69 manos | 52 manos |
| `INACTIVO_QUE_ACTUA` | 1 mano | 1 mano |
| `INACTIVO_CON_POSICION` | 20 manos | 17 manos |

La base canonica da cifras algo mayores porque no tiene las ciegas del SB que
la copia ya normalizo; no se usa como fuente de esta auditoria.

`ACTIVO_SIN_POSICION` cuenta 75 jugadores en las 67 manos filtradas. Ninguno
tiene cartas ni acciones: son, con la forma actual del dato, jugadores
sentados que no entraron en la mano. El esquema no tiene una bandera
`dealt`, asi que la forma no distingue por si sola entre "sentado sin
repartir" y "posicion perdida". Nombres repetidos: `triki12` (10),
`Johan Otero` (8), `Elyessi27` (7), `Geilyn21` (6), `Maicolp` (5), ademas de
marcadores como `P1`, `P4`, `P5`, `mur420` y `HERO`.

`ACTIVO_SIN_ACCION` es mas fuerte: el jugador tiene posicion y no actuo, no
foldo y no figura en `allin`. Por posicion en la copia filtrada:

| posicion | manos |
|---|---:|
| BTN | 13 |
| MP | 7 |
| UTG | 6 |
| CO | 5 |

Ejemplos: `H_0017` (MP), `H_0018` (BTN), `H_0028` (BTN). Son posiciones que
debian hablar y no tienen ninguna accion: o el registro las perdio, o
`active` esta mal puesto.

`ACTIVO_SIN_ACCION_CALLE` reparte las desapariciones por calle. En la copia
filtrada hay 119 casos en 52 manos: 31 en preflop, 34 en flop, 28 en turn y
26 en river. En preflop coinciden con `ACTIVO_SIN_ACCION` (BTN 13, MP 7,
UTG 6, CO 5). En las calles siguientes aparecen SB y BB que dejan de actuar:
`H_0002` (SB tras el preflop), `H_0015` (BB sin accion en flop, turn ni
river). Son checks o folds omitidos, no all-in: si lo fueran, estarian en
`allin`.

`INACTIVO_QUE_ACTUA` da una sola mano, `H_0294`: el SB (`CCE`) esta
`active: false` y aun asi tiene la ciega `SB p 0.5` que anadio la
normalizacion. En la base canonica no aparecia porque faltaba esa ciega. Es
una contradiccion real, no un efecto de la auditoria, y queda en cuarentena.

`INACTIVO_CON_POSICION` es una forma benigna: jugadores sentados que no
jugaron. Solo es defecto cuando ademas actuan, y ese caso lo separa
`INACTIVO_QUE_ACTUA`.

## 3. Lo que ya estaba y conviene no confundir

- `AUSENCIA_RESPUESTA_BB` sobre `H_1241` es un falso positivo: el BB esta
  all-in (`allin: ['p3']`) y el detector existente no lee `allin`. No se toca
  sin actualizar su cifra publicada y sus tests.
- `SHOWDOWN_SIN_WINNER` da 5 manos en la copia filtrada (`H_0447` BB,
  `H_0511` CO, `H_0744` UTG y dos mas). Es un defecto ya declarado; no entra
  en las cuatro clases de arriba.
- `H_0713` tiene `"pos": "UTF"` en una accion del river (deberia ser `UTG`).
  Es una errata de edicion manual; se conserva senalada.
- `H_0169` sigue pendiente de eliminar; no se borra desde esta auditoria.

## 4. Como se reproduce

```
python tools/auditar_rango.py --db trabajo/hands_db_sin_cuarentena.jsonl
python tools/auditar_rango.py --validar
```

`--validar` sigue reproduciendo las cifras con codigo de origen. Las clases
nuevas no tienen cifra publicada: se toman de este script, no de documentos
anteriores.

## 5. Decision

Las 52 manos de `ACTIVO_SIN_ACCION_CALLE` (que incluyen las 31 de
`ACTIVO_SIN_ACCION`) y `H_0294` de `INACTIVO_QUE_ACTUA` quedan en cuarentena:
son 53 manos sin solape con las 149 pendientes de bote, asi que la lista pasa
a 202 y la copia filtrada a 1056.

El motivo de no reconstruirlas: el jugador que desaparece tiene `pos`, no
tiene cartas y no aporta fichas, lo que es compatible con un fold omitido;
pero el dato no dice en que indice se produjo ni si fue un fold o un check.
Escribir esa accion seria inventarla. Se declara como ausencia y se aparta.

`ACTIVO_SIN_POSICION` no se aparta: los 75 jugadores de las 67 manos no
tienen cartas, no actuan y no aportan fichas. Se resuelven como sentados sin
repartir; la clase queda documentada como forma, no como defecto de datos.

`H_0294` es la excepcion del lote: no es una ausencia, es una contradiccion
(`active: false` con ciega). Se aparta igual porque no se puede decidir cual
de las dos mitades es la buena sin la grabacion.
