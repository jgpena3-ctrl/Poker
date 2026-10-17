# DECISIÓN — el objetivo del AUC: última decisión (A) o primera decisión (B)

> `revision_1`, Tarea 1. «Es una decisión tuya, y tiene coste».
>
> **Decisión: A — se mantiene la última decisión del héroe.**
>
> No es la opción que recomienda `revision_1`, y la razón está medida en la
> §2: **la razón que da para B no se sostiene**, porque el problema no es
> que la última decisión no traiga derrotas. Las trae. Trae 28.
>
> **Y hay una cuarta corrección de las cifras, que es la de fondo.** La §2
> usaba 131 / 78 / 53, y esas tres venían de **recalcular la etiqueta** en
> lugar de leerla. Con la etiqueta de `muestra()`:
>
> | | lo publicado antes | lo medido |
> |---|---:|---:|
> | preflop con etiqueta | 78 | **0** |
> | postflop con etiqueta | 53 | **48** |
> | total | 131 | **48** |
> | global `y = 1` / `y = 0` | 103 / 28 | **20 / 28** |
>
> La conclusión **no cambia** y ahora es más simple: el preflop no es «de una
> clase», es **vacío**. Y las 48 son todas postflop, con las dos clases.

**Y B1 tampoco es un arreglo.** No «trae las negativas»: **sustituye el
postflop por el preflop**. Con la etiqueta correcta, B1 deja el postflop en
cero observaciones, que es justo lo que el AUC mide hoy.

| | |
|---|---|
| la partición **no se mueve** | 29 % de manos en las tres opciones |
| el contrato firmado **no se toca** | `CONTRATO_L_SEC.md` sigue como está |
| el AUC **publicado no se recalcula** | sigue siendo el de `AUC_INTERVALO.md` |
| el AUC preflop | **no se calcula, y queda declarado permanente** bajo este objetivo |
| `DEFAULT_ALPHA` | **2,0**, sin cambio y sin que este documento lo mueva |

Nada de esto se implementa. Es una decisión y su coste, que es lo que R1
pide.

---

## 1. Qué se está decidiendo

El AUC de este proyecto evalúa **una decisión del héroe por mano**. Qué
decisión es, no estaba escrito en ningún sitio, y es lo que decide qué manos
pueden entrar.

- **A — la última decisión.** La mano se evalúa en la última acción del
  héroe, en la última calle en la que actuó. Es lo de hoy.
- **B — la primera decisión.** La mano se evalúa en la primera acción del
  héroe.

Son las dos naturales, y elegir una es elegir **qué momento del juego se
está evaluando**. El motor vivo recomienda en cada calle, así que ninguna de
las dos es ajena al sistema: son dos puntos de la misma línea temporal.

## 2. La medición, que es lo que decide

Toda la ventana fiable, 877 manos. Filtros de etiqueta saltados, que es lo
que separa «población vacía» de «población bloqueada».

> **Toda esta tabla se rehace con la etiqueta de `muestra()`.** La
> anterior venía de una réplica de los filtros y contaba manos sin etiqueta.
> Retirada entera.

| | A · última | B1 · primera |
|---|---:|---:|
| **preflop** con etiqueta | **0** | **67** |
| — `y = 1` | 0 | 20 |
| — `y = 0` | 0 | **47** |
| **postflop** con etiqueta | **48** | **0** |
| — `y = 1` | **20** | 0 |
| — `y = 0` | **28** | 0 |
| **total** con etiqueta | **48** | **67** |
| observaciones por mano | 1 | 1 |

**Y la lectura cambia.** B1 no «arregla el preflop»: **sustituye una
población por otra**. El preflop pasa de 0 a 67, y el postflop pasa de 48
a **cero**.

Eso es exactamente el argumento contra B, y ahora con cifras que no se han
movido: B1 no añade el preflop al objetivo, **lo convierte en el objetivo
entero**. Lo que el AUC mide hoy deja de medirse.

> Y B2 —«la primera decisión del héroe en cada calle»— multiplica las
> observaciones hasta cuatro por mano, todas en la misma partición porque la
> partición es por `hand_id`. No es fuga entre entrenamiento y prueba: es
> **dependencia dentro de la partición**. Y una mano que sale tres veces
> pesa tres veces en el estimador.

### 2.1 La razón que da R1 para B no se sostiene

R1 recomienda B porque «para eso hace falta que el héroe tenga decisiones
donde pueda ganar o perder». **Ya las tiene**: bajo A, el postflop son 48
observables, **20 positivas y 28 negativas**. El AUC no tiene un problema de
clase; y el preflop no aporta ni una observación.

Que es un problema distinto y más pequeño de lo que parecía:

| subpoblación | n | `y = 1` | `y = 0` |
|---|---:|---:|---:|
| todas las calles (A) | **48** | **20** | **28** |
| solo preflop (A) | **0** | 0 | 0 |

El preflop no aporta **ninguna** observación. Y el AUC publicado es
postflop: n = 11, reproducido exacto después del cambio de base.

### 2.2 Y B1, aplicada globalmente, destruye el postflop

De **48 observaciones postflop a cero**. No porque el corte «primera» sea
malo, sino porque la primera acción del héroe en la mayoría de las manos
**es la preflop**: con el corte en la primera, el postflop desaparece
completo.

> Antes decía «de 236 cortes a 1». El 236 era un recuento de *cortes* del
> recorte anterior, no de observaciones, y venía de la misma réplica
> equivocada. Con la etiqueta de `muestra()` la comparación es 48 contra 0:
> no «casi desaparece», **desaparece entero**.

Es decir: B1 no es «arreglar el preflop». Es **cambiar el objetivo de postflop a preflop**, y hacerlo sin decirlo. La incoherencia que R1 señalaba —«el postflop mantiene la última y el preflop la primera sería incoherente»— es real, y la medición muestra que **no hay forma honesta de mezclar**: o todo es última, o B1 hace desaparecer el postflop.

### 2.3 B2 multiplica y crea dependencia

1389 observaciones en 873 manos: hasta 4 por mano. Y todas caen en la **misma**
partición, porque la partición es por `hand_id`.

> Eso no es fuga entre entrenamiento y prueba: es lo contrario, es
> **dependencia dentro de la partición**. Y para un intervalo de confianza
> cuenta: el bootstrap remuestrea manos u observaciones, y son cosas
> distintas cuando hay repetidas. Con B2, una mano que sale tres veces pesa
> tres veces en el estimador.

R2 pedía exactamente esta comprobación. **No hay fuga** —la partición es
`sha256(hand_id) % 10 < 3`, depende del identificador y no del corte— pero
con B2 hay dependencia, y eso hay que decidirlo explícitamente si algún día
se considera.

## 3. Por qué A

1. **La razón de B no se sostiene** (§2.1): el objetivo ya tiene las dos
   clases. Lo que falta son las preflop, no las derrotas.
2. **B1 no es un arreglo del preflop, es otro objetivo** (§2.2), y aplicarlo
   hace desaparecer el postflop, que es lo que hoy está medido.
3. **A no toca nada firmado.** La partición no se mueve, el modelo no cambia
   —se ajusta sobre `cal.muestra()`, que depende de la etiqueta, no del
   corte—, y el AUC publicado sigue siendo válido.
4. **El alcance del daño es CERO, no pequeño.** El preflop no aporta
   **ninguna** observación aplicable: no son 78 de una clase, son 0. Y el
   postflop aporta **48**, con **20 positivas y 28 negativas**.

   > Este punto se escribió con las cifras de la réplica y decía «78
   > observaciones de una clase» y «131 con las dos clases». Retirado.

   Y eso cambia el argumento de signo, no lo debilita. No es que
   reorganizar el objetivo para arreglar 78 observaciones que hoy no se
   usan no compense: es que **no hay nada que arreglar por ese lado**. Lo
   único que hay que arreglar, si se arregla algo, es el **postflop** —que
   es lo que el AUC mide hoy— y B1 lo deja en **un** corte. Eso sí es un
   intercambio que no compensa.

## 4. El coste de A, que es real

**El AUC preflop no se calcula, y bajo este objetivo no se calculará nunca.**
No es una espera: es una consecuencia.

> Preflop, evaluado en la última acción del héroe, es una población de
> **una sola clase**. Un AUC binario necesita las dos.

Y con eso queda escrito lo que R2 pedía separar, que es lo que evita volver
a confundir las cosas:

| | | |
|---|---|---|

| **no hay datos** | ✗ | no es el caso: hay **83 cortes preflop** |
| **hay datos de una sola clase** | ✗ | tampoco: de esos 83, **0** tienen etiqueta |
| **no hay observaciones aplicables** | ✓ | es el caso, y es la razón |

**El motivo real, y cabe en una frase.** El corte en la última acción
del héroe, cuando cae en preflop, **solo puede caer en una mano que
termina en el preflop**. Y una mano que termina en el preflop no tiene
board; sin board no hay ganador verificable; sin ganador verificable
`muestra()` no le pone etiqueta.

No es un problema de clase. No es un problema de filtros. No es un problema
de «faltan cartas de los demás». Es que la mano no llega a tener board.

## 5. El coste de B, si algún día se quisiera

Para que no sea un salto al vacío:

| | |
|---|---|
| **cálculo** | **67** observaciones preflop × 40 combos. Medido: **31,5 s por combo**, y los 40 de una mano salen todos igual. **≈ 23 h de CPU**, en el orden de lo que ya costó una sola corrida de 23 manos |
| **modelo** | no se recalcula. `ProfileRangeModel.from_hands()` se ajusta sobre `cal.muestra()`, que depende de la etiqueta y no del corte |
| **partición** | no se mueve, medido: 29 % en las tres opciones |
| **postflop** | se pasa de 48 observaciones a **cero** |
| **contrato** | hay que escribir uno nuevo. `CONTRATO_L_SEC.md` está firmado y declara la población en términos del corte |

La caché por combo sí se reutiliza, porque `equity_preflop_contra_combo()`
es función pura de las dos manos. Eso no abarata la primera pasada.

> **El coste también se corrige, y no bajó por poco.** Este documento decía
> 270 observaciones y unas 94 horas de CPU. Las dos venían del mismo 270 de
> la réplica. Con la etiqueta leída, B da **67** observaciones, y el cálculo
> es de 40 combos a 31,5 s por combo:
>
> | | antes | medido |
> |---|---:|---:|
> | observaciones que entran | 270 | **67** |
> | × combos por observación | 40 | 40 |
> | × segundos por combo | 31,5 | 31,5 |
> | **horas de CPU** | **94,5** | **23,4** |
>
> Que no cambia la decisión y la deja **más fuerte**: B no es cara, es
> inútil. Compra 67 observaciones y a cambio deja el postflop —las 48 que el
> AUC mide hoy— en **cero**. 23 horas por una sustitución completa.

## 6. El tercer camino, nombrado y NO tomado

Hay una opción que no es A ni B: **una evaluación preflop separada, con su
propia población, declarada como tal**, sin tocar el objetivo global.

Sería: el AUC principal sigue evaluando la última decisión y no cambia; y
además se declara una segunda evaluación, de alcance preflop, en la primera
acción, con su contrato y su cifra.

**No se adopta aquí**, y la razón no es técnica: adoptarla exige decidir qué
se publica cuando las dos cifras no coincidan, y eso es una decisión de
gobierno de las cifras, no de código. Queda anotada para que la decisión se
tome con ella delante.

## 7. Lo que queda pendiente de documentar

R2 pedía dos cosas antes de adoptar B. **Una está escrita y la otra no**,
y al escribir la primera han salido cuatro más.

1. ~~Qué representa exactamente la predicción evaluada en cada corte.~~
   **Escrito**, y con sus cifras comprobadas contra el código:
   [`QUE_REPRESENTA_LA_PREDICCION.md`](QUE_REPRESENTA_LA_PREDICCION.md),
   `tools/test_que_representa.py`.

   Lo que sale de ahí, y son prerequisites de la decisión:

   - **A y B no son un recorte del mismo conjunto.** De 873 cortes, **235**
     cambian de calle entre los dos cortes; de esos, **232** miran un board de
     otro tamaño y **141** contestan a otro conjunto de rivales. El ejemplo:
     `H_0001` es river con 5 cartas contra 2 rivales en A, y **preflop** con 0
     cartas contra 4 rivales en B. Cambiar el corte no cambia *qué se
     pregunta*: cambia la pregunta.

   - **La predicción no es un número por mano.** **415 de 877** cortes tienen
     más de un rival vivo. `equity_de_mano()` devuelve una equity **por
     rival**, más `dispersion` y `mediana`, y su docstring dice que «la
     elección de rival es una decisión de quien mide y tiene que quedar a la
     vista». Lo que **no** está escrito en ningún `.md` es cuál es esa
     elección para el AUC, ni por qué. Y con B el conjunto de rivales cambia
     en 141 de los 235 cortes que cambian de calle, así que deja de ser
     neutro.

   - **El board tiene dos fuentes, y discrepan.** `tablero()` lee
     `comunitarias`; `villain_hasta_corte()` lee `streets.*.board`. En **5 de
     las 877** manos no coinciden. No se corrige aquí —cambia
     instrumentación y hay que medir de nuevo—, pero queda medido y escrito.

   - **La vía preflop es retrospectiva** y va marcada `observable: False`:
     enumera contra las cartas **reales** del rival, que al decidir no se
     conocían. El motor **no tiene camino de equity preflop**, y eso no es un
     detalle: es lo que hace que la predicción preflop no sea la predicción
     de una decisión.

   Quedan **sin escribir**, y son de la misma familia: **qué reducción a un
   número se usa en el AUC**, y **si la predicción se pondera por rival**.

2. **Qué mezcla la partición.** Comprobado y limpio: `sha256(hand_id) % 10
   < 3` depende del identificador. Ninguna opción mueve una mano entre
   particiones. Con B2 sí hay dependencia *dentro* de la partición (§2.3).

## 8. Cómo reproducir la medición

```
python tools/auditar_representatividad.py
```

§8 hace la comparación de los tres cortes. No escribe nada.

Y hay un test que fija el hecho que sostiene esta decisión: que la población
bajo el corte actual **ya tiene las dos clases**, que es lo que hace que B no
sea necesaria para tener un AUC calculable.
`tools/test_bloqueo_orden_filtros.py` y `tools/test_retraccion_y_auc.py`.