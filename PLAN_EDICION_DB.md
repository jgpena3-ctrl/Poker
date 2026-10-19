# PLAN DE EDICIÓN DE `data/hands_db.jsonl`

**Para verificar y avalar antes de tocar nada.** Nadie ha modificado la base.

- **SHA actual:** `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`
- **Registros:** 1258 · **Bytes:** 1 782 206
- **Listas:** generadas con `python tools/auditar_rango.py` sobre **H_0001..H_1014**
  (991 manos), contra la base **de hoy**, no contra documentos antiguos.

---

## 1. Conclusión en una línea

**[C] No hay un lote viable para las correcciones pendientes.** Las 50 manos con
defecto verificado requieren **edición manual con la grabación original**, porque
las cuatro clases de defecto son sobre **qué ocurrió en la mesa** y el JSONL no
conserva la evidencia para decidirlo.

**Lo que sí es viable en lote no es una edición: es un filtro de ventana**
(§ 6), que no toca ningún registro.

---

## 2. YA APLICADO — no tocar

Verificado contra la base de hoy, no contra documentación:

| id | qué era | **[C] estado hoy** |
|---|---|---|
| **CM-001** | `H_0141`: importe UTG `27.0` → `2.7` | **aplicada.** La 1ª acción preflop es `{'pos':'UTG','action':'b','amount':2.7}` |
| **CM-003** | 26 checks del BB insertados con `inferred:true` | **aplicada.** Quedan **23** marcas en la base |
| **CM-004** | ciega del BB después de acciones voluntarias (23 manos) | **aplicada.** Quedan **0** mal ordenadas. Las 23 siguen excluidas en `EXCLUSIONES_VENTANA_FABLE` |
| **DEFECTO_8** | acción después de foldear | **0 manos** en el rango auditado |
| **DEFECTO_652** | el BB no responde tras la subida | **0 manos** en el rango auditado |
| — | manos sin `winner` | **0.** Las 2 de la lista (`H_0342`, `H_0344`) ya no están en la base |

**[P]** `DOCS/CORRECCIONES_MANUALES.md` marca CM-001/CM-003/CM-004 con su estado
real, pero **CM-004 sigue marcado «abierta»** y es lo único que está desfasado.
No afecta a los datos; afecta a no que alguien lo intente «arreglar» otra vez.

---

## 3. NO ES UN DEFECTO — no tocar aunque parezca roto

**[C] `SIN_ALLIN` — 73 manos: `H_0001` … `H_0073` (contiguas).**

El campo `allin` falta porque las capturó una versión del grabador anterior a
que existiera ese campo.

> ⚠️ **Aviso — es una trampa.** Si «corregís» estas 73 añadiendo `allin: []`,
> **destruís la única huella que hoy permite distinguir el grabador de julio.**
> Esa huella es lo que permitió detectar que la base mezclaba dos
> implementaciones con semánticas distintas de `amount`. Perderla hace la base
> indistinguible de una que nunca tuvo ese problema.

---

## 4. LOS 4 GRUPOS A EDITAR A MANO — 50 manos

**[C] Cero solapamientos:** ninguna mano aparece en dos grupos. Total 50.

### Grupo A — `IMPORTE_SUBIDA` · 30 manos

Una subida que **no supera** la apuesta viva. Ejemplo: `preflop MP 1.0 no supera
la apuesta viva (1.0)`.

```
H_0049  H_0076  H_0104  H_0105  H_0107  H_0108  H_0117  H_0131  H_0139  H_0147
H_0148  H_0151  H_0159  H_0161  H_0163  H_0164  H_0167  H_0168  H_0169  H_0170
H_0171  H_0175  H_0177  H_0185  H_0197  H_0207  H_0214  H_0215  H_0249  H_0335
```

**Para decidir cada una hace falta:** el pantallazo del preflop, para saber si
el importe es un error de OCR o si la subida ocurrió a otro nivel.

**[P]** Instrumento: `tools/auditar_rango.py`, clase `IMPORTE_SUBIDA`, que ya
devuelve el detalle por mano.

---

### Grupo B — `SHOWDOWN_SIN_WINNER` · 15 manos

`showdown` cita a alguien que no está en `winner`.

```
H_0374  H_0376  H_0409  H_0447  H_0511  H_0744  H_0751  H_0759  H_0786  H_0833
H_0911  H_0915  H_0932  H_0957  H_0972
```

**Para decidir hace falta:** la grabación del showdown. **`showdown.winner1` es
texto OCR**, no un dato estructurado: sin el pantallazo no se puede saber a quién
nombra realmente ni si el nombre es correcto.

---

### Grupo C — `WINNER_FOLDEO` · 3 manos

`winner` incluye a un jugador que foldeó.

```
H_0602   p3(BTN) foldeo
H_0748   p2(UTG) foldeo
H_0893   p2(SB)  foldeo
```

**Para decidir hace falta:** la grabación. Puede ser un fold mal leído por el
OCR de estado, o un `winner` mal escrito.

---

### Grupo D — `ACCION_FANTASMA` · 2 manos

Una acción de una posición que no estaba en la mesa.

```
H_0519   'CO'
H_0846   'MP'
```

**Para decidir hace falta:** la grabación y el reparto de asientos. **[P]** Es la
más delicada: puede ser un asiento mal asignado en `players[]`, no una acción
inventada.

---

## 5. Por qué no hay lote

**[C]** Las cuatro clases comparten la misma forma: **el JSONL registra un
resultado del OCR, y el defecto es que el OCR leyó mal.** Para corregirlo hay que
sustituir un valor OCR por el valor real, y **el valor real no está en ninguna
parte del repositorio**.

**[C]** `tools/auditar_rango.py` **detecta**, no corrige. Los dos correctores que
existen (`tools/aplicar_correcciones.py`, `tools/aplicar_reinterpretacion.py`)
sólo cubren CM-001/002/003/004, **ya aplicados**, y ninguno toca estas clases.

**[D]** Un lote aquí sería escribir un valor inventado en 50 manos. Eso es
exactamente el error que produjo la retirada de 22 registros de `75bbdb7`, y
esta auditoría ya lo documentó.

---

## 6. Lo que SÍ es viable en lote — y no es una edición

**[C]** `PROYECTO.md` §6.4: hoy `learn.load_hands()` lee las 1258 y **ningún
consumidor declara ventana**. Las recomendaciones en vivo se calculan con 358
manos de dudosa fiabilidad.

**[P] Añadir una ventana declarada** — `load_hands(reliable_only=True)` o
`max_hands=900` — **no borra nada**: cambia qué población lee cada consumidor.

**[D] Esto no es una corrección de la base.** Es un cambio en el motor, y
`PROYECTO.md` §6.4a lo pone **antes** de tocar la DB.

⚠️ **[C] `reliable_only=True` excluye hoy 23 manos** (`EXCLUSIONES_VENTANA_FABLE`)
y su propio comentario declara que **el motivo escrito ya no describe la
exclusión**. Si se usa esta vía, ese motivo hay que escribirlo primero.

---

## 7. Procedimiento manual, si decides_edit_ar

Por cada mano, en este orden:

1. **Copia de seguridad con fecha.** No edites `data/hands_db.jsonl` directamente.
2. Abre la mano con `hand_editor.py` o sobre una **copia**.
3. Localiza el campo exacto que el detector señala
   (`tools/auditar_rango.py --json` da el detalle por mano).
4. **Consulta la grabación/pantallazo original.** Si no existe, **no corrijas**:
   anota `NO CORREGIBLE: sin original`.
5. Corrige **un solo campo**. No reformatees, no reordenes, no toques otros campos.
6. Reejecuta el detector. Debe bajar el contador **exactamente en 1**.
7. Cuando termines: `python tools/auditar_rango.py --validar` para confirmar que
   los detectores siguen dando las cifras de referencia.

**[P] Regla de seguridad:** si un campo necesita **inventar** un valor, se deja
como está y se documenta. Un hueco declarado es información; un hueco rellenado
con una suposición es ruido con apariencia de dato.

---

## 8. Casos sueltos

| id | qué es | qué hacer |
|---|---|---|
| **`H_0350`** | `players[].cards == "-"` | **solo si aparece el pantallazo.** Sin él, **no corregir** |
| **`H_1196`** | entrada `SB c 2.0` que el motor rechaza como posterior a acción voluntaria | **el rojo intencional.** No «arreglar» |
| **`H_1015`** | retirada en `75bbdb7`, **no figura en ninguna lista** | **decisión tuya**, no una corrección. Ver `AUDITORIA_SEMANTICA_GRABADOR.md` § 3.2 |
| **las otras 21 retiradas** | idem | **decisión pendiente**, no corrección |

---

## 9. Verificación

| comprobación | antes |
|---|---|
| SHA-256 de `data/hands_db.jsonl` | `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` |
| bytes | 1 782 206 |
| registros | 1258 |
| `python tools/auditar_rango.py --validar` | detects las cifras de referencia |

**[M]** Nada de esto se ha modificado. La base conserva su SHA.