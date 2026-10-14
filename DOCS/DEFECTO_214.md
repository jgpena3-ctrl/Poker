# DEFECTO 214 — el campo `winner` no es fiable

**Estado:** medido, sin corregir. **Base completa `e314f74`: 214. Rango
H_0001..H_1014: 11.**
**Instrumento:** `tools/auditar_rango.py`, clase `WINNER_FOLDEO`.
**Consecuencia para Fase D:** **no bloquea el motor, pero el campo no debe
consumirse.**

---

## 1. Qué es

`winner` incluye a un jugador que **foldeó** en algún momento de la mano. De
las 1280 manos, **214** la tienen.

Y no son 214 casos raros. Comparando manos con el mismo patrón —todos foldean
hasta las ciegas, 77 de ellas—:

| mano | `winner` grabado |
|---|---|
| `H_0345` | `hero(SB)` + `p1(BB)` — las dos ciegas |
| `H_1050` | `hero(BB)` + `p5(SB)` — las dos ciegas |
| `H_0360`, `H_0365`, `H_0400`, `H_0473`… | **solo** el BB |
| `H_0881`, `H_1006`, `H_1087` | **las seis** posiciones |

El campo se escribe en un punto que no siempre es el final de la mano. Con
esa tabla, **`winner` no es un campo del que se pueda fiar nadie sin
reconstruirlo**.

## 2. Identificadores (rango H_0001..H_1014)

```
H_0028, H_0505, H_0602, H_0748, H_0864, H_0879, H_0881, H_0882, H_0893, H_0895, H_0983
```

Clases relacionadas en el mismo rango:

- **`SHOWDOWN_SIN_WINNER` — 15**: `showdown` nombra a quien no ganó.
  ```
  H_0374, H_0376, H_0409, H_0447, H_0511, H_0744, H_0751, H_0759, H_0786, H_0833
  H_0911, H_0915, H_0932, H_0957, H_0972
  ```
- **`WINNER_VACIO` — 1**: `H_0086`.

Entre las tres, **27 de 991** (2,7 %) tienen algo que no cuadrar en el
resultado de la mano.

## 3. Veredicto: **grabación**, y de alcance estructural

No es poker ni un defecto de 27 manos: es un campo que el recorder escribe en
el momento equivocado. Se corrige en el recorder, hacia adelante, y **el
histórico no se reescribe**: sería reconstruir el final de 214 manos sin
original, justo lo que CM-004 ya prohibía.

## 4. Por qué en el bloque anterior se revirtió `H_0969` y `H_0970`

Ambas se corrigieron a mano. Se revirtieron por dos razones, y las dos se
sostienen con la cifra de 214:

1. **Corregir 1 de 214 no dice nada de las otras 213**, y deja la base con un
   campo «arreglado» en dos manos y roto en doscientas.
2. En `H_0970` la corrección **empeoraba** la mano: quitaba al BB de un bote
   que sí había ganado.

## 5. Consecuencia para Fase D

**El motor no consume `winner`.** `tools/medir_multiway.py` lo lee, pero para
informar; ninguna decisión del motor depende de él. Por tanto:

> **No bloquea la calibración.** Pero cualquier análisis de resultados que
> use `winner` —rendimiento por mano, manos ganadas, equity realizado— está
> calculando sobre un campo que miente en el 17 % de la base.

Si Fase D necesita resultados observados, hay dos caminos honestos:

- usar `showdown.winner1` cuando existe, que sí parece coherente con `winner`
  (es lo que la clase `SHOWDOWN_SIN_WINNER` mide), o
- declarar que la base no tiene campo de resultado fiable y no medirlo.

---

## 6. Nota sobre la cifra

214 es una de las dos cifras que **sí se reproducen** con el detector
permanente contra `e314f74` (`auditar_rango.py --validar`). La otra es el 652
de `DEFECTO_652.md`, que también se reproduce pero **no significa lo que se
creía**.