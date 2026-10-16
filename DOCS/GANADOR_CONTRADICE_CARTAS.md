# `winner` y las cartas — el error, y lo que sí hay

## Lo primero: dos errores míos, y el primero casi se publica

### El primero: «el 61 % de las manos está mal»

Comprobé si `winner` coincide con las cartas y salió **354 incoherentes de
584**. A punto de documentarlo como que el recorder está roto.

**La comprobación era mía y estaba mal.** Comparaba las cartas de **todo**
el mundo con el board. Un jugador que folteó antes **no estaba en el
bote**, y sus cartas registradas no compiten con nadie.

`H_0002` lo deja claro:

```
board  Ah 8c Qc
winner UTG  <- NO tiene cartas: GANO POR FOLD
flop  BB x 1.0 | UTG b 6.0 | CO f 0.0 | BB f 0.0
```

Mi código decía «la mejor es MP, que tiene `6c4s`» y concluía que `UTG`
estaba mal. `UTG` ganó sin showdown porque todo el mundo fold, y **tenía
razón**.

### El segundo: «no hay muestra si no llegaron al showdown»

Corregido lo anterior, la función seguía retornando `True` **al llegar** a
la última calle, sin inspeccionar sus acciones. Un jugador que folteaba en
el river entraba como si hubiera llegado al showdown.

La regla correcta es más simple y más fuerte: **un fold es definitivo**. El
que folteó, salió del bote y no puede ganar. Da igual la calle.

Con el filtro así aparecieron 25 supuestos «repartos incompletos»… que
también eran de este mismo bug.

## El resultado, ya con las dos correcciones

| | ventana de 877 | base entera |
|---|---:|---:|
| con `winner` declarado | 348 | 487 |
| **verificables por cartas** | **261** | **354** |
| **coherentes** | **260** | **353** |
| **ganador equivocado** | **1** | **1** |
| reparto incompleto | 0 | 0 |
| ganado por fold, no comprobable | 11 | 31 |

### El único defecto real

**`H_0909`**: `winner` declara a `CO`, que hace **337 759**, y `BB` hace
**682 097** con el mismo board. El ganador declarado pierde la comparación.
No es un reparto incompleto: es un ganador que no ganó.

Una mano en 877. **No afecta a la muestra de `L_sec`**, que se queda en 160
utilizables.

## Lo que queda

`H_0909`, declarado y fuera del ajuste. Arreglarla es tocar `data/`, con
migración, hash y backup. Aquí no.

## La lección

> **Un instrumento que dice «el recorder está roto» cuando la verdad es
> «mi comprobación está rota» es peor que uno que dice «no sé».**

Porque el primero produce un número alto, y un número alto se lee como un
problema grande y ajeno. Aquí produjo **61 %**, y era un filtro de dos
líneas mal puesto.

Tres cosas que salieron de ahi:

1. **El caso que desmiente se busca primero.** `H_0002` —el ganador sin
  cartas, que ganó por fold— era el que rompía el argumento entero, y lo
  tenía delante en la salida del script.
2. **Un número grande pide una prueba de que el número es real**, no una
  explicación de por qué. Yo tenía la explicación y no la prueba.
3. **`revision_2` lo pidió y por eso se encontró.** Nadie lo habría visto
  solo. Lo que parece demasiado evidente para mirar es exactamente lo
  que hay que medir.

Y una regla que queda escrita para no volver a hacerlo:

> **Antes de comparar a un jugador con el board, comprobar que estaba en
> el bote cuando terminó la mano.** Si no, no está compitiendo y sus cartas
  no dicen nada.

## Reproducir

```
python tools/calibrar.py particion
python tools/auditar_muestra_lsec.py
```
