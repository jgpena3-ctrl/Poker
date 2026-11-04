# Corrección puntual — H_1292

**Fecha de revisión:** 2026-10-29  
**Evidencia:** revisión visual comunicada por el mantenedor; el frame fuente no
está en las capturas versionadas del repositorio.  
**Alcance:** solo H_1292; no se reinterpretan otras manos sin evidencia.

## Hallazgo y cambio de datos

En el flop, UTG (`p3`) apostó 5.5 y CO (`p5`) foldeó. Un frame aislado mostró
oscura la estrella de UTG; el recorder guardó también `UTG f`, aunque UTG era
quien ganaba la mano.

En `data/hands_db.jsonl` se retiró únicamente esa acción fantasma y se dejó el
ganador como `['p3']` (UTG). Se conserva el fold de CO. No se cambian el bote ni
la auditoría monetaria: el excedente no igualado de 5.5 y su tratamiento son
independientes del fold falso.

Antes: flop `UTG b 5.5`, `CO f`, `UTG f`; ganadores `p3, p5`.  
Después: flop `UTG b 5.5`, `CO f`; ganador `p3`.

La captura original no está disponible en `pruebas/recorder/sesiones`; por eso
la atribución del frame transitorio se registra como evidencia aportada por el
mantenedor, no como reproducción local.

## Protección del recorder

El estado `inactivo` procede del brillo de estrella, así que no se acepta como
acción por sí solo. El recorder lo valida contra la secuencia de la calle: si
hay apuesta pendiente, debe ser el primero que aún debe responder; si no la
hay, debe ser el siguiente que aún no actuó. También rechaza un fold que dejaría
la mano sin ningún jugador. Por eso `UTG b; CO f; UTG f` es imposible: UTG ya
ganó la apuesta y nadie puede responderle. Un `UTG b; CO r; UTG f` sí es válido.
No hay espera de frames. Hay tests para ambos órdenes y para un fold preflop
fuera de turno.

En el mismo lote se detectaron otras 28 manos donde `winner` contenía una
posición que ya había foldeado. En todas ellas el ganador verdadero era el único
superviviente (o el último agresor cuando no quedaba superviviente); se redujo
`winner` a esa única entrada y, en los dos casos en que el ganador había sido
marcado como fold (`H_1320`, `H_1325`), se retiró ese fold fantasma. No se
toca ninguna otra acción. Las 28 quedan documentadas como corrección focal
derivada de H_1292, no como revisión del bloque completo.

## Comisión de esta mesa

La mesa en curso cobra 3% con tope de 0.3 BB (no 5% / 2.5 BB). Se actualizó
el recorder (`rake = min(0.03 * rake_basis, 0.3 * BB)`, `rake_cap = 0.3`) y el
bote se redondea a un decimal. Se revisaron las 45 manos con `pot_read` y
35 pasaron a cuadrar; se les actualizó `rake`, `pot_calculated`,
`pot_calculated_noninflated`, `final_pot` y se retiró la ambigüedad
`pot_read_vs_calculated`. Las 10 restantes tienen otros defectos de registro
(contribuciones, bet_read, etc.) que la comisión no explica.

## Bote no inflado en victorias por fold

En 10 manos recientes (`H_1284`, `H_1286`, `H_1291`, `H_1296`, `H_1297`,
`H_1301`, `H_1309`, `H_1316`, `H_1319`, `H_1321`) el pot no se inflaba con
la última apuesta no igualada: el recorder no detectaba el fold del rival
(porque la estrella oscurecida no se confirmaba) y por eso trataba la mano
como showdown, usando `matched - rake` en vez de `gross - rake`. Se corrigió
el detector de folds (`_fold_context_valid`) y se recalcularon esos 10 pots
(inflados). El recorder ya no comete ese error.

La base local tiene 1298 líneas tras la incorporación del bloque reciente; el
manifiesto canónico previo sigue describiendo el tramo revisado hasta H_1282.
Esta corrección focal no declara revisado el resto del bloque ni sustituye la
actualización del manifiesto cuando ese tramo se valide y se integre. SHA-256
de esta candidata local: `df2d0e2975e6e683a34bf14d7f10a99cec3529226210881167d0caa3458d4bc3`.
