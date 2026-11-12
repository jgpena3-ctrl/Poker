# F0.2 - contrato de integridad de escritura y arnés de fallos

**Estado:** F0.2 implementado para reauditoría. No implementa F1: no hay mutex
real, journal en disco, CAS, backups, cambios de writers, cambios de datos ni
cambios de conducta preflop/postflop.

## 1. Qué fija F0.2

F0.2 separa el contrato de la implementación. El contrato vive en
`motor/write_contract.py` y el arnés en `motor/test_write_contract.py`.

Reglas cerradas:

- Exclusión: mutex con nombre de Windows `Global\Poker.HandsDB.v1`.
- Sin fallback a lockfile, `msvcrt.locking` ni otro mecanismo.
- Sin soporte multi-host: si el volumen no garantiza el mutex, se aborta.
- `WAIT_ABANDONED`: se adquiere, se ejecuta recuperación y solo después se
  escribe.
- Timeout o fallo al crear/adquirir el mutex: abortar de forma visible.
- Lectores: instantánea verificada bajo el mismo mutex exclusivo; no hay lock
  de lectura.
- Journal corrupto, truncado, con evidencia no ligada al plan o con un tercer
  hash: cuarentena. Prohibida la restauración automática.
- Pins: se proponen para revisión; no se actualizan en runtime.
- Una ausencia no se convierte en cero, en hash válido ni en evidencia.
- El `WritePlan` es autoritativo: la evidencia no puede sobrescribir sus
  campos ni una evidencia ya verificada. Los reintentos solo son idempotentes
  si repiten exactamente la evidencia ya fijada.
- El CAS exige hash, líneas y bytes de la preimagen. Una discrepancia produce
  el estado terminal `cas_conflict`; no se reintenta con otra preimagen.
- El backup se identifica por `backup_txn_id`, disposición y nombre de archivo;
  debe ser copia exacta (hash y bytes) de la preimagen verificada.
- El manifiesto se declara en el plan y pasa por `manifest_pending` antes de
  su verificación; `manifest_path` debe ser `data/calibration_window.json`.
- Toda ruta se canonicaliza y se rechaza cualquier alias, symlink, junction o
  ruta fuera del repositorio.
- Toda evidencia se congela en profundidad; los mappings y secuencias anidados
  no se pueden mutar después de entrar en un `TransactionRecord`.

## 2. Máquina de estados

Secuencia normal:

```text
prepared
  -> preimage_verified
  -> backup_verified
  -> temp_verified
  -> replaced
  -> post_verified
  -> manifest_pending
  -> manifest_verified
  -> pins_proposed
  -> committed
```

Estados terminales:

```text
committed | cas_conflict | aborted | failed | quarantined
```

Reglas de fallo:

- `aborted`, `failed` y `quarantined` se permiten desde `prepared` hasta
  `temp_verified`.
- Antes de `replaced` se puede abortar o fallar sin tocar la base.
- Desde `prepared`, una discrepancia de CAS entra en `cas_conflict`, que es
  terminal y no admite reintento con otra preimagen, evidencia o plan.
- Desde `replaced` solo se permite `post_verified` o `quarantined`. Un fallo
  posterior al reemplazo no puede presentarse como `failed` ni como `aborted`.
- `committed` exige postimagen verificada, operación verificada, manifiesto
  resuelto y pins propuestos.
- `manifest_pending` registra la decisión de manifiesto antes de verificarlo;
  no se puede saltar hacia `manifest_verified`.
- Ningún estado terminal admite transición ni reintento.
- Un reintento de un estado no terminal solo se acepta sin cambios de
  evidencia y no añade un estado al historial.

`CasConflict` expone en `.record` el registro terminal `cas_conflict` que F1
debe persistir. El registro previo al conflicto no es un journal válido para
continuar: la recuperación solo acepta la cadena que termina en el estado
terminal.

## 3. Evidencia exigida

| Estado | Evidencia mínima |
|---|---|
| `prepared` | `txn_id`, `writer`, `target_path`, `operation`, hashes/líneas/bytes de preimagen y candidato, `lock_policy_fingerprint`, `planned_at` |
| `preimage_verified` | `observed_pre_sha256`, `observed_pre_lines` y `observed_pre_bytes` iguales a la preimagen declarada; discrepancia = `cas_conflict` |
| `cas_conflict` | preimagen observada completa, `cas_conflict_reason` y `cas_conflict_at`; exige discrepancia real |
| `backup_verified` | `backup_path` canónico, distinto del target y bajo `data/_backup`, `backup_txn_id` igual a `txn_id`, disposición `created` o `reused_same_txn`, y `backup_sha256`/`backup_bytes` iguales a la preimagen |
| `temp_verified` | `temp_path` canónico, distinto de target/backup/manifiesto/pins, con `txn_id` y sufijo `.tmp`; `temp_sha256`, `temp_lines` y `temp_bytes` iguales al candidato |
| `replaced` | `replaced_at` ISO-8601 con zona, `operation_verified=True` y la evidencia específica de la operación |
| `post_verified` | `post_sha256`, `post_lines` y `post_bytes` iguales al candidato |
| `manifest_pending` | `manifest_pending_at`; si el plan no exige manifiesto, `manifest_skipped_reason` |
| `manifest_verified` | si el plan exige manifiesto, `manifest_observed_pre_sha256`, `manifest_sha256` y `manifest_verified=True`; si no, `manifest_skipped_reason` |
| `pins_proposed` | `pins_applied=False`; si el plan exige pins, `pins_proposed_sha256`, `pins_symbols`, `pins_proposed_values` y `pins_source_sha256`; si no, `pins_skipped_reason` |
| `committed` | `committed_at`, postimagen verificada, manifiesto resuelto y pins no aplicados |
| `aborted` | `abort_reason` |
| `failed` | `failure_reason` |
| `quarantined` | `quarantine_reason` |

`pins_applied=True` siempre se rechaza. `pins_proposed_sha256` no es un hash
libre: debe ser el SHA-256 canónico de `pins_proposed_values`, que debe cubrir
exactamente `PINS_SYMBOLS`; `HANDS_DB_SHA256`, `HANDS_DB_LINEAS` y
`HANDS_DB_COMMIT` se contrastan con el candidato y con el formato de commit.
`pins_expected_sha256` es obligatorio en el plan y `pins_source_sha256` debe
coincidir con él, de modo que la propuesta quede ligada a la ruta y al
contenido de partida. Los pins son código: su actualización es una revisión
separada, no parte de la transacción.

## 4. Destinos y contrato de writers

`TARGET_POLICIES` declara categorías y operaciones permitidas:

| Categoría | Destinos | Operaciones | Controles mínimos |
|---|---|---|---|
| base | `data/hands_db.jsonl` | `append`, `rewrite` | lock, CAS, backup, manifiesto, pins |
| manifiesto | `data/calibration_window.json` | `rewrite` | lock, CAS, backup, manifiesto |
| modelo | `data/profile_ranges.json`, `data/postflop_ranges.json` | `rewrite` | lock, CAS, backup, manifiesto |
| derivado | `preflop_stats`, `player_stats`, `profiles`, `behavior`, `behavior_probs`, `observations` | `rewrite` | lock, CAS, backup, manifiesto |

`WriterDeclaration` exige todos los controles de la política de cada destino.
Un writer que declare un derivado con todos los controles en `False` falla; un
destino desconocido también falla. Las operaciones no permitidas por la
política (por ejemplo `append` sobre el manifiesto) se rechazan. El contrato
no declara que ningún writer actual ya cumpla esto: F3 debe migrar cada uno y
demostrarlo con sus pruebas.

## 5. Rutas, backups y transacciones

- `canonical_path()` resuelve `..`, symlinks y junctions; `WritePlan` exige
  además que la ruta declarada coincida exactamente con su forma canónica.
- Se rechazan rutas absolutas, separadores `\`, rutas fuera del repositorio y
  aliases de la base, el manifiesto, los pins o los destinos derivados.
- `txn_id` solo admite letras, números, punto, guion y guion bajo; no puede
  contener separadores.
- `backup_path` debe incluir `txn_id`, quedar bajo `data/_backup` y no colisionar
  con target, manifiesto, pins o snapshot de origen.
- `temp_path` debe incluir `txn_id`, terminar en `.tmp` y no colisionar con
  target, backup, manifiesto o pins.
- `backup_disposition` distingue `created` de `reused_same_txn`; una copia
  preexistente de otra transacción no es evidencia válida.

## 6. Semántica de operaciones

- `append`: el candidato no puede reducir líneas ni bytes; si conserva los
  bytes, debe conservar también el hash. En `replaced` exige
  `preimage_prefix_verified=True` y `append_boundary_verified=True`.
- `rewrite`: en `replaced` exige `rewrite_complete_verified=True`.
- `snapshot`: debe declarar `snapshot_of`, escribir bajo `data/_snapshot_f0/`,
  no tocar el recurso canónico y copiar la preimagen sin cambios. En `replaced`
  exige `snapshot_verified=True` y `canonical_target_unchanged=True`.

## 7. Journal y recuperación

El sobre de journal es versionado y encadenado:

- `schema_version=2`, `contract_version`, `txn_id`, `plan_fingerprint`,
  `sequence`, `state`, `previous_sha256`, `evidence`, `evidence_sha256` y
  `record_sha256`;
- `plan_fingerprint` liga cada registro a un `WritePlan` concreto;
- `evidence_sha256` liga la evidencia serializada al registro; el journal exige
  evidencia acumulada y no puede eliminar ni cambiar evidencia ya verificada;
- `record_sha256` es el SHA-256 canónico del registro sin incluirse a sí mismo;
- solo se permiten `previous_sha256`, `record_sha256` y `evidence_sha256`;
  cualquier otro campo de hash se rechaza como tercer hash;
- el JSON canónico rechaza claves no textuales, `NaN` e `Infinity`;
- un journal truncado, corrupto, con secuencia discontinua, `txn_id` o
  `plan_fingerprint` inconsistentes, evidencia vacía o transición inválida se
  pone en cuarentena;
- la recuperación exige el `WritePlan`; sin plan verificable no restaura aunque
  la estructura sea válida;
- recuperación: aborta si el último estado es anterior a `replaced`, pone en
  cuarentena si es `replaced` o posterior, y devuelve `cas_conflict` si el CAS
  terminó en conflicto.

## 8. Mutex

`LockPolicy` fija para F1: mutex `Global\Poker.HandsDB.v1`, timeout positivo,
sin fallback, sin multi-host, ACL y SID obligatorios, `WAIT_ABANDONED` con
recuperación previa y fallo visible. El plan incluye `lock_policy` y su
`lock_policy_fingerprint` queda fijado en la evidencia y en el journal. Sigue
sin implementar el mutex real.

## 9. Arnés de fallos

`motor/test_write_contract.py` usa una base simulada como cadena:

- la preimagen solo cambia al entrar en `replaced`;
- antes de `replaced`, cualquier fallo deja la preimagen intacta;
- después de `replaced`, el único cierre válido es `quarantined`;
- ningún camino de fallo puede llamar a `assert_committed()` con éxito;
- se prueban CAS terminal, journal ligado al plan/evidencia, evidencia profunda
  inmutable, destinos derivados, aliases de rutas, lock vinculado, operaciones,
  pins ligados a valores, JSON canónico y timestamps con zona.

Categorías de prueba:

1. Contrato puro: planes, evidencia, estados, writers, journal.
2. Simulación de fallos: arnés y matrices antes/después de `replaced`.
3. Integración real: pendiente de F1; F0.2 no abre archivos ni escribe `data/`.

## 10. Matriz de cierre D1-D10

| Defecto | Cierre F0.2 | Prueba representativa |
|---|---|---|
| D1 CAS no terminal | `cas_conflict` terminal, `CasConflict.record`, sin transición posterior | `test_preimage_mismatch_is_terminal_cas_conflict` |
| D2 journal sin plan/evidencia | `plan_fingerprint`, `evidence_sha256`, evidencia acumulada y recuperación con plan | `test_journal_rejects_empty_evidence_and_wrong_plan` |
| D3 evidencia mutable | congelado profundo de mappings, listas y conjuntos | `test_evidence_is_deeply_immutable` |
| D4 writers sin categoría | `TARGET_POLICIES` base/manifiesto/modelo/derivado y controles por categoría | `test_writer_declaration_fails_closed_for_all_target_categories` |
| D5 rutas y backups | canonicalización estricta, colisiones, raíz de backup, `txn_id` y disposición | `test_backup_path_must_be_canonical_owned_and_under_backup_root` |
| D6 lock no vinculado | `lock_policy` en plan/writer y `lock_policy_fingerprint` en evidencia | `test_lock_and_recovery_policy_is_fail_closed_and_bound_to_plan` |
| D7 operaciones sin semántica | targets/operaciones declarados y evidencia específica de `append`/`rewrite`/`snapshot` | `test_append_and_snapshot_operation_semantics`, `test_operation_evidence_is_required_before_replace` |
| D8 pins sin contenido | valores por símbolo, hash canónico, commit/líneas/hash y hash de fuente | `test_pins_are_proposed_not_applied_and_bound_to_values` |
| D9 JSON ambiguo | rechazo de claves no textuales, `NaN`/`Infinity` y hash canónico | `test_canonical_journal_hash_rejects_ambiguous_json` |
| D10 timestamps sin zona | validación ISO-8601 con zona en plan y evidencia | `test_timestamps_require_iso_8601_timezone` |

## 11. Lo que F0.2 no hace

- No crea `Global\Poker.HandsDB.v1`.
- No captura `WAIT_ABANDONED`.
- No lee ni escribe journal.
- No calcula CAS de la base ni hashes de archivos reales.
- No crea backups.
- No migra `record_hand`, `recorder_live`, `hand_editor`, `save()` ni los
  writers de `tools/`.
- No cambia `HANDS_DB_*`, `calibration_window.json`, derivados, matrices ni
  recomendaciones.
- No activa ninguna fase P0/B2.

## 12. Prueba de F0.2

```text
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest motor/test_write_contract.py -q -p no:cacheprovider
```

Resultado: `45 passed`.

La prueba no debe tocar `data/hands_db.jsonl` ni sus derivados.
