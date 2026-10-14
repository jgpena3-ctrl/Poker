# Migración CM-001 y CM-003

Commit de código: `9f4869f`. Aplicado con `tools/aplicar_correcciones.py`.

## Qué se corrigió

| | qué | manos |
|---|---|---|
| **CM-001** | `H_0141`, importe de la subida UTG: `27.0` → `2.7` (OCR) | 1 |
| **CM-003** | check del BB **inferido**: el preflop cerró, el BB no tiene acción propia, luego hizo check | 26 |

Los 26 checks llevan `"inferred": true` y **no** reutilizan `amount_type`.
Marcarlos como `observed` sería mentir: nadie los vio ocurrir.

## Cómo se decidió el alcance: 41 → 26

`tools/auditar_bb_check.py` inventariaba **41** manos, pero clasificaba con:

```python
propias = [x for x in bbs if x[1] != 'b' or x[3]]
```

Eso trata **cualquier** `'b'` del BB como su ciega. En 15 de las 41 la entrada
`BB b` está **después** de acciones voluntarias — y la ciega no puede ir ahí.
`_es_ciega_bb` exige `not voluntary_before`, así que el motor lee esa entrada
como una **subida voluntaria del BB**: `rol`, `squeeze`, `3bet`.

En esas manos al BB no le falta un check; le sobra una subida que no ocurrió.
Añadir el check no las arregla. La auditoría ahora pregunta al motor
(`preflop_events`) en vez de reimplementar su criterio, para que inventario y
motor no puedan divergir.

## Defecto de motor corregido antes (causa B)

`_es_ciega_bb` exigía además `amount <= bb`, con `bb = learn.BB` = **1.0**
nominal. Medido: rechazaba **4** manos cuya ciega real era 2.5–92.0 y cuyo
`BB b` estaba en el **índice 0**. El motor las creditaba con subidas
(`rol`/`squeeze`/`3bet`/`open`) que probablemente no ocurrieron.

La condición era redundante: si no ha habido ninguna acción voluntaria previa,
un `BB b` no puede ser una subida — nadie ha puesto dinero todavía, así que no
hay nada que subir. `voluntary_before` ya capturaba esa información.

Efecto: los 4 `open` espurios del BB son 0.

## Efecto medido

Sobre la base completa (1280 manos):

| | antes | después |
|---|---|---|
| `bb_check` | 310 | **336** (+26) |
| cualquier otra categoría | — | **sin cambios** |
| nº de manos | 1280 | 1280 |

Sobre la ventana fiable (900): `bb_check` 198 → 224, y la
subrepresentación pasa de 11.6% a **0.0%**.

## Reversión

```
# 1. restaurar (el backup local NO esta en git; se regenera del repo)
git checkout <commit_antes_de_la_migracion> -- data/hands_db.jsonl

# 2. regenerar los derivados
python tools/reconstruir_derivados.py regen

# 3. suite
python -m pytest motor/ -q
```

Hashes para verificar que se restauró lo correcto:

| | SHA-256 |
|---|---|
| antes | `ec868e9305d1e03abbdcd688aa8f86d6f95ffac7cc57d04fbfe36c3a1f66778a` |
| después | `bb46fec0f2e37dc7c4280cb2302d3180c0502cf9d289ab8430b1e6d957d912ee` |

Backup local en `data/_backup_aplicar_correcciones/hands_db.jsonl`
(gitignored). `hands_db.jsonl` está versionado, así que el backup del commit
anterior es siempre recuperable; el local está por si hay cambios sin commit.

## Idempotencia

Reejecutar `python tools/aplicar_correcciones.py --apply` detecta el estado
aplicado y no escribe nada. Cualquier estado intermedio (por ejemplo 13 de 26)
**aborta**.

## Lo que queda abierto

**23 manos** con la ciega del BB situada después de acciones voluntarias. El
motor les asigna una subida (`rol` 14, `squeeze` 6, `3bet` 3) que puede no
haber ocurrido. No se corrigen aquí: hacerlo exigiría inventar un
reordenamiento que los datos no dicen. Ver `tools/auditar_bb_check.py`.

**CM-002** (`H_0350`, cartas ausentes) sigue fuera: no hay evidencia suficiente
y no es verificable sin la captura.
