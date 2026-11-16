# Validación estratégica HU — Fase 8
## Certificación de preparación del piloto prospectivo HU

Fecha: 2026-11-15

## 1. Estado inicial verificado

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 142 passed, 1 skipped, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.

## 2. Pruebas de terminación abrupta

Se ejecutó un proceso hijo que registró una predicción, adquirió el bloqueo y fue terminado forzosamente.

Resultado:
- El archivo conservó el evento válido.
- El bloqueo quedó obsoleto.
- Un nuevo escritor pudo adquirir el bloqueo tras verificar que el PID ya no estaba vivo.
- El registro restaurado/leído permaneció íntegro.

Plataforma probada: Windows. Otras plataformas no se probaron en esta fase.

## 3. Pruebas de interrupción de escritura

Casos verificados:
- Registro íntegro: OK.
- Hash alterado: detectado.
- Evento truncado: detectado.
- Evento malformado: detectado.
- Fallo de escritura: sin registro parcial.
- Repetición de lectura: sin mutación de bytes.

La atomicidad lógica se verifica por validación previa. La atomicidad física depende del sistema de archivos y se documenta como limitación.

## 4. Prueba integral sintética

Ciclo ejecutado:
1. Crear registro.
2. Escribir predicción.
3. Verificar integridad.
4. Escribir resultado posterior.
5. Verificar integridad.
6. Crear respaldo.
7. Verificar respaldo.
8. Restaurar a ubicación distinta.
9. Verificar registro restaurado.
10. Comparar hashes de eventos.
11. Comprobar que la predicción original no cambió.
12. Comprobar que el registro original permanece disponible.

Resultado: OK, reproducible mediante tests automatizados.

## 5. Auditoría de recuperación

Verificado:
- Respaldo corrupto detectado.
- Hash lateral ausente o alterado detectado.
- Destino de restauración existente rechazado.
- Restauración a ubicación nueva exitosa.
- Igualdad de hashes antes y después.
- Rechazo de sobrescritura accidental.
- Preservación de eventos válidos anteriores.

No se implementó reparación automática. La recuperación requiere intervención explícita.

## 6. Auditoría de aislamiento

El prototipo `motor/hu_prospective.py` solo importa bibliotecas estándar. No importa ni llama a:

- `motor/asistente_live.py`
- serving
- recorder
- OCR
- captura
- writers históricos
- `data/hands_db.jsonl`

No hay integración automática con el motor. No hay captura automática. No hay escrituras en `data/`.

## 7. Protocolo operativo definitivo

### Inicio
1. Seleccionar ruta explícita fuera de `data/`.
2. Verificar que no es una ubicación protegida.
3. Comprobar integridad si el archivo existe.
4. Comprobar ausencia de otro escritor.
5. Registrar sesión, versión y referencia de datos.

### Durante la sesión
1. Registrar predicciones antes de observar acciones posteriores.
2. No completar retrospectivamente información ausente.
3. Añadir resultados como eventos separados.
4. Marcar oportunidades no evaluables.
5. No corregir ni sobrescribir eventos anteriores.

### Cierre
1. Liberar escritor.
2. Verificar integridad completa.
3. Crear respaldo.
4. Verificar respaldo.
5. Registrar conteos y hashes.
6. Documentar errores y eventos no evaluables.

### Recuperación
1. Detener nuevas escrituras ante cualquier corrupción.
2. Preservar el archivo original.
3. Verificar copias antes de restaurar.
4. Restaurar a ubicación nueva siempre que sea posible.
5. Registrar toda intervención manual.

## 8. Criterios de parada

Parada inmediata si ocurre:
- Hash incorrecto.
- Evento truncado.
- Referencia inconsistente.
- Identificador duplicado.
- Segundo escritor detectado.
- Ruta protegida.
- Esquema desconocido.
- Fallo de respaldo.
- Fallo de restauración.
- Ausencia de procedencia de una predicción.
- Imposibilidad de demostrar que los datos estaban disponibles en el instante de decisión.

## 9. Diseño de muestra

Sin iniciar recopilación real, se definen los principios:
- Solo HU.
- Separar posiciones y situaciones preflop/postflop.
- Separar entrenamiento, calibración y evaluación por tiempo o grupo.
- Preservar casos no evaluables.
- No confundir manos, decisiones, oportunidades de respuesta y observaciones independientes.
- Respetar el sesgo de disponibilidad de cartas y showdown.

Los tamaños muestrales deben derivarse de la precisión pretendida, la variabilidad y la dependencia de las observaciones. No se establecen umbrales universales.

## 10. Matriz de certificación

| Requisito | Estado | Evidencia |
|---|---|---|
| Registro append-only | CERTIFICADO | Tests y prueba integral |
| Identificadores únicos | CERTIFICADO | `test_duplicate_event_id` |
| Referencias válidas | CERTIFICADO | `test_outcome_requires_prediction` |
| Orden temporal | CERTIFICADO | `test_outcome_timestamp_order` |
| Campos ausentes permitidos | CERTIFICADO | `test_missing_fields_allowed` |
| Unknown no convertido a cero | CERTIFICADO | `test_unknown_values_not_converted` |
| Probabilidades inválidas rechazadas | CERTIFICADO | `test_invalid_probability` |
| Valores económicos incoherentes rechazados | CERTIFICADO | `test_incoherent_economics` |
| Evento malformado detectado | CERTIFICADO | `test_malformed_event` |
| Fallo de escritura sin parcial | CERTIFICADO | `test_write_failure_no_partial` |
| Eventos anteriores intactos | CERTIFICADO | `test_previous_events_intact` |
| Reproducción sin mutación | CERTIFICADO | `test_reproduce_without_modifying_bytes` |
| Datos posteriores rechazados | CERTIFICADO | `test_no_future_data_in_prediction`, `test_nested_future_data_rejected` |
| Rutas protegidas rechazadas | CERTIFICADO | `test_reject_protected_path`, `test_symlink_to_protected_data_rejected` |
| Hash canónico | CERTIFICADO | `test_canonical_hash_present` |
| Verificación de integridad | CERTIFICADO | `test_verify_integrity_ok`, `test_verify_detects_hash_tampering`, `test_verify_detects_truncated_event` |
| Bloqueo de segundo escritor | CERTIFICADO | `test_second_writer_rejected` |
| Copia de seguridad | CERTIFICADO | `test_backup_and_restore` |
| Restauración | CERTIFICADO | `test_backup_and_restore`, `test_restore_rejects_existing_destination` |
| Copia corrupta detectada | CERTIFICADO | `test_backup_corrupt_rejected` |
| Aislamiento de live/serving | CERTIFICADO | Inspección de imports y dependencias |
| Aislamiento de datos/artefactos | CERTIFICADO | Rutas protegidas y pruebas |
| Sin multiway | CERTIFICADO | `MULTIWAY_SOPORTADO=False` |
| Sin validación estratégica | CERTIFICADO | No se declaró rentabilidad |

## 11. Riesgos pendientes

- La atomicidad física depende del sistema de archivos.
- La concurrencia no está garantizada en todos los entornos.
- No existe protección criptográfica.
- No hay verificación automática de hash en lectura ordinaria.
- La recuperación puede requerir intervención manual.
- No existe aún evidencia real suficiente para validar rangos, equity o estrategia.

## 12. Recomendación final

El prototipo supera la certificación técnica de preparación para un piloto manual.

Sin embargo, no se autoriza todavía:
- registro de manos reales;
- integración con live/serving;
- validación estratégica;
- producción.

La siguiente decisión debe ser explícita y autorizar, si procede, un piloto manual read-only con observaciones reales.

## Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 142 passed, 1 skipped, 1 xfailed.
- `py_compile`: OK.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección o fase posterior.