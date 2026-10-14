# DECISIÓN CM-004

**Estado: NO DECIDIDO.** Tres bloques de revisión lo han pedido y tres lo
han esquivado. Se escribe con lo que se sabe y con lo que falta, para que
la decisión sea de quien tiene el dato, no de quien lo busca.

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

## 2. Por qué "no decidido" y no una respuesta inventada

Regrabar exige las **grabaciones originales** de esas 23 manos. Sin ellas
no hay a qué regrabar, y corregir el orden sería **inventar un orden**: saber
que la ciega va antes es deducirlo de las reglas, no de lo que pasó. Un
orden inventado es peor que un orden ausente, porque parece verdad.

**Lo que se comprobó:**

| | |
|---|---|
| `capturas/` | 128 ficheros PNG en la raíz + 47 en `capturas/juego/` |
| formato | `Captura de pantalla (NNN).png`, `mano1 (N).png` |
| ¿contienen un `hand_id` legible? | **no comprobado** |
| ¿son las 23 manos de CM-004? | **no se puede afirmar sin correlacionar** |

Hay capturas. **No se ha comprobado si son de estas manos.** Sin esa
comprobación, decir "se regraba" sería afirmar que existe un original que
nadie ha localizado.

## 3. Lo que sí se puede decidir sin el original

Independientemente de regrabar o migrar:

1. **Mantener las 23 manos y su procedencia intactas.** No se borran ni se
   "corrigen" con un orden inventado.
2. **Excluirlas de la calibración.** Es lo que pide revision_2 punto 4.
   `learn.load_hands(reliable_only=True)` es el sitio natural para una
   ventana fiable que las excluya, con la exclusión declarada y contada.
   Hoy no está hecho.
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
| **Alguien con acceso a las capturas** | si existe original para las 23 |
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