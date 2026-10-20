# ESTADO DEL TRABAJO: lo que está hecho, lo que sigue abierto, y lo que depende de A1

> Y este documento es el **registro** que el bloque pide: qué trabajo está
> terminado, qué sigue abierto, y qué depende de la revisión de las 203 manos.
>
> Y no es un informe: es un estado, y hay un test que comprueba que no se
> contradice a sí mismo.

## 1. TERMINADO, y con la medición

| | |
|---|---|
| **el contrato de la acción `p`** | `DOCS/CONTRATO_ACCION_P.md`. La semántica, los consumidores, y qué NO se hace |
| **el motor aprende la `p`** | `_es_ciega_bb` la reconoce, `preflop_events` salta las posts, y `entradas_bb_rechazadas` distingue las dos codificaciones |
| **la equivalencia de la codificacion** | MEDIDO: las doce categorias de la primera decision son **identicas** antes y despues, y las 921 ciegas siguen siendo 921 |
| **la auditoria de `rules.py`** | `DOCS/AUDITORIA_RULES.md`, con cuatro hallazgos y sus mediciones |
| **el defecto del contador de subidas** | declarado, fijado con un test, y con su **condicion de activacion** |
| **la cobertura de los guardianes** | el barrido mira la raiz y `trabajo/`, y el codigo fuera de las tres carpetas tiene que estar declarado |
| **el procedimiento de integracion** | `tools/integrar_copia.py`, probado en seco, y **listo para que A1 lo dispare** |

## 2. ABIERTO, y de quien es

| | de quien |
|---|---|
| las 203 manos | **de A1**. Y mientras no se cierren, no hay nada que recalibrar |
| `matrix` | de quien generó el fichero |
| las 5 manos con board divergente | de quien pueda interpretar los datos |
| la vía preflop del motor | del dueño de `motor/` |
| el peso por rival | de quien decida el objetivo |
| **el defecto del contador de subidas** | de la **recalibración**: se corrige cuando las cifras se re-deriven contra la base adoptada |

## 3. LO QUE DEPENDE DE A1, Y QUE ESTA PREPARADO

Y que no se depende de la base canónica, que sigue intacta:

| lo que falta | lo que hay hecho para que no falte |
|---|---|
| **el numero de ciegas de la copia** | el umbral lo fija A1. Y `tools/integrar_copia.py` **no lo puede dar por puesto**: sin umbral dice que la ejecucion esta INCOMPLETA y sale con codigo distinto de cero |
| **las categorias de la copia** | el procedimiento las mide y las compara con las de control |
| **el fallo del motor con la copia** | el procedimiento cuenta los errores de clasificacion, uno a uno |
| **la validacion de los guardianes** | el procedimiento lanza los dos, y solo si el destino es la base canonica |

Y el procedimiento, en una linea:

```
python tools/integrar_copia.py --umbral-ciegas <el que fije A1>
```

Y hace, en este orden:

1. intercambia `data/hands_db.jsonl` por la copia, **con restauracion
   garantizada en el `finally` y verificada por sha**;
2. mide los errores de clasificacion, las ciegas reconocidas y las
   violaciones de CM-004;
3. lanza los dos guardianes —el de vocabulario y el de no vacuidad—;
4. compara con los valores de control: 921 ciegas, 0 violaciones, y las doce
   categorias de la primera decision;
5. **falla** si las ciegas no bastan para el umbral declarado, si hay
   errores, o si las categorias no son las de control;
6. restaura la base canonica y **comprueba su sha**.

> Y la prueba de que el intercambio es seguro esta en
> `tools/test_integrar_copia.py`, y **no toca la base canonica ni un
> instante**: el test usa un destino temporal y una copia reducida de las
> primeras manos de verdad.

Y una cosa que conviene que conste, porque la adicion del proyecto la dijo
sola: `tools/integrar_copia.py` **ESCRIBE en la base**, y el instrumento
`tools/quien_escribe.py` —que mira por el ARBOL quien escribe en
`hands_db.jsonl`— lo detecto y el test de los escritores declarados fallo.
De modo que esta **declarado** como escritor, con su motivo, en
`motor/test_quien_escribe.py`.

> Y que un guardián del proyecto detecte un fichero nuevo que escribe, sin
> que nadie se lo diga, es exactamente para lo que está.

## 4. LO QUE NO SE HACE, Y POR QUE

| | |
|---|---|
| recalibrar con la copia | las cifras se re-derivan contra la base **adoptada**, y todavia no hay base adoptada |
| declarar canónica la copia | es la decisión de A1 |
| arreglar el defecto del contador | **recalibra**, y la recalibración viene después |
| ampliar los contratos por conveniencia | un contrato que crece para no tener que decidir es un contrato que no decide |

## 5. Y LO QUE ESTA EN SUS MANOS

> **El cierre técnico de este trabajo NO equivale a autorizar la adopción de
> la copia normalizada.** Esa decisión sigue dependiendo de la revisión de A1,
> de la validación completa de la base candidata, y de la comprobación de que
> el motor conserva la semántica esperada.
>
> Y el procedimiento de `tools/integrar_copia.py` es **lo que falta
> ejecutar**, no lo que falta escribir.
