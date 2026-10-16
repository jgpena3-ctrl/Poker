# Los 42 defectos de la ventana, contra lo que se va a calibrar

**Estado:** vigente. Cierra `DOCS/FASE_D_PLAN.md` §0.2.
**Instrumento:** `python tools/auditar_defectos_vs_denominadores.py`
**Base:** `bf60aa8` (revisión manual en `H_1070`), ventana de 877 manos.

> El plan afirmaba que los defectos «no bloquean». Eso era una **hipótesis con
> un motivo escrito**, y este documento la convierte en hecho o en su
> refutación. Es una refutación parcial: **dos de las cuatro clases sí tocan
> el denominador**, y una de ellas en las 25 manos.

---

## 1. El método, y por qué el primero estaba mal

La primera versión de este script **quitaba** las manos defectuosas de la
ventana y comparaba los totales. Daba que las cuatro clases «cambian» todo.

**Eso es aritmética, no contaminación.** Quitar 25 manos baja los totales
aunque las 25 fueran perfectas. El instrumento estaba respondiendo a otra
pregunta.

La pregunta que importa es: **¿el DEFECTO cambia lo que la calibración ve de
ESA mano?** El método correcto es dejar la mano y **neutralizar el defecto**:

| clase | qué se neutraliza, y en el sitio que lo produce |
|---|---|
| `IMPORTE_SUBIDA` | el importe de la subida pasa a superar el suelo de la calle |
| `ACCION_FANTASMA` | se retiran las acciones de posiciones sin jugador |
| `WINNER_FOLDEO` | `winner` deja de incluir a quien foldeó |
| `SHOWDOWN_SIN_WINNER` | `winner` pasa a ser el que nombra `showdown.winner1` |

Y se comparan, sobre esa mano y solo ella: los eventos preflop con su
categoría, los jugadores que aparecen, las celdas de `cnt`/`opp` que aporta, y
las observaciones.

> Un instrumento que se demuestra no demuestra que mide lo que dice medir. Este es
> el segundo instrumento roto en este bloque; el primero fue
> `tools/quien_escribe.py`, cuatro veces.

---

## 2. La clasificación

Cero «no verificado», que es lo que pedía el encargo.

| clase | manos en la ventana | **que tocan** | **qué toca** |
|---|---:|---:|---|
| `IMPORTE_SUBIDA` | 25 | **25** | categoría de un evento, y celdas de `cnt`/`opp` |
| `ACCION_FANTASMA` | 2 | **2** | eventos, jugadores, observaciones |
| `WINNER_FOLDEO` | 3 | **0** | **no toca nada** |
| `SHOWDOWN_SIN_WINNER` | 12 | **0** | **no toca nada** |

---

## 3. `IMPORTE_SUBIDA`: toca el denominador, en las 25 manos

**Esta es la refutación.** El plan decía:

> *«`IMPORTE_SUBIDA` (25) y `SHOWDOWN_SIN_WINNER` (12) viven en campos —
> `amount`, `showdown`, `winner`— que **no entran** en `learn.preflop_events`
> ni en `player_ranges.p_matrix`.»*

Eso es **falso para `IMPORTE_SUBIDA`**, y medido mano a mano:

```
H_0049   ('Hachirama', 'no_raise', 'limp', ...)   ->   ('Hachirama', 'no_raise', 'open', ...)
H_0214   ('ComboHunter','no_raise', 'limp', ...)  ->   ('ComboHunter','no_raise', 'rol',  ...)
```

Una subida cuyo importe no supera la apuesta viva **se cuenta como `limp`**, y
con el importe corregido se cuenta como `open` o `rol`. El campo `amount` sí
entra en `classify_first_action`.

| desplazamiento | eventos |
|---|---:|
| `limp` → `open` | **24** |
| `limp` → `rol` | **1** |

Efecto sobre las categorías de la ventana:

| categoría | con el defecto | sin el defecto | delta |
|---|---:|---:|---:|
| `limp` | 366 | **341** | −25 |
| `open` | 438 | **462** | +24 |
| `rol` | 171 | **172** | +1 |

**25 eventos desplazados sobre 4561**, el **0,55 %**. Los denominadores
(`no_raise`, `facing_open`, `facing_3bet`) **no se mueven**: un `limp` y un
`open` cuentan en el mismo `no_raise`. Lo que se mueve es **la categoría**,
que es justo lo que `player_ranges.p_matrix` usa para `cnt`.

> Y no es una sutileza: 8 de esas 25 manos cambian **celdas de `cnt`**, que
> es literalmente lo que `DEFAULT_ALPHA` y `FLAT_PRIOR` ponderan. Es el
> parámetro que Fase D iba a mover primero.

**No se corrigen aquí.** Son 25 manos y son dato, y el dato es del
mantenedor. Lo que sale de esta medición es el número: la categoría `limp` de
la ventana está **sobreestimada en 25 eventos**, y `open` subestimada en 24.

---

## 4. `ACCION_FANTASMA`: toca, y es el jugador inventado de §0.1

Las dos manos, y el mecanismo a la vista:

```
H_0846   jugadores: ['BLKsoul', 'Jarduan', 'MP', 'sergio39']
                 ->  ['BLKsoul', 'Jarduan', 'sergio39']
         eventos 4 -> 3 (desaparece ('MP', 'no_raise', 'fold', ...))
         observaciones 5 -> 4

H_0519   observaciones 9 -> 8     (los eventos preflop no cambian)
```

`'MP'` **no es un jugador**: es una posición. Es el mismo defecto que produce
el `CO` de `profiles.json` (§0.1 del plan). Cada mano fantasma aporta un
jugador que no existe, y `Profiles.from_hands` le pone etiqueta.

Contaminación: **una entrada de jugador inventada**, y una etiqueta
`TIBURON` con `n: 0` y confianza `0.0` que va a `profile_ranges.json`.

---

## 5. Las dos que no tocan nada

`WINNER_FOLDEO` (3) y `SHOWDOWN_SIN_WINNER` (12): **ninguna mano cambia**, ni
en eventos, ni en jugadores, ni en celdas de `cnt`/`opp`, ni en
observaciones.

Es lo que el plan decía de ellas, y ahora está medido. Viven en `winner` y en
`showdown`, y **nada de lo que alimenta la calibración lee esos campos**:
`preflop_events` mira `cards` y las acciones; `p_matrix` se construye
exclusivamente de eventos con cartas conocidas.

> «No verificado» y «verificado que no toca» son cosas distintas, y la
> diferencia es que la segunda se puede volver a comprobar. Eso es lo que
> hace este documento.

---

## 6. Qué queda abierto

| | |
|---|---|
| **25 `IMPORTE_SUBIDA`** | mueven la categoría de `limp` a `open`/`rol`. **Decisión del mantenedor**: corregir el importe, o aceptar el desplazamiento ydeclararlo en el plan que `limp` está sobreestimada en 25 |
| **2 `ACCION_FANTASMA`** | es §0.1 del plan: corregir las manos Y cerrar la causa en `extract_hand` |
| 3 + 12 | no bloquean nada. Se pueden dejar como están |

Y una consecuencia para el orden de Fase D: el plan elegía `DEFAULT_ALPHA`
porque se medía en minutos. Sigue siendo la elección correcta, **pero el
baseline con el que se compara tiene que ser el de la ventana tal como está**,
no el de una ventana «limpia», y eso hay que decirlo antes de empezar: si se
limpian las 25 manos a mitad de la calibración, el baseline cambia y las
métricas de antes y de después dejan de ser comparables.

---

## 7. Cómo se reproduce

```bash
python tools/auditar_defectos_vs_denominadores.py
```

| | |
|---|---|
| ventana | 877 manos, `load_hands(reliable_only=True)` |
| baseline medido | 4561 eventos · 145 jugadores · 1161 con cartas · 9252 observaciones · `cnt` 22 claves · `opp` 6 claves |
| determinismo | no usa azar ni reloj. `ProfileRangeModel` y `Profiles` son deterministas sobre el mismo fichero |
| ruido | ninguno. Se comparan tuplas exactas, no flotantes |