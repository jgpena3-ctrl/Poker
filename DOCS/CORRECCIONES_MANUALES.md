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

## CM-003 — 26 manos con el check del BB perdido *(inferencia, no dato observado)* ✅ APLICADA

| campo | valor |
|---|---|
| manos | **26** (no 41 — ver "Por qué 26 y no 41") |
| ubicación | `streets.preflop.actions` — falta la acción `BB: 'x'` al final |
| valor insertado | `{'pos':'BB','action':'x','amount':0.0,'inferred':true}` |
| motivo | el preflop cerró (existe flop) y el BB no tiene acción propia |
| evidencia | `tools/auditar_bb_check.py` |
| detectado | 2026-10-13 |
| aplicado | commit `e314f74` (script `9f4869f`) |
| efecto | `bb_check` 310 → 336 sobre 1280 manos; **ninguna otra categoría cambia** |

⚠️ **Esto NO es una corrección, es una inferencia.** A diferencia de una
corrección OCR, aquí no hay un valor original equivocado: falta un valor que el
recorder nunca vio. Por eso:

- el evento va marcado con `inferred: true` y **no** reutiliza `amount_type`.
  Marcarlo `observed` sería mentir: nadie lo vio ocurrir;
- la inserción va **al final** de la secuencia preflop, que es donde cae: el BB
  es el último en actuar, así que su check es lo último que ocurrió en preflop;
- el aumento agregado de `bb_check` **no demuestra** que cada inferencia
  individual sea correcta. Es una condición de aceptación, no una prueba.

### Por qué 26 y no 41

El inventario original decía 41, pero clasificaba con:

```python
propias = [x for x in bbs if x[1] != 'b' or x[3]]
```

Eso trata **cualquier** `'b'` del BB como su ciega. En 15 de las 41 la entrada
`BB b` está **después** de acciones voluntarias — y la ciega no puede ir ahí.
`learn._es_ciega_bb` exige `not voluntary_before`, así que el motor lee esa
entrada como una **subida voluntaria del BB**.

En esas 15 el BB no tiene un check perdido: tiene una subida de más. Son CM-004.

---

## CM-004 — 23 manos con la ciega del BB colocada después de acciones voluntarias

| campo | valor |
|---|---|
| manos | 23 |
| ubicación | `streets.preflop.actions` — la entrada `BB: 'b'` está mal ordenada |
| naturaleza | **defecto de orden**, no un valor equivocado |
| evidencia | `tools/auditar_bb_check.py` |
| detectado | 2026-10-13 |

Manos: `H_0031, H_0037, H_0039, H_0051, H_0067, H_0078, H_0104, H_0107, H_0109,
H_0127, H_0143, H_0147, H_0161, H_0170, H_0183, H_0210, H_0215, H_0248, H_0262,
H_0263, H_0279, H_0294, H_0722`

### Qué ocurre

La ciega se posta antes de cualquier acción. En estas 23 manos aparece
**después**. `learn._es_ciega_bb` exige `not voluntary_before` precisamente por
eso, así que **no la reconoce como ciega** y el motor la lee como una subida
voluntaria del BB.

Categoría que el motor les asigna al BB en su lugar:

| categoría | manos | ¿puede no haber ocurrido? |
|---|---|---|
| `rol` | 14 | sí |
| `squeeze` | 6 | sí |
| `3bet` | 3 | sí |
| **total** | **23** | |

Denominadores de calibración afectados: `no_raise` 14, `facing_open` 9.

### Decisión: **no migrar**

Corregirlo exigiría **inventar un orden** que los datos no dicen. No sabemos
dónde debería ir la ciega: sólo sabemos que ahora está mal. Moverla al
principio sería una conjetura, y el principio del proyecto es preferir dejar el
hueco a rellenarlo con un número inventado.

### Alternativa: regrabar

`PROYECTO.md` §6.4a deja abierto si la DB se regraba cuando se arregle el
recorder. Estas 23 son exactamente el caso que se resuelve **regrabando**, no
migrando: si el recorder emite la ciega del BB en su sitio, desaparecen solas.

### Impacto combinado con CM-003 (medido)

Los dos sesgos van en **direcciones opuestas**, y esto es lo importante: no se
pueden evaluar por separado.

| | efecto | dirección del sesgo |
|---|---|---|
| CM-003 (aplicada) | +26 `bb_check` | el BB parece **más pasivo** de lo que es |
| CM-004 (abierta) | 23 subidas del BB que pueden no haber ocurrido | el BB parece **más agresivo** de lo que es |

Medido sobre la base completa, motor actual, BB antes vs después de CM-003:

```
bb_check   298 -> 324  (+26)      <- CM-003
rol         60 ->   60  ( +0)
squeeze     22 ->   22  (  +0)
3bet        26 ->   26  (  +0)
```

**El efecto neto no se puede cuantificar** mientras CM-004 siga abierta: no se
sabe cuántas de esas 23 subidas ocurrieron de verdad. Until then, el perfil del BB
—su PFR, su frecuencia de 3bet y su perfil de squeezed— arrastra un error de
magnitud desconocida.

**Consecuencia para el plan:** Fase D (calibración) debería esperar a CM-004, o
aceptarse explícitamente calibrar contra un perfil de BB contaminado.

---

## Resumen

| id | tipo | confianza | estado |
|---|---|---|---|
| CM-001 | corrección OCR | alta | ✅ aplicada (`e314f74`) |
| CM-002 | corrección OCR | **no verificable** | ⏸ solo si aparece el pantallazo |
| CM-003 | inferencia | alta (lógica), no dato | ✅ aplicada (`e314f74`), 26 manos |
| CM-004 | defecto de orden | n/a | 🔴 **abierta**, 23 manos, no migrable |

**Impacto agregado en la calibración (Fase D):** CM-003 hizo que el BB pareciera
más pasivo de lo que es; CM-004 hace que parezca más agresivo. Se anulan en
dirección pero **no en magnitud**: el neto es indeterminado mientras CM-004 siga
abierta. Calibrar el BB antes de resolverla es prematuro.

**Cómo aplicar:** `python tools/aplicar_correcciones.py` (dry-run) y
`--apply` para escribir. El script es idempotente: reejecutarlo detecta la
migración aplicada y no toca nada; un estado a medias aborta. Detalle en
`DOCS/MIGRACION_CM001_CM003.md`.