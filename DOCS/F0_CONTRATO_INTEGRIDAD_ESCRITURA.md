# F0 — Contrato de integridad de escritura

## Estado de este documento

- Revisión de implementación/arnés: `F0.7 (2026-11-12)`; la versión del
  contrato serializado/journal permanece `F0.5` porque no cambió su esquema.
- HEAD auditado: `1a9a4277e7176abadf2c20af6cd6a3aab792d970`.
- Estado de implementación: `F0.7_LISTO_PARA_REAUDITORIA`.
- Estado Git: tres archivos F0 modificados, sin cambios staged ni untracked;
  `data/` intacta.
- Este documento **no declara F0 cerrado**. El cierre corresponde a una
  reauditoría independiente.
- No se inicia F1.
- No se implementan mutex real, journal en disco, CAS físico, backup,
  temporal ni replace.
- `MULTIWAY_SOPORTADO` permanece en `False`.

## 1. Objetivo y alcance

F0 define el vocabulario, las políticas, las transiciones y las garantías
verificables de una escritura canónica. F0 no abre archivos, no crea mutex, no
escribe journal y no toca `data/`. F1/F2 deben implementar el contrato sin
inventar estados ni aceptar evidencia incompleta.

F0.7 corrige exclusivamente la autorización por `id(record)` reutilizable
reproducida por la reauditoría independiente de F0.6. La instancia autorizada
se conserva por referencia fuerte y se compara con `is`. D1 sigue pendiente de
confirmación independiente; no se inicia F1.

## 2. Modelo de amenaza

### 2.1 Amenazas cubiertas

F0 cubre:

- Uso normal de la API con planes, declaraciones, evidencia y transiciones
  incompletas o contradictorias.
- Errores de programación que intentan saltar estados, reutilizar evidencia,
  debilitar políticas o completar una transacción invalidada.
- Extensibilidad accidental: subclases, duck typing, objetos mutables,
  políticas globales sustituidas o serializadores alternativos.
- Reutilización de campos copiados (`authority_id`, `txn_id`,
  `plan_fingerprint`, `transaction_uid`) para intentar adquirir autoridad por
  coincidencia.
- Journal estructuralmente válido pero no autenticado por una autoridad viva
  del proceso.
- Errores de tipo, rango, conversión, Unicode y nombres de artefactos.

### 2.2 Amenazas no cubiertas

F0 es un contrato Python, no una frontera de seguridad frente a código
arbitrario dentro del mismo proceso. No se garantiza protección contra código
que inspecciona y modifica módulos, globals, funciones privadas, el registro
de autoridades o los objetos en memoria. `frozen=True`, `NamedTuple`,
fingerprints y nombres privados no sustituyen un límite de proceso.

Tampoco se cubren:

- Recuperación entre reinicios.
- Coordinación multiproceso o multi-host.
- Persistencia de la unicidad de `txn_id`.
- Hardlinks, junctions, symlinks creados después de validar o carreras TOCTOU.
- Uso deliberado de la misma instancia de registro autorizada por código que
  ya controla el proceso. La autoridad se liga a la instancia, pero un
  atacante con acceso al proceso puede usar el objeto autorizado o modificar
  el registro en memoria. Esa frontera queda fuera de F0 y deberá ser tratada
  por F1 con persistencia y controles de proceso.

La limitación de código hostil no se usa para dejar bypasses accesibles por la
API contractual normal.

## 3. Autoridad, identidad y transacciones (D1)

### 3.1 Identidad

Cada transacción creada por `new_transaction()` recibe:

- `authority_id`: identificador opaco de la autoridad en memoria.
- `transaction_uid`: identidad única de la transacción, distinta de
  `txn_id` y del fingerprint del plan.

La autoridad se registra en `_AUTHORITIES` y queda ligada a:

- `txn_id`;
- fingerprint exacto del plan;
- `transaction_uid`;
- historial autorizado (`authorized_history`);
- referencias fuertes a registros autorizados (`authorized_records`);
- estado activo/inactivo.

`_authorize_record_instance()` conserva el propio objeto
`TransactionRecord` en `authorized_records`; `_check_authority()` exige que
alguna referencia autorizada sea el objeto recibido (`is`). No se guarda ni se
usa `id(record)` como capacidad: Python puede reutilizar ese entero después de
liberar el objeto. Una autoridad de otra transacción no se acepta aunque
coincidan `txn_id` y plan. `dataclasses.replace`, copias y reconstrucciones
manuales con todos los campos copiados son objetos distintos y no pueden
iniciar transiciones.

`new_transaction()` rechaza la reutilización de `txn_id` durante toda la vida
del proceso mediante `_USED_TXN_IDS`. No existe una operación de la API normal
que borre ese registro. Una vez que `_register_authority()` añade un ID, una
transición, una invalidación, un estado terminal o un fallo posterior al
registro no lo libera. La eliminación de una autoridad tras un error de
validación de su registro no elimina su `txn_id` usado.

La reproducción `new_transaction(plan) → reset_authority_registry() →
new_transaction(plan)` queda bloqueada: `reset_authority_registry()` ya no
existe en el módulo de producción. F0 mantiene unicidad por proceso; la
persistencia y la unicidad entre reinicios siguen pendientes de F1.

### 3.2 Historial autorizado

`_AuthorityState.authorized_history` empieza en `(prepared,)` y se amplía en
cada transición normal exitosa. Las transiciones que avanzan exigen:

- autoridad existente;
- correspondencia exacta con la transacción;
- estado activo;
- fingerprint del plan;
- que el historial del registro sea exactamente el historial autorizado
  actual.

`assert_committed()` aplica las mismas restricciones. Una copia antigua del
registro no puede continuar después de que la transacción haya avanzado; una
copia del registro actual puede reintentar su estado actual de forma
idempotente.

### 3.3 Invalidación CAS incondicional

En `transition()`, cuando la preimagen observada difiere de la declarada:

1. Se invalida primero la autoridad original.
2. Se fija su historial autorizado a `history + (cas_conflict,)`.
3. Solo después se construyen y validan los campos descriptivos del conflicto
   (`cas_conflict_reason`, `cas_conflict_at`, evidencia derivada).

Si la construcción del registro de conflicto falla por cualquier motivo, la
autoridad original permanece invalidada. Una excepción de validación no
reactiva la autoridad.

El mismo orden se aplica a la transición directa a `cas_conflict`: primero se
comprueba que existe una discrepancia real; si existe, se invalida antes de
validar los campos descriptivos. Si la preimagen coincide, se rechaza sin
invalidar.

### 3.4 Journal y autoridad

`journal_record_from_transaction()` incluye `authority_id` y
`transaction_uid` en el sobre y exige:

- registro validado;
- autoridad autenticable;
- historial autorizado compatible;
- que una autoridad inactiva solo pueda emitir los registros históricos de
  su conflicto (`prepared` y `cas_conflict`), nunca un commit.

`validate_journal_record(record, plan)` autentica la autoridad viva del
proceso, el `transaction_uid`, el `txn_id`, el fingerprint del plan y el
estado dentro del historial autorizado. Sin plan, la validación sigue siendo
estructural y **no autoriza recuperación**.

`validate_journal_chain(records, plan=...)` exige además:

- una única autoridad e identidad para toda la cadena;
- que los estados sean un prefijo exacto del historial autorizado;
- que una autoridad inactiva solo valide la cadena completa que termina en
  `cas_conflict`;
- que ninguna cadena convierta una transacción invalidada en `committed`.

Una cadena estructuralmente válida pero sin autoridad viva en el proceso se
rechaza cuando se aporta plan. `recovery_action()` devuelve `QUARANTINED` en
ese caso.

### 3.5 Límites de autoridad

La autoridad es en memoria, de proceso y ligada a instancias de registro. No
hay recuperación entre reinicios ni coordinación multiproceso. F1 deberá
persistir la identidad, la unicidad de `txn_id`, el historial y la
autenticación de journal, o cuarentenar lo que no pueda autenticar. La
identidad de instancia no se persiste: es una garantía de F0 en el proceso
actual, no una capacidad reutilizable tras reiniciar.

`authorized_records` conserva referencias fuertes a todos los registros
autorizados mientras la entrada de autoridad permanezca en `_AUTHORITIES`.
Esto evita que `id(record)` sea reutilizado para conferir autoridad a otra
instancia y permite serializar los frames históricos del journal. F0 no elimina
autoridades terminales durante la vida del proceso, por lo que el coste de
memoria crece con las transacciones y sus transiciones; F1 deberá definir una
política de persistencia/compactación que conserve la autenticación necesaria.
Una autoridad fallida durante la creación inicial se elimina junto con su
registro fallido.

## 4. Políticas efectivas y tipos (D4)

### 4.1 Política canónica

`TargetPolicy` es un `NamedTuple`: no tiene `__dict__`, por lo que
`object.__setattr__` no puede debilitar una instancia. Además, la fuente de
verdad interna no es el objeto público `TARGET_POLICIES`, sino
`_TARGET_POLICY_SPECS`, una representación de tuplas inmutables.

`_canonical_target_policy()` y `_canonical_snapshot_policy()` reconstruyen la
política desde esas especificaciones. `WriterDeclaration.validate()`,
`WritePlan.validate()`, `target_policy_fingerprint()` y
`plan_policy_fingerprint()` usan la representación canónica. Mutar o sustituir
un objeto de política público no debilita un plan nuevo ni un fingerprint.

### 4.2 Tipos aceptados

En puntos críticos se exige el tipo exacto, no `isinstance` ni duck typing:

- `WritePlan` exacto.
- `WriterDeclaration` exacta.
- `TargetPolicy` exacta.
- `LockPolicy` exacta.
- `TransactionRecord` exacto.

Se rechazan subclases de `WritePlan`, `WriterDeclaration`, `LockPolicy` y
`TransactionRecord` que puedan sustituir `validate()`, `as_dict()`,
fingerprints o serializadores. `new_transaction()` comprueba el tipo exacto
antes de llamar a `plan.validate()`, por lo que una subclase que no invoque el
validador original no puede entrar.

### 4.3 Vinculación del plan

`WritePlan.validate()` revalida en cada transición:

- `WriterDeclaration` exacta y validada;
- target exacto y operación permitida;
- política canónica efectiva;
- requisitos obligatorios de manifiesto y pins;
- `LockPolicy` efectiva y su fingerprint;
- correspondencia entre plan, declaración y target.

### 4.4 Manifiesto: destino de escritura declarado

Se resuelve la contradicción de F0.3 declarando que
`data/calibration_window.json` **sí es un target de escritura válido**, no solo
un artefacto protegido. Su política `manifest` exige lock, CAS, backup y
verificación de manifiesto, y no exige pins.

Cuando `target_path == TARGET_MANIFEST`:

- `manifest_path` debe ser el propio manifiesto;
- `manifest_expected_sha256` debe coincidir con `expected_pre_sha256`;
- `manifest_candidate_sha256` debe coincidir con `candidate_sha256`.

Así la política declarada es alcanzable y no queda una regla inalcanzable en
`TARGET_POLICIES`. Para targets que no son el manifiesto, `manifest_path` sigue
siendo `data/calibration_window.json` y la verificación es una precondición.

## 5. LockPolicy (D6)

`LockPolicy` exige un tipo exacto y valida en cada entrada crítica. El timeout:

- debe ser exactamente `int` o `float`, no `bool`, no subclase;
- debe ser finito y mayor que cero;
- para enteros, se convierte a `float` dentro de un `try` que captura
  `OverflowError`/`ValueError` y lo convierte en `WriteContractError`.

Por eso `10**1000`, `10**400`, `2**2000`, NaN, `+inf`, `-inf`, cero y negativos
son errores contractuales, no excepciones crudas.

Las subclases que anulan `validate()` o `as_dict()` se rechazan en
`WriterDeclaration.validate()`, `WritePlan.validate()` y
`lock_policy_fingerprint()`. El fingerprint se calcula con el `as_dict()` del
tipo exacto. Una mutación posterior de la política se detecta al revalidar el
plan y al comparar el fingerprint con la evidencia.

Los defaults de `WriterDeclaration` y `WritePlan` usan
`field(default_factory=LockPolicy)`, de modo que dos objetos no comparten
accidentalmente la misma instancia mutable.

## 6. Propiedad de backup y temporal (D5)

El esquema es inequívoco y usa el componente de identidad completo:

- Backup: `data/_backup/<txn_id>.jsonl`, directamente bajo `data/_backup/`.
- Temporal: `<directorio_del_target>/<nombre_del_target>.<txn_id>.tmp`, en el
  mismo directorio que el target.

`_check_backup()` exige que el padre canónico sea exactamente
`data/_backup` y que el nombre sea exactamente `txn_id + ".jsonl"`.
`_check_temp()` exige que el padre canónico sea el del target y que el nombre
sea exactamente `<nombre_target>.<txn_id>.tmp`.

No se usa pertenencia de `txn_id` como subcadena. `txn-f0` y
`txn-f0-other`, `txn-f0.other` o `txn-f0_other` no comparten backup ni
temporal. Se mantienen las comprobaciones de colisión con target, backup,
temporal, manifiesto, pins y snapshot.

Límites: F0 no resuelve hardlinks, junctions, symlinks creados después de
validar ni carreras TOCTOU. F1 debe abrir y verificar los objetos con las
garantías del sistema operativo.

## 7. Robustez contractual (D7 y D8)

### 7.1 D7 — Unicode y append

`append_content` debe ser exactamente `str`, no vacío, con LF y salto final.
La codificación UTF-8 se captura: un surrogate aislado produce
`WriteContractError`, no `UnicodeEncodeError`. Se mantienen las comprobaciones
de hash, bytes, líneas, frontera append y delta del candidato.

### 7.2 D8 — Pins literales

`pins_symbols` exige símbolos de tipo exacto `str`, no vacíos, sin espacios
iniciales ni finales y sin normalización silenciosa. Se mantienen cardinalidad
exacta, ausencia de duplicados y cobertura completa de `PINS_SYMBOLS`.

## 8. Validación parcial del journal (D2)

`validate_journal_record(record)` sin plan reconoce la estructura del sobre,
la cadena de hashes, la evidencia requerida y la coincidencia
`evidence.txn_id`. Sigue siendo una validación parcial: no autentica plan ni
autoridad y no autoriza recuperación.

Un registro `COMMITTED` mínimo sin plan puede ser estructuralmente reconocible,
pero:

- `recovery_action(records)` sin plan devuelve `QUARANTINED`;
- `validate_journal_record(record, plan)` rechaza la evidencia insuficiente;
- `recovery_action(records, plan=...)` devuelve `QUARANTINED`.

La validación estructural no se confunde con legitimidad de la transacción.

## 9. Estado global y aislamiento

`_AUTHORITIES` y `_USED_TXN_IDS` son estado de proceso. El contrato de
producción no ofrece una función de reset. El fixture autouse del arnés
reemplaza el comportamiento anterior de limpiar ambos registros en setup y
teardown, que eliminaba el estado previo sin restaurarlo. Ahora el fixture
conserva snapshots independientes (`dict` y `set`), instala contenedores
temporales vacíos para la prueba y restaura en `finally` el contenido previo y
las referencias a los contenedores originales. El snapshot conserva las
mismas instancias de autoridad y copia sus campos mutables y el contenido del
referencias a registros autorizados para restaurar la relación con `authority_id`,
`transaction_uid` y `txn_id`. La restauración ocurre también si la prueba
lanza una excepción. No se eliminan IDs usados al invalidar o
terminar una transacción; la operación de aislamiento está confinada al
arnés, no es una API de producción.

`TARGET_POLICIES` es un `MappingProxyType` de `TargetPolicy` inmutables.
`DEFAULT_LOCK_POLICY` sigue existiendo como referencia pública, pero los
objetos contractuales usan factories y no comparten la instancia.

F0 no implementa persistencia ni coordinación multiproceso.

## 10. Matriz D1–D10

La columna `Estado F0.7` describe la implementación y sus regresiones. No es
un cierre formal de F0: la reauditoría independiente debe verificar el estado
real del repositorio.

| Defecto | Estado F0.7 | Evidencia |
|---|---|---|
| D1 — Autoridad/CAS | `PARTIAL` | Referencias fuertes a instancias comparadas con `is` reemplazan `id(record)`; D1 completo sigue pendiente de reauditoría independiente. |
| D2 — Validador parcial | `CLOSED` | `validate_journal_record()` sin plan es estructural; `recovery_action()` sin plan cuarentena; test del `COMMITTED` mínimo. |
| D3 — Evidencia y transiciones | `CLOSED` | `REQUIRED_EVIDENCE`, `EVIDENCE_KEYS`, `_check_state_evidence()`, `transition()`, tests de estados y fault matrix. |
| D4 — Políticas inmutables | `CLOSED` | `TargetPolicy` `NamedTuple`, `_TARGET_POLICY_SPECS`, `_canonical_target_policy()`, tipos exactos, plan ligado a declaración/target/política/lock; manifiesto resuelto como target válido. |
| D5 — Propiedad backup/temp | `CLOSED` | `_check_backup()` y `_check_temp()` con nombre y padre exactos; tests de `txn-f0` frente a `txn-f0-other`, `.` y `_`. |
| D6 — LockPolicy | `CLOSED` | Validación de tipo/rango antes de conversión, `OverflowError` convertido, tipo exacto, fingerprint canónico, tests de enteros gigantes y subclases. |
| D7 — Unicode | `CLOSED` | `_check_append_content()` captura `UnicodeEncodeError`; test de surrogate aislado. |
| D8 — Pins literales | `CLOSED` | `_normalize_pins_symbols()` sin `strip()`; test de espacios iniciales/finales. |
| D9 — Canonicalización JSON | `CLOSED` | `_canonical_sha256()`/`journal_record_sha256()`; requisito F1 de `object_pairs_hook` documentado. |
| D10 — Límites y trazabilidad | `CLOSED` | Este documento, tests y restricciones explícitas; sin integración real. |

## 11. Trazabilidad defecto → implementación → regresión

| Defecto | Implementación | Regresiones principales |
|---|---|---|
| D1 reutilización de `id(record)` | Referencias fuertes en `authorized_records`; comparación de instancia con `is` | `test_d1_reconstruction_rejected_after_external_original_reference_dropped`, `test_d1_copies_and_reconstructions_are_not_authorized_instances`, `test_d1_authority_keeps_history_instances_alive_for_journal_lifecycle`, `test_d1_invalidated_authority_retains_only_real_conflict_instances` |
| D1 evidencia CAS malformada | `transition()` invalida antes de `_merge_evidence()`/`_validate_record()` | `test_d1_malformed_cas_conflict_evidence_still_invalidates`, `test_cas_conflict_invalidates_original_and_any_copy` |
| D1 autoridad de otra transacción | `transaction_uid` + `_check_authority()` | `test_d1_authority_from_another_transaction_cannot_be_borrowed` |
| D1 reutilización/reset de `txn_id` | `_USED_TXN_IDS` de vida de proceso, sin reset de producción; el arnés usa snapshot y restaura ambos registros en `finally` | `test_d1_txn_reset_audit_identifier_cannot_be_reused`, `test_d1_invalidation_does_not_release_txn_id`, `test_d1_normal_transition_does_not_release_txn_id`, `test_d1_terminal_transaction_does_not_release_txn_id`, `test_d1_failed_record_validation_still_burns_txn_id` |
| D1 journal/commit inválido | `_require_journal_authority()`, `_authenticate_journal_authority()`, `validate_journal_chain()` | `test_d1_invalidated_authority_cannot_emit_commit_journal_or_chain`, `test_d1_journal_chain_from_another_authority_is_rejected` |
| D1 copia/reconstrucción | Solo la instancia autorizada se admite; los frames se conservan para serializar journal histórico | `test_d1_copies_and_reconstructions_are_not_authorized_instances`, `test_d1_invalidated_authority_retains_only_real_conflict_instances`, `test_cas_conflict_invalidates_original_and_any_copy` |
| D4 mutación de `TargetPolicy` | `NamedTuple` + especificaciones canónicas | `test_d4_target_policy_is_immutable_and_canonical` |
| D4 subclases | `_require_exact_type()` en fronteras críticas | `test_d4_writeplan_subclass_cannot_override_validation`, `test_d4_writer_declaration_subclass_cannot_weaken_validation` |
| D4 manifiesto inalcanzable | `WritePlan.validate()` permite target manifiesto con hashes coherentes | `test_d4_manifest_target_is_writable_with_consistent_hashes` |
| D5 subcadena de `txn_id` | nombre y padre exactos | `test_d5_backup_and_temp_names_use_the_complete_txn_identity`, `test_d5_ambiguous_txn_identifiers_do_not_share_artifacts` |
| D6 enteros gigantes | conversión segura a `float` | `test_d6_huge_lock_timeouts_are_contract_errors_not_overflow` |
| D6 subclase de lock | tipo exacto + fingerprint canónico | `test_d6_lock_policy_subclass_cannot_forge_validation_or_fingerprint`, `test_mutated_lock_policy_is_rejected_at_all_entry_points` |
| D7 surrogate | captura de `UnicodeEncodeError` | `test_d7_lone_surrogates_are_contract_errors` |
| D8 espacios en pins | comparación literal | `test_d8_pins_symbols_are_literal_and_not_stripped` |
| D2 validador parcial | sin plan no autoriza recuperación | `test_d2_minimal_committed_record_is_partial_without_plan`, `test_journal_without_plan_is_structural_only_not_authorization` |
| Fixture/estado global | unicidad de vida de proceso; aislamiento por snapshot/reemplazo/restauración en `finally`, sin reset de producción | `test_fixture_restores_nonempty_registry_and_authority_identity`, `test_fixture_restores_both_registries_after_exception`, `test_fixture_preserves_an_initially_empty_state`, `test_fixture_scopes_isolate_tests_without_releasing_in_scope_ids` |

## 12. Clasificación de pruebas

1. **Contrato puro**: planes, políticas, declaraciones, lock, evidencia,
   estados, journal, canonicalización, Unicode, pins, nombres de artefactos.
2. **Simulación de fallos**: arnés de preimagen/postimagen, fault matrix,
   conflictos CAS, copias, autoridades inyectadas para simular el estado
   vulnerable anterior, cadenas de journal inválidas.
3. **Integración real**: **no incluida**. F0 no abre ni escribe `data/`, no
   crea mutex, journal, backup, temporal ni replace reales. No se declara
   integración real.

## 13. Comandos y resultados

Comandos requeridos para F0.7:

```text
python -B -m pytest motor/test_write_contract.py -q -p no:cacheprovider
python -B -m py_compile motor/write_contract.py motor/test_write_contract.py
git diff --check
```

Resultado de la suite: **109 passed**.

## 14. Integridad de `data/`

F0.7 no modifica `data/`, derivados, manifiestos, pins físicos ni
calibraciones. La verificación final de `git status --short -- data/` y
`git diff -- data/` debe quedar vacía; el informe de entrega registra el
resultado exacto.

## 15. Garantías reales y pendientes de F1

Garantías heredadas de F0.4–F0.6 y corrección de identidad F0.7:

- Ninguna ruta de la API normal alcanza `committed` con autoridad invalidada.
- Una autoridad no se reutiliza por coincidencia de `txn_id` y plan.
- Las transacciones nuevas no reutilizan `txn_id` dentro del proceso.
- Las políticas efectivas se reconstruyen desde una representación canónica.
- Las subclases críticas se rechazan.
- Backup y temporal usan el componente de identidad completo.
- Unicode y pins se validan literalmente.
- El journal no se confunde con autorización de recuperación.

Pendiente de F1:

- Persistencia de autoridades, historial y unicidad de `txn_id`.
- Recuperación entre reinicios y coordinación multiproceso.
- Mutex real, CAS físico, journal en disco, backup, temporal y replace.
- Verificación de hardlinks, junctions, symlinks y TOCTOU.
- Parser JSON estricto con `object_pairs_hook`.
- Integración real de writers y activación controlada.

## 16. Veredicto interno

`F0.7_LISTO_PARA_REAUDITORIA`

No se declara `F0_CERRADO` ni D1 `CLOSED`; la reauditoría independiente debe
confirmar el cierre. No se inicia F1.
