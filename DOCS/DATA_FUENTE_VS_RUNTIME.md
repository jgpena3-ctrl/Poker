# Qué es fuente y qué es runtime en `data/`

Medido con `python tools/clasifica_data.py` (no estimado): para cada fichero
versionado, se busca qué código lo **escribe** con `open(...,'w')` y quién lo
**referencia**.

## Fuente: se versiona

| fichero | por qué |
|---|---|
| `hands_db.jsonl` | la base. Sin ella no hay nada. |
| `preflop_matrices.json` | el prior de `learn`/`profile`/`player_ranges`. **No se regenera desde los datos** (`DIAGNOSTICO_CALIBRACION.md`): es fuente aunque parezca derivado. |

## Derivados: se versionan, pero se regeneran

Los escribe `python tools/reconstruir_derivados.py regen`. Versionarlos para
que el diff muestre el efecto de un cambio de código.

```
behavior.json   observations.json   player_stats.json
postflop_ranges.json   preflop_stats.json
profile_ranges.json    profiles.json
```

`behavior_probs.json`, `calib_1365.json`, `db_health.json` y `golden.json` los
escriben scripts concretos, no el regenerador. Se versionan por la misma
razón: permiten comparar contra una base conocida.

## Runtime: NO se versiona

| fichero | evidencia |
|---|---|
| `shadow_hierarchy.jsonl` | telemetría del modo sombra. Se escribe en cada sesión y también al correr los tests. Su valor está en acumularse. |
| `test_mano4_output.jsonl` | 0 referencias en todo el repo |
| `test_output2.jsonl` | 0 referencias |
| `test_output_mano3.jsonl` | `tools/test_mano3.py:39` lo asigna como `recorder.output_path`: es salida, no entrada |
| `test_trace.jsonl` | 0 referencias |
| `_backup_aplicar_correcciones/` | backup local de la migración CM-003 |
| `_snapshot_pre_rebuild_*/` | snapshots de reconstrucciones anteriores |

## Limitaciones del clasificador (medidas, no supuestas)

Dos correcciones sobre la primera versión, que daba falsos positivos:

| problema | efecto | arreglo |
|---|---|---|
| solo buscaba el literal `data/...` | `learn.py`, `db_health.py`, `postflop_ranges.py` construyen con `os.path.join` y aparecían como "nadie los escribe" | se buscan también `join` y `div` |
| `[^)]*` en el patrón de `join` | `observations.json`, `player_stats.json` y `profiles.json` seguían sin autor: `os.path.join` admite paréntesis anidados antes del nombre | ventana de 400 caracteres hacia atrás |

Un falso positivo de "nadie lo escribe" es peligroso en esta dirección:
invita a borrar algo vivo. Por eso el script marca la **forma** con que
detectó cada escritor (`[join]`, `[div]`, o literal sin marca).

**Lo que sigue sin detectar:** la ventana es heurística. Puede atribuir un
fichero a un módulo que lo cita cerca sin construirlo, y no ve escrituras
construidas en tiempo de ejecución. Antes de la ampliación se le escapaban
4 de 15 ficheros; ahora los 15 tienen autor. La clasificación es una ayuda con
evidencia, no una prueba.

## `db_health.json` — derivado, no histórico

revision_1 pedía verificarlo. Medido:

- lo escribe `motor/db_health.py:save_snapshot()`, con
  `SNAPSHOT_PATH = os.path.join(REPO_DIR, 'data', 'db_health.json')`;
- se regenera con `python -m motor.db_health --json`;
- `snapshot_delta()` lo **lee** para comparar contra la ejecución anterior,
  así que es estado acumulado, no basura.

Se versiona como los demás derivados: es la línea base con la que se mide si
la base empeora. No lo regenera `reconstruir_derivados.py`, y por eso su
regeneración es manual; queda dicho para que nadie lo busque en el script
equivocado.

## El criterio

Un fichero es **runtime** si se escribe al *usar* el sistema y nadie lo lee
como entrada. Versionarlo obliga a que cada sesión ensucie el diff y mezcla
telemonía con código.

Un fichero es **fuente** aunque parezca derivado, si el motor lo lee y no lo
puede regenerar. `preflop_matrices.json` es el caso: pesa 328 KB, tiene toda
la pinta de artefacto, y sin ella el prior del motor desaparece.
