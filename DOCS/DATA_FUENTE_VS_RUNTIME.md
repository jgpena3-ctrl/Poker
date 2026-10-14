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

## El criterio

Un fichero es **runtime** si se escribe al *usar* el sistema y nadie lo lee
como entrada. Versionarlo obliga a que cada sesión ensucie el diff y mezcla
telemonía con código.

Un fichero es **fuente** aunque parezca derivado, si el motor lo lee y no lo
puede regenerar. `preflop_matrices.json` es el caso: pesa 328 KB, tiene toda
la pinta de artefacto, y sin ella el prior del motor desaparece.
