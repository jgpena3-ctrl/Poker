# DECISIÓN CM-004

**Estado: NO DECIDIDO**, pero ya no por falta de dato: la comprobación de
originales está hecha y salió **negativa** (§2). Lo que queda es una
decisión de coste y riesgo que es tuya.

**Pregunta principal:** ¿se regraba `hands_db.jsonl` o se migra?
**Pregunta nueva (revision_1 Tarea 4):** ¿las 73 manos sin `allin` y
`H_0851` entran en esa decisión o se tratan aparte?

---

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
| **Tú** | si regrabar o migrar: es una decisión de coste y de riesgo |
| **Tú** | si las 73 manos sin `allin` entran aquí o se tratan aparte |
| ~~alguien con acceso a las capturas~~ | **resuelto: 0 de 23 correlacionables** |
| **Esto no depende de nadie** | los puntos 3.1–3.3 de arriba |

## 5. La pregunta nueva: las 73 manos sin `allin` y `H_0851`

**Propuesta: se tratan aparte, y no entran en CM-004.** Razón:

| caso | naturaleza | por qué no se mezcla |
|---|---|---|
| las 73 manos sin `allin` | **ausencia de campo**, por recorder antiguo | no hay dato que regrabar: es una versión anterior. Regrabar exige volver a jugar, no reparar |
| `H_0851` (1 caso) | **filtro incorrecto** al volcar | sí es reparable sin regrabar: el recorder sabe qué jugadores foldearon (`_folded_positions`) y no lo usó |

Son tres problemas distintos con tres arreglos distintos:

1. **CM-004** — orden inventable, no inventado: requiere el original.
2. **73 manos** — dato que nunca se grabó: requiere regrabar o aceptar la
   pérdida.
3. **INC-002** — un `and` que falta en la línea 1034: se arregla hoy en
   el código, y las manos ya afectadas (1) se declaran.

Mezclarlos en una sola decisión de "regrabar todo" costaría regrabar 73
manos por un campo que ni siquiera existía cuando se grabaron.

**Pendiente de tu confirmación.**

## 6. Efecto sobre la Fase D

Bloqueada. No por CM-004 solo:

- CM-003 y CM-004 se anulan en dirección pero no en magnitud → el perfil
  del BB tiene un error de magnitud desconocida.
- El contrato C4 (`select_best`) sigue sin especificar. revision_2 lo pide
  antes de usarlo como base de evaluación estratégica.
- F7.2.a está firmado pero la política multiway no está implementada, y el
  motor sigue entrando en multiway en silencio.

Ninguna de las tres se resuelve decidiendo CM-004.

## 7. Lo que propongo como siguiente paso

Sin comprometer la decisión:

1. **Comprobar si las capturas corresponden a las 23 manos.** Es la única
  Es lo único que bloquea la decisión principal, y es una comprobación, no
   una decisión.
2. **Implementar la exclusión de las 23 de la calibración** (punto 3.2),
   que no depende de la decisión.
3. **Arreglar INC-002 en el código** (una línea), declarando el registro ya
   afectado.

Los tres son reversibles y ninguno cierra la puerta a regrabar después.