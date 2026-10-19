# APUESTAS DIFICILES — PARA REVISAR EN LAS GRABACIONES

Las que **no** se pueden decidir con la mecánica del poker sola. Cada una
necesita ver la grabación original.

Criterio usado para NO tocar una acción:
- `ya` = lo que el jugador tenía puesto en la calle
- `viva` = la apuesta viva de la calle
- `importe` = lo que dice el fichero

| grupo | nº | por qué no se puede decidir |
|---|---:|---|
| **all-in** | 39 | el grabador guarda el stack entero |
| **bet con fichas previas** | 39 | `importe` puede ser el total o el incremento |
| **call raro** | 54 | no encaja en ninguna regla |
| **reraise ambiguo** | 12 | `importe == viva + ya`, dos lecturas posibles |
| **call-raise** | 0单独 | subida que sube justo lo que falta |

---

## 1. BET CON FICHAS PREVIAS — 39 (todas del SB)

```
H_0032 | preflop | SB | b 5.0 | ya=0.50 | viva=1.00
H_0042 | preflop | SB | b 5.0 | ya=0.50 | viva=1.00
H_0066 | preflop | SB | b 3.0 | ya=0.50 | viva=1.00
H_0095 | preflop | SB | b 6.0 | ya=0.50 | viva=1.00
H_0100 | preflop | SB | b 3.0 | ya=0.50 | viva=1.00
H_0113 | preflop | SB | b 3.0 | ya=0.50 | viva=1.00
H_0032 | preflop | SB | b 5.0 | ya=0.50 | viva=1.00   (repetida)
```

**Todas son el SB.** Postea 0.5 de ciega y acto seguido "apuesta". Dos
lecturas, y no hay forma de distinguirlas sin el vídeo:

| lectura | SB queda con | es un |
|---|---|---|
| `b 5.0` es el **total** en la calle | 5.0 | bet a 5.0 |
| `b 5.0` es el **incremento** | 5.5 | bet a 5.5 |

**[D]** Si en la grabación el SB pone una ficha de 5.0 en total, es la
primera. Si pone 5.0 *además* de la ciega, es la segunda.

** Pregunta clave para la grabación:** ¿cuántas fichas pone el SB en total?

---

## 2. RERAISE AMBIGUO — 12 (todas del BB)

```
H_0011 | preflop | BB | r 2.0 | ya=1.00 | viva=1.00
H_0053 | preflop | BB | r 2.0 | ya=1.00 | viva=1.00
H_0102 | preflop | BB | r 5.0 | ya=1.00 | viva=4.00
H_0135 | preflop | BB | r 9.0 | ya=1.00 | viva=8.00
H_0147 | preflop | BB | r 2.0 | ya=1.00 | viva=1.00
H_0391 | preflop | BB | r 2.0 | ya=1.00 | viva=1.00
```

El BB tiene 1.0 de ciega y sube a un importe que cumple `viva + ya`.

| lectura | BB queda con |
|---|---|
| `r 5.0` es el **total** | 5.0 |
| `r 5.0` es el **incremento** | 6.0 |

** Pregunta clave para la grabación:** la apuesta visible en la mesa tras la
subida del BB.

**[P]** Ojo con `H_0102` y `H_0135`: son las dos en las que `viva` es
distinto de 1.0, o sea que hubo una subida previa real. Son las más
interesantes para estudiar.

---

## 3. CALL RARO — 54

No encaja en ninguna regla: ni es el total, ni es lo que falta, ni es lo
primero de la calle.

```
H_0026 | preflop | SB | c 1.0 | ya=0.50 | viva=6.00
H_0026 | preflop | SB | c 5.0 | ya=0.50 | viva=6.00
H_0039 | preflop | BTN | c 6.0 | ya=6.00 | viva=11.00
H_0093 | preflop | BB | c 0.0 | ya=1.00 | viva=3.00
H_0093 | flop   | BB | c 3.1 | ya=8.10 | viva=8.10
H_0110 | river  | SB | c 0.0 | ya=12.00 | viva=24.00
```

Tres subgrupos distintos:

**a) Doble call del mismo jugador** (`H_0026`): el SB tiene `c 1.0` y luego
`c 5.0` con la misma viva de 6.0. Solo uno de los dos puede ser real.

**b) Call de 0.0 con fichas puestas** (`H_0093` preflop, `H_0110` river): el
jugador tiene fichas dentro y "apuesta" 0.0. O es un check mal grabado como
call, o le falta un paso intermedio.

**c) Call que no iguala** (`H_0039`): BTN tiene 6.0, la viva es 11.0, y
`call` 6.0. No es ni una cosa ni la otra.

** Pregunta clave para la grabación:** qué fichas mete el jugador y en qué
turno.

---

## 4. ALL-IN — 39

```
H_0034 | preflop | SB | r 88.6 | ya=0.50 | viva=1.00
H_0074 | preflop | UTG | r 38.2 | ya=3.00 | viva=9.00
H_0080 | preflop | SB | r 12.5 | ya=0.50 | viva=2.50
H_0084 | flop   | SB | r 36.8 | ya=0.00 | viva=7.10
H_0127 | preflop | CO | r 8.4  | ya=1.00 | viva=6.00
H_0196 | preflop | UTG | r 17.0 | ya=0.00 | viva=1.00
```

Tu pauta 3 dice que el all-in se guarda como la cantidad absoluta del jugador
en la calle, así que **no se tocan**. Pero hay una cosa que no cuadra y que
conviene mirar en la grabación:

**[D]** En `H_0194` el `MP b 121.0` del flop tiene stack 128.8, y después un
`b 6.0` en el turn. 5.0 + 121.0 + 6.0 = 132.0, **más que el stack**. Si el
all-in fuera de 126 (lo que le quedaba), no podría volver a apostar en el
turn. Alguna de las dos acciones está mal.

** Pregunta clave para la grabación:** si el MP se fue all-in en el flop o
siguió jugando.

---

## CÓMO USAR ESTE DOCUMENTO

1. Abrir una grabación de cada grupo.
2. Contar las fichas del jugador en la mesa.
3. Anotar la lectura correcta al lado del `hand_id`.
4. Pasarme la lista y aplico la corrección en bloque.

[Documento de trabajo. La base canónica no se toca.]