# HALLAZGOS DECLARADOS, Y POR QUÉ NO SE TOCAN

> Un hallazgo que no se corrige y no se declara es un fallo esperando a que
> alguien lo encuentre por sorpresa. Y un hallazgo que se corrige en el bloque
> que lo ha encontrado es un cambio de alcance disfrazado.
>
> Este documento declara los que **no** se corrigen, y por qué. Y la regla es
> la misma de `DOCS/SANEAMIENTO.md`:
>
> > Preferimos dejar una mano sin corregir a corregirla con una suposición: una
> > corrección razonada mal es indistinguible de un error, y nadie la va a
> > volver a mirar.

## La regla, y las dos mitades

| | |
|---|---|
| **preexistente** —que no es del cambio de este bloque— | se **declara** aquí y se **reporta**, y no se toca |
| **del cambio** —lo ha metido este bloque— | se **arregla** en el mismo commit, o se declara con su motivo |

Y el motivo de la primera fila es de procedimiento, no de gusto: un bloque que
arregla lo que ha encontrado deja de ser un bloque y se convierte en una
limpieza, y una limpieza mueve cosas que nadie ha medido.

## Y una cosa sobre este documento

Los hallazgos se nombran por su **nombre Unicode** y su **punto de código**, y
**no se reproducen**. Y no es una manía: este fichero está en el alcance del
barrido de caracteres, de modo que reproducir un carácter sospechoso aquí
sería **meter dos hallazgos nuevos**, y DECLARA el propio documento que los
declara.

> Un documento que declara los defectos no puede contenerlos. Y esa es la
> misma clase de error que un test que se señala a sí mismo.

## 1. Los 11 caracteres sospechosos

Y el número vive en una constante —`SOSPECHOSOS_ABAJO`, en
`tools/verificar_caracteres.py`— y un test lo compara con el de aquí, que es
la forma que tiene el proyecto de que una cifra y su sitio no se separen.

Y el barrido los encuentra por el **nombre Unicode** del carácter, y no por
rangos: `DOCS/LECCIONES_DE_INSTRUMENTACION.md` §19.

### 1.1 Los tres árabes — `motor/test_asistente_live.py`

MEDIDO, y lo que son: `ARABIC LETTER BEH` (U+0628), `ARABIC LETTER TEH`
(U+062A) y `ARABIC LETTER REH` (U+0631), **dentro de una palabra española**.
O sea que no es alfabeto: es una sustitución.

MEDIDO, y por qué los ve ahora y no antes: los rangos que tenía el barrido
iban de `0x3000` a `0x9FFF`, y el árabe está entre `0x0600` y `0x06FF`. O
sea que el barrido **no los veía**, y ahora sí.

**Por qué no se tocan:** el fichero es `motor/test_asistente_live.py`, que
está en la lista de «no tocar» de esta línea de trabajo, y la corrección —sea
cual sea— la tiene que hacer quien mantiene ese fichero.

### 1.2 Los dos BOM — `DOCS/APRENDIZAJE.md` y `DOCS/PROYECTO.md`

MEDIDO: `ZERO WIDTH NO-BREAK SPACE` (U+FEFF), al principio de los dos. O sea
un BOM, que es un byte que no se ve y que hace que el fichero se lea
distinto.

Y el barrido viejo no lo veía tampoco: de los invisibles solo cubría el
`U+FFFD`, el carácter de reemplazo.

**Por qué no se tocan:** son documentos, y un BOM al principio de un `.md` es
inofensivo para el contenido. Se declara para que no se pierda de vista, y
para que el día que se limpien sea una decisión y no un descuido.

### 1.3 Los cinco cirílicos y la coma CJK

| fichero | nombre Unicode | punto de código | qué es |
|---|---|---|---|
| `tools/test_disciplina_de_los_tests.py` | `CYRILLIC SMALL LETTER O` | U+043E | dentro de la palabra «hero» |
| `motor/test_canal_manual.py` | `CYRILLIC SMALL LETTER IE` | U+0435 | dentro de «exactamente» |
| `motor/test_canal_manual.py` | `CYRILLIC SMALL LETTER ES` | U+0441 | dentro de «exactamente» |
| `motor/test_canal_manual.py` | `CYRILLIC SMALL LETTER TE` | U+0442 | dentro de «exactamente» |
| `motor/test_canal_manual.py` | `CYRILLIC SMALL LETTER YA` | U+044F | dentro de «exactamente» |
| `motor/test_auditar_rango.py` | `IDEOGRAPHIC COMMA` | U+3001 | una coma CJK colada entre dos palabras |

MEDIDO, y el primero está en un fichero de `tools/`, que sí es de esta línea
de trabajo. Y **aun así no se toca**, y el motivo es el mismo que el de los
demás: **es preexistente**, y el alcance de un bloque es el cambio que
introduce, no la limpieza del repo entero.

> Y esto tiene un precio, y el precio se paga aquí: una `o` cirílica en un
> comentario es indistinguible de una `o` normal para quien lee. Lo que se
> puede hacer es **declararlo**, que es lo que hace este documento, y no fingir
> que no existe.

### 1.4 Y el que NO se toca, y es el más importante

`DOCS/INC-003_BARRIDO_DESTRUCTIVO.md` tiene un `CYRILLIC SMALL LETTER IE`
(U+0435) **deliberado**: es el ejemplo del incidente, y el propio documento
dice que es intencionado.

MEDIDO, y el motivo de que la excepción sea **por sitio** y no por carácter: el
**mismo** U+0435 en `motor/test_canal_manual.py` es una corrupción. Una
excepción por carácter los taparía a los dos, y el guardián no vería ni el
ejemplo ni la corrupción.

## 2. El docstring descuadrado de `motor/asistente_live.py`

MEDIDO: la línea 1365 tiene sangría 0, y el bloque de su docstring está en la
columna 8. Es un desfase real, y no un falso positivo: el guardián lo
comprueba contra el AST, y la línea pertenece al docstring.

**Por qué el guardián no lo ve:** el guardián de docstrings tiene su alcance
en `tools/`, y está declarado. Y está declarado **a propósito**: ampliarlo a
`motor/` pondría la suite en rojo sobre un fichero que esta línea de trabajo
no toca, y un guardián que se puede activar con un fichero ajeno es un
guardián que nadie va a activar.

**Quién lo arregla:** quien mantiene `motor/asistente_live.py`.

## 3. Y el fallo de este bloque, que no es un hallazgo del repo

Un script de corte se ejecutó dos veces, y la segunda **pisó la copia buena**
con la versión anterior del fichero, y se llevó por delante **ocho tests**.

MEDIDO, y por qué no dio ningún fallo: un test que desaparece no rompe nada,
porque no hay nada que ejecutar. Lo pilló el guardián de inventario, que mide
una cantidad y por lo tanto ve también las **pérdidas**.

Está en `DOCS/LECCIONES_DE_INSTRUMENTACION.md` §23, con la regla que sale:
un script que se vuelve a ejecutar tiene que ser idempotente.
