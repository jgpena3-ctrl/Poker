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

> **CORREGIDO el 2026-10-19.** Esta lección afirmaba que esas cuatro
> condiciones sustituyen al rango, y **es falso**, y está medido:
>
> ```
> chr(0xAC00).isprintable()  ->  True
> chr(0x4E00).isprintable()  ->  True
> chr(0x202E).isprintable()  ->  False
> chr(0x200B).isprintable()  ->  False
> ```
>
> O sea que el coreano y el chino **son imprimibles**, de modo que las cuatro
> condiciones, juntas, NO los detectan. Lo que detectan es lo **invisible**:
> los espacios de ancho cero, los Replacement Character y los selectores de
> variante.
>
> Y R1 pidió exactamente esta comprobación —«detecta coreano (0xAC00) y
> cualquier otro rango no cubierto por la lista»— y la medición la desmintió.
> Es la segunda vez en dos bloques que una lección escrita con una medición a
> medias se queda corta, y por eso lleva aquí la corrección y no el
> Arrangement.
>
> **La regla que sí detecta el coreano** es la que decide por el **nombre
> Unicode** del carácter, y está en §19. Y la lección de esta sección sigue
> siendo válida en su parte central —una lista escrita a mano se queda
> corta— y lo que se le añade es la otra mitad:
>
> > **Una condición derivada no es automáticamente mejor que una lista.** Lo
> > que la hace mejor es que se pueda DEMOSTRAR que cubre lo que tiene que
> > cubrir, y eso se comprueba con un caso, y no con un razonamiento.
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


### Y el otro medio: cómo se BUSCA en el historial

Y aquí está lo que el bloque anterior dio por bueno y era más flojo de lo que
parecía.

MEDIDO, las dos búsquedas, sobre el mismo fichero y el mismo defecto:

```
git log -S'apertura + 1'            ->  3 commits, y el de la CORRECCION NO ESTA
git log -S'% (nombre, apertura + 1,' ->  3 commits, y el de la CORRECCION SI ESTA
```

Y la razón de que la frase suelta **no** encuentre el commit que corrigió el
fallo es la que hace la lección útil:

> Al borrar el código se **AÑADIÓ** el comentario que lo explica. Y `git log
> -S` cuenta las apariciones de una cadena: una entró y otra salió, el
> recuento **no cambió**, y el commit no sale.

O sea que la búsqueda por la prosa no es «menos precisa»: es que **el commit
que importa es invisible**.

Y la regla, que es la misma de las dos mitades de leer el código:

> **Para preguntar al historial hay que usar el CÓDIGO, no la PROSA.** Y no
> porque la prosa sea menos exacta, sino porque la prosa y el código cambian
> a la vez, y un contador de apariciones no ve ese intercambio.

Y el detalle que hace que la regla no dependa de un texto escrito a mano: el
código tiene una FORMA —una llamada con un argumento con ese nombre—, y esa
forma se puede buscar sin ambigüedad. MEDIDO, el texto del código da tres
candidatos, y de los tres el correcto se distingue porque **en su padre está
la suma y en él no**.

> Y ese es el mismo «por el árbol, nunca por una ventana de texto» de la
> sección 4, aplicado al HISTORIAL. Y la misma razón: un `grep` por una frase
> encuentra la frase, y no sabe qué es lo que la frase dice.

### La forma que sí aguanta

Los dos fallos de este bloque eran del **guardián de la medición**, no de lo que
medía. Y esa es la misma forma de la sección 6, pero vista desde el otro lado:

- la sección 6 dice: un detector que produce un diagnóstico falso sobre algo que
  está bien es peor que uno que no mira;
- esta dice: un caso que pasa ante algo que está mal es peor que un caso que no
  existe.

Y los dos se evitan con lo mismo, y es una sola cosa: **el resultado hay que
compararlo con algo**. Con el valor medido, o con la versión anterior real.
## 19. Un rango escrito a mano se queda corto, y el que se queda corto no avisa

MEDIDO, y el antes y el después del mismo script sobre el mismo repo:

```
los rangos de antes:  7 hallazgos
la regla de ahora:   11 hallazgos
```

Y los cuatro que aparecen de mas son **reales**, y no los encuentro por
caso: los encuentra el nombre del caracter.

| | | |
|---|---|---|
| `motor/test_asistente_live.py` | `ARABIC LETTER BEH` | dentro de una palabra espanola |
| `motor/test_asistente_live.py` | `ARABIC LETTER TEH` | idem |
| `motor/test_asistente_live.py` | `ARABIC LETTER REH` | idem |
| `DOCS/APRENDIZAJE.md` | `ZERO WIDTH NO-BREAK SPACE` | un BOM, invisible |
| `DOCS/PROYECTO.md` | `ZERO WIDTH NO-BREAK SPACE` | idem |

Y por que los rangos de antes no los veian, que es la parte que importa:

- el arabe esta entre `0x0600` y `0x06FF`, y la lista no lo mencionaba;
- el BOM es un `U+FEFF`, y la lista solo cubria el `U+FFFD` —el caracter de
  reemplazo— de los invisibles.

Y el sintoma de un rango que se ha quedado corto **no es que senale de mas**.
Es que **no senala nada**:

> un rango que se queda corto devuelve cero hallazgos, y cero hallazgos es un
> verde.

Y la regla que lo sustituye se decide por el **nombre Unicode** del caracter,
que dice que es el caracter:

```
LATIN SMALL LETTER A WITH ACUTE   ->  LATIN, permitido
CYRILLIC SMALL LETTER O           ->  LETTER de otro alfabeto
ARABIC LETTER TEH                 ->  LETTER de otro alfabeto
THAI CHARACTER KO KAI             ->  CHARACTER de otro alfabeto
HANGUL SYLLABLE GA                ->  sin LETTER: hay que nombrarlo
CJK UNIFIED IDEOGRAPH-4E00        ->  sin LETTER: hay que nombrarlo
RIGHTWARDS ARROW                  ->  un simbolo, no un sistema
```

Y la moral, que es la de siempre pero con un caso nuevo: **una lista escrita a
mano se queda corta**. Da igual que la lista sea de campos, de busquedas, de
topes o de puntos de codigo. La unica defence es que la comprobacion se
deduzca de lo que mira, y no de una enumeracion.

## 20. Una cadena en un `if` no es un docstring, y el nombre de una funcion es una promesa

MEDIDO, con un caso inventado:

```
cadena al principio de un `if`    ->  la senalaba   (no es un docstring)
cadena al principio de un `for`   ->  la senalaba   (no es un docstring)
cadena al principio de un `with`  ->  la senalaba   (no es un docstring)
docstring de una funcion          ->  la senala     (si es lo que es)
docstring de una clase            ->  la senala     (si es lo que es)
```

Y el detector moria en el sitio equivocado: senalaba `<modulo>` como nombre
del nodo, que es la pista de que no era un docstring sino una cadena en un
bloque de control.

Y lo que hay que mirar, y no es «el primer elemento del body es una cadena»:

> En Python, un docstring es la primera expresion de cadena de un **modulo**,
> una **clase** o una **funcion**. Y nada mas.

Y la leccion, que es de las dos mitades:

- **el ARBOL sabe la diferencia**, y un `if` tiene `body` igual que una
  funcion;
- y **el NOMBRE de la funcion es una promesa**: si se llama
  `_docstrings_descuadrados`, entonces lo que senale son docstrings. Un
  detector que senala otra cosa no senala poco: senala otra cosa, y quien lo
  lea buscara un docstring donde no hay.

## 21. Un alias no reconocido es un fallo SILENCIOSO, y por eso no es «menor»

MEDIDO, con tres decoradores inventados:

```
@pytest.mark.parametrize("x", [1])     ->  lo cuenta
@pt.mark.parametrize("x", [1])         ->  NO lo cuenta
@mark.parametrize("x", [1])            ->  NO lo cuenta
```

Y lo que hay debajo de «no lo cuenta» es lo que importa: **el numero baja y
nadie lo ve**. El recuento es una AFIRMACION que se publica, y un recuento
que se equivoca en silencio es la clase de error que este bloque lleva
cuarenta bloques corrigiendo.

Y la decision que se tomo, y que R2 dejo abierta como «una cuestion de
contrato»:

- **opcion A**: restringir el contrato a la forma canonica —`pytest.mark`— y
  decirlo;
- **opcion B**: reconocer los alias, resolviendolos por el AST.

Se tomo la B, por un motivo medido: **las 17 llamadas del repo salen todas de
la forma canonica**, de modo que reconocer los alias **no cambia el numero de
hoy** y quita una clase de fallo silencioso que no se paga hasta que aparezca
el caso.

> Es el mismo argumento que la cota derivada y que el `pytest.mark` del bloque
> anterior: **una regla mas estrecha que no cuesta nada ahora y evita un fallo
> mas adelante.**

Y la regla de la forma canonica, que es la que hace que la B sea segura: el
nombre `pytest` no puede ser otra cosa, de modo que se acepta SIEMPRE; y un
alias se acepta SOLO si el propio fichero lo declara.

## 22. Una transaccion a medias, y que «cerrado» es una DECISION escrita

Y esta es la del cierre, y no es de instrumentacion: es de gobernanza.

Lo que paso, MEDIDO: el dueno de `data/` corrigio una mano, el cambio quedo
**sin commitear**, y el repo se quedo con **doce tests en rojo** que no eran
de nadie: seis por el hash obsoleto, dos por el reparto de acciones, y cuatro
por la gobernanza del incidente.

Y el protocolo del propio repo ya decia lo que habia que hacer, en
`DOCS/SANEAMIENTO.md` §5:

> el fichero se commitea primero, y el manifiesto apunta a ese commit
> despues

Y el `motor/test_canal_manual.py` lo decia de otra manera, y mejor:

> **O se commitea con el motivo, o se revierte: no hay tercera via.**

Y el «se commitea con el motivo» es la parte que no es opcional. Un commit
que corrige una mano sin decir por que es un cambio de dato sin causa, que es
exactamente lo que el canal manual existe para evitar.

Y la parte que mas cuesta, y que es la que R1 lleva cuarenta bloques
recordando:

> **Un incidente no se cierra porque la suite salga verde. Se cierra con una
> decision escrita.**

Y los dos ingredientes de esa decision:

1. **que rama** de las dos posibles se tomo —«el registro estaba mal» frente a
   «el invariante estaba mal»—, porque las dos tienen consecuencias
   distintas, y una de ellas es tocar el invariante;
2. **que se midio** que ninguna cifra publicada se movia, porque sin eso
   «cerrado» es una afirmacion sin respaldo.

Y el invariante se quedo como estaba. Lo que se corrigio fue el DATO. Y el
test sigue en la suite, sin `xfail` y sin `skip`, y ahora **pasa**.

> Relajar el invariante para poner el test en verde habria sido justo el
> error que el canal manual existe para evitar.
## 23. Un script que se re-ejecuta, y el guardian que se enteró

Y esta es la segunda vez en este bloque que un script mio pierde lo que habia
aplicado, y las dos por el mismo motivo, que es el de siempre: **un objeto
reconstruido**.

MEDIDO, lo que paso:

```
el script guardaba una COPIA del fichero, luego lo sustituia por la version
anterior, y luego lo reescribia con el inventario de ese estado
```

Y el script **se ejecuto dos veces**: la primera fallo en una comprobacion, y
la segunda **volvio a guardar la copia** —que ya era la version anterior— y
volvio a hacer el resto. O sea que la copia guardada era la buena y se
pisaba con la mala, en silencio.

Y el sintoma fue el mas discreto de todos: **faltaban ocho tests**. No un
fallo, no una excepcion: ocho tests que no estaban.

Y lo que lo pillo fue el guardian de siempre:

```
MEDIDO, tools=474   y el estado bueno era tools=482
```

O sea que **el guardia de inventario vio la perdida antes que nadie**. Y esa
es la parte que hay que escribir, porque es lo contrario de lo que parece:

> Un guardia que mide una cantidad no es solo un detector de CRECIMIENTOS. Es
> tambien un detector de **PERDIDAS**, y las perdidas no dan ningun sintoma:
> un test que desaparece no rompe nada, porque no hay nada que ejecutar.

Y la regla que sale, y que es de las que mas se olvidan:

> **Un script que se vuelve a ejecutar tiene que ser IDEMPOTENTE, y su primer
> paso no puede ser guardar una copia de lo que su segundo paso va a
> cambiar.** O se guarda DESPUES de decidir, o el paso que guarda se salta si
> ya se guardo.

Y la forma de evitarlo de verdad, que no es el orden de los pasos: **que el
script mida lo que va a hacer, y que la medida se compruebe contra un
numero esperado antes de escribir nada**. MEDIDO, y asi fue como se pillo: el
script decia `tools=474` y el estado bueno era `482`, y la asercion
paró el script antes de que hiciera daño.

Que es, otra vez, lo de siempre: **el resultado hay que compararlo con
algo**. Con el valor medido, o con la version anterior real.

### Y la recurrencia, que es la parte que hay que escribir

MEDIDO, y esto paso **OTRA VEZ, en el mismo bloque**, y con el mismo script:

```
el script se ejecuto dos veces
la segunda vuelvo a escribir el bloque entero
y quedaron: una constante duplicada y DOS TESTS DUPLICADOS
```

Y el detalle que hace la leccion mas util de lo que parece: **el guardiano de
inventario no lo pillo**. Un `def test_` repetido con el MISMO nombre es UNA
definicion para pytest, de modo que el recuento de tests **no cambia**, y una
constante repetida con el MISMO valor no la ve nadie.

> **La idempotencia de un script no la vigila ningun guardian del repo.** Es
> una propiedad del SCRIPT, y hay que mirarla a mano. Y un guardiano que
> cuenta definiciones no puede distinguir «dos definiciones» de «una
> definicion y un nombre repetido».

Y el patron del fallo, que es siempre el mismo: **el paso que escribe tiene
que ser idempotente por si mismo, o el script tiene que decir si ya lo ha
hecho.** Y la forma mas simple de decirlo:

```python
if MARCA not in s:
    s = s.replace(MARCA, NUEVO, 1)
```

Que es una linea, y que convierte un script que se puede ejecutar una vez en
uno que se puede ejecutar las que haga falta. Y el motivo por el que no lo
puse la primera vez es que **el script me servia para una vez** y no para
repetirse: y esa es exactamente la clase de error que se paga una vez
pagada.
## 24. Una declaración que solo ata los NOMBRES no ata la declaración

MEDIDO, y el hueco, que es lo que R2 señaló y que estaba en un test mío:

> el test comprobaba que el NOMBRE Unicode de cada hallazgo apareciera **en
> algún sitio** del documento. Eso no dice que el hallazgo esté asociado al
> **fichero** correcto, ni al **punto de código** correcto, ni que tenga una
> **justificación** concreta.

Y una declaración en la que el nombre aparece pero el fichero es el
equivocado sigue siendo una declaración falsa.

MEDIDO, con nueve mutaciones sobre la tabla de hallazgos, una por una:

```
el fichero equivocado                  ->  el test lo nota
el punto de codigo equivocado          ->  el test lo nota
el nombre equivocado                   ->  el test lo nota
una fila de mas, de un hallazgo que no existe  ->  el test lo nota
un motivo vacio                        ->  el test lo nota
un motivo de marcador de posicion      ->  el test lo nota
la linea equivocada del docstring      ->  el test lo nota
el fichero equivocado del docstring    ->  el test lo nota
la fila del docstring que no esta      ->  el test lo nota
```

Y la FORMA que ata, que son dos cosas:

> **una declaración POR HALLAZGO**, con `(fichero, nombre, punto de código,
> motivo)`, y una comparación de **CONJUNTOS**: lo declarado contra lo medido.

Y por qué conjuntos y no «cada fila está en el fichero»:

> «cada fila está» **no dice que no haya filas de más**, y una fila de más es
> un hallazgo declarado que no existe — que es peor que no declararlo, porque
> hace creer que se ha mirado algo que no se ha mirado.

Y el motivo se comprueba que **exista**, y no que sea bueno: que sea bueno lo
lee quien lo lee, y un test no puede juzgar un texto. Lo que sí puede es
decir que no es un marcador de posición vacío.

### Y la clase general

> **Una comprobación que mira el NOMBRE de una cosa no la ata a esa cosa.**
> Nombra la manera de escribirla, no la cosa.

Y el ejemplo de al lado, que es el de siempre: una lista de campos derivada
del corpus, una lista de búsquedas, un tope de argumentos. Todas se comprueban
por su **forma**, y por eso se pueden atar al objeto.

### Y lo que R2 dijo que también es una lección

> Eso no invalida el cierre; **delimita exactamente qué contrato cubren esos
> tests**.

Y eso es una regla que no estaba escrita:

> **Un test debe decir qué contrato cubre.** Un test que cubre menos de lo
> que su nombre sugiere es peor que uno que no existiera, porque su nombre
> promete más de lo que cumple. Y el que acompaña al nombre con «y NINGUNA de
> esas dos comprobaciones, por sí sola, garantiza que…» es exactamente la
> clase de matiz que hace que un cierre sea un cierre y no una afirmación.
## 25. El instrumento no puede ser el mismo que lo que se quiere comprobar

MEDIDO, y el hueco era de R2, y era real:

> el test de la declaracion construia un **diccionario**, de modo que una
> fila repetida con la misma clave se sobrescribia al construirlo, y la
> comparacion de conjuntos no la veia.

MEDIDO, y el sintoma, que es el de siempre: **ninguno**.

```
con una fila DECLARADA dos veces, con la misma clave:
    el numero de hallazgos MEDIDOS   : 11
    el numero de filas DECLARADAS   : 12
    el test                          : PASA
```

Y el principio, que es general y que no es mio:

> **EL INSTRUMENTO NO PUEDE SER EL MISMO QUE LO QUE SE QUIERE COMPROBAR.**
> Para comprobar que no hay duplicados hace falta una **lista** y un
> **conjunto**, no un conjunto.

Y un diccionario deduplica **por construccion**. De modo que un diccionario
**no puede** comprobar que no hay duplicados: no es que no mire, es que no
puede mirar.

### Y la sorpresa, que es lo que hace la leccion util

MEDIDO: el repo **ya tenia la convencion escrita**, en tres sitios:

```
tools/test_auc_integridad.py    len(ids) == len(set(ids))
tools/test_rules.py             len(set(spots)) == len(spots)
tools/test_estimador_preflop.py len(set(alts)) == 2
tools/test_sin_duplicados.py    defaultdict(list)  ->  len(v) > 1
```

Y mi test nuevo era **el UNICO** que usaba un diccionario para acumular claves
y luego comparaba conjuntos. O sea que la convencion existia, y el codigo
nuevo no la seguia.

> **Una convencion del repo que ya existe es una red de seguridad. Y saltarsela
> en codigo nuevo es el fallo, aunque el fallo se mire a si mismo y parezca
> una decision.**

Y el arreglo, que es el de siempre: **usar la convencion**, no inventar una.

### Y los dientes, permanentes

Y aqui esta lo que hace que esto no se repita: la comparacion sale como
FUNCION, `_problemas_de_la_declaracion(filas, medidos)`, y hay un test que le
pasa una tabla INVENTADA con una fila duplicada y comprueba que la ve.

Y el motivo de que salga como funcion es el de siempre:

> una comprobacion que solo se puede ejecutar contra el repositorio tiene
> dientes para el repositorio y ninguno para si misma.

Y el patron es el de `test_sin_duplicados.py`, que comprueba que su PROPIO
nombre no este declarado dos veces: un detector que vigila duplicados, que
comprueba que el detector sigue viendo duplicados.

### Y la familia, que ya son cuatro

Y este es el **cuarto** caso del mismo patron en cuatro bloques:

| | el instrumento | lo que no puede ver |
|---|---|---|
| §18 | un mutante escrito de memoria | el defecto de verdad |
| §23 | un contador de definiciones | un nombre repetido |
| §23 | un script re-ejecutado | lo que ya habia aplicado |
| §25 | un diccionario | una fila repetida |

> **Un instrumento que no puede ver lo que dice ver no da ningun sintoma cuando
> falla.** Y por eso hay que mirarlos uno a uno, con un caso que los mate, y
> no por la forma del codigo.

### Y un barrido, y lo que declara — CORREGIDO

> **CORREGIDO el 2026-10-19.** Lo que sigue estaba escrito como si la
> revision se hubiera hecho, y no se habia hecho. MEDIDO, y R2 lo senalo: eran
> «candidatos pendientes de revision individual», no 46 casos cuya unicidad
> este demostrada.

MEDIDO, y el barrido, con el ARBOL y no con un `grep`:

```
asignaciones `d[clave] = <lista o dict>` en el repo : 46
   de las cuales, FUERA de todo bucle                  : 38
   de las cuales, DENTRO de un bucle                   :  8
```

Y las **38 de fuera** se descartan por una razon MECANICA y no por opinion:

> Sin bucle que las envuelva, la asignacion se ejecuta una vez por llamada, y
> su clave se asigna una sola vez. Sobrescribir no puede perder nada.

Y las **8 de dentro** SI pueden tener la clave repetida, y se han revisado
UNA A UNA, y cada una lleva escrito por que esta bien. Y estan DECLARADAS en
el codigo —`ACUMULADORES_REPETIBLES`, en `tools/test_ejecutar_pytest.py`— con
un guardian que comprueba que no falte ninguna, que no sobre ninguna, y que
ninguna tenga el porque vacio.

Y el reparto de los ocho, que es lo que hace util la revision:

| | por que esta bien |
|---|---|
| `tables[name]` | la clave es el NOMBRE de una tabla, y las claves de un dict son unicas |
| `rank_pair_data[rank_key]` | la clave sale del INDICE del bucle, y un indice no se repite |
| `streets[key]` | las tres claves son LITERALES y distintas |
| `h['winner']` | la clave es literal, pero el bucle SALE con `break` en cuanto la asigna |
| `cache[hid]` | la clave es un id de MANO, y un id no se repite |
| `self.digit_templates[ch]` | la clave es una clave de un dict, y las claves de un dict son unicas |
| `region_data[rname][v]` | la clave REPETIDA es el objetivo, y la asignacion va con una guardia `if v not in ...` |
| `hashes[name]` | la clave es un NOMBRE de fichero, de una CONSTANTE con 7 nombres distintos |

Y el septimo es el que mas merece la pena, porque es **la misma forma** del
defecto y esta bien:

> `region_data[rname][v] = []` se ejecuta con la MISMA clave muchas veces, y
> sin la guardia `if v not in region_data[rname]` cada vez perderia la lista
> anterior. O sea que **la forma no dice nada**: la forma es la misma que la
> de un defecto, y lo que la salva es la guardia que la envuelve.

Y ese es el limite, y queda DECLARADO: **el porque de cada uno de los ocho es
PROSA leida por una persona, y un test no puede juzgarla.** Lo que el test
puede es comprobar que no falte ninguno, que no sobre ninguno, y que ninguno
sea un marcador de posicion.

Y la cifra vive en una constante, `ASIGNACIONES_QUE_SOBRESCRIBEN`, y el
guardian la compara con la medida: asi, anadir un sitio nuevo obliga a
declararlo, y quitarlo obliga a bajar la cifra a mano. Las dos son
decisiones.
## 26. Un invariante que da cero porque no puede dispararse

Y esta es la más peligrosa de todas, porque **no da ningún síntoma**: verde.

Y el caso, MEDIDO, con la COPIA NORMALIZADA de la base —que re-codifica las
ciegas como `p` —pass— en vez de `b` —bet—:

```
la canónica :  921 de 1258 manos con ciega RECONOCIDA, y el invariante da 0
la copia    :    6 de 1258 manos con ciega RECONOCIDA, y el invariante da 0
```

El MISMO cero, con dos significados opuestos:

- en la canónica, cero quiere decir «ninguna mano lo viola»;
- en la copia, cero quiere decir «**ya no hay ninguna `BB b` que pueda
  violarlo**».

> **La regla se ha apagado sola.** Y el motor la apaga sin decir nada, porque
> la regla que decide —`_es_ciega_bb`— exige `act == 'b'`, y en la copia la
> ciega ya no es una `b`.

Y eso es la quinta forma de la familia de §25, y la peor:

| | el instrumento | lo que no puede ver |
|---|---|---|
| §18 | un mutante escrito de memoria | el defecto de verdad |
| §23 | un contador de definiciones | un nombre repetido |
| §23 | un script re-ejecutado | lo que ya había aplicado |
| §25 | un diccionario | una fila repetida |
| **§26** | **un invariante que ya no puede dispararse** | **el hecho de que ya no mira** |

Y la forma general, que es lo que hay que llevarse:

> **Un invariante que da cero porque no hay nada que mirar no es un
> invariante que pasa: es un invariante que ha dejado de mirar.** Y el cero
> de un invariante no dice que el objeto esté bien: dice que el invariante no
> ha mirado nada.

### Y la regla que sale, y que es de las que mas cuesta

> **Un invariante que puede dar cero tiene que declarar, ADEMAS de su cero,
> CUANTAS COSAS ESTABA MIRANDO.** Y ese numero es una medida, no un supuesto,
> y se compara con el declarado a mano: porque un `> 0` tolerado no distinguiría
> «la base está bien» de «la regla se ha apagado».

Y el numero va con la **REGLA**, que es la que decide: si la regla cambia, el
numero cambia, y hay que actualizarlo. Que es el precio de que el guard vigile
algo.

### Y el otro guard, que es el hermano de este

Y el del **vocabulario**, que vigila que la base y el motor hablen el mismo
idioma. MEDIDO: la copia usa `p` 2514 veces, y `motor/learn.py` no menciona
`p` ni una vez.

Y las dos mitades juntas:

> **Un invariante que se apaga, y un objeto que cambia de idioma, se
> detectan con la MISMA pregunta: ¿qué está mirando esto, y cuántas cosas
> están mirando?**

Y el reproche al que se parecen los dos, y que es el reproche del §24:

> Un invariante que no declara su alcance —qué mira, y cuántas cosas— no
> vigila nada, y **no avisa de que no vigila nada**.
## 27. Una lección escrita en un sitio no se cumple en el de al lado

Y esta es corta, y es de las que más molestan, porque no es un fallo de
nadie: es una regla que el repo **ya tenía escrita** y que no se cumplía una
línea más abajo.

MEDIDO, en `tools/test_verificador_caracteres.py`, que es un fichero de 13
tests:

```
test_un_fichero_sin_seguimiento_es_todo_del_cambio
    "Un test que depende del estado del repositorio es un test que se rompe
     solo."

test_un_fichero_rastreado_y_sin_cambios_no_tiene_lineas_nuevas      <-- el que
    fijaba 'motor/test_canal_manual.py' como su ejemplo
```

Y el primero **explica** por qué el segundo no puede fijar un fichero: porque
en cuanto el fichero del test se commitea, deja de estar «sin seguimiento» y
el test empieza a fallar sin que nada haya cambiado. Y el segundo fijaba un
fichero **del repo**, y de los que más se tocan.

Y lo que lo rompió fue un cambio **legítimo y sin relacion**: añadir un
guardian de vocabulario a `motor/test_canal_manual.py`. Y el sintoma fue un
rojo en un sitio que no tiene nada que ver con el cambio.

> **La lección, escrita a treinta líneas de distancia, no gobierna el test
> de al lado.** Y el motivo es que una lección es prosa, y la prosa no se
> comprueba: un test que depende del estado del repositorio sigue
> dependiendo del estado del repositorio, por muy bien escrito que esté el
> comentario de al lado.

Y el arreglo, que es el de siempre: **el caso se CONSTRUYE, no se busca**. Y
aquí, por la vía de derivarlo:

```
el fichero se BUSCA entre los rastreados y sin cambios
    y se exige que NO este vacio            (un caso trivial no comprueba nada)
    y se exige que tenga un caracter que el BARRIDO senalaria  (que el escenario
                                                            sea el que se dice)
    y se acota a las carpetas que el barrido recorre  (un caso que nadie mira
                                                    no comprueba nada)
```

Y las tres exigencias son MEDIDAS, porque cada una se hizo necesaria al
ver que la anterior dejaba un caso trivial: sin la del tamaño, el helper
encontraba `motor/__init__.py`; sin la del caracter, el escenario no era el
que el test describia.

Y la general, que es la de siempre pero vista por el otro lado:

> **Un comentario que explica una regla no la hace cumplir.** Lo que la hace
> cumplir es un test que construye el caso, y que falla si el caso no se
> puede construir. Y un caso que no se puede construir tiene que **fallar**,
> no pasar: porque un caso que no se ha comprobado no es un caso que ha
> pasado.
