# L_SEC ESTADO — no se calcula, y por qué

## Veredicto

**`L_sec` no se usa como métrica secundaria hasta que la reconstrucción
respete el estado de información del momento evaluado y la cobertura sea
completa y no sesgada.**

Mientras tanto, **`DEFAULT_ALPHA` no se calibra**. Eso no ha cambiado en
tres bloques, pero las razones se han ido precisando.

---

## 1. `equity_de_mano.py` funciona y mide algo real

Reconstruye la situación desde la mano histórica y devuelve `sit.equity`,
**sin partida y sin captura**, siguiendo la misma cadena que
`asistente_live`: rango preflop → blockers → refinado postflop →
`situation`.

Se pudo sin reconstruir el bote porque **`equity` no usa el bote**: en
`situation()`, `equity = wins + 0.5 * ties` sale de las cartas y del
rango, y el bote solo alimenta `pot_odds` y `spr`. Y la aritmética de las
apuestas, por cierto, **no converge**: 26 de 877 coinciden con
`final_pot`.

Comprobado por fuera, que es la única forma de que valga:

| | |
|---|---:|
| equity mediana donde el hero **gana** | **0,7680** |
| equity mediana donde el hero **pierde** | **0,4309** |

> Esa validación estaba **contaminada**: se hizo antes de cerrar las fugas
> de abajo, y la temporal afectaba a **la mitad de la muestra**. Por eso
> no cuenta. La que cuenta es la de §3, repetida después de cerrarlas.

---

## 2. Las tres fugas que había, y su tamaño

Las encontró `revision_2`, y las tres eran ciertas.

### 2.1 Corte temporal — la grave

`rango_del_rival` refinaba el rango del rival con **todas** sus acciones
postflop de la mano, incluidas las posteriores al momento en que el hero
decidió. Es mirar al futuro.

| | |
|---|---:|
| manos de la muestra con acciones posteriores usadas | **78 de 156 (50 %)** |
| jugadas de futuro por mano | media 1,7 · máximo 5 |
| manos donde el rival juega **después** del hero **en la misma calle** | **88 de 154** |

Ese último dato es el que importa: **cortar por calle no bastaba.** Hacía
falta el índice de la acción, no solo la calle.

### 2.2 Bloqueadores

Se metían las cartas de **todos** los jugadores del registro, que son las
que se revelan en el showdown, y el hero entraba dos veces.

| | |
|---|---:|
| cartas del hero contadas de más | **310** |
| cartas de terceros no conocidas en ese instante | **216** |

No se puede hacer mejor con estos datos: el registro guarda las cartas
**finales** de cada jugador y no dice **en qué momento** se revelaron.
Meter las de terceros sería inventar que se sabían.

### 2.3 Ajuste mezclado con validación

`main()` ajustaba el modelo con la ventana entera. Las **6 de las 6**
claves de `opp` cambian según se ajuste con la ventana o con calibración.

Un modelo que ha visto las 39 manos de validación no mide
generalización: **mide recuerdo**.

Y una de las dos revisiones dijo que `import hashlib` faltaba de
`calibrar.py` y que eso daría `NameError`. **No es cierto**: está en la
línea 28, y los 26 tests de ese módulo llaman `muestra()` — que lo usa —
en cada corrida. Una alarma que se comprueba con el test en vez de con la
lectura del fragmento.

---

## 3. La cobertura, y por qué el camino preflop no basta

`hand_evaluator.evaluate_batch` declara board de **3 a 5** cartas y sus
subsets son de 5, 6 y 7. Con board vacío no hay subset y `situation`
revienta. Eso dejaba fuera **96 de las 161** manos.

`tools/equity_preflop.py` lo resuelve **enumerando**: dos manos de 2
cartas contra los **C(48,5) = 1 712 304** sorteos de 5 comunitarias.
1,7 millones de evaluaciones, unos 13 s por par.

Comprobado contra valores publicados, con la banda de plausibilidad escrita
**antes** de mirar:

| mano | equity medida | manual |
|---|---:|---:|
| **AA vs KK** | **0,8195** | ~0,82 |
| KK vs QQ | 0,8193 | ~0,82 |
| AKs vs QhQd | 0,4324 | ~0,43 |

> Y esa comprobación **encontró un bug real**: la comparación estaba
> invertida y `AA vs KK` daba 0,18. Una herramienta de poker que devuelve
> la equity del otro es el peor tipo de herramienta posible, y solo se
> nota comparando con un número que ya se conoce.

### Y la cobertura tenía un sesgo que el camino preflop no arregla

| | antes | |
|---|---:|---|
| con equity | 58 de 156 (37 %) | |
| victorias cubiertas | 20 de 21 (95 %) | |
| derrotas cubiertas | 38 de 135 (28 %) | |
| tasa de victoria de lo cubierto | 34,5 % | |
| tasa de victoria de la muestra | 13,5 % | |

Medir sobre esas 58 es medir contra la base rate equivocada. Con el camino
preflop la cobertura **sí** es completa, y el sesgo **desaparece por
construcción**, no por suerte.

---

## 4. El veredicto medido: `L_sec` ya es calculable y **pierde**

Con el camino preflop y las tres fugas cerradas, `L_sec` por fin se puede
calcular. Y el resultado es el contrario del que hacía falta.

| | |
|---|---:|
| cobertura | **159 de 161 (98,8 %)** |
| sin equity | 2, y las dos con motivo escrito |
| reparto de la muestra | 20 ganan · 3 repartos · 138 pierden |
| cobertura de las victorias | 19 de 20 (95 %) |
| cobertura de los repartos | 3 de 3 (100 %) |
| cobertura de las derrotas | 137 de 138 (99 %) |

**El sesgo ha desaparecido.** Antes cubría el 95 % de las victorias y el
28 % de las derrotas; ahora cubre las tres clases igual. Eso no es suerte:
es que el hueco estaba entero en preflop, y el enumerador lo llena.

Y la equity **sigue ordenando**, después de todas las correcciones:

| | equity mediana |
|---|---:|
| donde el hero **gana** | **0,7673** (n = 19) |
| donde el hero **pierde** | **0,4056** (n = 137) |
| **diferencia** | **+0,3618** |

### Y aquí está el problema

| | |
|---|---:|
| Brier con la mediana de la equity | **0,1783** |
| Brier del predictor constante `p = 0,1289` | **0,1076** |
| referencia declarada para las 161, sin equity | 0,1110 |

**La equity pierde contra decir «el hero va a perder».** No por poco: un
66 % más de error.

Y no es un problema de cobertura ni de sesgo, que ya están resueltos. Es
arítmética: la muestra es de **86 % de derrotas**, y la equity mediana del
hero anda entre **0,41 y 0,77**, así que **sobreestima** su chance en
casi todos los casos. Un modelo que exagerase a la baja ganaría.

> **Conclusión: `L_sec`, tal como el plan la define, no es un criterio
> válido para seleccionar `alpha`.** No porque no se pueda calcular —ya se
> calcula— sino porque mediría al motor por debajo de una constante, y
> ordenar candidatos por eso es ordenar por un error sistemático.

Eso **no** significa que la equity del motor sea mala. Significa que
**`equity` y «ganar el bote» no son la misma magnitud**, y el Brier entre
ellas penaliza al motor por una diferencia de escala que no es culpa del
motor.

### Lo que haría falta, y no se decide aquí

| opción | qué cambia |
|---|---|
| comparar contra la **mediana de la propia equity** y no contra `y` | deja de ser Brier, y con 41 manos no tiene potencia |
| usar `equity` como **ranking** y no como probabilidad | mide si el motor ordena manos, que sí hace: +0,36 |
| medir el **error del EV** de la acción, como se propuso al principio | requiere etiqueta de optimalidad, que la base no tiene (§2.1) |
| **declarar que no hay secundaria admisible** | lo que se hace mientras tanto |

La cuarta es la que se aplica, y por eso `DEFAULT_ALPHA` sigue en `2.0`.

## 4.b Lo que sigue bloqueando

1. **Ninguna de las cuatro está decidida.** Elegir una es un bloque con su
   propio `.md`, porque cambia qué se le pide a la fase.
2. **La significación.** Con 41 manos de validación y un reparto del 12 %,
   un cambio del 2 % no es distinguible del ruido. Sigue dicho en §2.1.1.b.

## 5. La regla, mientras tanto

- `calibrar.py` **no acepta** ningún valor de `DEFAULT_ALPHA` mientras
  `L_sec` no sea evaluable. Bloqueo en el flujo de control, salida 2.
- `L_sec` devuelve `None` **con el motivo**, no un número aproximado.
- Los dos motivos para no calibrar son **independientes** (§8 de
  [`CALIBRACION_DEFAULT_ALPHA.md`](CALIBRACION_DEFAULT_ALPHA.md)): si se
  arregla uno, el otro sigue bloqueando.

## 6. Reproducir

```
python tools/equity_preflop.py --comprobar
python tools/equity_de_mano.py --mano H_0798
python tools/equity_de_mano.py --manos 20
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 2.0 5.0
```