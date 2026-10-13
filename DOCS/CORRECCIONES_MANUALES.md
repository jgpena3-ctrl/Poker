# Correcciones manuales pendientes sobre `hands_db.jsonl`

Cada entrada es una corrección puntual sobre un valor concreto de la base, con
la evidencia que la justifica. **No se aplican a mano**: se aplican juntas,
mediante un script versionado y reversible, tal como advierte
`PROYECTO.md` §6.4a (*"nunca a mano, siempre script versionado"*).

Motivo de agruparlas: editar un JSONL a mano introduce errores de formato que
no se detectan hasta que algo downstream falla en silencio.

---

## CM-001 — `H_0141`, importe preflop de UTG

| campo | valor |
|---|---|
| mano | `H_0141` |
| ubicación | `streets.preflop.actions[0]` (`pos: 'UTG'`) |
| campo afectado | `amount` |
| valor actual | `27.0` |
| valor correcto | `2.7` |
| motivo | lectura del OCR con el punto decimal perdido |
| evidencia | `tools/investigar_importes.py` |
| detectado | 2026-10-13 |

**Evidencia:** en la misma mano, CO y BTN pagan `2.7` y SB paga `2.2`. Un open a
27.0 no es incompatible con stacks de 100 (un all-in es legal), pero no lo es
con que los tres siguientes paguen 2.7/2.7/2.2. La bets a 27.0 es la única
inconsistencia, y el factor 10 encaja con un punto perdido.

**Confianza:** alta, pero conviene confirmarla contra el pantallazo original si
se conserva.

---

## CM-002 — `H_0350`, cartas del jugador

| campo | valor |
|---|---|
| mano | `H_0350` |
| ubicación | `players[].cards` |
| campo afectado | `cards` |
| valor actual | `"-"` |
| valor correcto | *(cartas reales del hero, si el pantallazo las conserva)* |
| motivo | el recorder escribió el marcador `-` en vez de las cartas |
| evidencia | `PROYECTO.md` §6.3 |
| detectado | antes del 2026-10-13 |

**El código ya lo tolera** vía `cards.is_card_code()`, que filtra `'-'` y `''`.
El impacto actual es nulo; queda documentado por completitud.

**Confianza:** no verificable sin el pantallazo. Si no se conserva, **no corregir**:
inventar cartas sería peor que tener un marcador.

---

## CM-003 — 41 manos con el check del BB perdido *(inferencia, no dato observado)*

| campo | valor |
|---|---|
| manos | 41 (listadas por `tools/auditar_bb_check.py --json`) |
| ubicación | `streets.preflop.actions` — falta la acción `BB: 'x'` |
| valor correcto a insertar | `{'pos':'BB','action':'x','amount':0.0}` |
| motivo | el preflop cerró (existe flop) y el BB no tiene acción propia |
| evidencia | `tools/auditar_bb_check.py` |
| detectado | 2026-10-13 |
| subreprezentación | 41 de 830 eventos `bb_check` (**4.9%**) |

⚠️ **Esto NO es una corrección, es una inferencia.** A diferencia de una
corrección OCR, aquí no hay un valor original equivocado: falta un valor que el
recorder nunca vio. Por eso:

- el evento debe marcarse como inferido (`amount_type` o un flag propio), para
  que ningún consumidor lo presente como observado;
- la inserción debe ir **en su posición correcta** (después del último call
  preflop), para no romper el orden temporal corregido en F2;
- requiere re-reconstruir los derivados y comparar.

Por qué no está en la lista de "a corregir ya": mezclarla con CM-001/CM-002
contaminaría la comparación de la reconstrucción. Es un bloque propio.

---

## Resumen

| id | tipo | confianza | bloque |
|---|---|---|---|
| CM-001 | corrección OCR | alta | migración de correcciones |
| CM-002 | corrección OCR | no verificable | solo si hay pantallazo |
| CM-003 | inferencia | alta (lógica), no dato | bloque propio |

**Impacto agregado en la calibración (Fase D):** CM-003 sesga al BB como más
pasivo de lo que es, en `learn`, `stats`, `profile`, `behavior` y
`player_ranges`. No bloquea F5 (contratos de `rules.py`), pero **sí** debería
cerrarse antes de calibrar.

**Cómo aplicar:** `python tools/aplicar_correcciones.py --ids CM-001,CM-003`
(pendiente de escribir; debe hacer backup verificado y comparison, igual que
`tools/reconstruir_derivados.py`).