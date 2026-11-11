# P0-2 · Política sombra de elegibilidad por campo y observación

**Estado:** implementado y auditado en sombra; no activado en los modelos efectivos.
**Alcance:** base canónica de 1.344 manos y ventana fiable de 877 manos.
**Fuente de defectos declarados:** `DOCS/B1_EXCEPCION_INVENTARIO.json`.
**Reproducción:** `python tools/auditar_elegibilidad_campos.py`; añadir `--base`, `--json` o `--verify-no-change`.

## 1. Contrato

La política está centralizada en `motor/field_eligibility.py`. Evalúa por
separado el estado del campo y la elegibilidad de cada observación para cada
consumidor. **Nunca excluye una mano completa.** La decisión efectiva sigue
siendo la del modelo actual; las columnas “después” son únicamente la
proyección de la política.

Estados:

| Estado | Significado | Tratamiento sombra |
|---|---|---|
| `valid` | Campo disponible, coherente para el uso descrito | Usable según dependencia |
| `invalid` | Valor presente pero imposible/incompatible con evidencia declarada | Restringir la observación y solo sus dependencias justificadas |
| `absent` | Campo no capturado; nunca equivale a cero | Restringir solo consumidores que lo requieren |
| `derived_non_canonical` | Valor reconstruido o no fiable | No presentarlo ni tratarlo como dato canónico |
| `ambiguous` | Detector/evidencia no determina si es correcto | Informar; no activar una restricción nueva |

La política solo activa defectos declarados. Los hallazgos estructurales
adicionales quedan como `ambiguous`/no determinables. Excepción: marcas
objetivas `final_pot = NADA` y potes ausentes o no positivos no se usan en
resultados económicos. Los 6 conflictos internos que quedaron fuera de la
lista aceptada de exclusión de bote permanecen ambiguos; así la restricción
económica de la base es exactamente 39 manos.

Los campos `actions` y `action_order` son independientes. Una acción con
importe/código inválido no convierte automáticamente todo el orden de la mano
en inválido. Una observación directa solo contamina acciones posteriores que
dependan de su contexto; una acción de un jugador ya retirado es un no-op y no
propaga contaminación. Los índices declarados se verifican contra la evidencia
de posición, acción e importe (H_0327 declara índice 2, pero la apuesta cero es
el índice crudo 1).

## 2. Inventario campo × defecto × consumidor

| Campo | Defecto / estado observado | Consumidores que dependen | Regla sombra y alcance |
|---|---|---|---|
| Acciones | Secuencias imposibles declaradas; hallazgos no declarados ambiguos | `Oracle` marginal/granular, `PostflopRangeModel`, `ProfileRangeModel`, estadísticas preflop/postflop | Restringe la acción directa y observaciones dependientes según calle/consumidor; no la mano entera. La acción previa válida y las observaciones independientes siguen. |
| Orden de acciones | Acciones repetidas o códigos/orden no resolubles; ambiguos no declarados | Extractores y consumidores que reconstruyen secuencia | Se informa aparte de validez de acción. Una acción aislada inválida no anula todo el orden. Hallazgos de orden no declarados no se activan. |
| Posición | Jugador activo sin posición (55 base; 51 ventana) | Alineación de `extract_hand`; usos futuros por asiento | Se reporta ausente. Acciones sin posición alineable no se inventan; las filas ya omitidas por el extractor no se cuentan como nuevas observaciones. No invalida las demás acciones. |
| Identidad de jugador | Nombres repetidos/ausentes pueden impedir atribución; no se detectan defectos declarados en este campo | Etiquetas y estadísticas por jugador | Posición e identidad se evalúan aparte. Una identidad ambigua no convierte en inválida una observación Oracle atribuible por posición. |
| Cartas del jugador | Cartas parciales/ausentes por jugador; el estado por mano `valid` solo indica que hay cartas interpretables en la mano | `ProfileRangeModel`, `PostflopRangeModel`; no requeridas para Oracle marginal | No se sustituye ausencia por cero. Los rangos condicionados requieren cartas del jugador de la observación; Oracle marginal no. La salida JSON identifica cada observación con/sin cartas. |
| Tablero | 11 manos declaradas; contradicción entre `streets` y `comunitarias`, o tablero ausente | Oracle granular, postflop range, equity futura | Se usa el tablero por calle (`streets`) cuando es válido y se conserva aviso por contradicción; `comunitarias` contradictorio no lo invalida. Si falta el tablero, se restringe solo la observación postflop condicionada a textura/bucket; Oracle marginal por `facing` sigue utilizable. |
| Bote | 35 `NADA`, 4 no fiables activos; 6 conflictos ambiguos no activados | EV/ROI/pot odds/resultados económicos | `NADA`, ausencia y valor no positivo no alimentan EV/ROI. Los 4 potes no fiables son derivados no canónicos. El ganador/showdown es un campo distinto. |
| Stack | Nulo o derivado; 25 manos declaradas con stack activo nulo en base | Media de stack y etiqueta PEZ/TIBURON; perfil/rangos pueden emitir aviso de etiqueta | El valor nulo/derivado no se presenta como canónico. Se restringe la fila del consumidor de stack; no se eliminan las acciones Oracle/postflop que no necesitan stack. |
| All-in | Marca ausente (23 base; 18 ventana) | EV/SPR y llamadas cortas futuras | Ausencia informada; no se supone all-in ni se usa para descartar acciones actuales. Los modelos actuales auditados no consumen esta marca. |
| Showdown | Ausente o texto split incompleto (4 base; 1 ventana) | WTSD y W$SD | WTSD puede usar la llegada al showdown; texto de ganador inválido restringe el numerador W$SD, no Oracle, bote ni automáticamente WTSD. Sin showdown, ganador de fold no se interpreta como ganador de W$SD. |
| Ganador | Ausente sin showdown; split no legible/incompleto | W$SD | Se evalúa independientemente de bote y showdown. No se usa `None` como probabilidad ni se deriva el ganador a partir del resultado económico. |
| Resultado económico | Depende del estado del bote, no de la presencia de ganador | EV/ROI/pot odds | Solo se restringe por bote no utilizable. Una mano ganada sin showdown puede conservar un bote válido; showdown ausente no invalida por sí solo EV/ROI del bote. |

### Matriz resumida de consumidores

| Consumidor | Acciones/secuencia | Cartas | Tablero | Bote | Stack | Showdown/ganador |
|---|---|---|---|---|---|---|
| `oracle_por_facing` | Acción directa y dependencias pertinentes | No requerido | No requerido; contradicción solo aviso | No | Aviso de etiqueta, no exclusión de acción | No |
| `oracle_granular` | Como Oracle, solo postflop para comparación granular | No requerido por Oracle | Requiere calle válida postflop | No | Aviso de etiqueta | No |
| `postflop_range` | Acción directa/dependiente | Requeridas | Bucket válido requerido | No | Aviso si afecta etiqueta | No |
| `profile_range` | Evento preflop y secuencia | Requeridas | No | No | Aviso si afecta etiqueta | No |
| `preflop_stats` | Evento preflop, sin requerir cartas | No | No | No | No | No |
| `postflop_stats` | Iniciativa/defensas y dependencias | No | No | No | No | No |
| `showdown` | Solo si hay defecto que cambia la elegibilidad del evento | No requerida para oportunidad | No | No | No | WTSD separado de W$SD |
| `stack` | No | No | No | No | Valor numérico canónico requerido | No |
| `economic` | No, salvo análisis futuro explícito | No | No | Bote utilizable requerido | No | No como proxy del bote |

### Estados de campo observados

Conteo de manos por estado, no de observaciones. `player_cards=valid` significa
que hay cartas parseables en la mano; no que todos los jugadores tengan cartas.

| Campo | Ventana 877 | Base 1.344 |
|---|---|---|
| `actions` | valid 801; ambiguous 67; invalid 9 | valid 1.239; ambiguous 92; invalid 13 |
| `action_order` | valid 850; ambiguous 27; invalid 0 | valid 1.305; ambiguous 38; invalid 1 |
| `position` | valid 826; absent 51 | valid 1.289; absent 55 |
| `player_identity` | valid 877 | valid 1.344 |
| `player_cards` | valid 877 (parcial por jugador) | valid 1.344 (parcial por jugador) |
| `board` | valid 873; absent 4 | valid 1.338; absent 6 |
| `pot` | valid 877 | valid 1.299; absent 35; derived 4; ambiguous 6 |
| `stack` | valid 601; derived 276 | valid 974; derived 370 |
| `allin` | valid 859; absent 18 | valid 1.321; absent 23 |
| `showdown` / `winner` | valid 450; absent 426; invalid 1 | valid 612; absent 728; invalid 4 |
| `economic_results` | valid 877 | valid 1.305; invalid 39 |

## 3. Recuentos por consumidor

Los recuentos antes/después son observaciones candidatas vs. proyección sombra;
no son conjuntos de entrenamiento reconstruidos ni cambios efectivos.

| Alcance | Oracle marginal | Oracle granular postflop | Postflop range | Profile range | Preflop stats | Showdown | Filas stack | Economic |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ventana 877: antes | 8.657 | 3.695 | 1.388 | 1.168 | 4.594 | 451 | 5.262 | 877 |
| Ventana 877: después | 8.633 | 3.671 | 1.386 | 1.167 | 4.588 | 450 | 4.893 | 877 |
| Ventana 877: restringidas | 24 | 24 | 2 | 1 | 6 | 1 | 369 | 0 |
| Base 1.344: antes | 13.784 | 6.083 | 2.353 | 1.827 | 7.107 | 616 | 8.064 | 1.344 |
| Base 1.344: después | 13.739 | 6.040 | 2.345 | 1.823 | 7.094 | 612 | 7.566 | 1.305 |
| Base 1.344: restringidas | 45 | 43 | 8 | 4 | 13 | 4 | 498 | 39 |

Recuentos de cobertura condicionada:

| Métrica | Ventana 877 | Base 1.344 |
|---|---:|---:|
| Observaciones postflop conocidas con cartas candidatas | 1.396 | 2.363 |
| Observaciones conocidas perdidas por tablero ausente | 8 | 10 |
| Observaciones con contradicción `streets`/`comunitarias` (aviso, no descarte) | 16 | 16 |
| Manos con algún stack nulo | 276 | 370 |
| Filas de stack sin valor numérico | 369 | 498 |
| Manos con stack activo nulo declarado | 17 | 25 |
| Manos con showdown antes/después | 451 / 450 | 616 / 612 |
| Bote/economic antes/después | 877 / 877 | 1.344 / 1.305 |

### Categorías que cambian en `TransitionStats`

| Categoría | Ventana antes → después | Base antes → después |
|---|---:|---:|
| `vpip_opp` / `pfr_opp` | 4.594 → 4.588 | 7.107 → 7.094 |
| `vpip_act` | 1.681 → 1.680 | 2.673 → 2.668 |
| `pfr_act` | 706 → 705 | 1.049 → 1.048 |
| `b3_opp` | 1.587 → 1.586 | 2.348 → 2.341 |
| `b4_opp` | 123 → 121 | 166 → 164 |
| `cbet_opp` / `cbet_act` | 335/183 → 335/183 | 507/280 → 506/279 |
| `bar_opp` / `bar_act` | 265/172 → 265/172 | 411/266 → 410/265 |
| `rb_opp` | 204 → 202 | 321 → 318 |
| `f2bar_opp` | 371 → 370 | 588 → 586 |
| `wtsd_opp` / `wtsd_act` | 1.393/256 → 1.393/256 | 1.903/425 → 1.899/424 |
| `wsd_opp` / `wsd_act` | 256/139 → 256/139 | 425/233 → 424/231 |

Oracle marginal por calle (antes → después):

| Calle | Ventana 877 | Base 1.344 |
|---|---:|---:|
| Preflop | 4.962 → 4.951 | 7.701 → 7.681 |
| Flop | 1.826 → 1.826 | 2.967 → 2.960 |
| Turn | 1.174 → 1.165 | 1.916 → 1.904 |
| River | 695 → 691 | 1.200 → 1.194 |

El audit JSON contiene todas las categorías por evento/observación. En ventana,
los seis eventos preflop restringidos se distribuyen en 2 `fold`, 2
`fold_vs_3bet`, 1 `fold_vs_open` y 1 `open`; su detalle por mano y posición
está en `hand_issues`/`preflop_by_category` del JSON.

## 4. Oracle marginal vs. granular

| Ventana | Universo | Antes | Después | Restricciones |
|---|---|---:|---:|---:|
| Marginal por `facing` | Todas las calles | 8.657 | 8.633 | 24 |
| Granular por textura | Solo postflop | 3.695 | 3.671 | 24 |

Las 24 restricciones marginales se componen de 9 acciones directas, 13
dependencias y 2 códigos preflop declarados cuyo limp corto está registrado
como `b`. El granular postflop contiene 13 restricciones de acción (6 directas
y 7 dependencias postflop) y 11 observaciones sin tablero válido. No compara
preflop; por eso sus 24 no significan que marginal y granular tengan el mismo
universo. Las contradicciones de tablero son avisos porque el bucket usa
`streets`, no el campo `comunitarias` contradictorio.

## 5. Las 13 secuencias imposibles

El conteo “dependientes” siguiente incluye dependencias posteriores de la
secuencia; el desglose Oracle de la ventana clasifica dependientes de la misma
calle por separado. No se excluye ninguna mano.

| Mano | Calle / índice resuelto | Acción / defecto | Dependientes | Evidencia relevante |
|---|---|---|---:|---|
| H_0005 | turn / 4 | MP `b 13.0` tras su `x`, sin apuesta nueva | 7 | Directa; 4 dependencias Oracle en turn, además de dependencias posteriores |
| H_0059 | preflop / 6 | BTN `c 2.5` cuando SB y BB ya se retiraron | 0 | Call sobre apuesta propia/sin rival |
| H_0214 | turn / 2 | BB `b 1.0` tras su `x`, sin apuesta nueva | 4 | Directa más dependencias del contexto posterior |
| H_0226 | river / 2 | SB `c 4.9` después de retirarse MP | 0 | No queda apuesta viva que igualar |
| H_0327 | river / **1** (declarado 2) | MP `b 0.0` | 1 | Índice resuelto por evidencia; CO `f` depende de la acción |
| H_0357 | preflop / 2 | BB `b 0.5` tras postear 1.0; acción duplicada | 4 | La secuencia preflop posterior depende de ese estado |
| H_0834 | preflop / 5 | BTN `r 4.0` sin subida viva nueva | 2 | La evidencia también identifica BTN `b 1.0` como limp corto |
| H_0925 | river / 4 | MP `f` tras MP `c 9.0`, sin apuesta nueva | 0 | Restricción directa |
| H_0926 | turn / 0 | SB `x` después de haberse retirado en flop | 0 | No-op de SB; **solo esa observación** restringida |
| H_0946 | flop / 3 | UTG `x` enfrentando MP `b 7.1` | 0 | Check no legal con apuesta viva |
| H_1141 | preflop / 4 | SB `x` enfrentando la ciega BB | 0 | Check preflop no resuelto |
| H_1287 | preflop / 4 | CO `c 1.0` frente a 6.0, stack 20.0 | 4 | No es all-in corto; dependencias sin asumir fold/call correcto |
| H_1310 | preflop / 4 | SB `c 1.0` frente a 3.0, stack 92.4 | 13 | No es all-in; luego hay llamadas repetidas |

No se alteran las reglas de clasificación de P0-1. En particular, los
hallazgos no declarados (`check` preflop no resuelto, calls cortos, `posta`
repetida, short limps no respaldados) se reportan como ambiguos, no se
convierten en exclusiones.

## 6. Trazabilidad de las 126 observaciones Oracle

Las diez manos de la ventana suman **126** observaciones. No se tratan como un
bloque:

| Mano | Total | Directas | Dependientes | Código restringido | Ambigua no activada | Independientes |
|---|---:|---:|---:|---:|---:|---:|
| H_0005 | 23 | 1 | 4 | 0 | 1 | 17 |
| H_0059 | 5 | 1 | 0 | 0 | 0 | 4 |
| H_0214 | 16 | 1 | 2 | 0 | 0 | 13 |
| H_0226 | 13 | 1 | 0 | 0 | 0 | 12 |
| H_0327 | 14 | 1 | 1 | 0 | 0 | 12 |
| H_0357 | 5 | 1 | 4 | 0 | 0 | 0 |
| H_0832 | 10 | 0 | 0 | 1 | 0 | 9 |
| H_0834 | 6 | 1 | 2 | 1 | 0 | 2 |
| H_0925 | 18 | 1 | 0 | 0 | 0 | 17 |
| H_0926 | 16 | 1 | 0 | 0 | 0 | 15 |
| **Total** | **126** | **9** | **13** | **2** | **1** | **101** |

`--json` emite cada fila Oracle en `oracle_breakdown[hand_id].rows`, con
calle, posición, acción, importe, `facing`, textura, cartas conocidas y clase
(`directa`, `dependiente`, `codigo_restringido`, `ambigua_no_activada` o
`independiente`), evidencia cruda, motivo, alcance de dependencia y
elegibilidad marginal/granular por separado. Así se puede reproducir y revisar
individualmente cada una de las 126 observaciones sin copiar un resumen por
mano como si fuera una exclusión.

Casos que requieren tratamiento explícito:

* **H_0926:** 1 directa (SB `x` en turn), 15 independientes. La acción del SB
  después de su fold no propaga dependencia porque ese no-op no cambia el
  contexto.
* **H_0832:** CO `b 1.0` está declarado como limp corto. Se usa como limp en
  `preflop_stats`/`ProfileRangeModel`; la celda cruda Oracle preflop `b` se
  restringe, pero las otras 9 observaciones siguen.
* **H_0834:** el limp corto forma parte de la evidencia declarada de la
  secuencia imposible. Se restringe esa celda Oracle preflop además de la
  acción BTN `r` y sus dos dependencias.
* **H_0005:** el detector encuentra un `b 1.0` preflop compatible con limp,
  pero ese hallazgo no está declarado como defecto de esa acción. Se marca
  ambiguo y no se activa: sigue siendo una de las 17 observaciones
  independientes para el recuento efectivo de política.
* **H_0357:** las 5 observaciones de Oracle quedan afectadas por la secuencia
  preflop invalidada; no se extiende esa restricción a otras manos.

Las otras seis secuencias declaradas fuera de la ventana son H_0946, H_1141,
H_1287, H_1310, H_1328 y H_1354. La CLI las audita sobre la base, separadas del
universo de 126 de la ventana.

## 7. Datos no determinables y límites

| Fuente de ambigüedad | Ventana 877 | Base 1.344 | Activación |
|---|---:|---:|---|
| `call_insuficiente` detectado, posible all-in/call corto | 31 | 45 | No |
| `posta_repetida` no declarada | 2 | 2 | No |
| `preflop_no_resuelto` no declarado | 29 | 39 | No |
| `subida_sin_incremento` no declarada (código/limp) | 13 | 14 | No |
| Otras claves de orden/código ambiguas | Incluidas en el reporte por mano | Incluidas en el reporte por mano | No |

El total de la ventana es 76 hallazgos ambiguos/acciones, no 76 manos
excluidas; el total de la base es 103. Las filas omitidas por alineación de
posición, cartas desconocidas de algunos jugadores, valores derivados y
ganadores no legibles se dejan identificados por campo/observación; el audit
JSON conserva el detalle para seguimiento. Ningún cero, ganador, stack,
posición o carta se infiere para llenar una ausencia.

## 8. Pruebas y no interferencia

`motor/test_field_eligibility.py` contiene pruebas positivas y negativas para
acción tras fold, check frente a apuesta, apuesta cero, call sobre apuesta
propia, check repetido, short limp declarado/no declarado, resolución de
índice por evidencia, tablero contradictorio/ausente, `NADA`/bote no fiable y
conflicto no activado, stack nulo/derivado, cartas ausentes, split incompleto,
all-in ausente, identidad duplicada, posición no alineada y no exclusión de
mano completa. También fija los recuentos de ventana, las 126 observaciones,
las 13 secuencias y la paridad de los denominadores antes con
`TransitionStats`.

Verificación ejecutada:

```text
python -m pytest motor/test_field_eligibility.py motor/test_preflop_contract.py \
  motor/test_observations.py motor/test_behavior.py motor/test_postflop_ranges.py \
  motor/test_player_ranges.py motor/test_profile.py motor/test_stats.py \
  motor/test_asistente_live.py motor/test_learn.py -q
273 passed, 1 xfailed, 2 warnings

python tools/auditar_elegibilidad_campos.py --verify-no-change
profile_range              IGUAL
oracle                     IGUAL
postflop_range             IGUAL
oracle_inside_postflop     IGUAL
```

El fingerprint excluye solamente metadatos de procedencia volátiles (`built_at`,
`code_commit`, `arbol_sucio`); conserva conteos de entrada/uso, etiquetas,
tablas, `omega` y distribuciones. La auditoría vuelve a calcular el hash del
primer build después del segundo para comprobar que tampoco se muta un modelo
ya construido. `build_models()` invoca el hook opcional después de construir
los modelos y no filtra. Con modelos idénticos y el mismo estado/entrada, la
recomendación sigue siendo la misma. Un test ejecuta la misma recomendación
preflop determinista (misma semilla/estado) con ambos builds y compara acción,
frecuencias, candidatos y datos del sorteo; no se cambia ningún camino de
recomendación ni se activa la política estricta.

No se modificaron `data/hands_db.jsonl`, derivados históricos, matrices,
ventana, selecciones, priors, etiquetas, hashes/manifiestos/pins ni
recomendaciones. No se ejecutaron calibraciones ni se inició P0-3, B2 o
sesiones reales. P0-2 queda en sombra hasta autorización explícita para
cualquier activación.
