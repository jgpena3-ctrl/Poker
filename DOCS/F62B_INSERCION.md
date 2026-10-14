# F6.2.b — Mini-inventario del punto de inserción

Las cuatro preguntas de revision_1 §5, respondidas **midiendo**, no suponiendo.
Este documento es la especificación de F6.2.b.

## 1. ¿Qué hay en `_recomendacion_para` línea 1057? ¿Es el bloque sombra correcto?

Sí. Bloque medido:

```python
L1051  _shadow_ctx = None
L1052  if getattr(self, 'shadow', True):
L1053      jer = self._jerarquia(hero_pid, state)
L1057      if jer and jer.get('main'):
L1058          _reg = shadow_equity(sit.equity, board, street, jer,
L1059                               equity_source=villain_pos)
L1060          _shadow_ctx = (jer, _reg)
...
L1068  evs.spot = rp.spot
L1070  action = rules_select_best(evs, rp)[0]     <- LA DECISIÓN
L1073  if _shadow_ctx is not None:
L1075      self._shadow_log().append(shadow_record(
L1078          hierarchy=_shadow_ctx[0], shadow=_shadow_ctx[1], ...
L1080          action_production=action))
```

Tres consecuencias:

- **El productor va entre L1059 y L1060.** `_reg` es el dict que acabará en
  `shadow_record(shadow=...)`, así que las cuatro claves de `equity_main` se
  escriben sobre `_reg` ahí.
- **Queda ANTES de la decisión (L1070).** Estructuralmente no puede alterarla:
  la decisión se toma en `rules_select_best(evs, rp)`, y el productor solo
  escribe en `_reg`, que no es ni `evs` ni `rp`.
- **`shadow_equity()` se llama UNA sola vez, en L1058, antes.** Confirmado por
  lectura: no hay una llamada posterior que sobrescriba los valores por
  defecto. El riesgo que señalaba revision_2 no se materializa, pero el
  orden correcto lo evita por construcción.

## 2. ¿Qué rango construye `asistente_live` para `villain_pos`? ¿Se puede replicar?

Sí, y el patrón está en `L974-990`:

```python
spot, action = _preflop_spot(self.rec.hand, villain_pos)
reach = self.models.range_model.prob_vec(
    perfil, spot, action, pos=villain_pos,
    villain_pos=_pf_rival_pos(self.rec.hand, villain_pos, spot))
rs = RangeState(reach=reach)
rs.set_known_cards(list(hero) + list(board) + list(blockers))
for st_v, facing, act, board_str in _villain_postflop_actions(self.rec.hand, villain_pos):
    ...
    rs.update(postflop.prob_vec(perfil, st_v, facing, board_v, act))
```

Verificado que existen todos los helpers necesarios:

| helper | existe | para qué |
|---|---|---|
| `_perfil_for(villain, state)` | sí | perfil PEZ/TIBURON del rival |
| `_preflop_spot(hand, pos)` | sí | (spot, action) preflop |
| `_pf_rival_pos(hand, pos, spot)` | sí | rival contra el que mira la tabla |
| `_villain_postflop_actions(hand, pos)` | sí | refinado por calle |
| `RangeState` | importado | contenedor |

La única diferencia para `jer['main']` es de dónde salen `perfil` y `pos`:
`_perfil_for` toma un **pid**, y `jer['main']` es una **posición**. Ese es el
único trabajo real que hay que hacer.

## 3. ¿Qué pasa si `jer['main']` NO es `villain_pos`?

Es el caso normal, y es exactamente lo que `equity_main` existe para medir:
la equity de producción se calcula contra `villain_pos`, la del sombra contra
el rival principal de la jerarquía. Cuando coinciden, `equity_main` debe dar
prácticamente lo mismo; cuando difieren, la diferencia es la medición
interesante.

`shadow_equity` ya separa los dos conceptos con `equity_source` /
`equity_source_is_main`, así que el hueco está covered desde el punto de
vista del registro.

## 4. ¿Qué pasa si `jer['main']` está folded?

No puede estarlo, pero se comprueba igual.

`classify_villains` saca `main` de `agresores` (acciones `b`/`r`) o, si no hay,
de `checkers` (acción `x`). Un fold (`f`) no entra en ninguna de las dos
listas. Por tanto `main` **no puede** ser un jugador que hizo fold en esta
calle.

Aun así, la resolución posición → pid debe exigir `state[pid_state] ==
'activo'`, porque un rival puede haber hecho fold en una calle *anterior* y
seguir spelled activo en el estado. Si no se encuentra exactamente un pid
activo, se registra el motivo y no se sustituye por `villain_pos`.

## Requisitos de la salida (contrato ya inventariado, no se inventa)

| clave | tipo |
|---|---|
| `equity_main` | float o `None` |
| `equity_main_available` | bool |
| `equity_main_source` | str o `None` — identidad del rival |
| `equity_main_note` | identificador estable del motivo |

Motivos previstos, todos en el vocabulario ya usado:

| motivo | cuándo |
|---|---|
| `main_position_unresolved` | la posición no mapea a exactamente un pid activo |
| `main_range_unavailable` | no se pudo construir el rango |
| `empty_range_after_blockers` | el rango quedó vacío tras bloquear cartas |
| `equity_calculation_failed: …` | excepción al calcular |

Ninguno devuelve `0.0` como sustituto, y ninguno se convierte en una
recomendación de acción.

## Separación que hay que conservar

Tres campos con significados distintos, que no deben reutilizarse:

| campo | contra qué | quién decide |
|---|---|---|
| `equity_production` | el rival que construyó el llamador | **la decisión real** |
| `equity_main` | el rival principal de la jerarquía | solo registro |
| `equity_shadow` | `equity_production` + ajuste por checkers | solo registro |

## Prueba de invariancia

Con y sin el productor, `action` y `value` deben ser idénticos. Ya existe el
patrón en `recommend()` (`test_equity_main_no_altera_la_accion`); hay que
replicarlo en `asistente_live`, más los casos de fallo, que deben dejar la
decisión **exactamente igual** y registrar que no hubo equity principal.
