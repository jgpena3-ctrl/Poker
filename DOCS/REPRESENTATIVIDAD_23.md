# REPRESENTATIVIDAD_23 — las 23 manos preflop no son lo que parecían

> Tarea 2 de `revision_1`: auditar si las 23 representan las decisiones
> preflop del motor, o son un subconjunto sesgado. «Si hay un sesgo, dilo.
> Si no lo hay, también».
>
> **Respuesta corta: sí hay un sesgo, y es total. Las 23 no son una muestra
> de las decisiones preflop del motor: son la población de los *folds*
> preflop del héroe. Las decisiones preflop que sí son de la población del
> AUC no existen en este conjunto.**
>
> Y como consecuencia, las Tareas 3, 4 y 5 de `revision_1` quedan respondidas
> sin número: el AUC «con preflop incluido» no se calcula, y en la §6 está
> por qué, medido.

Reproducible con `python tools/auditar_representatividad.py`, que **no
escribe nada**.

---

## 1. Lo que son las 23

El corte de decisión es `corte_de_decision()`: la **última** acción del
héroe, y acepta `'b'`, `'c'`, `'r'`, `'f'` y `'x'`.

| | validación | calibración |
|---|---:|---:|
| cortes preflop | 23 | 75 |
| acción del héroe en el corte | **`f` en los 23** | **`f` en los 75** |
| su etiqueta | `y = 0` en los 23 | `y = 0` en los 75 |

Las 23 de validación tienen `y = 0`. Las 23. Las 75 de calibración también:
**98 de 98**. Eso no sale por azar, y no es que el héroe pierda siempre.

Un *fold* tiene `y = 0` **por construcción**: el que foldea no puede ganar
el bote. Y la población del AUC es **B**, «el héroe **continúa** o
**checkea**» (`CONTRATO_L_SEC.md` §8). Un fold no es ninguna de las dos
cosas.

> Estas 23 manos están fuera de la población declarada, y con `y = 0`
> garantizado. Meterlas en un AUC no añade manos: añade la regla de
> selección.

## 2. La cadena de selección: no descarta nada

| | universo | corte | **juega** | cartas | rival | perfil |
|---|---:|---:|---:|---:|---:|---:|
| validación | 41 | 23 | **0** | 0 | 0 | 0 |
| calibración | 119 | 75 | **0** | 0 | 0 | 0 |

Ni una sola mano se cae por falta de cartas del héroe, por villano
identificable o por perfil en el modelo. El único filtro que descarta
algo es el de la **acción**, y descarta el 100 % de los dos grupos.

Esto importa para leer la tabla: el sesgo **no lo introduce el
instrumento**. No hay una criba escondida que se quede con las manos
fáciles. La población entera de cortes preflop de validación es de folds,
y el instrumento la tomaba entera.

## 3. Criterio, declarado antes de mirar

Se declararon tres umbrales: C1, ninguna proporción de spot separada de
la referencia en más de 10 pp; C2, el villano más frecuente no pasa del
doble; C3, la proporción de premium no se separa en más de 10 pp.

Y se escribió, **antes de calcular**, qué no se puede concluir pase lo que
pase:

> Con n = 23 esto no puede detectar un sesgo pequeño. Que pasen C1, C2 y C3
> significa «no se detecta sesgo con esta muestra», no «no hay sesgo».

Referencia: los cortes preflop de **calibración** (75), un grupo
**disjunto**. La partición es `sha256(hand_id) % 10 < 3`
(`tools/calibrar.py:66`): depende del identificador, no del contenido, así
que calibración es una muestra del mismo proceso que validación.

> Un error de esta auditoría, escrito: la primera versión comparó las 23
> contra **la ventana entera**, que contiene las propias 23. Un grupo
> comparado consigo mismo da «separación 278 pp, p = 1,0». La referencia
> tiene que ser disjunta.

## 4. C1 — mezcla de spot: **no se detecta sesgo**

| spot | A (23) | B (75) | dif. | sigmas |
|---|---:|---:|---:|---:|
| `facing_3bet` | 34,8 % | 16,0 % | +18,8 pp | 1,7 |
| `facing_open` | 39,1 % | 61,3 % | −22,2 pp | −1,9 |
| `no_raise` | 26,1 % | 22,7 % | +3,4 pp | 0,3 |

Mayor separación observada: **22,2 pp**. **p por permutación = 0,1145**
(20 000 barajados de la etiqueta, semilla 11).

El umbral declarado de 10 pp **fallaba** en dos de tres spots. Pero con
n = 23 el error típico de una proporción está entre 10 y 10 pp: el umbral
estaba más allá del ruido. Un criterio sin calibrar contra el tamaño de la
muestra no es un criterio, es una moneda.

**C1 no se pasa, y el contraste dice que la diferencia no se distingue del
azar.** Se reporta el fallo del criterio declarado y el resultado del
contraste, los dos. No se cambia el umbral después de ver el número: eso
sería el error que este bloque lleva tres veces cometiendo.

## 5. C2 y C3

**C2 — villanos: el umbral falla, y no importa.**

| | A (23) | B (75) |
|---|---|---|
| más frecuente | DominoSaurio, 3 de 23 (13,0 %) | Franco1603, 4 de 75 (5,3 %) |
| villanos distintos | **20 de 23** | 48 de 75 |
| HHI | 0,059 | 0,026 |

Ratio 2,45×, y el umbral de «no pasar del doble» **falla**. Pero son
**tres** manos, y en el grupo A hay **20 villanos distintos para 23 manos**:
la concentración es baja en términos absolutos. Las tres son `H_0041`,
`H_0110`, `H_0121`.

**C3 — cartas del héroe: no se detecta sesgo.** Premium 0 % en ambos
(0,0 pp); pares 0 % contra 1,3 % (−1,3 pp, −1,0 σ); suited 30,4 % contra
21,3 % (+9,1 pp, 0,9 σ).

> Y aquí el criterio **pasaba en falso**, dos veces seguidas. El detector
> comparaba `s[:2]` con `'AA'`, `'KK'`… sobre cadenas como `'Qh3c'`, donde
> `s[2:4]` es `'3c'` y nunca puede ser un par de rangos: devolvía `False`
> **siempre**. Después el par se montaba como `'Q3'` en vez de `'AK'`, y
> seguía devolviendo `False` siempre. Un criterio que no puede fallar no
> es un criterio. Lo que lo destapó fue una tabla de siete casos de
> prueba con cartas de verdad —`'AhKs'`, `'QcJc'`, `'AcAd'`— escrita *antes*
> de mirar el resultado, y fallando.

## 6. Lo que hay de verdad, y si el preflop cabe

La última acción del héroe en las 877 manos fiables:

| calle | b | c | r | **f** | x | total |
|---|---:|---:|---:|---:|---:|---:|
| preflop | 30 | 3 | 48 | **554** | 2 | 637 |
| flop | 12 | 1 | 1 | 46 | 2 | 62 |
| turn | 37 | 1 | 0 | 28 | 1 | 67 |
| river | 35 | 16 | 3 | 22 | 31 | 107 |

- Decisiones preflop **jugables** (`b`/`c`/`r`) en toda la ventana: **81**.
- De las cuales **tienen etiqueta: 0**.
- Checks preflop: **2**. Con etiqueta: 0.

> **La población B en preflop no es pequeña: en este conjunto es vacía.**

Y hay una razón de por qué, y no es un azar del etiquetado:

- Si el héroe **juega y gana**, vuelve a actuar, y entonces el corte se
  mueve de calle. Para que el corte se quede en preflop con una acción
  jugada, la mano tiene que terminar ahí mismo.
- Para que tenga etiqueta hace falta un **ganador verificable**
  (`calibrar.muestra()` exige showdown verificable o victoria por fold con
  evidencia positiva).

Las dos cosas a la vez no se dan. Por eso las 81 manos jugables del
preflop no tienen etiqueta: o el héroe ganó y actuó después, y entonces el
corte no era preflop; o la mano terminó ahí mismo y no hay ganador
verificable; o la acción registrada no cierra la mano. En los tres casos la
mano sale de `muestra()`, y por eso no hay etiqueta.

## 7. Conclusión

**Las 23 no son representativas de las decisiones preflop de la población
B, porque las decisiones preflop de la población B no existen en este
conjunto.** Son representativas de otra cosa, y esa cosa está bien
definida: los folds preflop del héroe.

Sobre los tres umbrales declarados, tal cual:

| | veredicto |
|---|---|
| C1 mezcla de spot | el umbral **falla**; el contraste dice **p = 0,11**, no se distingue del azar |
| C2 villanos | el umbral **falla** (2,45×); son 3 manos y hay 20 villanos distintos |
| C3 cartas | no se detecta sesgo — y el detector estaba roto, dos veces |

**El sesgo que sí existe no está en ninguno de los tres.** Está en la
población entera, y se mide en la §6: la población B preflop son cero
manos.

### Y lo que esto responde de `revision_1`

| tarea | estado |
|---|---|
| 1. Dejar terminar la corrida | **parada a 11 de 23**, con motivo medido (§8) |
| 2. Auditar representatividad | este documento |
| 3. AUC de la población completa | **no se calcula**, y no por falta de tiempo |
| 4. ¿Cambia algo para Fase D? | **no**, y por qué (§9) |
| 5. `AUC_PREFLOP.md` | **no escrito**, a propósito (§9) |

### 8. Por qué se paró la corrida

La corrida iba 11 de 23 con 430 equities por combo en caché. A 31,5 s por
combo —medido, y los 40 de una mano salen todos igual, ninguno patológico—
las 12 que faltaban eran **4,2 h de CPU** para producir la equity de 23
manos que no pueden entrar en el AUC: las 98 con etiqueta son todas folds,
y 23 de ellas son la mitad de la muestra de una sola clase.

La caché por combo se conserva. Si algún día la pregunta es otra —por
ejemplo, si la equity predice la fuerza del villano en un *fold*— el trabajo
sirve. Para **esta** pregunta no.

> El número de combos por mano subió de 13,3 s a 31,5 s en mitad de la
> corrida, sin que nada en el código cambiara y sin que hubiera otro
> proceso. No está explicado y queda abierto. No se escribe una causa que no
> se ha medido.

### 9. Lo que NO se escribe, y por qué

**No hay `AUC_PREFLOP.md`.**

`revision_1` dice: primero el número, después el documento. Aquí **no hay
número**, y no es que falte: es que el número se podría calcular y no
mediría nada. Con 23 observaciones de una clase garantizada por
construcción, el AUC compararía «la equity de manos que el héroe foldeó»
contra «la equity de manos que el héroe jugó». Eso es una propiedad de la
regla de selección, no de la equity.

Escribir el documento con un número dentro sería escribir el número y
adjuntarle una advertencia. Un número con una advertencia al lado se lee
como número.

**Fase D no cambia.** `DEFAULT_ALPHA` sigue en **2,0**, por el argumento (3):
es el titular y ninguna evidencia admisible justifica sustituirlo. Ni (2)
ni este AUC dependían de él, y este AUC **no se ha calculado**, así que
tampoco puede moverlo. Lo que este bloque añade es una razón más para no
tocarlo, no una razón para cambiarlo.

## 10. Lo que se cambió en el código

| | |
|---|---|
| `ACCIONES_JUGADAS = ('b', 'c', 'r', 'x')` | la condición de la población B, escrita con el motivo y el `CONTRATO_L_SEC` al lado |
| etapa `0_accion_jugada` | el descarte por fold se **cuenta y se nombra** (`CLAVE_FOLD`), no se pierde en un `sin_rango` anónimo |
| `huella_de()` | huella del rango efectivo en la identidad de la caché (ver el commit anterior) |
| `--solo-recaudo` | enseña los ceros donde antes enseñaba 23 |

La tabla por etapas ahora tiene una columna más, y enseña `23` en «corte» y
`0` en «juega». Antes de este filtro enseñaba `23` y `23`, y no se veía
dónde se perdía la población.