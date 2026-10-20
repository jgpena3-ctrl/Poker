# ESTADO DEL TRABAJO: lo que está hecho, lo que sigue abierto, y lo que depende de A1

> Y este documento es el **registro** que el bloque pide: qué trabajo está
> terminado, qué sigue abierto, de quién es, y **qué condición lo
> desbloquea**.
>
> Y no es un informe: es un estado, y hay un test que comprueba que no se
> contradice a sí mismo: que todo lo abierto tiene dueño y condición.

## 1. TERMINADO, por A2

| | |
|---|---|
| **el contrato de la acción `p`** | `DOCS/CONTRATO_ACCION_P.md`. La semántica, los consumidores, y qué NO se hace |
| **el motor aprende la `p`** | `_es_ciega_bb` la reconoce, `preflop_events` salta las posts, y `entradas_bb_rechazadas` distingue las dos codificaciones |
| **la equivalencia de la codificación** | MEDIDO: las doce categorías de la primera decisión son **idénticas** antes y después, y las 921 ciegas siguen siendo 921 |
| **la auditoría de `rules.py`** | `DOCS/AUDITORIA_RULES.md`, con cuatro hallazgos y sus mediciones |
| **el defecto del contador de subidas** | declarado, fijado con un test, y con su **condición de activación** |
| **la cobertura de los guardianes** | el barrido mira la raíz y `trabajo/`, y el código fuera de las tres carpetas tiene que estar declarado |
| **el procedimiento de integración** | `tools/integrar_copia.py`, probado en seco con la copia sintética **completa** de 1258 manos, y con sus dos caminos de fallo |
| **los DOS fixtures** | uno **suave** —solo recodifica— y otro **duro** —además añade las ciegas que faltaban—, y el duro reconoce **1258** ciegas, las mismas que la copia real |
| **el número de ciegas, que no es una constante global** | lo mide cada fixture y lo dice en su informe, y es **exacto** y no un mínimo: un control que no puede fallar no es un control |
| **la auditoría del contrato de la `p`** | `DOCS/AUDITORIA_CONTRATO_P.md`: el inventario de los lectores y los productores, los tres efectos, los casos sintéticos, la compatibilidad con CM-004, y la **mutación** que demuestra que los tests no son vacíos |
| **la auditoría de `matrix`** | `DOCS/AUDITORIA_MATRIX.md`: el mapa real de los lectores, los contratos de lectura, y los cinco hallazgos con su categoría. Y sus tres decisiones, declaradas como de A1 |
| **la vía preflop observable** | `DOCS/OBSERVABLE_PREFLOP.md`: qué es observable, quién lo valida sin sesgo, y qué está medido y qué es hipótesis |
| **la declaración de los escritores** | `motor/test_quien_escribe.py`, y ahora **verificable**: qué escribe, dónde y bajo qué condición |

## 2. ABIERTO, de A1

| trabajo | dueño | condición de activación |
|---|---|---|
| las 203 manos sin resolver | A1 | la revisión manual de cada una, con la grabación original |
| el número de ciegas que la copia debe reconocer | A1 | haber cerrado las 203, y el número sale de los datos revisados. Y el procedimiento **no tiene un valor por defecto**: sin ese parámetro sale con código **2** |
| las doce categorías que la copia debe dar | A1 | lo mismo, y por un motivo que está medido: **la copia no es solo una re-codificación** |
| la primera ejecución real de `integrar_copia.py` | A1 | el número de ciegas declarado, y el control de categorías declarado |

## 3. ABIERTO, de A2, y DEPENDE de A1

| trabajo | dueño | condición de activación |
|---|---|---|
| el defecto del contador de subidas | A2, con A1 | las cifras se re-derivan contra la base **adoptada**, y no antes |
| la recalibración de perfiles, rangos y frecuencias | A2, con A1 | la base adoptada, y el manifiesto redeclarado |
| la traducción del `p` en las herramientas de auditoría que no son el motor | A2, con A1 | la base adoptada, porque su semantica depende de la codificacion final |

## 4. ABIERTO, de A2, INDEPENDIENTE

Y los cuatro frentes, con los CINCO campos que hacen falta para retomarlos:
**responsable**, **resultado medido**, **decisión pendiente**, **condición de
activación** y **prueba que demuestra el cierre**.

| frente | responsable | resultado medido | decisión pendiente | condición de activación | prueba que demuestra el cierre |
|---|---|---|---|---|---|
| `matrix` | A2, y A1 para las tres decisiones | el mapa: **tres** lectores del fichero, uno lo lee a través de otro, y tres solo lo mencionan. Y la cobertura: **324** spots, **252** con tabla, el **78 %** | qué significa una celda; el **22 %** de spots sin tabla; la regla de `Call_OR` | ninguna para la auditoría: se puede seguir midiendo. Y para las tres decisiones, la de A1 | `motor/test_lectura_matrices.py` (10) y `tools/test_cifras_no_movidas.py` (2) |
| las 5 manos con board divergente | A2, y A1 para 2 cartas | **27** de **29** son un resumen truncado —`comunitarias` es un subconjunto de `streets`— y se clasifican sin la grabación | la identidad de la carta de `H_0915` y de `H_0921` | la resolución es de A1, con la grabación | `tools/test_auditoria_frentes.py` (las dos cifras y su condición) |
| la vía preflop | A2, y quien decide el alcance | el contrato está escrito, sus **dos decisiones ya están tomadas**, y el camino **observable existe** en el motor: `equity_preflop_rango` no usa las cartas del rival, y hay un test de fuga que lo comprueba | que la equity observable **ordena** las manos —**no medido**, y el motivo es de coste—; y si la herramienta debe pasar a medirla, que **movería el AUC publicado** y es post-adopción | ninguna para la auditoría; las dos son de alcance | `tools/test_observable_preflop.py` (5) y `DOCS/OBSERVABLE_PREFLOP.md` |
| el peso por rival | A2, y quien decide el objetivo | la mediana se aplica sobre los rivales **evaluables**, y ahora el resultado lleva `n_evaluados`. Y el frente de **instrumentación está CERRADO**: la agregación hace lo que decía, y hay la evidencia de los seis casos | si la mediana es la reducción correcta, para la métrica siguiente | ninguna para la instrumentación: está cerrada. Y para la elección, de quien decide el objetivo | `tools/test_agregacion_rival.py` (9) y la evidencia en `DOCS/AUDITORIA_FRONTES.md` §4 |

> Y el patrón de los cuatro es el del proyecto entero: **la parte que se
> puede decidir desde el código está medida y es pequeña; y la parte que
> depende de los datos es de otra persona.**


## 5. ABIERTO, sin dueño asignado

| trabajo | dueño | condición de activación |
|---|---|---|
| ninguno | — | — |

> Y que este apartado este vacio **es una declaracion**: un trabajo abierto sin
> dueño es un trabajo que no se hace, y por eso el registro lo tiene
> explicito.
>
> **Y este apartado esta vacio porque TODO trabajo abierto tiene dueño.** Y si
> en el futuro aparece un trabajo sin dueño, **el test falla y obliga a
> decidir**: hay que darle un dueño, o hay que decidir que no es trabajo.
> Y las dos cosas son decisiones, y las dos se pueden tomar; lo que no se
> puede es dejar el trabajo sin dueño y que nadie lo mire.

## 6. LAS CONDICIONES DE ACTIVACIÓN, en una tabla

Y esta tabla es la que el test comprueba: **cada trabajo abierto tiene dueño y
condición**, y la condición dice **qué lo desbloquea**, no «cuando se pueda».

| trabajo | dueño | condición de activación |
|---|---|---|
| las 203 manos | A1 | la revisión manual de cada una, con la grabación original |
| el número de ciegas de la copia | A1 | haber cerrado las 203; el número sale de los datos revisados |
| las doce categorías de la copia | A1 | haber cerrado las 203; y el número sale de los datos revisados, y no del fichero de la copia |
| la primera ejecucion real de la integracion | A1 | el umbral declarado, y la copia validada |
| el defecto del contador de subidas | A2, con A1 | las cifras se re-derivan contra la base adoptada, y no antes |
| la recalibracion de derivados | A2, con A1 | la base adoptada, y el manifiesto redeclarado |
| la traduccion del `p` en las auditorias | A2, con A1 | la base adoptada, porque su semantica depende de la codificacion final |
| `matrix` | A2 | ninguna: se puede empezar ya |
| las 5 manos divergentes | A2 | ninguna para la clasificacion; la resolucion depende de A1 |
| la via preflop | A2 | ninguna: se puede seguir midiendo. Y para las dos decisiones de alcance, de quien decide |
| el peso por rival | A2 | ninguna: se puede empezar ya |

## 7. LOS COMANDOS PARA REPETIR LA VALIDACIÓN

Y con el resultado que se espera, para que repetirla no sea adivinar:

| | comando | resultado esperado |
|---|---|---|
| la suite entera | `python -m pytest motor recorder tools --ignore=tools/test_live.py --ignore=tools/test_mano6.py -q` | todo en verde |
| el procedimiento, en seco | `python tools/integrar_copia.py --destino <temporal> --origen <candidata> --ciegas-esperadas <N>` | codigo 0, y la base restaurada |
| el procedimiento, sin el numero | el mismo, **sin** `--ciegas-esperadas` | codigo **2**, y `INCOMPLETA` en la salida |
| el procedimiento, con el numero equivocado | `--ciegas-esperadas` con el de otra base | codigo **1**, y `EL NUMERO DE CIEGAS NO ES EL DECLARADO` |
| la base canonica | `python -c "import hashlib,io;print(hashlib.sha256(io.open('data/hands_db.jsonl','rb').read()).hexdigest())"` | `5ae2abd71832dccd3f1d58859a05b35494de24795841682f601e873b41ce4dc1` |

## 8. Y LO QUE NO SE HACE, Y POR QUÉ

| | |
|---|---|
| recalibrar con la copia | las cifras se re-derivan contra la base **adoptada**, y todavía no hay base adoptada |
| declarar canónica la copia | es la decisión de A1 |
| arreglar el defecto del contador | **recalibra**, y la recalibración viene después |
| ampliar los contratos por conveniencia | un contrato que crece para no tener que decidir es un contrato que no decide |
| reutilizar el 921 como umbral de la copia | el 921 es el control de regresión de la base **de hoy**, y nada más |
| dar por neutro el cambio de las doce categorías de la copia | **no lo es**: MEDIDO, la copia cambia el `final_pot` de 689 de las 1055 manos resueltas, y de esas la copia coincide con el bote resuelto y la base de hoy solo en 366. Y en 73 manos cambian los importes, y el importe decide la categoría |

## 9. Y LO QUE ESTA EN SUS MANOS

> **El cierre técnico de este trabajo NO equivale a autorizar la adopción de
> la copia normalizada.** Esa decisión sigue dependiendo de la revisión de A1,
> de la validación completa de la base candidata, y de la comprobación de que
> el motor conserva la semántica esperada.
>
> Y el procedimiento de `tools/integrar_copia.py` es **lo que falta
> ejecutar**, no lo que falta escribir.


## 10. QUÉ NO SE TOCA HASTA LA ADOPCIÓN

Y no es una lista de cosas intocables: es la lista de las cosas que **cambian
la respuesta**, con el motivo de cada una. Y el motivo es lo que las
sostiene: una cosa intocable sin motivo es una superstición, y una
superstición se negocia.

| | lo que no se toca | por qué |
|---|---|---|
| 1 | **el defecto del contador de subidas** | MEDIDO, un limp corto de ≤ 0.5 BB cuenta como una subida, y arreglarlo **recalibra**: toca 43 de las 877 manos de la ventana |
| 2 | **el AUC publicado** | su calculo depende del numero de manos (877 hoy) y de las DECISIONES de la base; y una recalibracion va despues de la adopcion |
| 3 | **el grafo de `preflop_matrices.json`** | lo leen **siete** modulos, y la intencion del fichero la declara A1: un cambio en el grafo sin la intencion fijada es un cambio a ciegas |
| 4 | **las cifras derivadas** | frecuencias, rangos y perfiles se derivan de la base; derivarlos contra una base que todavia no es canonica es medir sobre nada |
| 5 | **la herramienta de equity preflop** (`tools/equity_de_mano.py`) | MEDIDO, usaria la via **observable** en vez de la retrospectiva, y eso **moveria el AUC publicado** |
| 6 | **cualquier cifra que dependa del numero de manos** | la ventana fiable son **877** manos de la base de HOY y la copia tiene **1258**: el 29 de hoy no es el 29 de despues, y el 5 tampoco |

> Y el patron: **las cinco primeras se mueven al adoptar, y la sexta se
> vuelve a medir al adoptar**. Y ninguna se toca antes, porque antes no
> hay una base que las sostenga.

## 11. EL ESTADO DE A2, Y EL DE A1

> **A2 ha cerrado todo lo que puede cerrar sin A1; lo que queda abierto es de
> A1 o post-adopción.**

Y lo que queda abierto, con su dueño, está en §2 (lo de A1) y en §3 (lo de
A2 que depende de A1). Y lo que está en §4 son los frentes **independientes**,
que se han auditado y clasificado, y cuya decisión es de alcance.

Y los **dos controles** del procedimiento los declara **A1**, y el script
**no tiene valor por defecto para ninguno de los dos**:

| | quién lo declara | y qué pasa sin él |
|---|---|---|
| el número de ciegas | A1, al cerrar las 203 | el script sale con el código **2**, y el veredicto nombra **el número de ciegas** |
| el control de las doce categorías | A1, sobre la copia ya revisada | el script sale con el código **2**, y el veredicto nombra **el control de las categorias** |

> Y el motivo de que no haya valores por defecto: el de las doce categorías de
> la base de hoy es el control de **neutralidad de la codificación**, que es
> otra pregunta, y usarlo por defecto sería responder una que nadie ha
> hecho. Y el del número de ciegas sale de datos que todavía no son
> canónicos.

## 12. QUÉ DEBE HACER A1 ANTES DE DISPARAR

Y son cuatro pasos, y cada uno tiene su criterio de **hecho**, que es lo que
los hace comprobables y no una lista de intenciones.

| # | paso | su criterio de «hecho» |
|---|---|---|
| 1 | **cerrar las 203 manos** | las 203 tienen su bote resuelto con la grabación original, y el detalle lo dice: `trabajo/botes_aritmetica.jsonl` con `resuelto` en las 203 |
| 2 | **fijar el número de ciegas de la copia** | el número que el motor reconoce en la copia revisada, y el **control de categorías** que la copia da, medido sobre ella |
| 3 | **declarar los dos controles** | `--ciegas-esperadas <N>` y `--control-categorias <fichero.json>`, y el fichero con las doce categorías **de la copia**, no las de la base de hoy. Y **sin el control de categorías declarado el script NO da verde**: sale con el código **2**, que es INCOMPLETA y no FALLO, porque «no has decidido» no es «has fallado» |
| 4 | **disparar la primera ejecución real** | `python tools/integrar_copia.py --ciegas-esperadas <N> --control-categorias <fichero.json>`, y el resultado con las **tres** secciones, y el **código 0** |

> Y los dos controles del paso 3 son **declaraciones**, no medidas del
> script: y el de las categorías **tiene que ser el de la copia**, porque el
> de la base de hoy es el control de NEUTRALIDAD DE LA CODIFICACIÓN, y la
> copia no es solo una re-codificación (MEDIDO: cambia el `final_pot` de 689
> de las 1055 manos resueltas).
>
> Y el paso 4 **no lo dispara este trabajo**. Es de A1, y por una razón que
> no es de instrumentación: la adopción es una decisión sobre datos que
> todavía se están validando.

