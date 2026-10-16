# CALIBRACION DE `DEFAULT_ALPHA` — NO SE CALIBRA

## Veredicto

**`DEFAULT_ALPHA` se queda en `2.0`. No se calibra.**

No porque el parametro no tenga recorrido, sino porque **no queda ningun
criterio admisible para cambiarlo**: la metrica primaria no puede
distinguir candidatos, y la secundaria no se puede calcular.

Eso se decidio midiendo, no suponiendo. Se cayo en el guardian que wrote
`tools/calibrar.py` precisamente para esto, y el guardian fired.

---

## 1. Lo que se ejecuto

```
python tools/calibrar.py particion --escribir
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 1.5 2.0 2.5 3.0 5.0
```

| | |
|---|---|
| ventana | 877 manos (`load_hands(reliable_only=True)`) |
| particion | versionada en [`PARTICION_FASE_D.md`](PARTICION_FASE_D.md) |
| calibracion | 117 manos |
| validacion | 39 manos |
| eventos con cartas conocidas | 295 |

> `limp` esta sobreestimada en 25 eventos de 4561 (0,55 %). Las cifras de
> abajo **no son cifras limpias** (§5 de `FASE_D_PLAN.md`).

## 2. Lo que dio

| `alpha` | `L_prim` | mejora sobre 2.0 |
|---:|---:|---:|
| 0,5 | 0,176407 | +64,03 % |
| 1,0 | 0,305947 | +37,62 % |
| 1,5 | 0,407947 | +16,83 % |
| **2,0** | **0,490495** | — (referencia) |
| 2,5 | 0,559902 | −14,15 % |
| 3,0 | 0,619347 | −26,27 % |
| 5,0 | 0,792813 | −61,64 % |

Y en los extremos, para ver que la metrica no esta ciega:

```
L_prim(1.0) = 0.305947      L_prim(9.0) = 0.987361
```

La metrica **si** cambia cuando el parametro cambia. Ese era el primer
riesgo —una metrica que no ve su parametro produce un numero sin
origen— y esta descartado.

## 3. Por eso el resultado no es un resultado

La curva es **estrictamente monotonica**: `L_prim` sube con `alpha` sin una
sola excepcion entre 0,5 y 5,0, y tambien entre 0,1 y 100.

Una metrica que crece siempre hacia el mismo lado **no esta eligiendo**. Y
la razon se puede escribir:

```
p(alpha) = (cnt + alpha*prior) / (opp + alpha)
```

`L_prim` suma `log p` **solo sobre celdas observadas**, y toda celda
observada tiene `cnt >= 1`. Sobre esas celdas, el termino del prior es
**pura dilucion**: subir `alpha` baja `p`, baja `log p`, sube la perdida.

Medido celda a celda sobre las 262 celdas observadas de la particion:

| | celdas |
|---|---:|
| `dp/dalpha < 0` — subir `alpha` **baja** `p`, empuja la perdida **arriba** | **229** |
| `dp/dalpha >= 0` — empujan al reves | **33** |

Asi que la monotonia **no es una garantia matematica**, y conviene decirlo
con precision: 33 celdas la resistsen y no llegan a dar la vuelta al
agregado. Lo que si es cierto es que lo que `L_prim` mide, en esta muestra
y con esta formula, es **cuanto se diluyo el prior**, no que modelo
reparte mejor.

Y el "ganador" que sale de esa tabla, `alpha = 0,5`, dice exactamente una
cosa: *mezcla menos*. No dice nada sobre el poker. Elegirlo seria reportar
la respuesta trivial como si fuera un hallazgo.

## 4. La secundaria no se puede calcular

`L_sec` es el Brier de `sit.equity` sobre las 39 manos de validacion.
Devuelve `None`, y el motivo esta escrito en el codigo: **no hay API que
devuelva la equity del motor en un punto de decision historico**.
`asistente_live` construye la situacion completa; no expone la equity
suelta.

Sin secundaria no hay forma de distinguir *mejor ajuste* de *sobreajuste*,
que es justo lo que §2.1 declara que `L_prim` no puede hacer.

Y aunque se pudiera, ya se medirio que tiene que ganarle a un predictor
constante: `p = 0,199` saca **0,1592**, y el reparto es de **31 victorias
sobre 156 manos** (§2.1.1.b). Con 39 manos de validacion, un cambio del 2 %
no es distinguible del ruido.

## 5. El guardián, y por que es codigo

`tools/calibrar.py` no devuelve un ganador cuando la curva es monotonica.
Sale con codigo **2** y escribe el motivo:

```
GUARDIAN DE MONOTONIA: LA CURVA ES MONOTONA.
...
VEREDICTO: DEFAULT_ALPHA NO SE CALIBRA.
```

Es una condicion de salida, no un comentario. Un comentario se puede
saltar sin que nada se entere; una condicion de salida rompe el comando.

## 6. Un hallazgo lateral que no es de `alpha`

`p = 0` en **1 991 de 22 308 celdas** del grid (8,9 %) — y **tambien con
`alpha = 20`**. No es falta de regularizacion: la tabla de priors tiene
**127 ceros de 169 celdas**, y donde el prior es 0 y no hay conteo,
`p = 0` para todos los valores de `alpha`.

O sea: **`alpha` no es la palanca que arregla los ceros.** Son dos cosas
distintas y este bloque no las mezcla. Queda anotado para cuando toque, y
no se toca ahora.

## 7. Que reabriria esto

`DEFAULT_ALPHA` se puede recalibrar cuando **una** de estas sea cierta:

1. **Existe API para la equity en un punto de decision historico.** Con eso
   `L_sec` sale, y P1/P4/P5 dejan de ser "no evaluable".
2. **La metrica primaria cambia de forma.** Hace falta una que scoree tambien
   las celdas **no observadas** —las que hoy son invisibles para `L_prim`— o
   una que mida en particion de validacion.

Mientras no: `2.0`, que es el valor que lleva desde el principio y el unico
que tiene una justificacion escrita (§1.2).

## 8. Reproducir

```
python tools/auditar_importe_subida.py      # la decision A/B de §5
python tools/auditar_muestra_lsec.py        # la muestra y la referencia trivial
python tools/calibrar.py particion          # la particion, sin escribir
python tools/calibrar.py --param DEFAULT_ALPHA --valores 0.5 1.0 1.5 2.0 2.5 3.0 5.0
```

Ninguno de los dos ultimos escribe nada. `particion --escribir` es lo
unico que toca disco, y escribe un documento, no datos.