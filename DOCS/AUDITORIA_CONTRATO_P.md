# AUDITORIA DEL CONTRATO DE LA `p`: quien la lee, quien la produce, y que vigila

> Y el criterio de cierre de esta auditoría es el de R2: **cada consumidor tiene
> un contrato explícito y pruebas que detectan una interpretación incorrecta de
> `p`**. Y no basta con que los tests pasen: hace falta haberlos **visto
> fallar**, y eso es lo que hace la sección 5.

## 1. EL INVENTARIO, POR EL ÁRBOL

MEDIDO, y el inventario es **corto**, que es la mejor noticia:

| consumidor | qué hace con la `p` | su contrato |
|---|---|---|
| `motor/learn.py` `_es_ciega_bb` | una `BB p` es la ciega del BB | la ciega puede escribirse de las dos maneras |
| `motor/learn.py` `preflop_events` | **la salta**: no es una decisión | una posta pone dinero, no decide, y **no sube el nivel** |
| `motor/learn.py` `entradas_bb_rechazadas` | una `BB p` marca que el BB ya posteó | una ciega tarde es un rechazo, con las dos codificaciones |
| `motor/learn.py` `manos_con_orden_ciega_malo` | el invariante de CM-004 | mira las dos codificaciones |
| `tools/aritmetica_botes.py` | la acepta como acción que no suma | la aritmética del bote |
| `tools/interpretar_bote.py` | la acepta entre las acciones | idem |
| `tools/integrar_copia.py` | la excluye de las **decisiones** al comparar importes | la comparación de datos entre bases |

> Y los **productores**: `tools/fixture_copia_sintetica.py` (el fixture) y la
> herramienta del trabajo en paralelo (la copia real). Y no hay ningún otro ✓.

## 2. Y EL EFECTO EN CADA COSA, QUE SON TRES Y SE CONFUNDEN

| | lo que la `p` **no** hace | el test que lo fija |
|---|---|---|
| el **contador de subidas** | no cuenta como subida | `test_una_p_no_es_un_limp_para_los_demas` |
| la **clasificación preflop** | no produce evento, y el jugador sigue sin decidir | `test_una_p_sola_no_es_ninguna_decision` |
| la **reconstrucción del orden** | una `BB p` es la ciega, y una `BB p` tarde es un rechazo | `test_un_bb_p_tras_accion_voluntaria_no_es_ciega` |

> Y el caso que más se confunde es el **ante**, porque la ciega del BB la
> reconoce `_es_ciega_bb` en las dos codificaciones y **el ante no**: de modo
> que un ante mal tratado se cuela en el recuento de limps, que es un
> contador GLOBAL de la mesa. Y por eso el ante tiene su propio test ✓.

## 3. LOS CASOS SINTÉTICOS

Y todos son manos de tres líneas, y ninguno sale de la base —que hoy no tiene
ni una `p` ✓—:

| caso | qué mira |
|---|---|
| la ciega del BB como `p` | que se reconoce como ciega, y no como subida |
| una `BB p` **tarde** | que sale como rechazo, con el motivo de CM-004 |
| una `p` sola | que no produce ninguna decisión |
| las dos ciegas posteadas | que el SB no aparece como `limp` |
| **las ciegas consecutivas** | que no generan ninguna decisión |
| **el ante como `p`** | que no es una decisión y no sube el nivel |
| **una entrada desconocida** (`z`) | que **lanza**, y que no se convierte en una acción válida |
| **el invariante de CM-004** con la codificación nueva | que una `BB p` tarde sale igual que una `BB b` tarde |
| **un BB que ya posteó** | que una `b` posterior suya no es un rechazo |

## 4. Y LA COMPATIBILIDAD CON CM-004

Y MEDIDO, y es compatible ✓:

- el invariante de CM-004 mira las **dos** codificaciones ✓, de modo que el
  defecto es el mismo con dos nombres ✓;
- y una `BB p` que llega tarde sale con **el mismo motivo** que una `BB b`
  que llega tarde ✓.

Y lo que **no** es compatible, y ya estaba declarado de antes: el **defecto
del contador de subidas** —un limp corto de ≤ 0.5 BB contado como subida—,
que MEDIDO afecta a **43 de las 877** manos de la ventana fiable. Y su
activación es la **recalibración**, que es post-adopción ✓.

## 5. Y QUE LOS TESTS NO SON VACÍOS

Y esta es la parte que R2 pide, y la que un test que pasa no puede
demostrar. Y el método es **mutar el motor** y mirar si los tests lo notan ✓:

| mutación | qué rompe | resultado |
|---|---|---|
| M1 | el salto de las posts en `preflop_events` | **los tests lo notan** ✓ |
| M2 | `_es_ciega_bb` deja de reconocer la `p` como ciega | **los tests lo notan** ✓ |
| M3 | `entradas_bb_rechazadas` deja de marcar «el BB ya posteó» | **los tests NO lo notaban** ✗ |

> **Y M3 encontró un hueco REAL.** Y el hueco era este: que un BB que ya
> posteó la ciega, y después tiene una `b`, no puede tener una ciega
> segunda —porque si la tiene, se marca como rechazo, un falso positivo—.
> Y **ningún test lo miraba**. Y el test que lo cierra ahora existe ✓, y
> la contraparte también: la misma mano sin la `p` de antes **sí** es un
> rechazo ✓.

Y el motor se restauró después de cada mutación, verificado por sha ✓, y el
motor está **byte a byte** como estaba ✓.

## 6. Y EL INSTRUMENTO DE MUTACIÓN, QUE ES UN INSTRUMENTO Y NO UN TEST

Y `tools/mutar_contrato_p.py` **no es un test de la suite normal** ✓: se
ejecuta a mano cuando se quiere comprobar que los tests no son vacíos ✓, y
no en cada `pytest` ✓. Y el motivo es concreto: **muta el motor**, y un test
que muta el motor mientras corre la suite puede dejarlo roto si la suite se
interrumpe ✓.

Y sus cuatro condiciones de seguridad, que están comprobadas ✓:

| | |
|---|---|
| **árbol limpio** | sin cambios sin commitear, se niega, y **no muta nada** ✓ |
| **restauración siempre** | el original se guarda en memoria y se restaura en un `finally`, y **no depende de que el test pase**: si el test lanza, el fichero vuelve igual ✓ |
| **mutaciones declaradas** | las tres, con su descripción; y una que no lo está es un **error**, no un «no encuentro el patrón» ✓ |
| **sin rastro** | el sha del fichero restaurado, y ningún temporal en `motor/` ni en la raíz ✓ |
| **la CACHE invalidada** | el `.pyc` del módulo mutado se borra antes de correr los tests, y se corre con `PYTHONDONTWRITEBYTECODE=1` ✓ |

> Y esa última condición no es un detalle: **MEDIDO, sin ella el instrumento
> da falsos positivos** ✓. Y la razón es que la mutación M3 cambia `'p'` por
> `'q'` ✓, de modo que **el fichero conserva el mismo tamaño** ✓, y en
> Windows la marca de tiempo tiene una granularidad gruesa ✓: de modo que el
> `__pycache__` se podía considerar válido ✓, y el subproceso importaba el
> **bytecode mutado** en vez del código restaurado ✓. Y un instrumento que
> miente es peor que no tener instrumento ✓, porque su conclusión se cita ✓.

## Y LA TABLA, QUE ES LA EVIDENCIA

> **La tabla de mutaciones ES la evidencia de que los tests no son vacíos** ✓.
> Y no lo es porque las mutaciones existan ✓, sino porque **cada una la nota
> el test que la tabla declara** ✓.

Y la tabla, con sus cuatro filas ✓:

| mutacion | el invariante que rompe | el test que tiene que notarla |
|---|---|---|
| M1 | una posta no es una decision, y el jugador sigue sin decidir | `test_una_p_sola_no_es_ninguna_decision` |
| M2 | la ciega del BB puede escribirse de las dos maneras | `test_la_ciega_del_bb_grabada_como_p_se_reconoce` |
| M3 | un BB que YA posteo la ciega no puede tener una ciega segunda | `test_un_bb_que_ya_posteo_no_vuelve_a_ser_una_ciega` |
| M4 | un BB que NO posteo antes y tiene una `b` tarde es un rechazo | `test_sin_la_p_de_antes_la_b_del_bb_si_es_un_rechazo` |

> Y **una mutacion que nadie nota no es un detalle: es una BRECHA DE
> COBERTURA** ✓, y no un motivo para relajar el test ✓.

### Y los pares, y la verdad medida de la sensibilidad cruzada

Y M3 y M4 son **las dos caras del mismo hueco** ✓ —el BB que ya posteo ✓ y el
BB que no posteo antes ✓— y por eso son un par ✓.

Y lo MEDIDO ✓, que es lo que la tabla declara y lo que los tests comprueban ✓:

| | sensible a M3 | sensible a M4 |
|---|---|---|
| el caso de la `p` —un BB que ya posteo— | **si** ✓ | no ✓ |
| el caso de la `b` —un BB que no posteo antes— | no ✓ | **si** ✓ |

> Y lo de la diagonal en cero **no es un fallo**: son afirmaciones **opuestas**
> ✓, y por eso la regla de la tabla es **cada caso vigila lo suyo** ✓, y no
> «cada caso nota todas las mutaciones» ✓ —que seria imposible ✓.


### Y M3 ENCONTRÓ UN HUECO REAL, Y AHORA TIENE TEST Y CONTRAPARTE

> Y esto hay que dejarlo escrito, para que no se lea como «M3 estaba bien y no
> hacía falta»: **M3 no la vio nadie**, y por eso encontró un hueco ✓.

Y el hueco, en una frase: que un BB que **ya posteó** la ciega y después tiene
una `b` no puede tener una ciega segunda ✓ —porque si la tiene, se marca
como rechazo, un falso positivo— ✓.

Y ahora tiene **las dos caras** ✓:

| | lo que afirma | la mutación que lo rompe |
|---|---|---|
| el caso | un BB que ya posteó **no** es un rechazo | **M3** ✓ |
| la contraparte | un BB que **no** posteó antes **sí** es un rechazo | **M4** ✓ |

> Y el motivo de que la contraparte sea sensible a **M4** y no a **M3** ✓:
> son **casos distintos** ✓. M3 es el caso de la `p` —un BB que ya posteó— ✓,
> y la contraparte es el de la `b` —un BB que no posteó antes— ✓, y ahí la
> marca de «ya posteó» no interviene ✓. Y esa asertion es más útil que la
> que se leería al principio: dice que **cada caso vigila lo suyo** ✓, y que
> un solo test que vigilara los dos con una sola mutación no distinguiría
> nada ✓.

## 7. Y LO QUE QUEDA ABIERTO

| | | dueño |
|---|---|---|
| el **defecto del contador de subidas** | declarado, fijado con un test, y con su **condición de activación**: la recalibración | A2, con A1 |
| la **semántica de la `p` en las herramientas de auditoría** que no son el motor | su semántica depende de la codificación final | A2, con A1 |

> Y nada de esto es un hueco: es una excepción DECLARADA ✓. Y la diferencia
> entre un hueco y una excepción es la diferencia entre «nadie lo miró» y
> «está escrito, con su motivo y su condición» ✓.
