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
| **la declaración de los escritores** | `motor/test_quien_escribe.py`, y ahora **verificable**: qué escribe, dónde y bajo qué condición |

## 2. ABIERTO, de A1

| trabajo | dueño | condición de activación |
|---|---|---|
| las 203 manos sin resolver | A1 | la revisión manual de cada una, con la grabación original |
| el umbral de ciegas de la copia | A1 | haber cerrado las 203, y el número sale de los datos revisados |
| la primera ejecución real de `integrar_copia.py` | A1 | el umbral declarado, y la copia validada |

## 3. ABIERTO, de A2, y DEPENDE de A1

| trabajo | dueño | condición de activación |
|---|---|---|
| el defecto del contador de subidas | A2, con A1 | las cifras se re-derivan contra la base **adoptada**, y no antes |
| la recalibración de perfiles, rangos y frecuencias | A2, con A1 | la base adoptada, y el manifiesto redeclarado |
| la traducción del `p` en las herramientas de auditoría que no son el motor | A2, con A1 | la base adoptada, porque su semantica depende de la codificacion final |

## 4. ABIERTO, de A2, INDEPENDIENTE

| trabajo | dueño | condición de activación |
|---|---|---|
| `matrix`: auditar el origen de las discrepancias y las dependencias del calculo, sin regenerar derivados | A2 | ninguna: se puede empezar ya |
| las 5 manos con board divergente: clasificar cuales se pueden analizar desde el codigo y cuales dependen de A1 | A2 | ninguna para la clasificacion; la resolucion depende de A1 |
| la via preflop: revisar el recorrido de las acciones, sus contratos y la propagacion de estados, con pruebas sinteticas | A2 | ninguna: se puede empezar ya |
| el peso por rival: auditar la logica de asignacion y sus condiciones de aplicacion, sin recalibrar con la copia | A2 | ninguna: se puede empezar ya |

> Y los cuatro **auditados y clasificados** en
> [`AUDITORIA_FRONTES.md`](AUDITORIA_FRONTES.md), que dice, para cada uno, qué
> parte es del código y qué parte depende de A1. Y lo que sale de los cuatro es
> lo mismo: **la parte que se puede decidir desde el código está medida y es
> pequeña, y la parte que depende de los datos es de otra persona.**

## 5. ABIERTO, sin dueño asignado

| trabajo | dueño | condición de activación |
|---|---|---|
| ninguno | — | — |

> Y que este apartado este vacio **es una declaracion**: un trabajo abierto sin
> dueño es un trabajo que no se hace, y por eso el registro lo tiene
> explicito.

## 6. LAS CONDICIONES DE ACTIVACIÓN, en una tabla

Y esta tabla es la que el test comprueba: **cada trabajo abierto tiene dueño y
condición**, y la condición dice **qué lo desbloquea**, no «cuando se pueda».

| trabajo | dueño | condición de activación |
|---|---|---|
| las 203 manos | A1 | la revisión manual de cada una, con la grabación original |
| el umbral de ciegas de la copia | A1 | haber cerrado las 203; el número sale de los datos revisados |
| la primera ejecucion real de la integracion | A1 | el umbral declarado, y la copia validada |
| el defecto del contador de subidas | A2, con A1 | las cifras se re-derivan contra la base adoptada, y no antes |
| la recalibracion de derivados | A2, con A1 | la base adoptada, y el manifiesto redeclarado |
| la traduccion del `p` en las auditorias | A2, con A1 | la base adoptada, porque su semantica depende de la codificacion final |
| `matrix` | A2 | ninguna: se puede empezar ya |
| las 5 manos divergentes | A2 | ninguna para la clasificacion; la resolucion depende de A1 |
| la via preflop | A2 | ninguna: se puede empezar ya |
| el peso por rival | A2 | ninguna: se puede empezar ya |

## 7. LOS COMANDOS PARA REPETIR LA VALIDACIÓN

Y con el resultado que se espera, para que repetirla no sea adivinar:

| | comando | resultado esperado |
|---|---|---|
| la suite entera | `python -m pytest motor recorder tools --ignore=tools/test_live.py --ignore=tools/test_mano6.py -q` | todo en verde |
| el procedimiento, en seco | `python tools/integrar_copia.py --destino <temporal> --origen <candidata> --umbral-ciegas <N>` | codigo 0, y la base restaurada |
| el procedimiento, sin umbral | el mismo, **sin** `--umbral-ciegas` | codigo **2**, y `INCOMPLETA` en la salida |
| la base canonica | `python -c "import hashlib,io;print(hashlib.sha256(io.open('data/hands_db.jsonl','rb').read()).hexdigest())"` | `5ae2abd71832dccd3f1d58859a05b35494de24795841682f601e873b41ce4dc1` |

## 8. Y LO QUE NO SE HACE, Y POR QUÉ

| | |
|---|---|
| recalibrar con la copia | las cifras se re-derivan contra la base **adoptada**, y todavía no hay base adoptada |
| declarar canónica la copia | es la decisión de A1 |
| arreglar el defecto del contador | **recalibra**, y la recalibración viene después |
| ampliar los contratos por conveniencia | un contrato que crece para no tener que decidir es un contrato que no decide |
| reutilizar el 921 como umbral de la copia | el 921 es el control de regresión de la base **de hoy**, y nada más |

## 9. Y LO QUE ESTA EN SUS MANOS

> **El cierre técnico de este trabajo NO equivale a autorizar la adopción de
> la copia normalizada.** Esa decisión sigue dependiendo de la revisión de A1,
> de la validación completa de la base candidata, y de la comprobación de que
> el motor conserva la semántica esperada.
>
> Y el procedimiento de `tools/integrar_copia.py` es **lo que falta
> ejecutar**, no lo que falta escribir.
