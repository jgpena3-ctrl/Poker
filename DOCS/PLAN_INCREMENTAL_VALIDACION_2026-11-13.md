# Plan incremental de corrección y validación HU/MW (2026-11-13)

**Estado:** plan. No implementa cambios, no escribe datos, no activa multiway.

**Regla de oro:** no se pasa a la fase siguiente por “pasar tests”. Cada fase
tiene validación mecánica, estadística y estratégica; ninguna de las tres
sustituye a las otras.

**Base:** commit `8197eee` y snapshot de
`DISCREPANCIAS_AUDITORIA_2026-11-13.md`.

**Orden:** primero HU; después MW read-only; al final política MW y activación.

## 0. Fase 0 — Auditoría reproducible (actual)

**Objetivo:** fijar qué se midió, con qué definición y sobre qué datos.

**Entregables:**

- `tools/auditar_estrategia_reproducible.py`.
- `DOCS/DISCREPANCIAS_AUDITORIA_2026-11-13.md`.
- `DOCS/INVENTARIO_DEFECTOS_ESTRATEGICOS_2026-11-13.md`.
- `DOCS/DEPENDENCIAS_HU_MW_2026-11-13.md`.
- `DOCS/DISENO_ARQUITECTURA_MULTIWAY_2026-11-13.md`.
- Este plan.

**Validación mecánica:** el script corre en limpio, imprime commit y hashes,
y no escribe en `data/`.

**Validación estadística:** las cifras reproducidas coinciden con su
denominador; las no reproducidas quedan marcadas.

**Validación estratégica:** ninguna. La fase 0 no demuestra calidad de
decisión.

**Salida:** inventario de discrepancias y defectos priorizado.

**No-go:** no se declara corregido ningún defecto; no se toca código; no se
activa nada.

## 1. Fase 1 — Paridad preflop HU

**Defectos:** D-01, D-02, D-03, D-04, D-11.

**Objetivo:** que live, entrenamiento y contrato usen la misma interpretación
de la primera decisión preflop.

**Trabajo de diseño (antes de tocar código):**

1. Fijar `PreflopDecision` canónico: acción, denominador, `raises_before`,
   `limps_before`, `callers_before`, `last_aggressor`, importe, categoría,
   estado y cobertura.
2. Decidir el tratamiento de `b` corto, `b` de apertura, `bb_check`, `limp`,
   `call_limp`, `squeeze`, `rol`, `fold_vs_open` y `fold_vs_3bet`.
3. Decidir qué pasa con `unresolved` (40 `check_non_bb`, 4 `unknown`): no se
   convierten en `open` por defecto.
4. Definir la política de cobertura: exacto, alias, gap, imposible,
   desconocido. Sin `or 0.0` silencioso.

**Implementación posterior (no ahora):**

- Una sola fuente de lectura preflop.
- La ruta live consume el contrato; la sombra legacy se conserva solo para
  comparación.
- El entrenamiento usa la etiqueta canónica; la legacy queda declarada.

**Validación mecánica:**

- Paridad por evento: misma categoría, denominador, `n`, `vs`, limp.
- 100 % de los eventos clasificados o explícitamente unresolved.
- Cero casos de `unknown` convertidos en `open`.
- Matriz de confusión legacy→canónico con conteos y denominadores.
- Casos límite: `b` ≤1 BB, `b` >1 BB, `b` después de `r`, `c` antes/después
  de `r`, `x` de BB, fold, squeeze.

**Validación estadística:**

- Frecuencias por categoría y denominador contra el contrato.
- Intervalos por bootstrap; no comparar porcentajes sin n.
- La diferencia de 54 etiquetas y 44 unresolved debe quedar explicada.

**Validación estratégica:**

- Comparar la tabla elegida y la acción resultante, no solo la etiqueta.
- Revisar una muestra estratificada de spots; el cambio debe ser explicable.
- No declarar mejora por AUC o log loss agregado.

**Criterio de salida:** paridad mecánica completa; discrepancias restantes
documentadas y aceptadas; revisión de que la acción no cambió sin justificación.

**Rollback:** mantener la lectura legacy detrás de un flag de comparación;
poder volver sin mezclar etiquetas.

**Riesgo:** cambiar una etiqueta puede cambiar la tabla y la acción. Es un
cambio de comportamiento, no un refactor cosmético.

## 2. Fase 2 — Cobertura y etiquetas HU

**Defectos:** D-04, D-11, D-12, D-14.

**Objetivo:** que cada spot declare si tiene tabla, alias, gap o imposible, y
que el entrenamiento no use etiquetas incompatibles.

**Trabajo:**

- Mapa de cobertura por `(acción, posición, vs)` y por `(denom, posición)`.
- Regla de decisión para `coverage_gap`: no recomendar, usar prior declarado o
  ampliar incertidumbre; nunca 0.
- Perfil con `source`, `n`, `confidence`; default `unknown`.
- Snapshot/versionado de datos y artefactos.

**Validación mecánica:**

- 1.080 `Call_OR` y 78 `4B/Call_3B` sin cobertura deben aparecer como tales.
- 69 fallback `other_vs` no pueden presentarse como exactos.
- Todo `prob_vec` no vacío; ningún cero silencioso.
- Todo perfil tiene fuente o `unknown`.

**Validación estadística:**

- Calibración por fuente de prior: exacta, alias, flat.
- Comparación contra baseline uniforme.
- Cobertura efectiva y `n_eff` por spot.
- No usar el 78,5 % como evidencia de calidad.

**Validación estratégica:**

- En spots sin cobertura, la salida debe ser conservadora o “no soportada”.
- Revisar que un `unknown` no se convierta en una acción segura falsa.

**Criterio de salida:** cobertura declarada en el 100 % de los spots; ningún
fallback silencioso; perfiles con procedencia.

## 3. Fase 3 — Equity actual, showdown y EV HU

**Defectos:** D-07, D-15.

**Objetivo:** separar tres conceptos que hoy se llaman “equity”.

**Trabajo:**

- `CurrentEquity`: board actual; sin runout.
- `ShowdownEquity`: runout; `n_runouts`, `n_combos`, seed, IC.
- `EvByAction`: árbol, fold/call/raise, side pots, stack efectivo.
- Etiquetar cada número con su fuente y su muestra.

**Validación mecánica:**

- Comparar Monte Carlo contra enumeración exacta en casos pequeños.
- Misma semilla y mismo `n` → mismo resultado.
- Un board de 3, 4 y 5 cartas no mezcla etiquetas.
- `fold` con EV real, no 0 inventado.
- EV no finito no se convierte en 0.

**Validación estadística:**

- Error estándar o IC por caso.
- Sensibilidad a seed y a `n_runouts`.
- No comparar 100 con 200 runouts sin declararlo.
- Casos flush draw, overpair, gutshot: reproducir 0,596207→0,726362;
  0,966235→0,855701; 0,181776→0,304762.

**Validación estratégica:**

- La decisión debe usar el objeto correcto: actual para lectura de calle,
  showdown para equidad final, EV para acción.
- Revisar que un cambio de equity no se compense con un sesgo de política.

**Criterio de salida:** tres campos separados y etiquetados; ningún consumidor
usa `equity` ambiguo.

## 4. Fase 4 — Sombra multiway read-only

**Defectos:** D-08, D-10, D-09.

**Objetivo:** medir qué cambiaría un modelo MW real sin activar ninguna
recomendación.

**Trabajo:**

- `MultiwayRangeSet` con un rango por rival.
- `primary_opponent` solo para presentación; la decisión usa el conjunto.
- `union()` queda como baseline etiquetado, no como equity.
- Sombra: calcular `current_equity` y `showdown_equity` MW y compararlas con la
  ruta HU actual, sin cambiar la acción.

**Validación mecánica:**

- Todo spot `n_players>2` tiene conjunto de rivales, no un ID.
- Blockers compartidos; ningún combo imposible.
- `union` no se usa en la ruta de decisión.
- La sombra no escribe en la base de decisiones ni cambia la acción.

**Validación estadística:**

- Diferencia de equity MW vs baseline, con IC.
- Cobertura por rival y por spot.
- Sensibilidad al modelo de correlación (independiente, latente, etc.).
- No usar una muestra sintética para inflar el denominador real.

**Validación estratégica:**

- Comparar acciones contrafactuales, no solo equity.
- Identificar spots donde la decisión HU cambia; revisar una muestra.
- Si el cambio no es explicable, la sombra no está lista.

**Criterio de salida:** sombra reproducible, con etiqueta `correlation_model`,
`n_samples`, seed e IC; `MULTIWAY_SOPORTADO` sigue en `False`.

## 5. Fase 5 — Equity y EV multiway

**Objetivo:** pasar de una sombra de equity a un EV MW defendible.

**Trabajo:**

- Muestreo conjunto de rivales; side pots; empates; stacks.
- EV por acción con fold/call/raise/all-in.
- Incertidumbre de rango y de runout.
- Comparación contra baselines: un rival, unión, independencia.

**Validación mecánica:**

- Conservación de bote y stacks.
- Side pots correctos en casos construidos.
- Un rival con un solo combo no rompe la normalización.
- Empates repartidos; no duplicar masa.

**Validación estadística:**

- Calibración de equity MW en muestras held-out.
- Brier/log loss por calle y por número de rivales.
- IC de la diferencia de EV; no solo media.
- Tamaño de muestra mínimo por celda; celdas vacías declaradas.

**Validación estratégica:**

- EV vs baselines y vs política HU; no basta ganar en promedio.
- Revisar robustez a errores de rango y a la correlación.
- No declarar “mejor” con una muestra pequeña o con leakage.

**Criterio de salida:** EV MW con supuestos explícitos y error medido.

## 6. Fase 6 — Política MW y activación

**Objetivo:** decidir si existe una política MW, no solo una equity MW.

**Trabajo:**

- Reglas MW propias; `n_players` + conjunto de rangos.
- `range_advantage`/`nut_advantage` sobre el conjunto; `UNKNOWN` si falta.
- `multiway_soportado` visible en la salida.
- Comparación contra política HU y baselines.

**Validación mecánica:**

- Ningún spot MW usa una regla HU sin declararlo.
- `select_best` no inventa fold.
- La salida incluye fuente, cobertura, muestra, seed y versión.
- Rollback probado.

**Validación estadística:**

- Held-out por sesión, no por mano.
- Calibración y EV con IC.
- Sin leakage de resultados.
- Estabilidad entre ventanas.

**Validación estratégica:**

- Comparación con agentes controlados y con baselines.
- Revisión de casos extremos: 3-way, 4-way, side pots, all-in.
- No activar por una métrica única.

**Criterio de activación:** G0–G8 del diseño cumplidas; revisión independiente;
`MULTIWAY_SOPORTADO` solo entonces.

**Rollback:** flag de activación, ruta HU intacta, logs comparables.

## 7. Matriz de validación

| Nivel | Qué prueba | Qué no prueba |
|---|---|---|
| Mecánico | contrato, paridad, cobertura, invariantes, side pots | calidad estadística |
| Estadístico | calibración, IC, error, held-out | optimalidad estratégica |
| Estratégico | EV vs baseline, robustez, casos extremos | garantía universal |

Un cambio solo pasa si:

1. La validación mecánica es completa.
2. La validación estadística tiene muestra y denominador declarados.
3. La validación estratégica muestra una mejora explicable o, como mínimo,
   ausencia de degradación justificada.
4. El rollback funciona.
5. La trazabilidad de datos y código está registrada.

## 8. Datos dinámicos y regeneración

- Toda fase se ejecuta sobre un snapshot con hash.
- Si cambia `hands_db.jsonl`, se repite la auditoría y se anota la diferencia.
- No se regeneran `profile_ranges`, `postflop_ranges`, `behavior` ni matrices
  sin justificación y sin registrar la cadena de dependencia.
- Una corrección histórica no se propaga automáticamente a artefactos.
- Los datos sintéticos solo se usan para tests controlados y se etiquetan; no
  se mezclan con el denominador real.

## 9. Entregables de esta fase

- Auditoría reproducible y discrepancias documentadas.
- Inventario de defectos priorizado.
- Mapa de dependencias HU/MW.
- Diseño conceptual de arquitectura.
- Este plan.
- Sin cambios en `motor/`, `data/` ni `MULTIWAY_SOPORTADO`.

## 10. Fuera de alcance

- Implementar la arquitectura completa.
- Activar `MULTIWAY_SOPORTADO`.
- Escribir recomendaciones experimentales en la base.
- Regenerar modelos o matrices.
- OCR, recorder o captura.
- Declarar una corrección por pasar tests.
