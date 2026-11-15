# Matriz de pruebas y aceptación (2026-11-13)

**Estado:** diseño. No implementa tests, no modifica `motor/`, no escribe `data/` y no valida una versión nueva.

**Objetivo:** convertir los contratos y escenarios de referencia en criterios verificables para aceptar o rechazar cada etapa de la migración, sin confundir paridad mecánica, calidad estadística y mejora estratégica.

Esta matriz define pruebas futuras. No afirma que los tests existan, que hayan sido ejecutados ni que el código actual cumpla los criterios.

---

## 1. Capas y dependencias

```text
Contrato preflop y estado
    ├── Ambigüedad y secuencia
    ├── Escenarios de referencia
    │     ├── Cobertura
    │     └── Rango y prior
    │           ├── Equity
    │           └── EV
    │                 └── Multiway sombra
    │
    ├── Migración y compatibilidad
    │     └── Shadow / rollback
    │
    └── Evaluación estadística y estratégica
```

Las capas tienen dependencias, pero no forman una única cadena en la que cualquier fallo bloquee indiscriminadamente todas las demás.

Reglas:

1. Un fallo del contrato preflop bloquea cualquier consumidor que dependa de él.
2. Un fixture sin materialización verificable no puede utilizarse como prueba ejecutable.
3. Un fallo de cobertura bloquea el uso de esa consulta como evidencia exacta.
4. Un fallo de rango bloquea los cálculos de equity y EV que dependan de ese rango.
5. Un fallo de equity bloquea los EV que la utilicen.
6. Un fallo de distribución conjunta bloquea la equity y el EV MW afectados.
7. Un fallo de migración bloquea esa migración, pero no invalida automáticamente pruebas independientes de contrato, rango o equity.
8. Un fallo estratégico no se compensa con pruebas mecánicas verdes.
9. Una prueba de una capa superior no puede anular un fallo de una dependencia inferior.

Cada prueba debe declarar su tipo:

- `unit`: comportamiento aislado;
- `contract`: cumplimiento de una interfaz o invariante;
- `fixture`: escenario de referencia reproducible;
- `statistical`: propiedades estadísticas;
- `strategic`: evaluación de calidad de decisión;
- `integration`: interacción entre componentes;
- `regression`: ausencia de cambios no autorizados.

---

## 2. Matriz de pruebas

### 2.1 Contrato preflop

La categoría describe el estado de decisión del héroe antes de actuar. La acción observada del héroe se registra separadamente.

| ID | Fixture / entrada | Esperado | Nivel |
|---|---|---|---|
| PRE-001 | R01–R17 materializados | Estado, categoría, plan y consulta de rango según contrato; acción observada separada | fixture |
| PRE-002 | `UTG b 2.5` en unopened pot | Spot `OPEN`; acción observada open; `raise_number=1`; agresor UTG | unit |
| PRE-003 | `MP b 1.0` en unopened pot, con BB=1 | Spot de limp; `short_limp=True`; no cuenta como raise | unit |
| PRE-004 | UTG completa como limp; MP foldea antes de cualquier subida | MP no se clasifica `fold_vs_open`; se conserva el contexto de limp | unit |
| PRE-005 | Open + caller; BB hace raise | Spot de squeeze; acción observada squeeze; no se etiqueta como 3bet ordinaria sin distinguir el caller | unit |
| PRE-006 | Uno o más limpers; SB hace raise | Spot ROL; no se clasifica como open | unit |
| PRE-007 | Open + 3bet; héroe CO hace raise | Spot `FACING_3BET`; acción observada 4bet; contador de raises coherente con open, 3bet y 4bet | unit |
| PRE-008 | Héroe BTN enfrenta 3bet y hace call | Spot `FACING_3BET`; acción observada call; plan de respuesta a 3bet, no de respuesta a 4bet | unit |
| PRE-009 | Héroe BTN enfrenta 4bet y hace raise | Spot `FACING_4BET`; acción observada 5bet; plan 5B/Call_4B si existe cobertura válida | unit |
| PRE-010 | Héroe enfrenta 5bet y hace raise | Acción observada 6bet; categoría/plan fuera de soporte si el contrato no contempla ese nivel | unit |
| PRE-011 | BB llega a su opción sin subida vigente y hace check | Spot `CHECK_BB`; acción observada check; consulta de rango según aplicabilidad, no `no_range` por defecto | unit |
| PRE-012 | BTN hace check en un contexto donde no puede hacerlo legalmente | Secuencia inválida o contaminada; no se inventa un spot válido | unit |
| PRE-013 | BB aparece haciendo check mientras existe una subida vigente que debe igualar | Acción ilegal o secuencia contaminada; `unresolved`, sin plan | unit |
| PRE-014 | Mano sin primera acción voluntaria del héroe | `status=no_decision`; no se genera `decision_plan`; no se genera `range_query`; no se genera etiqueta de entrenamiento; no se genera acción de serving | unit |
| PRE-015 | Primera acción voluntaria del héroe existe, pero falta información para resolver el contexto | `status=unresolved`; no se transforma en `no_decision`; no se inventa una acción ni se activa un fallback que convierta la incertidumbre en una decisión | unit || PRE-018 | `p` como evento inicial | Evento de posta; `non_decision`; nunca limp ni acción voluntaria | unit || PRE-019 | BB registra dos posts BB en el mismo prefijo | Post duplicado/anómalo; secuencia contaminada; sin plan | unit || PRE-016 | BB puede hacer check después de limpers | Spot de opción BB; distinguir check de ROL; no clasificar como unopened automáticamente | unit |
| PRE-017 | Acción agresiva con incremento válido después de open y 3bet | Contador de raises y categoría coherentes con el nivel enfrentado | unit |

Los fixtures deben especificar posición, secuencia completa, ciegas, importes y acción previa al héroe. Una secuencia abreviada no basta para validar una clasificación contextual.

### 2.2 Ambigüedad y secuencia

| ID | Entrada | Esperado |
|---|---|---|
| AMB-001 | Importe ausente en evento que lo requiere | `unresolved`; razón `importe_ausente`; sin plan |
| AMB-002 | Importe cero en evento que exige contribución positiva | `unresolved`; razón `importe_cero`; sin plan |
| AMB-003 | Acción desconocida | `unresolved`; razón `accion_desconocida` |
| AMB-004 | Posición ausente cuando es necesaria | `unresolved`; razón `pos_ausente` |
| AMB-005 | Raise sin incremento respecto al nivel vigente | `unresolved`; razón `subida_sin_incremento` |
| AMB-006 | Secuencia contaminada antes de la decisión | No hereda una categoría anterior; estado `unresolved` |
| AMB-007 | No existe primera decisión voluntaria del héroe | `sin_decision`; no se crea una decisión ficticia |
| AMB-008 | Dos eventos incompatibles en el mismo orden | Secuencia contaminada; no se selecciona uno arbitrariamente |
| AMB-009 | `p` sin evidencia suficiente para identificar el tipo de post | Evento desconocido/posta no clasificada; no se convierte en voluntaria |
| AMB-010 | Precisión del importe desconocida | No se compara como si fuera una cantidad exacta |
| AMB-011 | Importe cuantizado exactamente representable | Se conserva la cuantización declarada; no se confunde con incertidumbre de medición |
| AMB-012 | Falta información de button/seat order requerida | Orden no evaluable; no se inventa orden legal |
| AMB-013 | Acción posterior a fold del mismo jugador | Secuencia contaminada o evento inválido según contrato |
| AMB-014 | Jugador all-in vuelve a actuar | Secuencia inválida; no se procesa como acción legal |

### 2.3 Cobertura

La cobertura se determina para una consulta contextual completa. Una clave ausente no demuestra por sí sola que la situación sea imposible.

| ID | Consulta | Esperado |
|---|---|---|
| COV-001 | Clave exacta existente | `exact`; `source_key` identificada |
| COV-002 | Consulta con alias documentado | `alias`; `alias_of` y origen visibles |
| COV-003 | `Call_OR` sin tabla ni alias válido | `coverage_gap`; no se trata como exacta |
| COV-004 | Consulta `OR_BB` sin limpers y con estado unopened | `impossible` solo si el contrato contextual demuestra que no existe esa decisión |
| COV-005 | BB con limpers y opción de check o ROL | Se evalúa el spot contextual; no se declara `OR_BB` imposible de forma universal |
| COV-006 | `4B BTN vs CO` con fallback `other_vs` | `coverage_gap` y fallback explícito; nunca `exact` |
| COV-007 | Acción sin posición necesaria | `unknown`; no `coverage_gap` por defecto |
| COV-008 | Lookup con alias | `alias_of` visible y trazable |
| COV-009 | Celda gap en entrenamiento | Excluida o marcada como gap; nunca convertida en frecuencia cero |
| COV-010 | Combinación de consultas con estados distintos | Agregado conserva cada estado y aplica una regla de combinación explícita |
| COV-011 | Consulta con estado legal no reconstruible | `unknown` o `unsupported`; no `impossible` por ausencia de clave |
| COV-012 | Tabla exacta con snapshot distinto | No se presenta como cobertura exacta del snapshot actual sin validar compatibilidad |

Las pruebas deben distinguir:

- `exact`;
- `alias`;
- `coverage_gap`;
- `impossible`;
- `unknown`.

`fallback_other_vs` no es un sexto estado de cobertura. Es un mecanismo de fallback que debe conservar el estado `coverage_gap`.

### 2.4 Escenarios de referencia

| ID | Fixture | Esperado |
|---|---|---|
| SCN-001 | R01–R14, una vez materializados | Categorías, estados y planes conforme a la especificación; no asumir que todos tienen tabla utilizable |
| SCN-002 | R15–R17 | No inventar plan; distinguir unresolved, no decision y consulta no aplicable |
| SCN-003 | R02/R04/R07 | `Call_OR` gap; no usar como exacta |
| SCN-004 | R11/R12 | Distinguir gap sin fallback y gap con fallback |
| SCN-005 | S01–S07 | Casos límite sin categoría inventada |
| SCN-006 | S08–S13 | Niveles de apuesta, acciones observadas y spots enfrentados coherentes |
| SCN-007 | L01–L05 | Alias, impossible, gap, fallback y unknown diferenciados |
| SCN-008 | Fixture sin hash o fuente verificable | `needs_source_materialization`; no se usa como evidencia reproducible |
| SCN-009 | Fixture con acción observada posterior | La acción no altera retroactivamente el estado anterior a la decisión |
| SCN-010 | Fixture con posts y contribuciones | El estado monetario se reconstruye sin doble contabilización |

Los fixtures reales solo son ejecutables cuando tienen secuencia completa, importes, posts, posiciones, orden, snapshot y procedencia suficientes. No se rellenan datos ausentes por intuición.

### 2.5 Rango y prior

| ID | Caso | Esperado |
|---|---|---|
| RNG-001 | Rango vacío | Estado vacío con `empty_reason` |
| RNG-002 | Rango vacío → equity | `unknown` o `unsupported`; nunca `0.0` |
| RNG-003 | Prior plano | `source_kind=prior`; no observación |
| RNG-004 | `prob_vec` vacío | No normaliza ni divide por cero |
| RNG-005 | Blockers eliminan combos incompatibles | Se eliminan antes de normalizar; se conserva masa/procedencia y motivo |
| RNG-006 | `fallback_other_vs` | Se identifica como aproximación con `coverage_gap` |
| RNG-007 | `n_eff` | No se presenta como número de manos observadas |
| RNG-008 | `reach` ya incorporado a likelihood | No se vuelve a multiplicar |
| RNG-009 | Prior + likelihood | Posterior reproducible conforme a la regla declarada |
| RNG-010 | Todas las masas quedan en cero | `empty` o `unsupported` con causa; no distribución uniforme silenciosa |
| RNG-011 | Combo incompatible con board | Se excluye antes de calcular equity |
| RNG-012 | Perfil desconocido | No se convierte automáticamente en rango amplio válido sin modelo declarado |
| RNG-013 | Observación de fold sin cartas reveladas | No genera combo en `ObservedRange` |
| RNG-014 | Frecuencia sin denominador | No se presenta como estadística válida |

### 2.6 Equity

Se aplican los nombres del contrato corregido:

- `CurrentBoardStrength`: fuerza de la mano en el board actual, sin runouts.
- `EquityToShowdown`: participación esperada considerando runouts futuros.

| ID | Caso | Esperado |
|---|---|---|
| EQ-001 | Board actual sin runouts | `CurrentBoardStrength`; no se presenta como equity al showdown |
| EQ-002 | Runouts futuros | `EquityToShowdown`; método y espacio de runouts declarados |
| EQ-003 | Enumeración exacta vs MC | Diferencia evaluada frente a incertidumbre de muestreo y tolerancia predefinida |
| EQ-004 | Mismo seed y entradas | Mismo resultado MC, bajo la misma versión y orden de muestreo |
| EQ-005 | Empate | `tie` separado; reparto correcto |
| EQ-006 | Board y dead cards | Entradas explícitas y validación de cartas duplicadas |
| EQ-007 | Rango vacío | `unknown` o `unsupported`; no cero |
| EQ-008 | CurrentBoardStrength vs EquityToShowdown | No se mezclan ni se comparan como la misma métrica |
| EQ-009 | Side pots | Equity y participación por bote elegible |
| EQ-010 | All-in | El jugador conserva elegibilidad según contribuciones |
| EQ-011 | Folded | El jugador no puede ganar ningún bote |
| EQ-012 | Varios rivales | Distribución conjunta; no suma de equities HU |
| EQ-013 | Exact enumeration | No exige CI de muestreo inexistente; conserva incertidumbre de modelo/rango |
| EQ-014 | MC | `n_samples`, seed y CI de muestreo declarados |
| EQ-015 | Blockers compartidos | Asignación completa sin cartas duplicadas |
| EQ-016 | Dependencia multiway | Política conjunta y supuestos visibles |

### 2.7 EV

| ID | Caso | Esperado |
|---|---|---|
| EV-001 | Fold | Valor respecto al nodo declarado; inversiones previas tratadas como costes hundidos |
| EV-002 | Call | Coste adicional, bote elegible y resultados modelados |
| EV-003 | Raise sin modelo de respuesta | Inválido; no se presenta EV completo |
| EV-004 | Raise con modelo de respuesta | `FieldResponse` y ramas relevantes declaradas |
| EV-005 | Árbol truncado | `tree_depth` y valoración de hojas visibles |
| EV-006 | Cobertura gap | Se identifica como aproximación; no se compara silenciosamente con exact |
| EV-007 | Una muestra | No basta para aceptar una decisión |
| EV-008 | Mismo seed y entradas | Reproducibilidad del cálculo MC |
| EV-009 | Check con decisiones posteriores | Árbol posterior declarado cuando sea necesario |
| EV-010 | All-in y side pots | EV por estructura de botes y elegibilidad |
| EV-011 | Coste hundido | No se contabiliza dos veces |
| EV-012 | Unidades diferentes | No se comparan EV incompatibles |
| EV-013 | Intervalos muy solapados | Se declara ambigüedad; no se fuerza una selección por diferencia insignificante |
| EV-014 | Modelo de respuesta incompleto | `unsupported` o `provisional`; no se rellena con probabilidades inventadas |

### 2.8 Multiway

| ID | Caso | Esperado |
|---|---|---|
| MW-001 | `union()` como campo | Prohibido como distribución o equity de campo |
| MW-002 | Dos o más rivales | Creencias individuales conservadas |
| MW-003 | Blockers compartidos | Asignación conjunta válida sin duplicados |
| MW-004 | Colisión | Rechazo completo contabilizado; no reparación parcial |
| MW-005 | Independencia | Etiqueta `independence_baseline` |
| MW-006 | Correlación | Distribución conjunta/modelo obligatorio |
| MW-007 | Condicionamiento por acciones | Cada acción se incorpora una sola vez |
| MW-008 | Muestreo conjunto | La distribución aceptada coincide con la distribución objetivo |
| MW-009 | Muestreo ponderado | Pesos conservados y tamaño efectivo calculado correctamente |
| MW-010 | Rechazo elevado | Diagnóstico visible; no se alteran rangos silenciosamente |
| MW-011 | All-in | Conserva elegibilidad, pero no vuelve a actuar |
| MW-012 | Side pot | Cálculo por niveles de contribución y elegibilidad |
| MW-013 | Tie/odd chip | Regla determinista declarada |
| MW-014 | Folded | No gana ningún bote |
| MW-015 | Rango vacío | `unknown` o `unsupported`; no cero |
| MW-016 | EV sin respuesta | Inválido |
| MW-017 | Mismo seed y versión | Mismos samples |
| MW-018 | UI | `MULTIWAY_SOPORTADO=False`; sin recomendación MW |
| MW-019 | Cobertura desigual | Cobertura por rival; no se oculta con promedio |
| MW-020 | Rango marginal legal, conjunto imposible | Distribución conjunta no utilizable |
| MW-021 | Independencia condicionada | Marginales resultantes compatibles con el condicionamiento conjunto |
| MW-022 | Correlación sin parámetros/modelo | `unsupported`; no se acepta la etiqueta sola |
| MW-023 | All-in y side pot | Elegibilidad distinta para cada bote correctamente representada |
| MW-024 | Shadow report | No se presenta como recomendación ni como etiqueta de entrenamiento |

### 2.9 Migración y artefactos

| ID | Caso | Esperado |
|---|---|---|
| MIG-001 | Artefacto sin `contract_version` | `unknown_contract`, salvo que exista evidencia verificable de compatibilidad legacy |
| MIG-002 | Artefacto con versión distinta | Rechazo, adaptación explícita o marca de incompatibilidad |
| MIG-003 | Router `legacy` | Acción legacy reproducible |
| MIG-004 | Router `shadow` | Acción legacy; cálculo canónico aislado y comparación registrada |
| MIG-005 | Router `canonical` sin cobertura | `unsupported`/abstención explícita; nunca fold inventado |
| MIG-006 | Rollback de serving | Retorno a legacy verificado |
| MIG-007 | Rollback de artefacto | Restauración por identidad, hash y manifiesto verificables |
| MIG-008 | Regeneración selectiva | Solo artefactos autorizados y afectados; manifiesto de procedencia |
| MIG-009 | Artefacto con snapshot distinto | Rechazo o incompatibilidad explícita |
| MIG-010 | Artefacto con contrato compatible y hash válido | Aceptación conforme a la política de compatibilidad |
| MIG-011 | Rollback durante una ejecución | Estado final consistente; sin mezcla de versiones |
| MIG-012 | Modo canonical sin resultado utilizable | Caller recibe estado explícito de no decisión; no se inventa acción |

La política de abstención de `canonical` debe definirse antes de servirlo. Si el consumidor operativo exige una acción, debe existir un contrato explícito para ese caso. No se puede transformar `unsupported` en fold, check o call por conveniencia.

### 2.10 Sombra y no regresión

| ID | Caso | Esperado |
|---|---|---|
| SHW-001 | Log por defecto | Memoria o mecanismo temporal expresamente autorizado; no `data/` |
| SHW-002 | Diferencia de acción | Registrada; no corregida automáticamente |
| SHW-003 | Modo shadow | No cambia recomendación |
| SHW-004 | Fallo de contrato | Bloquea el consumidor dependiente |
| SHW-005 | `MULTIWAY_SOPORTADO` | Permanece `False` |
| SHW-006 | Hashes de datos | Sin cambios |
| SHW-007 | Artefactos | Sin regeneración o sustitución |
| SHW-008 | Escritores | No se ejecutan escritores reales |
| SHW-009 | Desactivar sombra | Ruta legacy permanece funcional |
| REG-001 | `_preflop_spot` | No se modifica durante fase documental |
| REG-002 | `_preflop_raises` | No se modifica durante fase documental |
| REG-003 | `table_plan` | No se modifica para forzar paridad artificial |
| REG-004 | Acción HU live | Idéntica con router legacy en la muestra de regresión |
| REG-005 | Resultado shadow | No se incorpora a entrenamiento automáticamente |

### 2.11 Calibración y evaluación

| ID | Caso | Esperado |
|---|---|---|
| CAL-001 | Sin dataset de evaluación | No se declara calibración |
| CAL-002 | Split temporal | Sin fuga entre sesiones/manos relacionadas |
| CAL-003 | Features posteriores a decisión | Prohibidas |
| CAL-004 | Test ya consultado | No se presenta como test independiente después de iterar |
| CAL-005 | Predicción probabilística | Brier/log loss/fiabilidad cuando correspondan |
| CAL-006 | ECE | Bins, metodología y limitaciones declarados |
| CAL-007 | Intervalos | Unidad de bootstrap compatible con dependencia entre observaciones |
| CAL-008 | EV held-out | No se sustituye por accuracy |
| CAL-009 | Comparación | Baseline explícito y mismo conjunto de evaluación |
| CAL-010 | Priors | No se evalúan contra las mismas manos usadas para construirlos como si fueran datos independientes |
| CAL-011 | Resultados por segmento | Se reportan posición, stack, spot y cobertura |
| CAL-012 | Umbral | Definido antes de consultar el test |
| CAL-013 | Métrica agregada favorable | No oculta regresiones materiales por segmento |
| CAL-014 | Resultado económico | No se atribuye automáticamente a calidad de la decisión sin controlar varianza y condiciones |

---

## 3. Criterios de aceptación

### 3.1 Mecánicos

- Todos los fixtures ejecutables de contrato pasan.
- Todos los escenarios materializados tienen expected verificable.
- Los campos obligatorios y estados están presentes.
- `gap`, `unknown`, `empty` e `impossible` conservan significados distintos.
- Ningún estado desconocido se convierte en cero, fold o tabla exacta.
- Mismo seed, mismas entradas y misma versión producen resultados reproducibles.
- No hay cambios no autorizados en `motor/`, `data/`, artefactos o `MULTIWAY_SOPORTADO`.
- Los fallos se reportan por prueba y por capa; no se ocultan en un agregado.

### 3.2 Estadísticos

- Cada frecuencia observada declara numerador, denominador, filtros y fuente.
- Cada estimación declara su procedencia y cobertura.
- `n_obs`, `n_opp`, `n_eff`, `n_combos`, `n_runouts` y `n_samples` no se intercambian.
- Un prior no se presenta como observación.
- La enumeración exacta no exige CI de muestreo artificial.
- MC declara tamaño de muestra, semilla y método de intervalo.
- La comparación exacta vs MC utiliza tolerancias y criterios definidos antes de ejecutar.
- La incertidumbre de muestreo no se confunde con incertidumbre del modelo.
- Calibración solo con dataset congelado y evaluación separada.
- No se acepta una métrica agregada sin análisis de fiabilidad e incertidumbre cuando corresponda.

### 3.3 Estratégicos

- Evaluación temporal held-out.
- EV/utility con baseline declarado: flat, tabla, legacy u otro modelo explícito.
- No se declara mejora por paridad con legacy.
- No se declara mejora por accuracy si el EV/utility held-out empeora.
- Se revisan escenarios individuales y resultados por segmento.
- Los umbrales de mejora se fijan antes de observar el test.
- La incertidumbre estratégica y las limitaciones de cobertura se documentan.
- Una mejora en HU no implica automáticamente validez MW.
- Una mejora en simulación no implica automáticamente mejora en juego real.

### 3.4 Operativos

- `MULTIWAY_SOPORTADO=False`.
- Modo `shadow` no cambia la acción.
- Router legacy reproduce la acción previa en la muestra de regresión.
- La abstención de canonical está definida antes de su eventual serving.
- Rollback de serving y artefactos probado antes de cualquier migración que los utilice.
- Logs de diferencias no se utilizan como datos de entrenamiento.
- No se ejecutan escritores reales durante esta fase.
- El modo experimental puede desactivarse sin alterar la ruta HU.

---

## 4. Reglas de bloqueo y avance

1. Un fallo de contrato preflop bloquea las pruebas de consumidores que dependan de ese contrato.
2. Un fixture no materializado no cuenta como prueba aprobada.
3. Un fallo de cobertura bloquea la utilización exacta de la consulta afectada.
4. Un fallo de rango bloquea equity y EV dependientes.
5. Un fallo de equity bloquea EV dependientes.
6. Un fallo de distribución conjunta bloquea equity y EV MW.
7. Un fallo de migración bloquea esa migración y su serving; no invalida automáticamente pruebas independientes.
8. Un fallo de rollback bloquea cualquier cambio de serving que dependa de ese mecanismo.
9. Un test mecánico verde no demuestra calibración.
10. Una calibración correcta no demuestra superioridad estratégica.
11. Una evaluación estratégica favorable no autoriza por sí sola la activación.
12. La activación requiere aprobación explícita y evidencia correspondiente a la versión, snapshot y alcance que se pretende activar.

No se permite compensar fallos de una capa con resultados favorables de otra.

---

## 5. Evidencia que debe conservarse

Cada ejecución de la matriz debe conservar, como mínimo:

- versión del contrato;
- commit evaluado;
- hash del snapshot de datos;
- versión de fixtures;
- entrada completa y expected de cada fixture;
- resultado real y diferencia frente a expected;
- configuración de semillas;
- versión de modelos;
- reporte de cobertura por estado y rival;
- diagnósticos de blockers y rechazos;
- resultados exactos y MC separados;
- side pots, elegibilidad y empates;
- métricas, curvas e intervalos aplicables;
- diff de acciones en sombra;
- hashes antes/después de datos y artefactos;
- resultado de rollback cuando corresponda;
- clasificación de cada resultado: mecánico, estadístico, estratégico u operativo.

Los informes deben permitir reproducir una ejecución sin depender de valores copiados manualmente desde una ejecución anterior.

---

## 6. Límites de esta fase

Esta matriz no autoriza:

- Implementar los tests.
- Modificar `motor/`.
- Modificar `data/`.
- Corregir registros históricos.
- Regenerar artefactos.
- Ejecutar migraciones.
- Cambiar el router live.
- Activar `canonical`.
- Activar multiway.
- Cambiar `MULTIWAY_SOPORTADO`.
- Ejecutar escritores reales.
- Declarar validación estratégica.

**Principio final:** los tests verifican contratos y propiedades concretas. Pasarlos demuestra que esas propiedades se cumplen en los casos evaluados; no demuestra que el modelo sea rentable, esté calibrado o tome mejores decisiones. La aceptación mecánica, estadística, estratégica y operativa son decisiones separadas.