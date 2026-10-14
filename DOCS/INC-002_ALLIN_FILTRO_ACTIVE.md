# INC-002 — el filtro `p['active']` ensucia el campo `allin`

**Estado:** abierto. **Arreglo pendiente de la decisión CM-004.**
**Magnitud medida:** 1 caso en 900 manos (0,7 %).
**No se arregla aquí.** Es un defecto del recorder, y el recorder se toca
al decidir si la base de datos se regraba o se migra.

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

## 5. Por qué no se arregla ahora

Porque no es un bug de lógica, es un bug de **procedencia**: la información
correcta (`_folded_positions`) existe en el recorder y no se usa al volcar.
Arreglarlo tiene dos costes distintos:

- **Arreglar el código** de aquí en adelante es de una línea.
- **Reparar las manos ya grabadas** exige volver a escribirlas, y eso es
  exactamente la decisión de CM-004.

Hacer la primera sin la segunda dejaría la base con dos reglas distintas
según la antigüedad de cada mano. Peor que hoy.

## 6. Qué haría falta para cerrarlo

1. Que la línea 1034 filtre también por no-foldeado:

   ```python
   and p['pos'] not in self._folded_positions
   ```

2. Reparar o descartar los registros ya afectados. Con 1 caso en 900, la
   opción barato es **declararlos** en vez de regrabar: el coste de
   regrabar una mano por 0,7 % de ruido no está justificado.
3. Lo decide CM-004, no este documento.

## 7. Lo que este defecto NO invalida

- El contrato F7.2.a, que ya declara el cruce como "0 más datos malos".
- La cota de 38 puntos desconocidos: es otra causa (el campo ausente en
  las 73 manos antiguas), no esta.
- El resto de las 899 manos: un registro defectuoso no describe el
  recorder entero.