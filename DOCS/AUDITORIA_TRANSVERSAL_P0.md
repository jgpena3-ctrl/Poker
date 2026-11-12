# Auditoría transversal — cierre de P0-1 a P0-5

**Resultado: auditoría terminada; contratos siguen sin activar.** No se cambió
código, tests, datos ni modelos. El único entregable de este bloque es este
informe. Los hallazgos se registran para revisión; no se corrigen aquí.

Base de referencia: `data/hands_db.jsonl`, 1.344 manos; ventana
`reliable_only/first-900-minus-23=877`; hash de ventana
`ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed`; hash de
base `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.
La identidad la declara P0-4; la procedencia de la reproducción B1 continúa
`partial`/`unverified`.

## 1. Dictamen ejecutivo

Los contratos son **compatibles como instrumentos de sombra cuando se leen
según su dominio**, pero no son un contrato transversal ejecutable: P0-1,
P0-2 y P0-3 no adjuntan por sí mismos el mismo hash de base/ventana de P0-4.
Además, P0-2 no propaga su elegibilidad a los cálculos de etiquetas P0-5 ni a la
clasificación contextual P0-1; los auditores postflop sí conservan la
proyección P0-2 por observación.

Hallazgos principales, sin intervención:

1. **P0-5 declara `valid_for_serving=True` para datos cuya procedencia es
   `partial`.** Ejemplo reproducible: `Sp1609`, estado `provisional`, fuente
   `partial`, `contract_label=PEZ`, `valid_for_serving=True`. Ningún consumidor
   live lee este campo, pero el valor contradice el criterio de P0-5 de exigir
   procedencia adecuada antes de validar una etiqueta.
2. **P0-5 calcula etiquetas desde eventos que P0-2 marca restringidos sin
   consignar esa proyección en la decisión de etiqueta.** En la ventana hay 6
   eventos `preflop_stats` restringidos (4 en `H_0357`, 2 en `H_0834`). Una
   eliminación hipotética de esos eventos no cambia las etiquetas de esos seis
   jugadores; aun así, P0-5 no documenta esa dependencia.
3. **P0-1 y P0-2 pueden discrepar sobre la misma secuencia.** En `H_0357`, P0-1
   lee la `BB b 0.5` repetida como `blind/non_decision`; P0-2 la marca
   `invalid` (`subida_sin_incremento`) y restringe cuatro decisiones posteriores.
4. **P0-2 aplana importe ausente a `0.0` en su secuencia de detección.** Un caso
   sintético queda como `apuesta_cero`/`ambiguous`, mientras P0-1 conserva
   `None` y lo declara `unresolved: importe_ausente`. La incertidumbre no se
   activa, pero se pierde la distinción en el detalle P0-2.
5. `range_lab_gui.load_models()` combina rangos cargados de artefactos históricos
   con un Oracle reconstruido desde la base actual; P0-4 ya la clasifica
   `not_suitable`. No es el camino live de `build_models`, pero queda como
   contradicción de procedencia en herramienta auxiliar.
6. La suite reproduce las **23 fallas** conocidas: 22 son expectativas fijadas
   al corte anterior de 1.253 manos y se reproducen con las primeras 1.253
   líneas actuales; la restante detecta 11 escritores de la base no declarados
   en el inventario de `test_quien_escribe`. Esta última es un inventario
   desactualizado y requiere investigación/decisión de mantenimiento; no debe
   descartarse como una falla inocua.

La paridad de la regla de stack de P0-5 es correcta cuando se suministra la
misma evidencia (138/138). P0-3 separa observaciones, manos distintas y prior;
no hay evidencia de que sus coeficientes se presenten como intervalo de
confianza. Los contratos no activan filtros ni cambian decisiones actuales.

## 2. Matriz de consistencia entre contratos

| Dimensión | P0-1 `preflop_contract` | P0-2 `field_eligibility` | P0-3 evidencia postflop | P0-4 procedencia | P0-5 etiquetas | Evaluación transversal |
|---|---|---|---|---|---|---|
| Unidad | acción/estado de secuencia | campo y observación × consumidor | observación/celda/acción y mano distinta | componente/artefacto/base/ventana | etiqueta/jugador/evidencia | granularidades distintas; no existe un ID común de observación en los cinco contratos |
| Identidad de fuente | auditor offline informa conteo/ventana por contexto, no hash propio | CLI informa `ventana_877`/`base_1344`, no hash propio | `hands_source=data/hands_db.jsonl`, `scope=input`; no hash propio | base y ventana con hashes, commit y estados | para build actual reutiliza `build_models_envelope`; histórico conserva campos ausentes | los resultados ejecutados usan la misma ventana, pero P0-1/2/3 no quedan criptográficamente ligados a ella en su payload |
| Restricción | `unresolved` semántico, no filtro | restricciones proyectadas por campo y consumidor | guarda `eligibility_projection`; no filtra el builder | calcula compatibilidad; no filtra | no importa elegibilidad P0-2 a la etiqueta | P0-2 → P0-3 se propaga en el sidecar; P0-2 → P0-1/P0-5 no se propaga |
| Estado de dato | `resolved`, `unresolved`, `non_decision`; categoría `unknown` si no se interpreta | `valid`, `invalid`, `absent`, `derived_non_canonical`, `ambiguous` | cobertura (`<3`, `<20`, `≥20`, `prior_only`, `no_evidence_no_prior`) y confianza `not_quantified` | `verified`, `partial`, `unknown`, `incompatible`; origen separado | `current_evidence`, `provisional`, `historical`, `unknown`, `insufficient_evidence`, `incompatible_provenance` | coherentes dentro de cada namespace; no son enums intercambiables |
| Conteo de muestra | no es un contrato de fiabilidad estadística | antes/después es proyección de observaciones, no datos filtrados | `observation_count` y `distinct_hand_count` separados; manos y observaciones no se mezclan | manos recibidas y ventana/base separadas | `hands_n`, `n_vpip`, conteos VPIP/PFR y stacks separados en campos | P0-3 es el más explícito; P0-5 no añade cantidad de stacks ausentes ni elegibilidad P0-2 |
| Prior/cobertura | `range_query_status` informa categoría consultable | no declara que exista un prior de rango | declara fuente, soporte, `prior_weight`, `observation_weight`, `confidence=not_quantified` | `preflop_matrices` sigue `unknown` | no estima prior | no hay conversión necesaria, pero `available` en P0-1 no significa que exista una matriz prior |
| Alcance de activación | instrumentación shadow; no reemplaza `_preflop_spot`/`_recom_preflop` | la política no filtra `build_models` | sidecar no entra a `p_action`, EV o selector | auditor read-only | no importado por producción | sin activación de P0-1..P0-5 |

### 2.1 Identidad y procedencia

P0-4 declara que la ventana actual coincide con la identidad verificada en
`calibration_window.json` y mantiene `build_models=partial` porque la
reproducción B1 está sin verificar. P0-5 reutiliza el envelope de P0-4 para
`Profiles.from_hands`; en este sentido no inventa otro hash. P0-5 también deja
`window_hash=None` para `profiles.json`, que no guarda ese hash.

En cambio:

- `tools/auditar_contrato_preflop.py::informe` devuelve `hands=877` y
  comparaciones, pero no un hash de base o ventana.
- `field_eligibility.shadow_report` devuelve conteos para el objeto `hands`
  recibido; el CLI agrega el scope textual `ventana_877` o `base_1344`, no el
  hash.
- `tools/auditar_muestra_postflop.py::audit` devuelve `scope=input` y nombra la
  ruta fuente, sin fijar hash de base/ventana en su payload.

No se atribuye a esos contratos una procedencia que expresamente desconozcan;
el defecto es que **no la adjuntan**. Para el presente informe la ventana se
identificó externamente con P0-4 y se ejecutaron los tres auditores sobre
`load_hands(reliable_only=True)`.

P0-4 mantiene los derivados históricos como `partial`; el hash canónico que
coincide no los convierte en actuales. `preflop_matrices.json` sigue
`unknown`. No se halló una declaración de compatibilidad histórica→base actual.

### 2.2 Semántica de estados y de cobertura

Los nombres repetidos (`unknown`, `partial`, `incompatible`) tienen dominios
distintos. En concreto:

- preflop `unresolved` significa que una acción/secuencia no se interpreta;
- P0-2 `ambiguous` significa que el detector no determina si el campo es
  utilizable y por regla no activa una restricción nueva;
- P0-3 `<3`/`<20` son bandas de cobertura, no confianza;
- P0-4 `partial`/`unknown`/`incompatible` describen procedencia o
  compatibilidad;
- P0-5 `provisional` describe evidencia pequeña, no procedencia `partial`.

No hay confusión semántica dentro de las funciones consultadas, pero tampoco hay
un adaptador común que impida comparar por error estados de dominios distintos.

En P0-1, `PreflopClassification.range_query_status` distingue `available`,
`no_range`, `no_table` y `unresolved`. `available` significa que el modelo de
rango reconoce la categoría/consulta; **no prueba** que haya matriz prior. La
clasificación de tablas de `preflop.classify_missing_table` es otra dimensión.
La documentación P0-1 advierte expresamente que las categorías `limp`/
`call_limp` apuntan a tablas LIMP ausentes y que `preflop_matrices` tiene
procedencia desconocida. Por tanto no se encontró una conversión real de
`no_table` a `available`, aunque el nombre `available` podría leerse demasiado
ampliamente fuera de ese contexto.

## 3. Trazabilidad de extremo a extremo

Los ejemplos reales usan la ventana de 877 salvo donde se marca explícitamente
“sintético”. P0-1 se muestra en su lectura estricta; el entrenamiento efectivo
sigue usando el adaptador legado. “Efectivo” en esta tabla es descripción del
camino actual, no autorización para activarlo.

| Caso | P0-1 | P0-2 | P0-3 | P0-4 | P0-5 / consumidores | Incertidumbre que permanece |
|---|---|---|---|---|---|---|
| Acción preflop ambigua: sintético `UTG b` sin `amount` | Conserva `amount=None`; `unknown/unresolved`, `importe_ausente`; acciones siguientes quedan `secuencia_ambigua` | `field_eligibility._indexed_seq` convierte `None` en `0.0`; `ActionIssue(apuesta_cero, ambiguous)`, detalle `UTG b 0`; no activa restricción nueva | No es una observación postflop | Sin envelope individual del caso | P0-5 no consume esta traza; training legado históricamente convierte importe ausente a 0 | P0-2 pierde en el diagnóstico la diferencia entre ausente y cero. No cambia el modelo porque el hallazgo sintético es ambiguo y las políticas siguen shadow |
| Limp corto: `H_0834`, BTN `b 1.0` | Strict: `limp`, `short_limp=True`, `resolved`, `range_query_status=available` para categoría | `code_ambiguous`, no restringe el evento de limp para stats/profile; Oracle marginal restringe el `b` crudo por no distinguirlo de una subida. La posterior `BTN r 4.0` se declara inválida (`accion_sin_nueva_apuesta`), con dependencias SB/BB | Si aporta postflop, su propia traza sigue filtro por cartas/tablero; el auditor no convierte la categoría preflop en evidencia postflop | Matrices LIMP siguen ausentes/unknown; P0-4 no declara prior compatible | `preflop_event_contexts` de P0-2 corre `legacy=True` para alinear entrenamiento, no la semántica estricta de P0-1 | P0-1 dice que el limp es clasificable; P0-2 conserva el limp para ciertos consumidores, pero marca raw `b` como no distinguible en Oracle. La diferencia es de consumidor/código raw, no una etiqueta de tabla |
| Error de secuencia: `H_0357`, BB repite `b 0.5` tras `p 1.0` | Reconoce la segunda acción BB como `blind/non_decision` por posición/estructura; no recibe el defecto declarado de P0-2 | La marca `subida_sin_incremento` es `invalid`, `taints_context=True`; restringe las cuatro decisiones preflop siguientes. En `preflop_stats` esos cuatro eventos quedan restringidos sombra | Solo se propaga si una observación postflop depende de ese defecto; la política P0-2 aplica su alcance por calle/consumidor | El informe P0-4 declara el mismo artefacto/base; no resuelve el conflicto de secuencia | El builder/`Profiles.from_hands` efectivo sigue usando los eventos legacy; P0-5 no adjunta las cuatro restricciones. Removerlas hipotéticamente no cambia estas etiquetas, pero la traza no se registra en cada etiqueta | Contradicción de validez entre P0-1 (no-decisión) y P0-2 (acción repetida inválida), además de falta de propagación a P0-5. Ningún contrato filtra live |
| Tablero ausente: `H_0372`, river UTG/BTN `x` con `board=[]` | No cambia el estado preflop | Board river `absent`; los dos checks son utilizables por Oracle marginal; no por Oracle granular ni postflop bucket | No hay bucket válido, así que no entra a celdas postflop de `PostflopRangeModel`; la observación marginal por facing puede permanecer | Se sabe que el auditor recibió 877, pero P0-3 no sella hash de ventana en ese reporte | Rangos postflop no deben inferir textura/bucket con board ausente | No se conoce la textura del river; no se inventa ni se sustituye por textura vacía |
| Observación restringida por P0-2: `H_0005`, turn, Jarduan `f` | Preflop no determina esta restricción | La acción deriva de `MP b 13` tras `MP x`, sin apuesta nueva; la fila posterior es `dependent`, no directa | La fila sigue dentro del `model.opp` efectivo: auditor la cuenta entre 1.388 y anota `eligible_p02_shadow=False`; quedan 2 restringidas de 1.388 | Procedencia de manos/prior del modelo se declara desde mismo input, pero no hash en el JSON P0-3 | El builder no filtra; el sidecar transmite causa/consumidor. El rango/Oracle efectivo se mantiene igual | P0-2 marca restricción hipotética, no resuelve la acción verdadera ni reconstituye la apuesta |
| Consulta con muestra pequeña: `H_0909`, PEZ/flop/bet/bucket 1 | No es decisión preflop | 1 observación elegible, 1 mano distinta, 0 restringidas | Consulta `c`: observación 1/1 mano; prior `por_facing` con soporte 113; `prior_probability=0.4515`; `prior_weight=2/3`, `observation_weight=1/3`; estimación `0.634333...`, `confidence=not_quantified` | El prior se construyó desde las mismas manos de entrada, no desde una fuente independiente verificada | El prior de la celda está explícito; `OracleResponse`/P0-3 no lo llaman intervalo de confianza | Una mano y prior de fuente compartida; dependencia/correlación no calibrada. No se suman soporte del prior y n como muestras independientes |
| Etiqueta con evidencia insuficiente: sintético `PlayerProfile(n=0, stack=None, VPIP/PFR ausentes)` | No aplicable | P0-2 no se invoca en el caso sintético | No aplicable | P0-5 actual hereda envelope parcial si se usa la base actual | `Profiles.simple_label` efectiva devuelve `TIBURON`; P0-5 registra `state=insufficient_evidence`, `label=TIBURON`, `contract_label=UNKNOWN`, `valid_for_serving=False` | El fallback efectivo puede aún alimentar serving si aparece un asiento sin stack; contrato en sombra no cambia ese comportamiento |
| Modelo histórico/desconocido | Categoría preflop y cobertura de tabla son dimensiones diferentes | No convierte procedencia del modelo en elegibilidad de una fila | Artefactos históricos cargados sin sidecar de evidencia dejan `distinct_hand_count=None`; no se infiere desde `opp` | `profile_ranges` y `postflop_ranges`: históricos/partial; `preflop_matrices`: unknown; combinación rebuilt-vs-historical incompatible | `range_lab_gui.load_models()` carga esos rangos y reconstruye Oracle con manos/labels actuales; la UI no identifica claramente mezcla. P0-4 la clasifica `not_suitable`. `PostflopRangeModel.load()` por sí solo pierde `_oracle` y cae a prior 0.2 con n>0 | No puede afirmarse que las tablas históricas y el Oracle reconstruido comparten base, ventana o commit; no se traslada procedencia actual al derivado |

### 3.1 Restricciones preflop y etiquetas

La proyección P0-2 reporta 6 eventos preflop restringidos en la ventana. Los seis
son: `CamiloG208`, `HarryPoker18`, `Jarduan`, `pardoKing` en `H_0357`, y
`vidents`, `RABBUNI` en `H_0834`. En `H_0357` son tres folds y un open; en
`H_0834`, dos folds vs 3bet.

Una cuenta sombra que resta esos eventos de los denominadores/numeradores
VPIP/PFR deja las etiquetas actuales de esos seis sin cambio. No se usó ese
contrafactual para construir modelos ni modificar recomendaciones. Es evidencia
de **no flip en estos casos**, no evidencia de que P0-5 aplique la política:
`label_audit()` no llama `preflop_event_eligibility`, y `training_decision`
recibe estadísticas agregadas que no conservan los IDs restringidos.

También hay 369 filas de stack no utilizables según el consumidor P0-2 en la
ventana y 65 nombres con algún stack nulo en su conteo; P0-5 promedia stacks
numéricos disponibles y registra el número observado, pero no incluye un
contador por jugador de stacks ausentes ni la proyección P0-2. Los `None` no se
convierten a cero en `mean_stack_by_player`; el problema es la falta de trazado
de elegibilidad, no una imputación a 0.

## 4. Inventario de contradicciones y riesgos

Escala: **alta** = peligro si se activara o se usara como válido; **media** =
trazabilidad/interpretación inconsistente en sombra; **baja** = ambigüedad
terminológica documentada. “Intencional shadow” no significa corregido ni
activable.

| ID / gravedad | Ubicación | Caso reproducible | Hallazgo / efecto actual | Clasificación |
|---|---|---|---|---|
| C1 · alta antes de activar | `motor/preflop_contract.py::walk_preflop`; `motor/field_eligibility.py::assess_hand` | `H_0357`, BB `b 0.5` duplicada | P0-1 estricto la toma por blind non-decision; P0-2 la marca inválida y restringe cuatro dependientes. La salida de P0-1 no transporta el taint P0-2. | Contrato de clasificación sin enlace de elegibilidad; shadow no altera efectiva |
| C2 · alta antes de activar | `motor/label_contract.py::training_decision`; `field_eligibility.py::preflop_event_eligibility` | 6 eventos restringidos en `H_0357`/`H_0834` | P0-5 asigna métodos/evidencia agregada sin señalar esas observaciones restringidas. El contrafactual no cambia las seis etiquetas. | Restricción consumida solo en reporte, no incorporada a decisión de etiqueta |
| C3 · alta antes de servir | `motor/label_contract.py::training_decision` | `Sp1609`: `provisional`, `provenance_status=partial`, `valid_for_serving=True` | Validez de serving no consulta `provenance_status`; `partial` de P0-4 no se propaga como bloqueante/desconocido. Campo shadow no leído en producción. | Inconsistencia interna del contrato P0-5; no intervención efectiva |
| C4 · media | `motor/field_eligibility.py::_indexed_seq` (336) y `_raw_action` (1251) vs `preflop_contract.normalize_actions` (352-358) | Sintético `UTG b` con `amount=None` | P0-1 conserva ausencia y devuelve `unresolved/importe_ausente`; P0-2 representa `0.0`, emite `apuesta_cero/ambiguous`. No lo activa, pero la evidencia del motivo se degrada. | Pérdida de distinción ausencia/cero en diagnóstico |
| C5 · media, auxiliar | `tools/range_lab_gui.py::load_models` (47-78) | Carga `profile_ranges.json`/`postflop_ranges.json` históricos y reconstruye Oracle actual | Mezcla una fuente histórica con una reconstruida; procedencia no queda visible para el usuario de la UI. P0-4 ya la declara `not_suitable`; no es camino live de `build_models`. | Modelo auxiliar con procedencia mezclada y divulgación insuficiente |
| C6 · media | `motor/label_contract.py::historical_decision`; `data/profiles.json` | 6 campos-stat con actual `None` y artefacto `0.0` | BLKsoul/rb, Chang2113/bar, Rio28/bar, Santiago ja/bar, mur420/bar, trombosis2.0/rb. El estado histórico no permite determinar si es conversión de denominador ausente o diferencia de versión. | Apariencia de cero para categoría ausente; origen desconocido, no se atribuye causalidad |
| C7 · media de identidad | P0-1 auditor, `field_eligibility` CLI/JSON, P0-3 auditor | Ejecución en `reliable_only` | P0-4/P0-5 pueden sellar identidad; los outputs de P0-1/2/3 conservan conteo/scope/ruta pero no el mismo hash. | Falta de vínculo criptográfico común en reportes; no falsa procedencia explícita |
| C8 · media de fallback | `motor/profile.py::simple_label`; `motor/asistente_live.py::_perfil_for` | Sin stack/VPIP/PFR | La etiqueta efectiva cae en `TIBURON`; P0-5 correctamente deja `contract_label=UNKNOWN` e insuficiente en su contrato, pero no altera la etiqueta efectiva. | Default efectivo conocido; no debe leerse como evidencia ni como activación P0-5 |
| C9 · baja / riesgo de lectura | `PreflopClassification.range_query_status`; `preflop.classify_missing_table` | H_0834 limp corto frente a matriz LIMP ausente | `available` significa categoría reconocida por el modelo de rango, no matriz prior encontrada. El código separa cobertura; P0-1 documenta ausencia LIMP y P0-4 `preflop_matrices=unknown`. | No se observó conversión efectiva; término susceptible a lectura incorrecta |
| C10 · informativo | `PostflopRangeModel.evidence_for`; `Oracle.evidence`; P0-3 doc §§3-4 | `H_0909`, n=1, prior por facing | Muestra 1/1 mano y peso algebraico prior 2/3; confianza `not_quantified`. Oracle viene del mismo input, y su soporte no se realimenta al fade de fallbacks `label`/`poblacion`. | No se llama evidencia independiente ni confianza; dependencia de fuente compartida permanece sin cuantificar |

### 4.1 Contradicciones que no se encontraron

- No se encontró que P0-4 declare compatibles los derivados históricos con la
  base actual. Los pares rebuilt-vs-historical dan `incompatible`; con matrices
  desconocidas, el resultado es `unknown`/warning, no compatible.
- No se encontró que P0-3 convierta `distinct_hand_count=None` de una carga
  histórica en cero. Lo conserva como desconocido.
- Los `None` actuales de denominadores en `TransitionStats.freq` se conservan
  como `None`; las seis diferencias `0.0` están en el artefacto histórico y su
  causa queda desconocida.
- El sidecar postflop registra `prior_probability`, fuente y pesos, con
  `confidence=not_quantified`; `alpha`/peso no se denominan confianza.
- No se encontró una conversión automática de categoría preflop `unresolved` a
  una categoría de tabla: status de decisión, cobertura de rango y existencia
  de matriz son campos separados.

## 5. No intervención de los cinco contratos

### 5.1 Ejecución transversal antes/después

Se construyó un modelo sintético determinista y se midió antes/después de
ejecutar en sombra los cinco auditores: P0-1 `informe`, P0-2 `shadow_report`,
P0-3 `audit`, P0-4 `audit_provenance` y P0-5 `label_audit`.

El snapshot estable SHA-256 incluyó etiquetas, serializaciones de los modelos de
rango preflop y postflop, distribución Oracle, vector de rango, vector
postflop. El snapshot antes y después fue idéntico:

```
73e4b34a189df1b5c5eee4394a07265741581273e343f8275b09fc77b5130e8c
```

En la misma ejecución se llamó dos veces a `_recomendacion_para` con estado
sintético, semilla fija y mismos modelos. Fueron iguales el texto completo,
mapa EV por acción y acción elegida:

```
acción: call
EV: fold=0.0, call=13.617113223854801 BB
texto, EV y elección: iguales antes/después
```

No se inició sesión real ni se usó recomendación en una mesa real.

### 5.2 Comprobaciones independientes reproducidas

| Contrato | Evidencia de no intervención |
|---|---|
| P0-1 | `motor/test_preflop_contract.py::test_sombra_no_cambia_la_recomendacion_preflop`: EV, acción elegida y acciones candidatas iguales con log de sombra activado/desactivado |
| P0-2 | `python tools/auditar_elegibilidad_campos.py --verify-no-change`: fingerprint de los tres modelos idéntico con/sin hook; resultado `OK` |
| P0-3 | `python tools/auditar_muestra_postflop.py --verify-no-change`: resultado `OK`; huellas documentadas de tablas `ccfcb558...`, estimaciones `a16b0572...` y Oracle `50b254d7...`; test compara texto/EV/acción con sidecar normal y fallido |
| P0-4 | `motor/test_provenance_contract.py::test_audit_does_not_change_models_or_vectors`: labels, digest postflop y `prob_vec` idénticos |
| P0-5 | `motor/test_label_contract.py::test_audit_does_not_change_models_labels_or_vectors`: labels, digest postflop y vector idénticos; hash etiquetas efectivas `dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060` |

La ejecución completa también pasó todas las pruebas de los contratos salvo las
23 fallas históricas listadas en §6. No se modificó `hands_db.jsonl`,
`profiles.json`, `calibration_window.json`, `preflop_matrices.json`, modelos,
rango, prior, etiquetas ni constantes de recomendación. `MULTIWAY_SOPORTADO`
sigue `False`.

## 6. Las 23 pruebas fallidas, clasificadas individualmente

Reproducción actual: `python -m pytest motor -q` → **1036 passed, 1 skipped,
6 xfailed, 23 failed**. Los 22 casos de cifras/bases se contrastaron en memoria
con las primeras 1.253 líneas actuales de `hands_db.jsonl` (sin escribir copia):
conteo 1.253, último ID `H_1282`; los valores emblemáticos que fallan vuelven
a coincidir con los esperados del corte antiguo. La base entera actual es 1.344
manos. No se cambia ningún test ni dato.

| # | Prueba fallida | Esperado → actual | Clasificación y evidencia |
|---:|---|---|---|
| 1 | `test_accion_p::test_la_base_de_hoy_ya_usa_p` | `preflop p=2522` → 2702 | **Expectativa histórica obsoleta (scope 1.253).** Primeras 1.253 líneas: 2522. No indica regresión P0. |
| 2 | `test_auditar_origen::test_las_cifras_de_posiciones_estan_fijadas` | 1253 manos → 1344 | **Expectativa histórica obsoleta.** Falla en el tamaño fijado al corte anterior. |
| 3 | `test_auditar_origen::test_un_jugador_sin_pos_es_uno_que_no_jugo` | 804 → 861 | **Expectativa histórica obsoleta.** En primeras 1.253 líneas, sin_pos=804 y con_accion=0, como declara el test. |
| 4 | `test_auditar_origen::test_no_hay_mesa_corta_ni_ante_ni_straddle` | `{6:1253}` → `{6:1344}` | **Expectativa histórica obsoleta.** Aserción de alcance anterior; actual incorpora 91 manos más. |
| 5 | `test_auditar_origen::test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | `{1.0:1253}` → `{1.0:1344}` | **Expectativa histórica obsoleta.** Primeras 1.253: 1253 BB de 1.0. |
| 6 | `test_auditar_origen::test_las_calls_que_no_llegan_a_la_viva` | 42 → 47 | **Expectativa histórica obsoleta del corte.** Primeras 1.253: 42. No se atribuye causa a las 5 adicionales sin investigación mano a mano. |
| 7 | `test_auditar_origen::test_el_patron_del_bb_es_exacto_no_aproximado` | 52 → 60 | **Expectativa histórica obsoleta del corte.** Primeras 1.253: 52. |
| 8 | `test_auditar_origen::test_el_bote_exacto_cuadra_en_373_de_1253` | 373 → 394 | **Expectativa histórica obsoleta del corte.** Primeras 1.253: 373. |
| 9 | `test_auditar_origen::test_el_rake_no_explica_el_bote` | 373 → 394 | **Expectativa histórica obsoleta del corte.** Reutiliza el mismo conteo de ajuste; primeras 1.253: 373. |
| 10 | `test_auditar_origen::test_aportar_mas_que_el_stack_no_depende_del_rake` | 12 → 13 | **Expectativa histórica obsoleta del corte.** Primeras 1.253: 12. El caso nuevo no se diagnostica aquí. |
| 11 | `test_auditar_origen::test_el_json_y_el_informe_cuentan_lo_mismo` | suma 1253 → 1344 | **Expectativa histórica obsoleta.** Aserción de alcance; el instrumento sigue sumando sus estados internamente. |
| 12 | `test_cm004::test_el_invariante_de_cm004_puede_dispararse` | 1253 ciegas reconocidas → 1344 | **Expectativa histórica obsoleta.** Primeras 1.253: 1253. No se cambió el detector CM-004. |
| 13 | `test_diagnostico_grabador::test_la_base_son_dos_grabadores` | 1182 con `allin` → 1273 | **Expectativa histórica obsoleta del inventario de datos.** Primeras 1.253: 1182 con `allin`, 71 sin él. |
| 14 | `test_diagnostico_grabador::test_la_apertura_cambia_tras_la_normalizacion` | live `{b:100,c:520,r:467}` → `{b:100,c:561,r:514}` | **Expectativa histórica obsoleta del corte.** Primeras 1.253 reproducen `{b:100,c:520,r:467}`; mano-editor mantiene `{b:31,c:29,r:4}`. |
| 15 | `test_diagnostico_grabador::test_las_42_calls_por_debajo_de_la_viva` | calls totales 2603 → 2832 | **Expectativa histórica obsoleta del corte.** Primeras 1.253 reproducen 2603. |
| 16 | `test_diagnostico_grabador::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | 42 llamadas cortas → 47 | **Expectativa histórica obsoleta del corte.** Primeras 1.253 reproducen 42. No se atribuye causa a las adicionales. |
| 17 | `test_diagnostico_grabador::test_la_clasificacion_sobre_la_base` | calculables 5001 → 5417 | **Expectativa histórica obsoleta del corte.** Primeras 1.253: calculables=5001, sospechosas=29, indeterminadas=23. |
| 18 | `test_diagnostico_grabador::test_el_desglose_por_accion_por_resultado_es_coherente` | matriz fija (5001 calculables) → matriz de base 1344 | **Expectativa histórica obsoleta del corte.** El desglose actual es la misma métrica sobre un alcance mayor; primeras 1.253 reproducen 5001 calculables. |
| 19 | `test_diagnostico_grabador::test_el_reparto_por_accion_suma_el_total_de_la_base` | `b/c/r=1448/2603/1002` → `1545/2832/1099` | **Expectativa histórica obsoleta del corte.** Primeras 1.253 reproducen `1448/2603/1002`. |
| 20 | `test_diagnostico_grabador::test_los_ids_se_resuelven_con_el_boton` | 204 IDs → 221 | **Expectativa histórica obsoleta del corte.** Primeras 1.253 reproducen 204; confirmados=46. |
| 21 | `test_lista_saneamiento::test_por_defecto_cubre_toda_la_base` | resumen/manos 1253 → 1344 | **Expectativa histórica obsoleta del alcance.** El test aún fija la base anterior; no se cambia el instrumento. |
| 22 | `test_lista_saneamiento::test_el_rango_por_defecto_sigue_siendo_toda_la_base` | 1253 → 1344 | **Expectativa histórica obsoleta del alcance.** Misma obsolescencia de conteo. |
| 23 | `test_quien_escribe::test_el_inventario_coincide_con_el_instrumento` | inventario declarado 7 escritores vs instrumento 18 | **Fixture/inventario desactualizado; requiere investigación.** El instrumento encuentra 11 escritores adicionales capaces de escribir: `corregir_anotaciones_20261110.py`, `corregir_bote_inflado_fold.py`, `corregir_folds_showdown.py`, `corregir_mano_H_1333.py`, `corregir_resultados_20261029.py`, `corregir_resultados_20261104.py`, `corregir_sesion_20261104.py`, `corregir_showdown_posicion.py`, `eliminar_mano_H_1323.py`, `limpiar_anotaciones_ruido.py`, `limpiar_notas_inferidas.py`. No se deduce que sean autorizados/seguros solo porque existan; hace falta revisar su política de escritura y declarar el inventario. |

### 6.1 Balance de clasificación

- 22/23 fallas: **expectativas históricas de 1.253 manos**, contrastadas con el
  prefijo actual que reproduce las cifras del test. No se observaron como
  regresiones P0-1..P0-5.
- 0 fallas identificadas como regresión de los cinco contratos.
- 1/23: **inventario de escritores obsoleto**, con hallazgo operativo real que
  requiere revisión explícita. No se clasifica como simple falso positivo ni se
  resuelve en esta auditoría.
- La diferencia total de 91 manos y cualquier anomalía específica entre el
  prefijo y la base completa no se atribuye causalmente aquí. No se ajustan
  umbrales ni cifras de los tests.

## 7. Pruebas ejecutadas y límites

1. `python -m pytest motor -q` — **1036 passed, 1 skipped, 6 xfailed,
   23 failed**; desglose individual en §6.
2. `python tools/auditar_elegibilidad_campos.py --verify-no-change` — tres
   modelos idénticos con/sin hook, `OK`.
3. `python tools/auditar_muestra_postflop.py --verify-no-change` — `OK`.
4. Auditoría transversal de snapshot y recomendación determinista, descrita en
   §5.1 — snapshot estable y salida idénticos.
5. P0-4 `audit_provenance()` reporta commit de referencia `3e61b5f` y árbol
   limpio durante la ejecución del auditor; su hash de ventana coincide con el
   de esta auditoría.

La auditoría no determina el origen de las diferencias estadísticas del
artefacto `profiles.json`, el motivo de cada una de las cinco llamadas cortas
fuera del prefijo, ni si los 11 escritores adicionales debían quedar
autorizados. Esos son hallazgos pendientes, no supuestos.

## 8. Restricciones, cambios y estado final

- No se modificaron base canónica, derivados, hashes, manifiestos, pins, ventana
  877, matrices, rangos, priors, etiquetas, probabilidades, selección,
  recomendaciones ni `MULTIWAY_SOPORTADO=False`.
- No se activó contrato, filtro, política ni restricción.
- No se inició B2, calibración ni sesión real.
- No se alteraron tests para ocultar las 23 fallas.
- El único archivo nuevo de esta auditoría es
  `DOCS/AUDITORIA_TRANSVERSAL_P0.md`.

**La auditoría se detiene aquí.** Los hallazgos C1-C10 y el inventario de
escritores se presentan para revisión; no se corrigen ni activan sin
autorización explícita.
