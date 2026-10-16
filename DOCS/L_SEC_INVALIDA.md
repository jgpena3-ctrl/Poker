# L_SEC — no es aplicable a Fase D, y el motivo NO era el que se pensaba

## La conclusión que se retiró

El bloque anterior escribió:

> `L_sec` pierde contra una constante (0,1783 contra 0,1076). O sea que
> `L_sec` no es un criterio válido para seleccionar `alpha`.

El **número era correcto**. La **causa era falsa**, y lo que faltaba era una
medición que no se había hecho: **por qué** pierde.

Y resulta que pierde por una razón que no la invalida.

## Lo que pasa al separar los dos métodos

| | n | Brier de la equity | constante óptima | |
|---|---:|---:|---:|---|
| **observable** — postflop, contra el rango estimado | 60 | **0,1962** | 0,2124 | **GANA** |
| **retrospectiva** — preflop, contra la mano real del rival | 99 | 0,1674 | **0,0000** | pierde |
| **las dos juntas** — lo que se midió antes | 159 | 0,1783 | 0,1076 | pierde |

La retrospectiva tiene **0 victorias en 99 manos**. Una constante que
predice «el hero pierde» saca **0,0000** en ese subconjunto por
construcción, y cualquier predicción positiva es peor. No es que la equity
sea mala ahí: es que **ese subconjunto no tiene nada que predecir**.

Y lo observable es lo contrario: **la equity gana al trivial**, 0,1962
contra 0,2124, y ordena con **+0,3300** (0,7673 donde gana, 0,4373 donde
pierde).

> ### Conclusión corregida
>
> **`L_sec` no está refutada. Está incompleta.**
>
> Lo que falla no es la métrica: es que solo se puede calcular en el
> **38 %** de la muestra, y en ese 38 % **funciona**.

## Por qué solo el 38 %

Porque **el motor no tiene ningún camino de equity preflop**. Medido, los
dos intentos:

| lo que se intentó | por qué falla |
|---|---|
| `situation(hero, [], ...)` | `evaluate_batch` declara board de **3 a 5** cartas |
| `decision.runout_equity(hero, [], ...)` | `_villain_arrays` llama a `evaluate_batch` con 0 cartas y pide `_SUBSETS[2]` |

`_SUBSETS` tiene `{5, 6, 7}`. **Cualquier** camino que termine en
`evaluate_batch` con menos de 5 cartas revienta, y los dos lo hacen.

Lo único que hay para preflop es la enumeración contra las cartas **reales**
del rival, y eso es **retrospectiva**: al decidir, esas cartas no se
conocían.

Que no sea lo mismo lo demuestra el resultado: si la enumeraciónretropectiva
midiera la misma magnitud que la observable, ambas darían parecido, y no.

## La corrección de la etiqueta, que fue un error mío

Este bloque ó si `winner` coincide con las cartas ytpó **32
incoherencias**. No las hay.

La comprobación comparaba las cartas de **todo** el mundo con el board. Un
jugador que folteó antes **no estaba en el bote**, y sus cartas registradas
no compiten.

El caso que lo demuestra es `H_0002`:

```
board Ah 8c Qc
winner UTG
flop BB x 1.0 | UTG b 6.0 | CO f 0.0 | BB f 0.0
```

`UTG` **no tiene cartas registradas** porque ganó por fold. Mi comprobación
decía «el mejor es MP, que tiene `6c4s`» y concluía que `UTG` estaba mal.
`UTG` estaba bien, y `MP` había folderado preflop.

Con el criterio correcto —solo los que no foltearon antes de la última
calle con acciones— el número es:

| | manos |
|---|---:|
| ventana de 877, verificables por cartas | 261 |
| **coherentes** | **261** |
| **incoherentes** | **0** |
| ganador por fold, sin cartas: **no comprobable** | 87 |

Y en la **base entera**: 369 verificables, 344 coherentes, **25
incoherentes, todos repartos incompletos y ninguno con ganador
equivocado**.

Detalle en [`GANADOR_CONTRADICE_CARTAS.md`](GANADOR_CONTRADICE_CARTAS.md),
que empieza contando el error este.

## Lo que queda

| bloque | por qué |
|---|---|
| **motor: un camino de equity preflop** | sin eso, `L_sec` cubre el 38 % y Fase D no puede decidir |
| **una métrica que no dependa del 86 % de derrotas** | con esta muestra la constante óptima es muy fuerte |
| **`data/`: los 25 repartos incompletos** | declarados, fuera del ajuste |

El primero bloquea. Los otros dos solo importan cuando el primero esté.

## La regla, mientras tanto

- `calibrar.py` **no acepta** ningún valor de `DEFAULT_ALPHA`: sin
 secundaria evaluable, salida 2.
- `equity_de_mano.py` marca cada equity como `observable` o no, y ningún
 agregado mezcla las dos.
- La retrospectiva se conserva para auditar el evaluador y estudiar manos.
 **No** es la equity de una decisión.

## Reproducir

```
python tools/equity_preflop.py --comprobar
python tools/equity_de_mano.py --mano H_0798
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 2.0 5.0
```
