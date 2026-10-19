# Lecciones de instrumentación

Lo que se ha aprendido **midiendo el propio instrumento**, no el sistema que el
instrumento vigila. Es un documento aparte de `APRENDIZAJE.md`, que es de las
lecciones del motor: perfiles, frecuencias, rangos. Aquí no hay manos ni
rangos; hay comprobaciones que no medían lo que decían.

Cada punto lleva la medición que lo sostiene. Un punto sin medición no está
aquí.

## 1. Tres fallos de parche, medidos

### 1.1 Un `find` que dio −1 y un `s[-1:]`

```python
j = s.find(NL + NL + 'def _es_raise', i)
if j < 0:
    j = s.find('def _es_raise(', i)
s = s[:i].rstrip() + NL + NL + s[j:]
```

El corte anterior ya había borrado `_es_raise`, así que `j` era `-1` y
`s[j:]` era `s[-1:]`: **el último carácter**.

Lo que se llevó:

```
@@ -3114,170 +3164 @@ BUSQUEDAS_ACEPTADAS = ()
-def _lineas_de(nombre):
-def _es_raise(nombre, linea):
-def test_no_hay_busquedas_sobre_fuente_sin_declarar():
-def test_el_inventario_de_busquedas_detecta_una_decoracion():
-def test_el_barrido_de_mensajes_alcanza_los_raise_y_solo_los_de_tools():
```

**170 líneas por una**, y no eran código de este bloque: eran **tres tests**,
incluido el que vigila al detector.

Las tres piezas no fallan:

- un `find` que devuelve `-1` no falla
- un `s[-1:]` sobre un `-1` no falla
- y los dos juntos borran el fichero y lo escriben como si fuera el resultado

Un fallo de medición que devuelve el valor que esperas ver, en su forma más
barata: **no hay error**.

### 1.2 Reconstruir el objeto y perder lo aplicado

Las sustituciones se hacían sobre `texto`; una función reescribía `texto` desde
`L`, que era el original. Las sustituciones desaparecieron sin decir nada.

La misma clase: un arreglo que se pierde porque se reconstruye el objeto entero
en vez de tocar la parte. El aviso es el nombre — `L` es el original, `texto` es
el acumulado —: dos objetos con el mismo nombre lógico y distinto contenido es
la trampa.

### 1.3 Un corte de docstring, y el error dos líneas más abajo

El corte empezaba en la comilla y no en el inicio de línea, así que la sangría
se duplicaba. El síntoma era un `IndentationError` **dos líneas después** del
sitio real, con el docstring correcto. Tres intentos de adivinar, y los tres
señalando la línea equivocada.

## 2. La regla que sale de los tres

```
cuando algo falla en un parche,
IMPRIMIR lo que se va a escribir.
```

Un parche que solo dice «fallo» obliga a la segunda ejecución. Uno que imprime
la región da el fallo a la primera.

Y hay dos casos distintos, con arreglo distinto:

- **el texto se corrompe al escribirlo** → el bloque va a un fichero aparte, y
  el script lo pega
- **el parche rompe la estructura** → el fallo imprime la región

## 3. El guardia que faltaba en los tres

```
def test_ antes: 42
def test_ despues: 43
```

No basta con que el código parsee. **Un parche que quita código tiene que decir
cuánto quita**, y si quita más de lo que decía, se para.

Y la medida que importa es el recuento, porque **un test que desaparece no
rompe nada**: no hay nada que ejecutar, y la suite sigue verde.

> Una comprobación que se puede quedar vacía en verde. Y aquí la comprobación
> vacía era el parche.

Hoy ese guardia está en `tools/test_ejecutar_pytest.py`, con tres cifras — una
por carpeta — porque un total con una cifra mágica no dice dónde se rompió.

## 4. Las dos mitades de leer el código

Resumido, y medido cuatro veces seguidas:

```
prosa  -> normalizar espacios y buscar en una línea
código -> el árbol, y no una ventana de texto
```

Por qué las dos: una comprobación que busca prosa sin normalizar devuelve
siempre `False`, y una que devuelve siempre `False` **pasa**.

Y una tercera cosa, que es la más útil de las tres:

```
una aguja que NO EXISTE falla siempre, y se ve
una aguja que existe pero MIDIO mal, se ve también
una aguja que existe y mide bien es la única que no hay que mirar
```

MEDIDO, un ejemplo de la primera: el mensaje dice `SINTAXIS INVALIDA` y el test
buscaba `SYNTAXIS INVALIDA`. Una `y` de diferencia, y el test caía.

## 5. Cuatro familias de «no mide lo que dice»

Todas medidas, todas con el arreglo al lado:

| # | La comprobación | Por qué no mide | El arreglo |
|---|---|---|---|
| 1 | el límite de profundidad de `_llega_a_sentencia` | nunca se alcanzó: 1 a 13 niveles, siempre igual | quitarlo; `ast` es acíclico |
| 2 | el `tope` de `_argumentos_para` | declaraba **rota** una plantilla válida con 16 especificadores | derivar la cota de la longitud |
| 3 | `_es_raise` | clasificaba por el texto de la línea | traer la clase del nodo |
| 4 | el guardia de control | decía «el repo» y miraba un fichero | `os.walk`, y decir cuántos mira |

Y una quinta, añadida después:

| 5 | el `except (SyntaxError, UnicodeDecodeError)` | el `parse` estaba fuera del `try`, así que la palabra sobraba | capturar cada excepción donde puede ocurrir |

Sobre la 5, que es la más discreta de las cinco:

> no sobra el código, **sobran las palabras**.

## 6. Y la que más cuesta: la que vigila al detector

MEDIDO, 336 hallazgos, 1 mal clasificado:

```
hallazgos por el ARBOL:  336
hallazgos por el TEXTO:  336
DESACUERDOS:            1
```

El desacuerdo era un `assert` cuyo **mensaje** empieza por *«el barrido
debería encontrar al menos 20 `raise`»*. La palabra «raise» estaba en la línea.

> **La comprobación que vigila al clasificador estaba ella misma mal
> clasificada.**

Eso no es un fallo del detector: es un fallo del sitio desde el que se
mide. Y por eso el arreglo de un instrumento empieza por darle un caso
inventado, no por afinar la regla: una regla que se afina sigue siendo una
regla, y la siguiente palabra la rompe.

## 7. Las tres listas que una comprobación puede tener

1. **mide bien** — la única que no hay que mirar
2. **existe y mide mal** — se ve al leer el resultado
3. **existe y no mide nada** — verde, y es la peligrosa

La tercera es la que se ha buscado en este proyecto, once veces, y siempre con
la misma pregunta al principio: **¿se ha ejecutado alguna vez la condición que
dice comprobar?**

## 8. Y la que solo se ve al fallar

MEDIDO, 290 plantillas, 1 rota:

```
'`%s` y `%s` tienen campos distintos:%n' % ('For', 'AsyncFor')
-> TypeError: not enough arguments for format string
```

R2 decía `ValueError`; sale `TypeError`, porque los dos `%s` se comieron los
argumentos.

Peor que un `ValueError`:

> el fallo **borra la causa** y además **confunde sobre la causa**.

Y nunca se ve, porque el mensaje se construye solo cuando la aserción falla. La
prueba donde estaba existe precisamente para detectar un cambio futuro del AST:
**su único trabajo es hablar cuando algo va mal, y no puede hablar.**

Por eso hay que construir los mensajes con mentiras:

```
'%s' % ()       -> TypeError: not enough arguments
'%s' % (x, y)   -> TypeError: not all arguments converted
```

Solo hay un número de argumentos que funciona, y se encuentra preguntando. El
comprobador no cuenta nada, y por eso no puede equivocarse al contar.

Y para que el dummy no rompa el instrumento: MEDIDO, el repo usa `%s` ×180,
`%d` ×99, `%r` ×98, `%f` ×21. Una cadena de mentira revienta en `%f`, porque
`%f` llama a `float()`. Un comprobador que falla por culpa de su propio
instrumento es un comprobador que no sirve.