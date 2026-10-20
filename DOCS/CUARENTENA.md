# CUARENTENA DE LA COPIA DE TRABAJO

> **Estado:** vigente.
> **Alcance:** `trabajo/hands_db_edicion.jsonl`.
> **No toca** `data/hands_db.jsonl` ni la ventana fiable de `motor/learn.py`.

## 1. Que se aparta

Las manos de la copia cuyo bote sigue pendiente de revision:

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack) | 4 |
| `NADA` (el bote no coincide con ninguna lectura) | 126 |
| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | 20 |
| `AUDITORIA:ACTIVO_SIN_ACCION_CALLE` | 52 |
| `AUDITORIA:ACTIVO_SIN_ACCION` (incluidas en las 52) | 31 |
| `AUDITORIA:INACTIVO_QUE_ACTUA` | 1 |

Las tres primeras listas se solapan: una mano `STACK` puede ser tambien
`NADA`. La union de las pendientes de bote son **149 manos**. A ellas se
anaden **53** de estado de jugadores, sin solape: **202 en cuarentena** y
**1056** en la copia filtrada.

De las 20 `ACCION_AMBIGUA`: 13 `REPARTO`, 6 `NETO_IGUAL` y 1 `REAL`. Las
`DEVUELTA` ya se resolvieron y no entran.

Las 52 de estado de jugadores son manos con una calle que tiene acciones y un
jugador `active` que desaparece de ella sin fold ni all-in. Las 31 de
`ACTIVO_SIN_ACCION` son el caso extremo: no actuan en ninguna calle. El
patron es consistente con un fold omitido: tienen `pos`, no tienen cartas y
no aportan fichas. No se reconstruye porque el dato no dice en que indice se
folio ni si la accion omitida fue un fold o un check; ponerla seria inventar
la accion, no leerla.

La 53 es `H_0294`: el SB esta marcado `active: false` y conserva la ciega
`SB p 0.5` que anadio la normalizacion. Es una contradiccion que no se
resuelve sin la grabacion.

## 2. Los dos ficheros

| fichero | contenido |
|---|---|
| `trabajo/cuarentena.jsonl` | una linea por mano: `hand_id`, `motivos`, `clase`, `causa` |
| `trabajo/hands_db_sin_cuarentena.jsonl` | las 1056 manos que no estan en cuarentena |

La copia filtrada conserva las lineas ORIGINALES de la copia, no una
reserializacion: lo que no esta en cuarentena no cambia ni un byte.

## 3. Por que no se mete en el motor

`motor/learn.EXCLUSIONES_VENTANA_FABLE` cambiaria la ventana fiable de 877
manos y, con ella, las cifras publicadas. Adoptar la cuarentena en el motor es
una decision posterior a la revision; no es un efecto de este instrumento.
Mientras dure la revision, la cuarentena vive en `trabajo/`.

## 4. Como se regenera y se comprueba

```
python tools/cuarentena.py --desde-auditoria trabajo/auditoria_jugadores.json --clases ACTIVO_SIN_ACCION,ACTIVO_SIN_ACCION_CALLE,INACTIVO_QUE_ACTUA --resumen
python tools/cuarentena.py --desde-auditoria trabajo/auditoria_jugadores.json --clases ACTIVO_SIN_ACCION,ACTIVO_SIN_ACCION_CALLE,INACTIVO_QUE_ACTUA --escribir
python tools/cuarentena.py --desde-auditoria trabajo/auditoria_jugadores.json --clases ACTIVO_SIN_ACCION,ACTIVO_SIN_ACCION_CALLE,INACTIVO_QUE_ACTUA --verificar
```

`--resumen` solo lee. `--escribir` crea los dos ficheros. `--verificar`
comprueba que la cuarentena y la copia filtrada no se solapan y que su suma es
el total de la copia. Sin `--desde-auditoria` se reproducen solo las 149 de
bote; con el, se anaden las clases de estado de jugadores.

Los motivos salen de `trabajo/botes_aritmetica.jsonl`, que a su vez sale de
`tools/aritmetica_botes.py`. Si se resuelve una mano, se vuelve a ejecutar el
aritmetico y despues este script: la cuarentena no se edita a mano.

## 5. Cuando una mano sale

Una mano sale de cuarentena cuando su bote deja de ser `STACK`, `NADA` o
`ACCION_AMBIGUA` en la traza, o cuando la auditoria deja de marcar la
desaparicion de un jugador. No sale porque se decida ignorarla: sale porque el
dato ya tiene una lectura unica.

## 6. Lo que NO hace

- No borra manos de la copia.
- No corrige ningun `amount` ni ningun `final_pot`.
- No cambia el manifiesto de la base canonica.
- No decide que manos son validas: solo las aparta mientras se revisan.
