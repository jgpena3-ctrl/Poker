# INC-002 — el filtro `p['active']` ensucia el campo `allin`

**Estado:** **ARREGLADO EN CÓDIGO**. Pendiente solo el registro histórico.
**Arreglo:** `recorder/recorder_live.py:1042`, una línea.
**Tests:** `recorder/test_inc002.py` (4 casos).
**Magnitud histórica:** 1 caso en 900 manos (0,7 %), y **efecto cero** sobre
las cifras de F7.2 (ver §5).
**Decisión de regrabar/migrar:** `DECISION_CM004.md` (sigue abierta).

---

## 1. Dónde

`recorder/recorder_live.py:1034`

```python
out = {k: v for k, v in self.hand.items() ...}
out['allin'] = [p['_id'] for p in self.hand['players']
                if p['_id'] in self._allin_players and p['active']]
```

El `and p['active']` es el filtro.

## 2. Qué significa `active` (y qué no)

`players[].active` **no** significa "no ha foldeado". Significa **"estaba
sentado con posición al empezar la mano"**:

`recorder/recorder_live.py:361`

```python
'active': bool(positions.get(pid)) and pid not in MANUAL_INACTIVE,
```

Se calcula en `start_hand()`, antes de que ocurra una sola acción. Un
jugador que se commitmenta y después foldea sigue teniendo `active: True`
para siempre.

**Consecuencia:** el filtro de la línea 1034 no excluye a nadie. Deja pasar
a los jugadores que se commitmentaron y luego se fueron.

## 3. Cómo se manifiesta

`H_0851`:

```
preflop  UTG r 3.5 · MP f · CO f · BTN c 2.5 · SB f · BB f
flop     UTG x · BTN b 4.0 · UTG f        <-- foldea
allin    ['UTG']                          <-- y sigue aqui
```

UTG se compromete en el preflop, checkea en el flop, ve una apuesta y
foldea. `allin` lo declara comprometido porque `active` es `True`.

Efecto: el clasificador cree que UTG no puede actuar cuando sí se fue, y lo
cuenta como bloqueado en un punto donde ya no está en la mesa.

## 4. Magnitud

Medido sobre la ventana fiable (900 manos), con
`tools/auditar_solapamiento_multiway.py`:

| | |
|---|---|
| entradas en `allin` | 138 |
| de las cuales con un fold posterior | **1** |
| | **0,7 %** |

Es poco. No es cero, y mientras no se arregle, el cruce
`folds_hasta` × `no_puede_actuar` **no es 0 por construcción**: es 0 más
este. Está declarado como tal en `CONTRATO_F72A.md` §4.3.

## 5. Efecto real sobre las cifras: CERO

Medido sobre la ventana fiable completa, el único registro defectuoso es
`H_0851`, y **no aporta ningún punto de decisión**:

- su hero es `CO`, que **foldeó en el preflop**;
- el resto de sus calles no tienen acciones;
- por tanto `puntos_decision_mano(H_0851) == []`.

Un registro corrupto que no llega al conteo no puede sesgarlo. El 0,7 %
sigue siendo real como tasa de defecto del recorder, pero **su impacto en
F7.2 es nulo**.

Esto no es un argumento para dejar el defecto: el recorder sigue
produciendo basura y, en otra mano, ese error sí habría caído en el
numerador. Lo que dice es que la decisión de regrabar **no se sostiene en
esta incidencia**.

## 6. El arreglo aplicado

`recorder/recorder_live.py:1042`

```python
out['allin'] = [p['_id'] for p in self.hand['players']
                if p['_id'] in self._allin_players and p['active']
                and p['pos'] not in self._folded_positions]
```

La condición `and p['pos'] not in self._folded_positions` es **la misma que
ya usaba el bloque de al lado** (línea 1022, `all_still_in`) para decidir
quién sigue en la mano. No es una regla nueva: es aplicar la que el
recorder ya tenía y no usaba en este sitio.

**Solo hacia adelante.** Las manos ya grabadas no se tocan: `H_0851` sigue
en el fichero con su `allin` erróneo, y por eso
`multiway.contradiccion_allin_fold()` tiene que seguir detectándolo y
marcando el punto como `DESCONOCIDO`.

### Cómo se verifica

`recorder/test_inc002.py` comprueba el filtro leyendo el AST del recorder,
no simulando un recorder entero: el resto de `_allin_players`,
`_folded_positions` y `players[]` ya tienen sus propios tests. Tres
garantías:

1. el predicado menciona `_folded_positions`;
2. **no** se ha perdido ninguna de las otras tres condiciones (`active`,
   `_allin_players`, proyección a `_id`);
3. un compromiso sin fold sigue saliendo, y con fold deja de salir — que es
   el requisito de no arreglar una cosa rompiendo la otra.

## 7. Lo que queda abierto

Solo una cosa, y **no depende de CM-004**: decidir qué hacer con el
registro histórico. Con el impacto medido en cero y siendo 1 de 138, la
opción barato es **declararlo** — el mecanismo reversible ya está en
`EXCLUSION_CM004.md` §6 — en lugar de regrabar una mano por 0,7 % de ruido
que no sesga ninguna cifra.

## 8. Lo que este defecto NO invalida

- El contrato F7.2.a, que ya declara el cruce como "0 más datos malos".
- La cota de puntos desconocidos: es otra causa (el campo ausente en las 73
  manos antiguas), no esta.
- El resto de la ventana: un registro defectuoso no describe el recorder
  entero.
