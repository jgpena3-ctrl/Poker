# Auditoría de `no_puede_actuar()` — INC-001

revision_1 **Tarea 2** y revision_2 **punto 1 (bloqueante)**.
Se para aquí: hay solapamiento, así que F7.2 queda bloqueada.

- **Código medido:** `d5da514`
- **Script:** `python tools/auditar_solapamiento_multiway.py`
- **Salida cruda:** `DOCS/AUDIT_NOPUEDE_ACTUAR.txt`
- **Suite:** 610 passed, 1 skipped (591 → 610, +19)

> Los dos `.txt` de este bloque (`AUDIT_NOPUEDE_ACTUAR.txt` e
> `INVENTARIO_MULTIWAY_HEAD.txt`) **están en `.gitignore`**: `.gitignore:34`
> trae `*.txt` y el proyecto solo versiona `.md` en `DOCS/` (verificado:
> `baseline_folds_900.txt` tampoco está versionado). Son salidas de
> herramienta, regenerables; este `.md` es la versión que sí queda en el
> historial. Si se quieren versionar, hay que pasarlos con `git add -f`, y
> esa decisión es de quien revise.

---

## 1. Representación real del all-in

El dato **existe**, y la regla vieja no lo usaba.

`hand['allin']` es una lista de identificadores **internos de asiento**:
`hero`, `p1`…`p5`. No de posiciones.

```python
# recorder_live.py:1034
out['allin'] = [p['_id'] for p in self.hand['players']
                if p['_id'] in self._allin_players and p['active']]
for p in out['players']:
    del p['_id']          # <-- la llave se borra
```

El dato del all-in sobrevive; **la unión con su posición se tira**. Por eso
`allin` no trae `pos` y por eso alguien concluiría que "no se puede
saber quién es all-in".

**Sí se puede.** `players[]` se rellena recorriendo `PLAYER_IDS` en orden,
así que `players[i]` *es* `PLAYER_IDS[i]` y el índice reconstruye la unión.

| | |
|---|---|
| manos con campo `allin` | 827 / 900 |
| manos sin campo `allin` | **73** |
| ids resueltos a posición | **138** |
| ids sin posición | **0** |
| longitudes de `players[]` | `{6}` — todas |

Distribución de ids: `p3` 27, `p5` 27, `p2` 26, `p4` 20, `hero` 19, `p1` 19.

**La calle del all-in** se deduce: un jugador que se commitmenta no vuelve a
actuar, así que **su última acción registrada *es* la del all-in**. `allin`
es un hecho de fin de mano, y esta es la deducción que lo baja a cada calle.

---

## 2. Diagnóstico: qué clasifica mal

```python
if isinstance(a, dict) and a.get('pos') and a.get('action') == 'r':
    activos.discard(a.get('pos'))      # "ha subido" ~ "se ha commitmentado"
```

| | |
|---|---|
| raise distintos en la ventana | 625 |
| **falsos positivos** (subió, conserva fichas) | **534 — 85,4 %** |
| **falsos negativos** (all-in conseguido con call) | **47** |
| **precisión de la regla vieja** | **14,6 %** |

La regla falla en **las dos direcciones**:

- **FP**: `H_0074` BTN subió a 9.0 con 141.1 de stack; el all-in real era
  UTG, que se commitmentó a 38.2. `H_0076` UTG subió y no hay all-in alguno.
- **FN**: `H_0075`, `H_0077`, `H_0104` — el BB/MP se commitmenta **igualando**
  un all-in. Una bajada no registra `'r'`, así que la regla vieja nunca lo ve.

### ¿Se sostiene el 169?

**No.** No porque el número sea mayor o menor, sino porque se apoyaba en una
regla con 14,6 % de precisión.

### Ortogonalidad `folds_hasta` × `no_puede_actuar`

| clasificador | ambos | solo uno | ninguno |
|---|---|---|---|
| actual (raise) | **178** | 5122 | 1901 |
| evidencia (allin) | **1** | 4319 | 2262 |

**Veredicto: no son ortogonales.** Un jugador que subió y *luego* foldeó cae
en los dos conjuntos a la vez — doble conteo real. Por eso "el desglose
cuadra" (1368 + 305 + 21 = 1694) no demostraba que el 1694 fuese correcto.

Con la regla nueva el cruce es 1, y **no es 0 por construcción**: es un
registro corrupto (§2.b).

### 2.b. Defecto del dato, no del clasificador

`allin` se filtra al volcar con `p['active']`, y `active` significa **"estaba
sentado al empezar la mano"**, no "no ha foldeado". Un jugador que se
committea y después foldea queda en la lista.

| | |
|---|---|
| entradas en `allin` | 138 |
| de las cuales con un fold posterior | **1 — 0,7 %** |

`H_0851`: UTG sube preflop, checkea en el flop, BTN betea 4.0 y **UTG foldea**
— y sigue en `allin`. Es el cruce de 1 de la tabla anterior.

---

## 3. Inventario recalculado

Mismo denominador, los mismos puntos de decisión.

| calle | MW en el bote | MW (regla actual) | MW (evidencia) |
|---|---|---|---|
| flop | 171 | 101 | 138 |
| turn | 84 | 46 | 63 |
| river | 42 | 22 | 24 |
| **TOTAL** | **297** | **169** | **225** |

El all-in reclasifica **128** spots con la regla vieja y **72** con la nueva.
La nueva reclasifica menos porque ya no confunde "ha subido" con "se ha
committeado".

**107 puntos de decisión sin evidencia** (campo `allin` ausente, 73 manos).
Se quedan **fuera del numerador**: no se fuerzan. De ellos, 51 son multiway
en el bote. Por tanto el multiway que puede responder está en un
**intervalo, no en un punto**:

```
225  <=  MW que puede responder  <=  276
```

> **Para F7.2 la cifra de referencia es ese intervalo, no el 169.**
> El 16,8 % de `RESUMEN_SECCION.md` queda invalidado.

---

## 4. Tests nuevos

`motor/test_nopuede_actuar.py`, 19 casos. Sintéticos, según pide revision_2:

| caso | qué separa |
|---|---|
| `test_raise_ordinario_no_es_allin` | subida que conserva fichas |
| `test_resubida_no_es_allin` | **resubida** (tres veces subido) |
| `test_resubida_y_call_final_siguen_pudiendo_actuar` | resubida no superada **no** es all-in |
| `test_allin_por_raise_no_puede_actuar` | all-in real por subida |
| `test_allin_por_call_no_puede_actuar` | **all-in por call — el FN** |
| `test_fold_no_genera_no_puede_actuar` | el que foldeó |
| `test_foldeo_una_calle_tarde_no_bloquea_en_la_anterior` | fold en el turn no bloquea en el flop |
| `test_allin_en_el_flop_no_puede_actuar_en_el_flop` | cuenta desde su calle |
| `test_allin_en_el_turn_sigue_pudiendo_actuar_en_el_flop` | `allin` es de fin de mano |
| `test_sin_campo_allin_es_desconocido_no_vacio` | **estado desconocido ≠ vacío** |
| `test_allin_vacio_es_vacio_de_verdad` | vacío de verdad |
| `test_players_con_otro_tamano_es_desconocido` | supuesto de orden roto |
| `test_multiway_con_allin_que_no_es_el_raiser` | el caso que cambia la clasificación |

### Autoverificación

Un test que solo pasa no demuestra que sepa fallar. Se comprobó **mutando**
`no_puede_actuar` para que use la evidencia: fallan **5**, incluidos los dos
casos de `test_la_regla_vieja_se_demo_incapaz_de_estar_correcta`. Si la regla
se arregla algún día, esos tests avisan en vez de quedarse mintiendo.

---

## 5. Qué NO se ha hecho, y por qué

- **No se ha tocado F7.2 ni la política multiway.** revision_1 dice: si hay
  solapamiento, parar y abrir incidencia. Hay solapamiento.
- **No se ha cableado la regla nueva al motor.** Vive en
  `tools/auditar_solapamiento_multiway.py` como candidato. Firmarla es el
  punto 2 de revision_2, y ese contrato se escribe *antes* de cambiar
  estrategia.
- **No se han abierto las tareas 3–5 de revision_1** (CM-004, contrato C4,
  `RangeState.position`). Siguen pendientes.

## 6. Lo que hace falta para desbloquear

1. Decidir si la regla nueva sustituye a la vieja en
   `no_puede_actuar()`, o si la vieja se conserva como declared limitation.
2. Si se sustituye: el **contrato F7.2.a** de revision_2 punto 2, por
   escrito, con los ejemplos de frontera que pide.
3. Los **73 manos sin campo `allin`**: o se regraban, o se declaran
   descartadas del denominador de F7.2. Hoy son 107 puntos de decisión sin
   clasificar.
4. `H_0851` (`allin` con fold posterior): defecto del recorder, no del
   clasificador. Corregir el filtro de guardado o aceptar 0,7 % de ruido.