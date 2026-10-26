# ACCION `p` FUERA DE SB/BB — HALLAZGOS

> **Solo lectura.** No se ha modificado la base, ni los derivados, ni el motor.
> Base: `data/hands_db.jsonl`, SHA
> `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`,
> 1253 manos.

## 1. Lo que hay medido

Hay **2522 `p`**, todas en preflop:

| posicion | acciones | manos distintas |
|---|---:|---:|
| BB | 1253 | 1253 |
| SB | 1220 | 1220 |
| CO | 23 | 23 |
| MP | 12 | 12 |
| BTN | 11 | 11 |
| UTG | 3 | 3 |

Fuera de SB/BB hay **45 manos y 49 acciones**:

- **44 manos con 48 acciones de 1.0**. Cuatro manos tienen dos:
  `H_0117`, `H_0151`, `H_0171`, `H_0197`.
- **1 mano con una accion de 0.5**: `H_0595`.

La hoja de ruta habla de “45 manos con una `p` ... con importe 1.0”. La
medicion exacta es 45 manos, pero **44 con importe 1.0 y una con importe 0.5**.
No es la misma poblacion.

## 2. El orden no sostiene “limp”

Las 49 acciones estan en el indice 1, 2 o 3 del preflop, y **ninguna tiene una
accion voluntaria anterior**. Pero el orden de los asientos importa:

- CO, MP y BTN actuan **despues** de UTG en un preflop normal. En estas manos
  su `p` aparece antes que UTG o antes que cualquier accion voluntaria.
- En 41 de las 44 manos de 1.0 la accion no puede ser un limp voluntario sin
  reordenar la mano: el jugador actuaria fuera de turno.
- Las 3 manos de UTG (`H_0104`, `H_0105`, `H_0215`) si podrian ser un limp:
  UTG es el primero en actuar tras las ciegas.
- `H_0595` no puede ser un limp: es una `p` de 0.5 en BTN, por debajo de la
  apuesta viva de 1.0.

El patron es mas compatible con **postas forzadas** (ciega muerta, ante o
posta de entrada) que con limps:

- importe exactamente igual a la ciega nominal (1.0 o 0.5);
- colocadas al principio, antes de las acciones voluntarias;
- el jugador sigue actuando despues (`x`, `c` o `f`);
- el contrato de `p` ya dice que una posta **no es una decision**.

## 3. Efecto actual en el motor

`learn.preflop_events` salta toda `p`. Si las 49 acciones se recodificaran a
`c`, las 45 manos cambian su conjunto de eventos. Ejemplos:

- `H_0026`: hoy no hay evento de CO; con `c` aparece `CO limp 1.0` y MP pasa
  de `open` a `rol`.
- `H_0049`: hoy MP es `bb_check`; con `c` aparece `MP limp 1.0`.
- `H_0138`: hoy hay `MP limp`; con `c` aparece ademas `BTN limp` y MP pasa a
  `call_limp`.
- `H_0147`: hoy BB es `open`; con `c` aparece `CO limp` y BB pasa a `rol`.

No se ha aplicado la recodificacion.

## 4. La fuente manual lo confirma: son postas de entrada

`trabajo/editados.txt` es el registro de correcciones manuales de la copia.
Dice, literalmente:

- `H_0519`: «no se toca co en preflop, entra a la mesa con un ciega p:1
  antes de iniciarse la ronda preflop».
- `H_1228`: «la secuencia de co si se puede, entra a la mesa con p:1, en su
  turno checkea, luego le toca volver a hablar ante la subida de sb a 3 y
  resube a 5».

Las dos manos estan entre las 44. Eso cierra la lectura: la `p` de 1.0 es una
**ciega muerta o posta de entrada**, puesta antes de la ronda voluntaria, y no
un limp. `H_0595` es el mismo tipo de posta, con el importe de la SB.

Por tanto la hoja de ruta se equivoca al llamarlas limps. La lectura correcta
es la del contrato: `p` es una posta, no una decision, y el motor ya la salta
correctamente. No hay que recodificar a `c`.

Lo que queda por corregir es la **documentacion y las auditorias** que las
describen como limps o como antes. La base no se toca.

## 5. Decision

1. **Mantener las 49 acciones como `p`.** No se recodifican.
2. **No contarlas como limps ni como decisiones.** El motor ya lo hace bien.
3. **Corregir los textos** de la hoja de ruta y de las auditorias que digan
   “limp” o “ante” para estas 45 manos.
4. **Declarar `H_0595`** como posta de 0.5 en BTN, pendiente de confirmar con
   la grabacion original.

No se calibra ni se regeneran derivados por este hallazgo.
