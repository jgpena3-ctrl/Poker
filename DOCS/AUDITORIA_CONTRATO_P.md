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

## 6. Y LO QUE QUEDA ABIERTO

| | | dueño |
|---|---|---|
| el **defecto del contador de subidas** | declarado, fijado con un test, y con su **condición de activación**: la recalibración | A2, con A1 |
| la **semántica de la `p` en las herramientas de auditoría** que no son el motor | su semántica depende de la codificación final | A2, con A1 |

> Y nada de esto es un hueco: es una excepción DECLARADA ✓. Y la diferencia
> entre un hueco y una excepción es la diferencia entre «nadie lo miró» y
> «está escrito, con su motivo y su condición» ✓.
