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

| | A · última | B1 · primera | B2 · primera, por calle |
|---|---:|---:|---:|
| cortes totales | 873 | 873 | **1389** |
| población B con etiqueta | 131 | **271** | 538 |
| — `y = 1` | 103 | 217 | 387 |
| — `y = 0` | **28** | **54** | 151 |
| observaciones por mano | 1 | 1 | **hasta 4** |
| **cortes postflop** | **236** | **1** | 508 |

### 2.1 La razón que da R1 para B no se sostiene

R1 recomienda B porque «para eso hace falta que el héroe tenga decisiones
donde pueda ganar o perder». **Ya las tiene**: bajo A, la población B
completa son 103 victorias y 28 derrotas. El AUC no tiene un problema de
clase; tiene un problema **preflop**.

Que es un problema distinto y más pequeño de lo que parecía:

| subpoblación | n | `y = 1` | `y = 0` |
|---|---:|---:|---:|
| todas las calles (A) | **48** | **20** | **28** |
| solo preflop (A) | **0** | 0 | 0 |

El preflop no aporta **ninguna** observación. Y el AUC publicado es
postflop: n = 11, reproducido exacto después del cambio de base.

### 2.2 Y B1, aplicada globalmente, destruye el postflop

De **236 cortes postflop a 1**. No porque el corte «primera» sea malo, sino
porque la primera acción del héroe en la mayoría de las manos **es la
preflop**: casi todos los cortes B1 caen en preflop.

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
4. **El alcance del daño es más pequeño.** El preflop degenerado son 78
   observaciones de una clase. Toda la población son 131 con las dos clases.
   Reorganizar el objetivo para arreglar 78 observaciones que hoy no se usan
   es un intercambio que no compensa.

## 4. El coste de A, que es real

**El AUC preflop no se calcula, y bajo este objetivo no se calculará nunca.**
No es una espera: es una consecuencia.

> Preflop, evaluado en la última acción del héroe, es una población de
> **una sola clase**. Un AUC binario necesita las dos.

Y con eso queda escrito lo que R2 pedía separar, que es lo que evita volver
a confundir las cosas:

| | | |
|---|---|---|
| **no hay datos** | ✗ | no es el caso: hay 78 observaciones |
| **hay datos de una sola clase** | ✓ | es el caso, y es la razón |

## 5. El coste de B, si algún día se quisiera

Para que no sea un salto al vacío:

| | |
|---|---|
| **cálculo** | 270 observaciones preflop × 40 combos. Medido: **31,5 s por combo**, y los 40 de una mano salen todos igual. **≈ 94 h de CPU**, en el orden de lo que ya costó una sola corrida de 23 manos |
| **modelo** | no se recalcula. `ProfileRangeModel.from_hands()` se ajusta sobre `cal.muestra()`, que depende de la etiqueta y no del corte |
| **partición** | no se mueve, medido: 29 % en las tres opciones |
| **postflop** | se pasa de 236 cortes a 1 |
| **contrato** | hay que escribir uno nuevo. `CONTRATO_L_SEC.md` está firmado y declara la población en términos del corte |

La caché por combo sí se reutiliza, porque `equity_preflop_contra_combo()`
es función pura de las dos manos. Eso no abarata la primera pasada.

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

R2 pide dos cosas antes de adoptar B, y las dos siguen abiertas:

1. **Qué representa exactamente la predicción evaluada en cada corte.** En
   la última acción, la equity se calcula con las cartas del héroe y el
   rango del rival en ese instante. Con el corte en la última calle, el
   board disponible es el de esa calle. No está escrito en ningún `.md` y es
   lo primero que habría que escribir antes de cambiar el objetivo.

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