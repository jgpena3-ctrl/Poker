# Botes no encontrados - revision manual

Generado por `tools/aritmetica_botes.py`.

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack: no se normaliza) | 0 |
| `NADA` (el bote no coincide con ninguna lectura) | 0 |
| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | 0 |

En las `STACK` el registro ya es imposible (un jugador compromete mas que su stack), asi que normalizarlo dispararia el bote: se dejan intactas. En las `NADA` el bote declarado no sale con ninguna combinacion de apuestas parciales/absolutas, con ni sin comision, ni con ni sin la ciega del SB.

De las `ACCION_AMBIGUA`: `REPARTO` 0 (mismo neto y bruto; cambia quien aporta), `NETO_IGUAL` 0 (mismo neto; cambian importes igualados), `REAL` 0 (el neto cambia; hay que decidir). Solo `REAL` afecta a la ganancia. Las `DEVUELTA` (subida no pagada; el neto no cambia) se resuelven solas eligiendo la lectura absoluta.
