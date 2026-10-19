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

Lo que se llevó, MEDIDO en el `git diff`:

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

> **Esto es razonamiento, no una medición.** Sale de las tres de
> arriba, que sí tienen medición, y no tiene una propia: es una regla
> sobre ellas.

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

MEDIDO, antes y después de un parche:

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

MEDIDO, todas: cada fila es su propia medición. Y todas con el arreglo
al lado.

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

MEDIDO: la tercera se ha buscado en este proyecto once veces. Y siempre con
la misma pregunta al principio:

> **¿se ha ejecutado alguna vez la condición que dice comprobar?**

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

## 9. Dos copias de la misma medición

R2 lo señaló sobre un guardia de recuentos:

`
el comentario:      tools 459, motor 834, recorder 4     suma 1297
la constante:       {'tools': 461, 'motor': 834, ...}   suma 1299
`

Dos copias de la misma cifra, MEDIDO, y no coincidían.

> No es cosmético aunque lo parezca. Las cifras eran **el objeto** del guardia,
> así que si están dos veces, hubo un momento en que una era la buena y la otra
> no — y no hay forma de saber cuál.

Una cifra al lado de la cifra buena es **una medición que no se puede
repetir**, porque no dice de cuándo es.

Y el arreglo no es ponerlas al día:

`
la CONSTANTE tiene las cifras, porque es lo que el test compara
el COMENTARIO no tiene cifras, porque no se compara con nada
`

Es la misma leccion de las dos listas idénticas, con otras palabras: **dos
copias de la misma cosa se ven iguales y pueden divergir, y el arreglo es que
solo haya una**.

Y en lugar de las cifras, la orden que las produce:

`
python -m pytest tools/test_ejecutar_pytest.py -k no_ha_desaparecido
`

que no se puede quedar vieja, porque se ejecuta. Y el fallo del test imprime
la declarada y la medida, una al lado de otra: la medición está donde se ve.

## 10. Un alcance que se declara y se vigila

Un guardia que decía «el repo entero»usaba os.listdir, que no baja a
subcarpetas.

MEDIDO: hay **cero** tests en subcarpetas. O sea que hoy «el repo entero» es
cierto.

Y «hoy» no es una propiedad. El arreglo no fue bajar, y el motivo es
concreto: **un .py en una subcarpeta puede no ser un módulo de este repo**,
y bajar obligaría a decidir eso.

El arreglo fue:

- el alcance se declara como **el primer nivel**, y
- el guardia **falla si algún día hay tests abajo**

Que es la diferencia entre «el alcance es el repo» —que es una frase— y «el
alcance es el primer nivel, y hay un guardia que dice cuándo eso deja de ser
verdad».

Y una segunda medida, que R2 señaló: el guardia fijaba **funciones** y no
decía si había mirado **todos los ficheros**. Un .py con un solo test sigue
siendo un fichero. Ahora hay dos cifras y dos comprobaciones, que es lo mismo
que hace el guardia de caracteres de control con su mirados.

## 11. Y una reflexión sobre el orden

MEDIDO, lo que abrió este bloque, y que no estaba en ninguna tarea:

`
sintaxis invalida  -> SyntaxError de Python   nombra el fichero: False
no es utf-8        -> mi AssertionError      nombra el fichero: True
`

De las dos palabras de un except, **una seguía viva y la otra era adorno**.

Y la cuarta forma de la familia, con un disfraz que no se había visto:

`
un test que depende del ORDEN de los ficheros y mide uno de ellos
`

Con tres ficheros en un directorio, sorted decide cuál falla primero — el
alfabético — y el caso pedido nunca se mide. Con dos nombres cambiados de
sitio, el test habría pasado sin comprobar nada.

El arreglo es el de siempre: **aislar la pieza para poder darle el caso**. Un
directorio por caso.
## 12. Un guardia que mide una magnitud y no dice cuál

MEDIDO, y las tres magnitudes no son la misma:

```
definiciones test_* a cualquier profundidad : 1300
definiciones test_* ANIDADAS                : 0
tests que pytest RECOGE                       : 1350

funciones con parametrize                   : 17
clases que heredan de unittest.TestCase      : 0
```

Pytest ejecuta **50 más** de los que hay definidos, y la diferencia sale de
las 17 funciones parametrizadas.

El guardia mide definiciones, y se le puede preguntar por qué:

```
MEDIDO: `--collect-only` tarda cuarenta segundos e importa los módulos.
Un guardia de cuarenta segundos no es un guardia: es un coste que acaba
descartado por quien lo escribió.
```

Y el **punto ciego, dicho**:

> si a una de esas 17 funciones se le quita **un caso** de su
> `@parametrize`, pytest recoge uno menos y el guardia **no se entera**, porque
> la función sigue estando.

Lo que se puede tapar se tapa con una segunda medida barata: el número de
funciones parametrizadas. Lo que **no** se puede tapar sin ejecutar pytest es
el número de *casos* de cada una, y eso queda declarado como punto ciego y no
como garantía.

Y la regla, que es la de todo el documento:

> Un guardia que dice «no ha desaparecido ningún test» sin decir **qué magnitud
> mide** está haciendo una afirmación sobre otra cosa.

## 13. Un alcance escrito más ancho que el real

MEDIDO, sobre el guardia de docstrings: detecta líneas no vacías cuya sangría es
menor que la de la apertura. Y nada más.

Lo que **no** hace, y hay que escribir:

- no comprueba que la sangría sea múltiplo de cuatro
- no comprueba tabs contra espacios
- no comprueba la sangría de las líneas de código de al lado

Y por qué el límite no es teórico: un docstring cuya apertura no sea múltiplo de
cuatro **pasaría** este guardia. De modo que el test no puede sostener «todos los
docstrings están bien puestos»; solo sostiene «no hay líneas que se salgan del
bloque por la izquierda».

> Un alcance escrito más ancho que el real es una afirmación que nadie puede
> fiscalizar.

## 14. Y el más discreto: un `+1` de más

R2 lo señaló:

```
apertura = primero.lineno
... % (nombre, apertura + 1, ...)
```

`lineno` de Python **ya es 1-based**. De modo que el `+1` señalaba una línea
después de la real.

Y es del tipo más discreto que lleva este documento entero:

> un `+1` de más no da ningún síntoma. El mensaje sale, parece razonable, y nadie
> lo comprueba porque no hay nada que comprobar.

Corregido. Y ahora el mensaje señala la **culpable**, que es la segunda de las
dos opciones que ofrece R2 —y la que hay que mirar: la apertura se deduce del
nombre de la función, la línea suelta no—.

MEDIDO, en `_parametrizados`: la apertura era la 3792 y la culpable la 3823.

Y un detalle de la corrección: el guardia se disparó **sobre el código que él
mismo acababa de traer**, por una línea con tres espacios en vez de cuatro.

> Es lo que hace un guardia: mirar. Y mirar lo que uno acaba de escribir es lo
> único que no se puede hacer a ojo.
## 15. Texto donde tenía que haber identidad

MEDIDO, con un decorador inventado:

```
decorador con la palabra pero que NO es pytest   texto=1  estructural=0
decorador de pytest de verdad                    texto=1  estructural=1
función test_ anidada con parametrize            texto=1  estructural=1
```

La regla era `if 'parametrize' in ast.unparse(decorador)`.

Eso cuenta un decorador ajeno que lleve la palabra en un argumento. Y cuenta
una función anidada, que pytest **no recoge**.

La regla nueva son dos condiciones: que sea una llamada cuyo atributo final se
llame exactamente `parametrize`, y que el receptor termine en `pytest.mark`. Y
solo funciones de **nivel de módulo**, por una razón que no es de estilo:

> pytest no recoge una función anidada. Un guardia que las contara estaría
> contando cosas que no se ejecutan.

MEDIDO: la regla más estrecha da **el mismo 17**. Y eso es lo que hace falta
para poder decir que el número significa lo que dice.

## 16. Un `continue` que se traga un fichero

MEDIDO, y hoy no hay ningún fichero ilegible en las tres carpetas. O sea que
el `continue` **no estaba produciendo un recuento incorrecto**.

Y eso es «hoy no pasa», no «no puede pasar». Y por qué importa igual:

> un `continue` que se traga un fichero convierte el recuento en una
> **declaración** —«hay 17 funciones parametrizadas»— y si se tragara uno, la
> declaración sería falsa y nadie lo vería.

Que es lo contrario de lo que hacía el hermano del mismo fichero, que **para y
nombra el fichero**. O sea que el repositorio tenía dos políticas para «un
fichero que no se lee», y eso hay que elegirlo, no dejarlo.

## 17. Y la más útil de las tres: un guardia con el rango puesto a ojo

MEDIDO: una palabra en coreano colada en un comentario de un fichero de texto.
El barrido la dejó pasar.

Y la causa no es la palabra: es que **el rango estaba escrito a mano**, y
0x2E80–0x9FFF cubre los ideogramas chinos y **no** cubre el coreano, que
empieza en 0xAC00.

Y es la **segunda** vez que este guardia deja pasar algo, y las dos por lo
mismo: un conjunto de valores puesto a ojo en vez de derivado.

> La lista de valores que hay que mirar es la misma clase de cosa que las
> listas de campos, que las listas de búsquedas y que los topes de argumentos:
> **escritas a mano, pueden quedar cortas sin que nada se note.**

Y el patrón del arreglo es el de la cota derivada: no «más rangos», sino una
condición que no dependa de enumerar. Aquí, la de que un carácter sea raro de
verdad:

- no es imprimible
- no es espacio ni tabulador ni salto
- no es ASCII
- y no está en el rango de la puntuación de Unicode, que sí puede aparecer

Que son cuatro condiciones y ninguna lista.
## 18. Y la que se parece más a un agujero: un «roto» que no es el roto

MEDIDO, y esto es lo que más cuesta del bloque:

```
la variante ROTA que puse:   sueltas[0] + 1   ->  senala la 5   ->  el test PASA
la variante ROTA de verdad:  apertura + 1     ->  senala la 3   ->  el test FALLA
```

La primera no era la versión anterior del código: era **otra cosa que parece la
versión anterior**. Y el caso no la mató, porque no podía: no era el fallo que
se suponía que cubría.

Y por qué importa más de lo que parece:

> un caso que no muere ante un mutante equivocado no es un caso aprobado; es un
> caso que solo se ha probado contra lo que su autor imaginó.

Y el síntoma es el peor de los posibles, porque **no da ninguno**: el caso pasa,
el guardia está bien, y la hoja de ruta dice «cubierto». La cobertura aparente
y la cobertura real han divergido y no hay forma de verlo desde dentro.

Y de dónde sale el error, y aquí está la regla:

> **el mutante tiene que salir del HISTORIAL, no de la imaginación.**

Y eso se puede hacer, y es una línea: `git show` del commit que corrigió el
defecto da la expresión exacta. Escribirla de memoria —como hice— produce algo
plausible y falso a la vez.

Y la segunda forma de la misma, medida en el mismo bloque:

```
lo que ESPERABA que hiciera:   AssertionError, porque el caso «mata»
lo que hace el caso bueno:      no lanza nada, que es lo correcto
```

Un testigo que calla es un testigo que pasa. Confundir «no lancé nada» con «fallé»
es el mismo error con el signo cambiado: los dos TIMES el papel de un resultado
sin interpretarlo.

### La forma que sí aguanta

Los dos fallos de este bloque eran del **guardián de la medición**, no de lo que
medía. Y esa es la misma forma de la sección 6, pero vista desde el otro lado:

- la sección 6 dice: un detector que produce un diagnóstico falso sobre algo que
  está bien es peor que uno que no mira;
- esta dice: un caso que pasa ante algo que está mal es peor que un caso que no
  existe.

Y los dos se evitan con lo mismo, y es una sola cosa: **el resultado hay que
compararlo con algo**. Con el valor medido, o con la versión anterior real.
