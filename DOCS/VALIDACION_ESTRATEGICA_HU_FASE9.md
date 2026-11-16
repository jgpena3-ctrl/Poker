# Validación estratégica HU — Fase 9
## Piloto prospectivo HU con registro manual de observaciones reales

Fecha: 2026-11-15

## 1. Estado inicial verificado

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 142 passed, 1 skipped, 1 xfailed.
- `git diff --check`: OK.
- `MULTIWAY_SOPORTADO=False`.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.

## 2. Auditoría F9-A

Se verificó el protocolo y el prototipo prospectivo:

- Inicialización y verificación de integridad: implementado y probado.
- Registro de predicciones antes de acciones posteriores: implementado.
- Registro posterior de resultados sin alterar la predicción original: implementado.
- Validación de IDs y referencias: implementado.
- Detección de duplicados: implementado.
- Validación temporal y prevención de fuga: implementado.
- Bloqueo de escritor único: implementado.
- Verificación al cierre: implementado.
- Backup y comprobación de backup: implementado.
- Restauración sin sobrescribir original: implementado.

No se detectaron defectos críticos ni carencias que impidan cumplir los requisitos del piloto.

No se realizaron cambios de código en esta fase.

## 3. Capacidad del esquema

El esquema permite registrar:

- Oportunidades evaluables y no evaluables.
- Decisiones resueltas, unresolved y no_decision.
- Cobertura exacta, parcial, desconocida e imposible.
- Procedencia y naturaleza de rangos.
- Predicciones de respuesta y probabilidades.
- Equity, definición y método.
- EV por acción y supuestos.
- Acción recomendada y alternativas.
- Información posterior y resultado.
- Motivos de exclusión.

No exige introducir datos que el usuario no pueda observar o conocer legítimamente en el momento de la decisión.

No permite completar retrospectivamente predicciones, probabilidades, rangos o EV.

## 4. Protocolo operativo del piloto

1. Seleccionar ruta explícita fuera de `data/`.
2. Verificar integridad inicial.
3. Registrar la predicción antes de conocer la acción posterior.
4. Añadir el resultado como evento separado.
5. Marcar oportunidades no evaluables con motivo.
6. No corregir ni sobrescribir eventos anteriores.
7. Crear y verificar backup al cierre.
8. Documentar errores y exclusiones.

## 5. Criterios de inclusión, exclusión y parada

Inclusión:
- Oportunidades HU reales observadas desde el inicio del piloto.
- Contextos con información suficiente para registrar la predicción.
- Casos evaluables y no evaluables.

Exclusión:
- Oportunidades con fuga temporal.
- Registros duplicados no explicados.
- Falta de procedencia de la predicción.
- Imposibilidad de demostrar que los datos estaban disponibles en el instante de decisión.

Parada inmediata:
- Hash incorrecto.
- Evento truncado.
- Referencia inconsistente.
- Identificador duplicado.
- Segundo escritor detectado.
- Ruta protegida.
- Esquema desconocido.
- Fallo de respaldo.
- Fallo de restauración.
- Ausencia de procedencia.
- Fuga temporal.

## 6. Estado del piloto

No se registraron observaciones reales en esta fase.

Estado del piloto: **preparado, no iniciado**.

No se inventaron datos ni se generaron registros ficticios.

## 7. Limitaciones y métricas pendientes

- No se puede calcular calibración sin denominadores suficientes.
- No se puede declarar calidad estratégica sin referencias independientes.
- No se puede declarar rentabilidad.
- No se puede validar superioridad de una acción sin evidencia suficiente.
- Los tamaños de muestra deben justificarse por métrica y población.

## 8. Veredicto separado

- Preparación técnica: satisfactoria.
- Integridad del registro: satisfactoria.
- Evidencia estratégica: no demostrada.
- Rentabilidad: no demostrada.

## 9. Verificación final

- HEAD: `eaeac112cc9ae461493a87e27bfd124a3d0c8678`
- SHA-256 de `data/hands_db.jsonl`: `3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E`
- Suites HU: 142 passed, 1 skipped, 1 xfailed.
- `py_compile`: OK.
- `git diff --check`: OK.
- Sin cambios en live/serving, datos, artefactos, pines ni PR-03.
- Sin commits.

La fase termina aquí. Se requiere autorización explícita para iniciar el registro real o cualquier corrección posterior.