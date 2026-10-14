# DECISIÓN CM-004

**Estado: REFUTADA por los hechos — ver §0.** La Opción A se firmó a las
12:23 del 14/10 y las 23 manos se reinterpretaron a mano a las 12:56, sin
documentar. La decisión ya no describe el estado de la base.

**Pregunta principal:** ¿se regraba `hands_db.jsonl` o se migra?
**Pregunta nueva (revision_1 Tarea 4):** ¿las 73 manos sin `allin` y
`H_0851` entran en esa decisión o se tratan aparte?

---

## 0. Decisión

> ### Opción A — aceptar la pérdida. **Firmada, y luego retirada.**
>
> **Razón que se firmó:** las 23 ya están excluidas y preservadas, así que
> el coste conocido de seguir es cero y el beneficio del OCR incierto.
>
> **Qué la retiró:** 33 minutos después, las 23 se reescribieron a mano en
> `hands_db.jsonl`. La condición 1 de la decisión — *«las 23 manos
> permanecen **intactas**»* — dejó de cumplirse sin que nadie lo decidiera.
>
> **Quién y cómo:** corrección manual del mantenedor de la base. No hay
> script que la reproduzca, ni documento que la explicara en su momento. Se
> declara ahora en `CM004_REINTERPRETACION.md` y se puede verificar con
> `tools/verificar_cm004.py`.

Lo que cambia con esto, y lo que no:

| | |
|---|---|
| **El defecto de CM-004 sí está resuelto** | el invariante da 0 de 1280: no queda ninguna `BB b` que el motor lea como una subida. `motor/test_cm004.py` lo fija |
| **pero no con un original** | `CORRELACION_CAPTURAS_CM004.md` sigue diciendo 0 de 23 localizables. Son reinterpretaciones, no dato observado |
| **y 6 de las 23 no son un cambio de etiqueta** | reconstruyen el preflop: `H_0039`, `H_0051`, `H_0067`, `H_0109`, `H_0143`, `H_0263`. Ver `CM004_REINTERPRETACION.md` §3.2 |

### La condición 1, revisada

> ~~las 23 manos **permanecen intactas** en `hands_db.jsonl`~~

No se cumple. Se sustituye por: **las 23 han sido reescritas a mano, están
declaradas una a una, y ninguna tiene original verificable.**

### La condición 2, revisada

> quedan **fuera** de `reliable_only=True`; la ventana queda en **877**

Se sigue cumpliendo, **pero por un motivo que ya no es el que se escribió.**
El motivo declarado en `motor/learn.py:63` era *«la entrada `BB: b` aparece
después de acciones voluntarias, luego el motor la lee como una subida que
puede no haber ocurrido»*. Ese motivo **ya no se cumple en ninguna de las 23**.

La exclusión sigue en pie, pero sobre un fundamento distinto y **todavía no
escrito**: el sustituto tampoco tiene original. Eso es una decisión nueva, no
la que se firmó.

> **Pendiente de decidir.** Si las 23 vuelven a la ventana, el denominador
> pasa de 877 a 900 y **todas** las cifras de `CONTRATO_F72A.md` y
> `RESUMEN_SECCION.md` hay que recalcular. No es una consecuencia automática:
> es una decisión, con su coste, y es de quien mantiene la base.

### Qué NO cierra esto

CM-004 era el bloqueo *conocido*. Este lo gestiona. No demuestra que el
resto de la ventana sea perfecto, y Fase D sigue bloqueada por dos cosas
que esto no toca:

- **CM-003 y CM-004 se anulan en dirección pero no en magnitud.** El
  perfil del BB tiene un error de magnitud desconocida. Sigue siendo así,
  y ahora además se sabe que 6 de las 23 se reconstruyeron: el error de
  magnitud **no** solo viene de CM-003.
- **La reconstrucción sin original no se ha revisado contra la grabación.**
  `H_0067` es la más frágil: parte una llamada grabada en dos e inventa un
  importe. Ver `CM004_REINTERPRETACION.md` §3.2.

### La puerta que se deja abierta, y con qué criterio

La Opción C — buscar otra fuente legítima (vídeo, otro ordenador, copia de
las capturas de otra máquina) — no se descarta: se considera **más barata
que el OCR** porque no requiere interpretar imágenes.

**Criterio para reabrir:** si aparece un original, se valida la
reconstrucción *sobre las manos afectadas* y se revierte lo que no se sostenga.

**Criterio para reconsiderar el OCR:** solo si el perfil del BB medido
sobre 877 manos cambia de forma relevante al compararlo con el de 900. Si
no cambia, el 0,7 % era irrelevante. Ese comparativo es trabajo de Fase D.

**Criterio nuevo, el que este bloque deja escrito:** una reinterpretación sin
original **no se valida comparando el resultado con lo que ya estaba**. Se
valida contra la grabación, o no se valida. Es lo que separa las 17
correcciones de etiqueta — una regla, exacta sobre las 1280 — de las 6
reconstrucciones, que son decisiones de una persona mano a mano.

## 1. Qué es CM-004

| | |
|---|---|
| manos | 23 |
| campo | `streets.preflop.actions` — la entrada `BB: 'b'` está mal ordenada |
| naturaleza | **defecto de orden**, no un valor equivocado |
| evidencia | `tools/auditar_bb_check.py` |
| detectado | 2026-10-13 |

La ciega se posta antes de cualquier acción. En estas 23 aparece después.
`learn._es_ciega_bb` exige `not voluntary_before` precisamente por eso, así
que **no la reconoce como ciega** y el motor la lee como una subida que
puede no haber ocurrido.

Manos: `H_0031, H_0037, H_0039, H_0051, H_0067, H_0078, H_0104, H_0107,
H_0109, H_0127, H_0143, H_0147, H_0161, H_0170, H_0183, H_0210, H_0215,
H_0248, H_0262, H_0263, H_0279, H_0294, H_0722`.

## 2. Originales: comprobado, NEGATIVO

Regrabar exige las **grabaciones originales** de esas 23 manos. Sin ellas
no hay a qué regrabar, y corregir el orden sería **inventar un orden**: saber
que la ciega va antes es deducirlo de las reglas, no de lo que pasó. Un
orden inventado es peor que un orden ausente, porque parece verdad.

**La comprobación está hecha.** `python tools/correlacionar_capturas.py`,
resultado en [`CORRELACION_CAPTURAS_CM004.md`](CORRELACION_CAPTURAS_CM004.md).

| | |
|---|---|
| ¿hay timestamp por mano? | **sí**, 1280 de 1280 |
| PNG en `capturas/` | 174 (127 raíz + 47 en `juego/`) |
| método 1 — fecha ± tolerancia | **no sirve**: ±24 h da 22 de 23, pero con 7,6 capturas por mano. Es ruido de sesión, no correlación |
| método 2 — número del nombre | **no sirve**: los números tienen 102 huecos y no siguen a `H_00NN` (delta mediano 261 h) |
| **correlacionables** | **0 de 23** |

Con los métodos disponibles, **no hay original verificable**. Queda el OCR
sobre `capturas/`, que no se ha hecho porque revision_1 pidió no hacerlo y
porque de 174 PNG habría que descartar 173 para confirmar uno.

**Esto no cierra la decisión, pero la reduce mucho.** Según revision_2, sin
original verificable la decisión de regrabar "se convierte en aceptar la
pérdida o conseguir otra fuente legítima, no en inventar una reparación".

## 3. Lo que sí se puede decidir sin el original

Independientemente de regrabar o migrar:

1. **Mantener las 23 manos y su procedencia intactas.** No se borran ni se
   "corrigen" con un orden inventado.
2. **Excluirlas de la calibración. HECHO.** `learn.load_hands(
   reliable_only=True)` las excluye desde `EXCLUSIONES_VENTANA_FABLE`.
   La ventana pasa de 900 a **877** manos, con el motivo consultable y
   7 tests que lo protegen. Detalle en
   [`EXCLUSION_CM004.md`](EXCLUSION_CM004.md). Las manos NO se borran:
   siguen en el fichero y en `reliable_only=False`.
3. **No declarar que CM-003 y CM-004 se compensan.** CM-003 hace al BB más
   pasivo y CM-004 más agresivo, y se anulan en *dirección*. Pero la
   **magnitud** del efecto de CM-004 no se conoce: depende de cuántas de
   esas 23 manos pesan en la ventana y de cómo se distribuyen. Compensarse
   en dirección no es compensarse en magnitud. Por eso Fase D sigue
   bloqueada aunque se arreglara CM-004 mañana.

## 4. Qué depende de quién

| | |
|---|---|
| ~~si regrabar o migrar~~ | **resuelto: Opción A, firmada en §0** |
| **Tú** | si las 73 manos sin `allin` entran aquí o se tratan aparte |
| ~~alguien con acceso a las capturas~~ | **resuelto: 0 de 23 correlacionables** |
| **Esto no depende de nadie** | los puntos 3.1–3.3 de arriba |

## 5. La pregunta nueva: las 73 manos sin `allin` y `H_0851`

**Decidido aparte.** No entran en CM-004, por tres razones:

| caso | naturaleza | por qué no se mezcla |
|---|---|---|
| las 73 manos sin `allin` | **ausencia de campo**, por recorder antiguo | no hay dato que regrabar: es una versión anterior. Regrabar exige volver a jugar, no reparar |
| `H_0851` (1 caso) | **filtro incorrecto** al volcar | sí es reparable sin regrabar: el recorder sabe qué jugadores foldearon (`_folded_positions`) y no lo usó |

Y ya no son hipótesis: las tres cosas están hechas.

- Las 73 siguen siendo **desconocidas** para cualquier decisión que
  necesite evidencia de `allin`, y no se inventa el valor.
  `CONTRATO_F72A.md` §2.
- `H_0851` está **arreglado en el recorder** hacia adelante
  (`INC-002_ALLIN_FILTRO_ACTIVE.md` §6), y su registro histórico se
  preserva tal cual. El detector de contradicción **se queda**: es lo que
  impide que ese registro se cuele como si fuera bueno.
- Ninguna de las dos se regraba.

## 6. Efecto sobre la Fase D

CM-004 ya no bloquea. Quedan dos cosas, y esta decisión no las toca:

- **CM-003 y CM-004 se anulan en dirección pero no en magnitud.** El
  perfil del BB tiene un error de magnitud desconocido. Sigue siendo así,
  y es la razón por la que Fase D necesita medir sobre 877 y comparar con
  900 antes de dar cualquier peso por bueno.
- **El contrato C4** (`select_best` con `evs` vacío), sin especificar.

Y una tercera, que no es un bloqueo sino una condición de calidad:

- **F7.2.a está firmado como contrato pero la política multiway no está
  implementada**, y el motor sigue entrando en multiway en silencio.
  `CONTRATO_F72A.md` §7 lo prohíbe cablearlo todavía.

## 7. Lo que queda hecho de lo que se propuso

| | |
|---|---|
| comprobar si las capturas corresponden a esas 23 | **hecho: 0 de 23** |
| excluir las 23 de la calibración | **hecho: 877, con tests y motivo consultable** |
| arreglar INC-002 en el código | **hecho: una línea, con test** |

Los tres eran reversibles y ninguno cerró la puerta a regrabar después.
