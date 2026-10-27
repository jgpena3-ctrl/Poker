# Auditoría de pins — 2026-10-26

**Base canónica:** `data/hands_db.jsonl`
**SHA-256:** `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`
**Líneas:** 1253
**HEAD:** `0738503bcefa32f9dab79f68cac62c2fdcec9774`
**Estado:** calibración **bloqueada**.

Este documento cierra la re-anclada de los pins de `tools/` contra la base
adoptada. No crea commits, no toca la base, no cambia parámetros de
calibración y no recodifica ninguna acción `p`.

## 1. Suite de referencia

El procedimiento habitual del repositorio excluye las dos pruebas que no son
suite —piden entrada por teclado o una captura que no está en el repo—:

```powershell
python -m pytest motor recorder tools --ignore=tools/test_live.py --ignore=tools/test_mano6.py -q
```

Resultado de la última ejecución completa:

| | |
|---|---:|
| aprobadas | **1556** |
| fallidas | **9** |
| omitidas (`skipped`) | **2** |
| `xfailed` | **5** |
| `xpassed` | **0** |

Las 2 omitidas son de entorno/diseño, no fallos:
`motor/test_hierarchy.py:678` (sin `anchor_match`, `equity_shadow` es `None`
por diseño) y `tools/test_cifras_a1.py:373` (la cuarentena de A1 está vacía,
no hay liberación que simular).

Los 5 `xfailed` son de `motor/test_cm004.py`, con la razón declarada: la base
actual no es el estado reproducible de `02fc641` y el canal manual está
cerrado (`revision_1`). No hay `xpass`.

Las 9 fallidas están clasificadas en §4. Ninguna es una regresión funcional
del motor: las 9 dependen de dos artefactos que la adopción dejó obsoletos
(el análisis publicado del AUC y los fixtures de copia sintética).

## 2. Cómo se cuenta la suite

`tools/test_ejecutar_pytest.py` no cuenta casos de pytest: cuenta **funciones
de test** por carpeta con `ast`, y las compara con cuatro constantes
deliberadas. También cuenta ficheros y funciones con `@pytest.mark.parametrize`.

| constante | valor | qué mide |
|---|---:|---|
| `TESTS_POR_CARPETA['motor']` | 889 | funciones `test_*` en `motor/` |
| `TESTS_POR_CARPETA['recorder']` | 4 | funciones `test_*` en `recorder/` |
| `TESTS_POR_CARPETA['tools']` | 616 | funciones `test_*` en `tools/` |
| `FICHEROS_POR_CARPETA` | 72 / 4 / 131 | ficheros `test_*.py` |
| `PARAMETRIZADOS_ABAJO` | 21 | funciones con `parametrize` |

No son dinámicas a propósito: el guardia existe para detectar que **una prueba
desaparece**, y una comparación contra el propio descubrimiento de pytest no
podría detectarlo (ambos lados bajarían juntos). El precio es que hay que
actualizarlas a mano cuando se añade o se quita una prueba legítima; el
procedimiento es ejecutar el guardia y actualizar **las cuatro** cifras a la
vez. La cifra de pytest de la §1 (1572 casos) es mayor porque incluye la
expansión de los `parametrize`; no sustituye a las constantes.

El guardia se ejecutó dos veces sobre el estado final (una aislado y otra
dentro de la suite completa) y dio el mismo resultado: 61 pruebas del propio
fichero, todas en verde.

## 3. Pins y declaraciones re-anclados (17)

Todas las cifras se recalcularon contra la base de 1253 con las funciones de
producción y, cuando fue posible, con una segunda vía independiente. Las
propiedades estructurales (contrato de asientos, la secuencia de
comprobaciones de board, la etiqueta leída de `muestra()`, el guardia de
tipos) no se tocaron.

| archivo | prueba | antes → después | clase |
|---|---|---|---|
| `test_bloqueo_orden_filtros.py` | showdown verificable | 1 → 3 (`H_0080`, `H_0223`, `H_0485`) | A |
| `test_bloqueo_orden_filtros.py` | cortes preflop | 83 → 76; etiquetas `[]` → `{H_0080, H_0223}` | A |
| `test_bloqueo_orden_filtros.py` | motivo sin board | 83 → 76; 74 sin board; 2 con board y etiqueta | A |
| `test_bloqueo_orden_filtros.py` | corte en la primera | 67 (20/47) → 61 (21/40) | A |
| `test_cifras_a1.py` | números estables | `ESTABLES` `(1258, 877, 921)` → `(1253, 877)` | A |
| `test_cifras_a1.py` | falsos positivos | mismo re-anclaje; `1253` es estable | A |
| `test_contrato_etiqueta.py` | dos representaciones del board | 83 → 76; `comunitarias` 0 → 2; `streets` 2 | A |
| `test_decision_y_guardias.py` | conteos de la tabla | 378/67/20/47 → 328/61/21/40 | A |
| `test_etiqueta_se_lee.py` | cifras de la herramienta | 223/48/0 → 212/50/2 (postflop 48 = 20/28) | A |
| `test_etiqueta_se_lee.py` | corte en la primera | 67/20/47 → 61/21/40 | A |
| `test_etiqueta_se_lee.py` | tabla contra filas | 873 → 866 filas | A |
| `test_fold_no_es_poblacion.py` | preflop en población B | `[]` → `[H_0080]`; `sp` 23 → 25; fold 23 → 24 | A |
| `test_que_representa.py` | A y B no son recorte | (638,235,232,141) → (633,233,230,142) | A |
| `test_que_representa.py` | predicción por rival | 415 → 396; 0→139, 1→331 | A |
| `test_registro.py` | números de la cuarentena | `'202'` dentro de `'2026'` era un falso positivo; ahora se busca el número entero | C |
| `test_verificar_caracteres.py` | número de hallazgos | 11 → 12 | D |
| `test_verificar_caracteres.py` | declaración por hallazgo | se declara `motor/test_learn.py` `U+FFFD` (preexistente) | D |

### Evidencia de las cifras nuevas

- `877` sigue siendo la ventana fiable; `76` son los cortes preflop de la
  población B y `61` los del corte en la primera.
- `H_0080` (y=1) y `H_0223` (y=0) tienen `comunitarias.river` y ganador
  verificable; su última decisión es preflop pero la mano continuó. No son un
  recalculado: `test_resto_de_muestra_nunca_inventa_una_etiqueta` sigue
  comprobando fila a fila que `y` es el de `muestra()`.
- `H_0485` tiene el board solo en `streets`, no en `comunitarias`; por eso no
  tiene etiqueta y sigue siendo el caso que demuestra la inconsistencia de las
  dos representaciones.
- Las doce categorías de `tools/integrar_copia.py` se re-anclaron al contrato
  de adopción (`trabajo/control_categorias_adopcion.json`), que coincide con
  `DOCS/CANAL_MANUAL_CERRADO.md`: `3bet=86`, `bb_check=348`,
  `call_3bet=15`, `call_limp=322`, `call_open=594`, `fold=2211`,
  `fold_vs_3bet=139`, `fold_vs_open=1471`, `limp=564`, `open=587`,
  `rol=275`, `squeeze=25`. Ya no existe `4bet` en la base de 1253.
- `test_que_representa` y su documento se actualizaron juntos; las cifras
  viejas describían la ventana pre-adopción.

## 4. Fallos pendientes (9) — clase D

Los 9 tienen la misma naturaleza: el código de producción es correcto, pero
el artefacto que la prueba compara quedó obsoleto con la adopción. No se
actualizaron sus expectativas porque hacerlo destruiría el objeto de la
prueba o publicaría una conclusión estadística nueva sin decisión explícita.

### 4.1 Análisis publicado del AUC (6)

| prueba | esperado | medido con la base de 1253 |
|---|---|---|
| `test_etiqueta_se_lee::test_el_auc_publicado_se_reproduce` | 14 filas; 6/5; AUC 0,7667; IC [0,4333; 1,0000]; p 0,0896 | 13 filas; 5/5; AUC 0,76; IC [0,4; 1,0]; p 0,1057 |
| `test_reduccion_auc::test_la_mediana_reproduce_el_auc_publicado` | 6/5; 0,7667; [0,4333; 1,0000] | 5/5; 0,76; [0,4; 1,0] |
| `test_reduccion_auc::test_sin_el_filtro_se_reproduce_el_numero_malo` | 47 obs; 0,8308 | 47 obs; 0,8271 |
| `test_reduccion_auc::test_cuantas_observaciones_tienen_mas_de_un_rival` | 11 obs; 1 multi-rival | 10 obs; 0 multi-rival |
| `test_reduccion_auc::test_el_recorrido_entre_reducciones_es_menor_que_el_ic` | recorrido 0,0333 < 0,5667 | recorrido 0,0000 < 0,6000 |
| `test_reduccion_auc::test_las_seis_reducciones_son_una_de_ellas_o_otra` | `{0,7667, 0,8000}` | `{0,76}` |

Causa demostrada: la adopción redujo la población de validación de 11 a 10
observaciones (de 6/5 a 5/5). No es una mejora del modelo: el AUC baja de
0,7667 a 0,76 y el IC sigue incluyendo 0,5. Además, con **0** observaciones
multi-rival, las seis reducciones coinciden y el recorrido es 0,0000; la
prueba de que «la reducción no importa» se vuelve vacua.

Artefacto a regenerar antes de tocar los pins:
`DOCS/AUC_INTERVALO.md` y `DOCS/QUE_REPRESENTA_LA_PREDICCION.md` §4. Requiere
una decisión explícita porque cambia una conclusión publicada (aunque no la
calibración).

### 4.2 Fixtures de copia sintética (3)

| prueba | causa |
|---|---|
| `test_integrar_copia::test_el_flujo_completo_pasa_contra_el_fixture_suave` | `tocadas == 0`: la base canónica ya trae todas las ciegas como `p`, así que `recodificar()` no encuentra ninguna `b` que convertir |
| `test_integrar_copia::test_los_dos_fixtures_tienen_umbrales_distintos` | los dos fixtures miden 1253 ciegas; la invariante «dos umbrales distintos» ya no se puede cumplir sin rediseñar el fixture suave |
| `test_fixture_duro::test_el_fixture_duro_no_toca_los_antes_ni_los_straddles` | `convertidas == 0`: no queda ninguna `BB b` de importe 1.0 en la base |

#### Los fallos de `test_integrar_copia`, uno a uno

El resumen previo hablaba de 8. La captura más antigua conservada tiene 7;
la diferencia es la pareja de umbral cruzado, que en el estado inicial
pasaba y el reemplazo mecánico de 921/1258 por 1253 rompió. Se explican los
9 para que ninguno quede sin nombre.

| # | prueba | causa | estado |
|---|---|---|---|
| 1 | `test_el_flujo_completo_pasa_contra_el_fixture_suave` | `tocadas == 0` (base ya normalizada) | **abierto** |
| 2 | `test_el_flujo_completo_pasa_contra_el_fixture_duro` | 1258 → 1253; `tocadas` 1258 → 33; `dejadas` 0 → 1220 | resuelto |
| 3 | `test_los_dos_fixtures_tienen_umbrales_distintos` | ambos miden 1253 | **abierto** |
| 4 | `test_el_control_de_categorias_bloquea_y_no_se_puede_hacer_informativo` | `CONTROL_CATEGORIAS` viejo y umbral 921; ahora usa el contrato de adopción y el umbral medido | resuelto |
| 5 | `test_el_control_declarado_bloquea_de_verdad` | ídem | resuelto |
| 6 | `test_una_diferencia_semantica_no_bloquea_la_integridad` | ídem | resuelto |
| 7 | `test_camino_completo_los_dos_controles_declarados` | `CONTROL_CATEGORIAS` viejo | resuelto |
| 8 | `test_el_umbral_del_suave_no_sirve_para_el_duro` | el reemplazo mecánico la dejó pasando el umbral correcto; con el umbral cruzado real vuelve a comprobar lo que dice | resuelto |
| 9 | `test_el_umbral_del_duro_no_sirve_para_el_suave` | ídem | resuelto |

Los dos abiertos son el mismo contrato: el fixture suave se diseñó para
recodificar una `b` que la base de 1253 ya no tiene.

Causa demostrada: los fixtures se diseñaron sobre una base con ciegas `b`.
La base de 1253 ya las normalizó a `p`, y `recodificar()` es un no-op. No se
relajó la aserción porque el `tocadas > 0` es precisamente la garantía de que
el fixture no es vacuo; convertirla en `== 0` sería convertir un contrato roto
en una prueba que siempre pasa. El rediseño del fixture es una decisión de la
siguiente fase.

## 5. Invariantes que no se tocaron

- `data/hands_db.jsonl` y `data/hands_db.jsonl.bak`: sin cambios.
- SHA-256 canónico y 1253 líneas: verificados antes y después.
- `tools/calibrar.py` y los parámetros de calibración: sin cambios.
- Semántica de `p`: sin cambios.
- Contrato de asientos (`motor/multiway.posicion_de_id`,
  `ContratoAsientosInvalido`): sin cambios.
- `test_resto_de_muestra_nunca_inventa_una_etiqueta`, guardia de tipos,
  guardia de vocabulario y no vacuidad: siguen en pie.

### Observación de integridad (no causada por esta fase)

`data/hands_db.jsonl.bak` tiene 1258 líneas y SHA medido
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2`. La hoja
de ruta cita `5ae2abd7…` para el original. El fichero es local y no está
versionado, y esta fase no lo ha escrito en ningún momento (`git diff -- data`
está vacío). La diferencia es preexistente y queda anotada como pendiente de
integridad de datos; no afecta a la base canónica, que sí coincide con el SHA
esperado.
