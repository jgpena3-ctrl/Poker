# Validación estratégica HU — Fase 6
## Auditoría adversarial independiente del registro prospectivo

Fecha: 2026-11-15

## 1. Alcance de la auditoría

Se intentó romper deliberadamente el prototipo `motor/hu_prospective.py` sin modificar contratos HU aceptados ni activar funcionalidades operativas.

Áreas auditadas:
- Persistencia append-only.
- Rutas protegidas.
- Identificadores duplicados.
- Inmutabilidad de predicciones.
- Orden temporal.
- Campos ausentes y valores desconocidos.
- Probabilidades inválidas.
- Valores económicos incoherentes.
- Eventos malformados.
- Fallos de escritura.
- Integridad de eventos anteriores.
- Reproducción sin modificar bytes.
- Datos posteriores en predicciones, incluyendo anidamiento.
- Enlaces simbólicos hacia datos protegidos.
- Integridad del hash canónico.

## 2. Defectos encontrados y corregidos

### F6-001 — Datos posteriores anidados no detectados

- Tipo: `DEFECTO_MECANICO`
- Evidencia: una predicción podía incluir `metadata={"nested": {"final_pot": 100.0}}` sin rechazo.
- Impacto: permitía contaminar una predicción con información futura.
- Corrección: validación recursiva de claves prohibidas en cualquier nivel del payload.
- Prueba: `test_nested_future_data_rejected`.

### F6-002 — Resolución de rutas protegidas dependiente del directorio actual

- Tipo: `DEFECTO_MECANICO`
- Evidencia: `_safe_storage_path` usaba `Path.cwd()` para identificar `data/`.
- Impacto: la protección podía variar según el directorio de ejecución.
- Corrección: la protección se basa en la raíz del proyecto calculada desde el módulo.
- Prueba: `test_symlink_to_protected_data_rejected` (skip si no hay soporte de enlaces).

## 3. Garantías demostradas

| Intento adversarial | Resultado |
|---|---|
| Registrar resultado sin predicción | Rechazado |
| Identificador duplicado | Rechazado |
| Sobrescribir predicción | Rechazado por append-only |
| Timestamp inválido | Rechazado |
| Probabilidades inválidas | Rechazado |
| Valores económicos negativos | Rechazado |
| Evento malformado | Rechazado |
| Fallo de escritura | Sin registro parcial |
| Eventos anteriores alterados | No observado |
| Lectura modifica bytes | No observado |
| Datos posteriores en predicción | Rechazado |
| Datos posteriores anidados | Rechazado tras corrección |
| Ruta protegida | Rechazado |
| Enlace simbólico a dato protegido | Rechazado si está soportado |

## 4. Limitaciones demostradas

### F6-003 — Verificación de hash no automática

- Tipo: `LIMITACION_DE_COBERTURA`
- Evidencia: `read_events()` no recalcula ni compara `canonical_hash`.
- Impacto: una alteración externa del archivo no se detecta al leer.
- Decisión: no se implementó verificación automática en esta fase; se documenta como limitación.
- Mitigación futura: añadir verificación explícita de integridad en una fase posterior, si se autoriza.

### F6-004 — Atomicidad limitada

- Tipo: `LIMITACION_DE_COBERTURA`
- Evidencia: la escritura se realiza en una operación `write`, seguida de `flush` y `fsync`.
- Impacto: una interrupción durante la escritura puede dejar una línea parcial.
- Decisión: no se implementó escritura atómica por append en esta fase.
- Mitigación futura: usar un protocolo de escritura temporal y append controlado, si se autoriza.

### F6-005 — Concurrencia no soportada

- Tipo: `LIMITACION_DE_COBERTURA`
- Evidencia: no hay bloqueos entre procesos.
- Impacto: escrituras concurrentes pueden entrelazarse.
- Decisión: documentada como fuera de alcance.

### F6-006 — Sin protección criptográfica

- Tipo: `LIMITACION_DE_COBERTURA`
- Evidencia: el hash demuestra integridad respecto del contenido hasheado, no autenticidad.
- Impacto: un atacante con acceso al archivo puede reescribirlo y recalcular hashes.
- Decisión: no se implementó firma ni protección criptográfica.

## 5. Clasificación de hallazgos

| ID | Tipo | Escenario | Impacto | Severidad |
|---|---|---|---|---|
| F6-001 | DEFECTO_MECANICO | Datos posteriores anidados | Contaminación de predicción | Media |
| F6-002 | DEFECTO_MECANICO | Ruta protegida dependiente del cwd | Bypass potencial de protección | Media |
| F6-003 | LIMITACION_DE_COBERTURA | Hash no verificado automáticamente | Alteración externa no detectada | Media |
| F6-004 | LIMITACION_DE_COBERTURA | Atomicidad limitada | Línea parcial ante interrupción | Baja |
| F6-005 | LIMITACION_DE_COBERTURA | Concurrencia no soportada | Entrelazado de escrituras | Baja |
| F6-006 | LIMITACION_DE_COBERTURA | Sin protección criptográfica | Reescritura con hash recalculado | Media |

No se encontraron bypasses que permitan sobrescribir una predicción mediante la API del prototipo.

## 6. Pruebas ejecutadas

- `motor/test_hu_prospective.py`: 19 passed, 1 skipped.
- Conjunto HU incluyendo el prototipo: 133 passed, 1 xfailed, 1 skipped.
- `py_compile`: OK.
- `git diff --check`: OK.

## 7. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

El prototipo supera la auditoría adversarial básica, con dos defectos mecánicos corregidos y cuatro limitaciones documentadas.

La fase termina aquí. Se requiere autorización explícita para cualquier corrección, piloto o fase posterior.