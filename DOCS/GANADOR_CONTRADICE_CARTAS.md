# `winner` y las cartas — el error, y lo que sí hay

## Lo primero: un error mío que casi se publica

Este bloque comprobó si `winner` coincide con las cartas y el primer
resultado fue **«354 manos incoherentes de 584, el 61 %»**, y a punto de
publicarse como defecto de la base.

Era una comprobación mala.

Comparaba las cartas de **todos** los jugadores con el board. Pero un
jugador que folteó antes **no estaba en el bote**, y sus cartas registradas
—que el recorder guarda igual— no compiten con nadie.

`H_0002` lo deja claro:

```
board Ah 8c Qc
winner UTG <- no tiene cartas: GANO POR FOLD
flop BB x 1.0 | UTG b 6.0 | CO f 0.0 | BB f 0.0
```

Mi código decía: «la mejor mano es de MP, que tiene `6c4s`», y concluía
que `winner` estaba mal. `UTG` ganó el bote sin showdown porque todo el mundo
fold, y **tenía razón**. `MP` había folderado preflop.

> **El instrumento estaba mal y habría publicado un defecto de 61 % que no
> existe.** Un número alto no es evidencia de un problema grande: a veces es
> evidencia de una pregunta mal hecha.

El criterio correcto: **solo los jugadores que no foltearon antes de la
última calle con acciones**.

## Lo que sí hay, con el criterio correcto

### Ventana de 877

| | manos |
|---|---:|
| con `winner` declarado | 348 |
| **verificables por cartas** | **261** |
| **coherentes** | **261** |
| **incoherentes** | **0** |
| ganador por fold, sin cartas: no comprobable | 87 |

**Cero ganadores equivocados.** `winner` es fiable cuando se puede
comprobar.

### Base entera

| | manos |
|---|---:|
| con `winner` declarado | 487 |
| verificables por cartas | 369 |
| coherentes | 344 |
| **incoherentes** | **25 (6,8 %)** |
| de ellos, **ganador equivocado** | **0** |
| de ellos, **reparto incompleto** | **25** |
| no comprobables | 118 |

### El único defecto real: repartos incompletos

En esas 25 manos los ganadores declarados **sí hacen la mejor mano**, pero
hay un tercero que hace exactamente lo mismo y no está declarado. O sea:
el reparto del bote no se registró entero.

Es el mismo tipo de cosa que los 25 repartos incompletos que el mantenedor ya
corrigió a mano en `H_1030..H_1070` (`CANAL_MANUAL_CERRADO.md` §4), y que
siguen en las manos anteriores.

**No se corrige aquí**: es tocar `data/`, con migración, hash y backup.

En la ventana de 877 hay **0**, así que **no afecta a la muestra de
`L_sec`**.

## Por qué importa igual

1. **`winner` no es comprobable en el 20 % de la ventana** (87 de 348). Quien
 ganó por fold y no tiene cartas no se puede verificar con las cartas.
 No es un defecto, es un límite del dato, y hay que saberlo.
2. **La etiqueta de `L_sec` se acepta sin comprobar en esas 87.** Es la
 única fuente, y se declara como tal.
3. **El método que sí funciona**: exigir, cuando es comprobable, que
 `winner` coincida exactamente con las mejores manos evaluadas. Con eso
 salen **0 incoherentes** en la ventana y la muestra queda en **161
 utilizables, 20 victorias, 3 repartos**.

## Reproducir

```
python tools/calibrar.py particion
python tools/auditar_muestra_lsec.py
```

El desglose del auditor cuenta `INCOHERENTE: reparto incompleto` y
`ganador por fold, no comprobable`. Si los dos se mueven, hay que rehacer
esto.
