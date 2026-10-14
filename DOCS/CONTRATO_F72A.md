# CONTRATO F7.2.a — quién puede actuar

**Estado:** firmado. Sustituye a la regla del raise (F7.1) en la
clasificación de multiway.
**Implementación:** `motor/multiway.py`
**Decisión:** revision_1 (la regla nueva sustituye a la vieja).
**Cifras:** medidas por `python tools/auditar_solapamiento_multiway.py`.

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

### 5.1 Lo que este contrato cambia respecto a la decisión de revision_1

revision_1 (Tarea 2) fijó el denominador en **225**, con cota **276**.
Esas cifras eran correctas **bajo el marco por calle**, y ese marco quedó
invalidado en este mismo bloque. Lo que sigue es el denominador vigente.

revision_2 lo pide explícitamente: publicar la diferencia frente a 169 y
frente al intervalo 225–276.

### 5.2 Qué es un punto de decisión

Un punto de decisión es **una acción del hero**. No "una calle con
acciones". El inventario de F7.1 contaba lo segundo, y por eso metía en el
numerador puntos en los que el hero ya no estaba en la mano: no había nada
que decidir. Peor: al restar 1 al número de activos para excluir al hero,
en esos puntos restaba de más.

| | puntos |
|---|---|
| calles inspeccionadas (900 manos × 3 postflop) | 2700 |
| en las que el hero no tiene ninguna acción | 2159 |
| el hero **folds** (decisión real, no consulta equity) | 37 |
| con ningún rival al que responder | 18 |
| **decisiones clasificables** | **466** |
| **desconocidas** | **38** |

De las 1316 calles que tenían acciones, **757 no eran decisiones del
hero**: un 56 % del numerador viejo.

### 5.3 Cifras

| | puntos |
|---|---|
| HU | **254** |
| MULTIWAY confirmado | **212** |
| DESCONOCIDO (fuera del numerador) | 38 |
| el hero folds (fuera: no consulta equity) | 37 |
| **denominador de F7.2** | **466** |

De los 38 desconocidos, 26 serían multiway si en ellos nadie estuviera
all-in. La cota es:

```
212 (base) + 26 (techo sin evidencia) = 238
```

### 5.4 Contraste

| cifra | marco | regla | estado |
|---|---|---|---|
| 304 MW | por calle | del raise | **rechazada** (14,6 % de precisión) |
| 169 MW | por calle | del raise | **rechazada** (misma causa) |
| 225 MW (cota 276) | por calle | evidencia | **sustituida**: no cuenta decisiones |
| **212 MW (cota 238)** | **por instante** | **evidencia** | **vigente** |

El **16,8 %** de `RESUMEN_SECCION.md` no significa nada con este
denominador. Con el vigente, el multiway es **212 de 466 = 45,5 %** de las
decisiones clasificables.

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