# CONTRATO F7.2.a — quién puede actuar

**Estado:** firmado. Sustituye a la regla del raise (F7.1) en la
clasificación de multiway.
**Implementación:** `motor/multiway.py`
**Decisión:** revision_1 (la regla nueva sustituye a la vieja).
**Denominador:** **507 puntos de política**, sobre la ventana de 877 manos
(las 23 de CM-004 están excluidas: `EXCLUSION_CM004.md`).
**Cifras:** medidas por `python tools/auditar_solapamiento_multiway.py`, que
importa `motor/multiway.py::metrica_politica()`. El instrumento vive en el
motor y el script y los tests lo importan: una copia en cada sitio es
exactamente como vuelve un bug.

> Este contrato va **antes** que la política multiway. Ningún consumidor
> puede cablear la regla sin este documento, y ningún documento puede
> usarla sin él.

---

## 1. Las dos firmas

```python
no_puede_actuar(hand, street) -> set | None
no_puede_actuar_en_instante(hand, street, indice) -> set | None
```

Devuelven las posiciones que **están en el bote pero ya no pueden actuar**.
El hero se excluye en `puede_responder`, no aquí: `no_puede_actuar`
responde a "quién se ha comprometido", y eso incluye al hero cuando es él
quien se compromete.

| | cuándo se usa |
|---|---|
| `no_puede_actuar` | comparación histórica por calle. **Aproximación declarada.** |
| `no_puede_actuar_en_instante` | **la que se firma.** |
| `puede_responder` | la que se usa para clasificar. Envuelve a la anterior y resta el hero. |

### Por qué hay dos

`no_puede_actuar` dice que un all-in en la calle `S` bloquea desde el
**principio** de `S`. Eso es falso: un rival puede actuar *antes* de que
otro se commitmente en esa misma calle. Medido, la aproximación por calle
reclasifica **72 puntos** de HU a MULTIWAY que en realidad sí son multiway
cuando se respeta el orden. Por eso existe la versión por instante.

La firma por calle **no se borra**: sin ella no hay forma de medir cuánto
equivoca la otra. Lo que no puede es ser la que decide.

---

## 2. `None` = sin evidencia. Los tres casos, y solo tres

`None` **no** significa "nadie está all-in". Significa que no hay dato
suficiente para saberlo. La distinción es la diferencia entre medir y
adivinar.

| # | caso | cómo se detecta | manos afectadas |
|---|---|---|---|
| 1 | el campo `allin` **no está** | `'allin' not in hand` | 73 de 900 |
| 2 | hay all-in pero **su calle es indeterminada** | está en `allin` y no tiene ninguna acción registrada | 0 de 900 |
| 3 | `players[]` **no mide lo que el mapeo necesita** | `len(players) != 6` | 0 de 900 |

`allin: []` **no** es uno de ellos. Es información: significa que se
comprobó y que nadie se compromete. Se devuelve `set()`.

### El caso 1 no se suplirá por inferencia

Las 73 manos son `H_0001..H_0073`, un **prefijo contiguo** grabado entre
el 27 y el 28 de julio por un recorder que aún no escribía el campo. Todas
las ≥ `H_0074` lo tienen; todas las < `H_0074` no lo tienen. Es una
frontera de versión, no corrupción.

**No es reconstruible sin inventar.** El `stack` guardado es el de *inicio*
de mano y el importe de un `r` es "raise to", no un incremento, así que la
suma de apuestas no reconstruye el compromiso. Se conserva el estado
desconocido. Ver `AUDIT_NOPUEDE_ACTUAR.md` §2.

---

## 3. Política de `None` para el motor

> **Quien reciba `None` no fuerza HU ni MULTIWAY. El punto sale del
> numerador y se cuenta aparte.**

Concretamente:

1. No se colapsa a `set()`: sería afirmar que nadie está all-in.
2. No se cuenta como HU "por defecto": sería la clasificación más
   frecuente y no la más probable.
3. Se contabiliza en su propia categoría: `DESCONOCIDO`.
4. Un consumidor que no sepa tratar `DESCONOCIDO` **no debe consumir el
   clasificador**. Prefiero un hueco declarado a un número inventado.

`clasificar_decision()` ya devuelve este cuarto estado, y `DESCONOCIDO`
no se fusiona nunca con `HU` ni con `MULTIWAY` en ningún sitio.

---

## 4. Los cuatro ejemplos de frontera

Todos con test en `motor/test_nopuede_actuar.py`.

### 4.1 Resubida que no es all-in

`UTG b 3 → MP r 9 → CO r 24`, `allin: []`.

CO ha subido dos veces y conserva fichas. **No puede actuar** es falso.
La regla del raise lo marcaba bloqueado; de 625 jugadores que marcaba en
la ventana fiable, **534 no estaban all-in** (85,4 %).

### 4.2 All-in por call

`UTG b 3 → BTN r 38.2 → UTG c 38.2`, `allin: [UTG]`.

UTG se ha comprometido sin haber subido nunca: un `call` a un all-in no
registra `'r'`. La regla del raise **no lo veía nunca**. Medido: **47**
falsos negativos en la ventana fiable.

### 4.3 Fold posterior al all-in

`H_0851`: UTG sube preflop, checkea en el flop, BTN betea y **UTG foldea**.
`allin: [UTG]`.

Es un **registro corrupto**, no un fallo de la regla: el recorder filtra
`allin` con `p['active']`, que significa "estaba sentado al empezar". La
regla cree al dato —bien-. Magnitud: **1 de 138 (0,7 %)**. Va en
[`INC-002_ALLIN_FILTRO_ACTIVE.md`](INC-002_ALLIN_FILTRO_ACTIVE.md).

### 4.4 All-in en calle anterior: no bloquea en la actual

`MP b 5 (flop) → BB c 5 → MP r 140.1 (turn)`, `allin: [MP]`.

El campo `allin` es un hecho de **fin de mano**. La calle se deduce: quien se
compromete no vuelve a actuar, así que **su última acción es la del
all-in**. En el flop MP todavía puede responder.

---

## 5. El denominador de F7.2

### 5.1 Lo que este contrato cambia respecto a F7.1

Las cifras de F7.1 no son la misma métrica que estas. Cambian **dos cosas
a la vez**, y por eso no se comparan:

1. **QUÉ se cuenta.** F7.1 contaba *calles con acciones*. Aquí se cuentan
   **acciones del hero**: cada vez que el hero tiene que decidir, incluso
   si es dos veces en la misma calle.
2. **CÓMO se cuenta.** F7.1 contaba por calle, y daba por hecho que un
   all-in bloquea desde el principio de su calle. Aquí se cuenta por
   **instante**, respetando el orden real de las acciones.

### 5.2 Qué es un punto de decisión

Una **acción del hero**. Dos motivos, y los dos importan:

- Si el hero **apuesta y luego tiene que decidir otra vez ante una
  resubida**, son dos decisiones con dos situaciones distintas: entre una y
  otra puede foldear un rival o incorporarse otro. Medido: **110 calles**
  de la ventana tienen 2 o 3 acciones del hero.
- Una calle con acciones en la que el hero **no aparece** no es un punto
  de decisión: no hay nada que decidir. Y al restar 1 al número de activos
  para excluir al hero, en esos puntos se restaba de más.

### 5.3 El desglose, cuadrado

Este cuadro cuenta **todos** los puntos de decisión, folds incluidos. No es el
denominador de la política: ese sale en §5.4, y la razón de que sean
distintos es precisamente lo que esta sección prepara.

| | puntos |
|---|---|
| calles inspeccionadas (877 manos × 3 postflop) | **2631** |
| · sin ninguna acción | 1353 |
| · con acciones pero sin acción del hero | 730 |
| · con ≥1 acción del hero | 548 |
| **acciones del hero = puntos de decisión** | **656** |
| · HU | 320 |
| · MULTIWAY | 258 |
| · DESCONOCIDO | 52 |
| · sin ningún rival al que responder | 26 |

Las dos sumas cuadran y el script lo verifica con `assert`, no a ojo:

```
1353 + 730 + 548 = 2631 calles
320 + 258 + 52 + 26 = 656 puntos
```

> Una versión anterior de esta tabla sumaba 2718 en vez de 2700, porque
> los 26 "sin rival" ya estaban dentro del bloque de "sin acción del hero".
> El número era correcto; la presentación mentía. Por eso ahora hay `assert`
> y un test que reproduce el cuadre.

### 5.4 La tabla cruzada, y por qué el denominador son 507

Un punto **fold** es una decisión real pero **no consulta equity**: no hay nada
que repartir entre HU y MULTIWAY para una política multiway. Cuenta como
decisión y no como punto de política, y se declara aparte para que nadie lo
compare con los que sí usan la equity.

| clase | fold | no fold | total | **de política** |
|---|---:|---:|---:|---:|
| HU | 39 | **281** | 320 | **281** |
| MULTIWAY | 32 | **226** | 258 | **226** |
| DESCONOCIDO | 9 | 43 | 52 | 0 |
| sin ningún rival al que responder | 9 | 17 | 26 | 0 |
| **TOTAL** | **89** | **567** | **656** | **507** |

Tres cuadres, y el script los verifica con `assert`:

```
578 + 52 + 26 = 656 puntos      todo lo clasificado, folds incluidos
 89 +      567 = 656 puntos      filas por columnas
507 = 281 + 226                  la política no contiene folds
```

> **El denominador son 507, no 578.** La versión anterior de este documento
> publicaba 578, que incluía 71 folds del hero dentro de HU y MULTIWAY: 39 y
> 32. Entre ellos, 32 multiway que nunca producen una recomendación.
>
> El **porcentaje no se mueve**: 44,6 % antes y después. Lo que cambia son las
> cuentas, 258/578 → 226/507. Y eso es un argumento **más fuerte**, no más
> débil: la conclusión de política se llega igual por dos caminos. Lo que
> estaba mal no era el número, era publicar el denominador sin decir que
> llevaba folds dentro.

De los 43 desconocidos **no fold**, 29 serían multiway si en ellos nadie
estuviera all-in. La cota sale de ahí y con el **mismo criterio** que la
métrica principal — sin contar los 9 folds de esa misma fila:

```
226 (base) + 29 (techo sin evidencia) = 255
```

### 5.5 ⚠ La cifra que cambia la política

> ## MULTIWAY = 226 de 507 = **44,6 %**
>
> **Antes F7.1 decía 16,8 %.** Con el mismo nombre de métrica pero otro
> denominador, el multiway casi se triplica.
>
> Esto no es una mejora del dato: es que se estaba midiendo otra cosa. Pero
> **quien lea este contrato tiene que verla**, porque 16,8 % y 44,6 % llevan
> a políticas opuestas: con el primero, el multiway es un caso marginal que
> se puede ignorar; con el segundo, es casi la mitad de las decisiones y
> no se puede seguir entrando en él en silencio.
>
> Si F7.2.a se firma sobre 16,8 %, se firma sobre un error.

Por qué la diferencia es tan grande, en una línea: F7.1 contaba calles con
actividad, muchas de ellas donde el hero ya había folded, y en las que
restaba un rival de más al excluirlo. El denominador viejo estaba
inflado por puntos que no son decisiones, y el multiway estaba medido por
calle, no por instante.

La corrección temporal, medida **sobre los mismos 507 puntos de política** —
sin folds, como la métrica principal:

| | MULTIWAY |
|---|---:|
| por calle | 152 |
| **por instante** | **226** |
| la regla por calle se queda | **74 spots corto** |

> Compararla con folds dentro era medir una cosa contra otra: el numerador
> «por instante» venía sin folds y el denominador sí los traía. Los folds
> volvían por la puerta de atrás.

### 5.6 Contraste

| cifra | qué cuenta | regla | estado |
|---|---|---|---|
| 304 MW | calle con acciones | del raise | **rechazada** (14,6 % de precisión) |
| 169 MW | calle con acciones | del raise | **rechazada** (misma causa) |
| 225 MW (cota 276) | calle con acciones | evidencia | **sustituida**: no cuenta decisiones |
| 174 MW | acción del hero | evidencia, por calle | **sustituida**: ignora el orden |
| 258 MW (cota 287) | acción del hero | evidencia, por instante | **sustituida**: el denominador llevaba folds |
| **226 MW (cota 255)** | **acción del hero** | **evidencia, por instante, sin folds** | **vigente** |

El 16,8 % de `RESUMEN_SECCION.md` no significa nada con este denominador.

---

## 6. El contrato que falta dentro de este (equity)

Esto es lo que revision_2 exige declarar mientras no se implemente la
política:

> El motor solo dispone de **equity heads-up** contra **un** rival. En un
> punto con dos o más rivales capaces de responder, esa equity **no es la
> equity del spot**, y no debe presentarse como si lo fuera.

Consecuencias, hasta que exista una evaluación conjunta validada:

1. `equity_main` es HU por construcción, también en un sitio multiway.
   Sigue siendo **comparable entre manos**, y no comparable con una
   equity multiway verdadera.
2. **No** se presenta `equity_main` como estimación multiway.
3. **No** se implementa `RangeState.union()` como atajo: suma masas sin
   normalizar (medido: dos rangos uniformes dan masa total 2652) y eso no
   es la distribución conjunta contra dos rivales.
4. Si el contrato vigente no permite una decisión segura en multiway, la
   recomendación se marca como **no soportada**, con la razón y la
   versión de la política en sombra.

**Ninguna de estas cuatro está implementada todavía.** Implementarlas es
F7.2.b y queda bloqueada detrás de este contrato.

---

## 7. Lo que este contrato NO autoriza

- **No** autoriza cablear el clasificador en `asistente_live.py`.
- **No** autoriza tocar pesos de rango ni calibrar contra estas cifras.
- **No** autoriza borrar ni regrabar las 73 manos.
- **No** autoriza usar 169, 225, 276, 304 ni el 16,8 % como base de
  decisión. Están aquí solo como registro de lo que se midió antes.