# Auditoría de consumidores de hands_db.jsonl

Bloque previo a CM-003. Ejecutar con:

```
python tools/auditar_consumidores.py
```

## Por qué bloquea la migración

CM-003 inserta 41 acciones marcadas con `inferred: true`. Si algún camino
**reescribe** `hands_db.jsonl` reconstruyendo cada acción con un conjunto
cerrado de claves (`{'pos':…, 'action':…, 'amount':…}`), el campo se pierde en
silencio y las inferencias acaban presentándose como observaciones. Eso es
justo el fallo que CM-003 existe para evitar.

El riesgo **no** está en los lectores: `load_hands` devuelve los dict que le
da `json.loads`, sin transformarlos. Está en quien reescribe el fichero.

## Método

Análisis AST sobre todo el `.py` del repo, buscando un único patrón
peligroso: un bucle o comprehension que **recorre `actions`** y produce un
dict literal. `.append({...})` no cuenta — crea una acción nueva y no toca
las existentes.

## Resultado

**Ninguno.** Sección 2 del script: `ninguna`.

Ficheros que tocan `hands_db.jsonl`:

| fichero | escribe la DB | recorre `actions` reconstruyendo |
|---|---|---|
| `hand_editor.py` | **sí** | no |
| `motor/learn.py` | no (`data/preflop_stats.json`) | no |
| `motor/db_health.py` | no (`SNAPSHOT_PATH`) | no |
| `motor/player_ranges.py` | no (`profile_ranges.json`) | no |
| `motor/postflop_ranges.py` | no (`postflop_ranges.json`) | no |
| `motor/hierarchy.py` | no | no |
| `recorder/recorder_live.py` | no (hands nuevas) | no |
| `recorder/record_hand.py` | no (hands nuevas) | no |
| resto | lectura | no |

## Comprobación manual de `hand_editor.py`

Único escritor real de la DB, y el patrón AST no cubre llamadas indirectas:

- `_write()` (línea 586): `f.write(json.dumps(h, …))` sobre `self.hands`,
  que son los dict cargados tal cual de `json.loads` (línea 26). Ida y vuelta
  completa: cualquier clave extra sobrevive.
- `_add_action` (línea 497): `…setdefault('actions',[]).append({…})`. Añade al
  **mismo objeto lista**, no sustituye. Las acciones con `inferred` no se
  tocan.

`_savejson()` (línea 573) escribe un `.json` suelto, no el JSONL.

## Limitación del análisis

El patrón que se busca es un bucle o comprehension que **recorre `actions`** y
produce un `dict` literal:

```python
for a in hand['streets'][st]['actions']:
    x = {'pos': a['pos'], 'action': a['action'], 'amount': a['amount']}
```

**No** se detectan dos formas:

1. **Comprehension que llama a una función auxiliar**, que a su vez devuelve un
   dict cerrado:
   ```python
   nuevas = [limpiar(a) for a in actions]
   def limpiar(a):
       return {'pos': a['pos'], 'action': a['action'], 'amount': a['amount']}
   ```
   El AST ve una comprehension que no produce un dict literal: llama a
   `limpiar`.

2. **Serialización indirecta**: construir el dict en otro módulo y asignarlo.

Verificado: no existe tal función en el repo hoy. Pero el análisis **no es
exhaustivo**. Si se añade cualquier helper de "limpieza" o "normalización" de
acciones, hay que repetir esta comprobación a mano (y conviene añadir el caso
como test).


## Veredicto

`inferred: true` es seguro en el pipeline Python. No hay ningún esquema que
lo rechace ni ningún lector que lo descarte.

**Pendiente para cuando exista un consumidor no-Python** (exportación a otro
formato, script externo): ahí habría que repetir esta comprobación.
