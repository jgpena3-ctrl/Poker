# EL IMPACTO DE LA BASE NORMALIZADA, MEDIDO

> Este documento mide qué le pasa a este repositorio si la **copia
> normalizada** de la base —`trabajo/hands_db_edicion.jsonl`— pasa a ser la
> base canónica. Y no lo dice: lo mide.
>
> Y el trabajo en paralelo de la base está en `PLAN_EDICION_DB.md` y
> `FRONTERA_GRABADOR.md`, que son suyos, y que este documento no toca.

## 0. El resumen, en cinco líneas

1. **Hoy no hay impacto**: el commit de la copia **no toca `data/`** y el
   manifiesto sigue cuadrando. MEDIDO: el sha del disco es el declarado.
2. **La copia no es una edición de la base: es un cambio de CODIFICACION.**
   MEDIDO: las 1258 manos cambian, y las 900 de la ventana de calibración
   también.
3. **El motor no conoce la codificación nueva.** MEDIDO: `motor/learn.py` no
   menciona la acción `p` ni una vez, y la copia la usa 2514 veces.
4. **Adoptarla sin más haría que el motor LANZASE** —`ValueError: acción
   preflop desconocida: 'p'`—, que es lo bueno, pero por casualidad: llega
   en mitad de una calibración y el motivo no está declarado en ningún sitio.
5. **Y algo peor que un fallo: el invariante de CM-004 daría CERO sin
  mirar nada.** MEDIDO: 921 manos con ciega reconocida frente a 6. Un verde que
   miente es peor que un rojo.

## 1. Qué es la copia, y qué cambia

| | |
|---|---|
| la canónica | `data/hands_db.jsonl` · 1258 manos · sha `5ae2abd7…` |
| la copia | `trabajo/hands_db_edicion.jsonl` · 1258 manos |
| los mismos `hand_id` | sí, y en el mismo orden |
| manos que cambian | **1258 de 1258** |
| por campo | `streets` en las 1258, `final_pot` en 689, `showdown` en 10, `winner` en 3, `players` en 2 |

Y el cambio de fondo, MEDIDO, es el **vocabulario de acciones**:

```
la canónica : b 2397   c 2558   f 4996   r 1019   x 2856
la copia    : b 1481   c 2569   f 4998   r  982   x 2883   p 2514
```

La acción nueva es `p` —pass—, y aparece **2514 veces, todas en el preflop**.
Y no es un adorno: son **las ciegas**, que en la canónica se graban como
apuestas y en la copia como pases:

```
la canónica : ('SB', 'b', 0.5)   ('BB', 'b', 1.0)
la copia    : ('SB', 'p', 0.5)   ('BB', 'p', 1.0)
```

Y el importe no se toca, de modo que la información no se pierde: cambia la
**palabra**, no la cifra.

## 2. Qué le pasa al motor

MEDIDO, y con la copia pasada por el motor entero, sin tocar `data/`:

| | la canónica | la copia |
|---|---|---|
| cargar la base | 877 manos en la ventana, sin error | 877 manos, sin error |
| clasificar la primera acción | las 8058 acciones clasifican bien | **`ValueError: acción preflop desconocida: 'p'`** |
| manos con ciega **reconocida** por el motor | **921** de 1258 | **6** de 1258 |
| el invariante de CM-004 | 0 violaciones | 0 violaciones |

Y la tercera fila es la que hay que mirar dos veces, porque **el invariante da
cero en las dos**:

- en la canónica, cero quiere decir «ninguna mano lo viola»;
- en la copia, cero quiere decir «**ya no hay ninguna `BB b` que pueda
  violarlo**».

La regla se ha apagado sola. Y el motor la apaga sin decir nada, porque la
regla que decide —`_es_ciega_bb`— exige `act == 'b'`, y en la copia la ciega
ya no es una `b`.

> **Un invariante que da cero porque no hay nada que mirar no es un
> invariante que pasa: es un invariante que ha dejado de mirar.** Y eso es
> peor que un rojo, porque el rojo se ve.

## 3. Qué le pasa a las cifras publicadas

MEDIDO, y por qué hay que recalibrar:

- **las 900 manos de la ventana cambian.** No es un cambio de un par de manos:
  es la ventana entera.
- **el reparto por acción cambia**: `b` baja 916 y aparece `p` con 2514. Y el
  AUC se calcula sobre acciones.
- **las 23 exclusiones de CM-004 cambian** las 23, y su motivo —«el registro
  está mal»— queda sin revisar.
- **las 991 manos del rango auditado cambian** las 991.
- el **manifiesto** —sha, commit— queda obsoleto, y hay que redeclararlo.

O sea que la adopción no es «cambiar un fichero»: es **rehacer la
calibración**, y el número que sale no se parece al que hay ahora.

## 4. Y el impacto en ESTE trabajo de instrumentación

MEDIDO, y son cosas distintas:

| | |
|---|---|
| el inventario de ficheros de `tools/` | **roto**: 110 declarados, 112 medidos. Los dos nuevos son `tools/aritmetica_botes.py` y `tools/interpretar_bote.py`. |
| el barrido de caracteres | **aguanta**: los 11 hallazgos declarados siguen siendo 11, y los ficheros nuevos no traen ninguno |
| el guardián de docstrings | **aguanta**: su alcance es `tools/`, y los ficheros nuevos no tienen ninguno descuadrado |
| el invariante de CM-004 | **aguanta**, porque la base no ha cambiado |
| las cifras publicadas | **intactas**, porque la base no ha cambiado |

Y un punto que conviene señalar: **dos `.py` nuevos están FUERA del alcance de
todos los guardianes**. `hand_editor.py` está en la raíz del repo, y
`trabajo/ABRIR_EDITOR_COPIA.py` en `trabajo/`. Y el alcance de los guardianes
es `tools/`, `motor/` y `recorder/`. De modo que ese código no lo vigila
nadie: ni el inventario, ni el control de caracteres, ni el de docstrings.

> No es un defecto del trabajo en paralelo: es que **el código del repo vive
> en `tools/`, `motor/` y `recorder/`**, y lo que hay fuera de ahí no está
> bajo vigilancia. Y eso hay que decidirlo, no dejarlo: o esos ficheros se
> mueven a `tools/`, o el alcance de los guardianes se declara más ancho, y
> las dos cosas son decisiones.

Y lo mismo con los **documentos**: el trabajo en paralelo ha puesto seis `.md`
en la **raíz** del repo —`PLAN_EDICION_DB.md`, `FRONTERA_GRABADOR.md`,
`INDICE_DEFECTOS.md`, `APUESTAS_DIFICILES.md`,
`AUDITORIA_SEMANTICA_GRABADOR.md` y `REVISION_DIAGNOSTICO_GRABADOR.md`—, y
la convención del repo es que los documentos viven en `DOCS/`.

MEDIDO: no rompe nada. `tools/test_estado_y_herramientas.py` comprueba que
existan los **cinco** documentos que declaran un estado, y no que todos los
`.md` estén en `DOCS/`. Pero significa que esos seis documentos **no los
vigila nadie**: no los mira el barrido de caracteres, que solo recorre
`DOCS/*.md`, y no los cubre el inventario.

> Y esto no es un «el sitio de los documentos es donde ponen cada uno»:
> es que **un documento fuera del alcance de los guardianes es un documento
> que nadie lee**. Y el que decide dónde va un documento tiene que decidir
> también quién lo vigila.

## 5. Lo que tiene que pasar ANTES de la adopción, y en este orden

Y el orden no es decorativo, y sale de la regla que ya está escrita en
`DOCS/CANAL_MANUAL_CERRADO.md`: *«el fichero se commitea primero, y el
manifiesto apunta a ese commit después»*. Y de la del motor: *un contrato
antes de tocar `motor/`*.

1. **El motor tiene que aprender la acción `p`.** Es un cambio en
   `motor/learn.py`, y por la regla del proyecto **necesita un contrato
   antes**. Y no es un detalle: `_es_ciega_bb` exige `act == 'b'`, así que
   hasta que el motor sepa lo que es un `p`, **no hay ciega que reconocer**,
   y ni el invariante de CM-004 ni la aritmética del bote pueden funcionar.
2. **El invariante de CM-004 tiene que re-derivarse** para la codificación
   nueva, y hay que escribir **qué invariante** es el nuevo. El actual, sin
   cambios, da cero sin mirar nada.
3. **La lista de exclusiones se vuelve a decidir.** Las 23 Exclusion han
   cambiado, y su motivo estaba atado al registro antiguo.
4. **El manifiesto se redeclara**: sha, commit y líneas.
5. **La ventana, la partición y el AUC se recalibran**, y las cifras
   publicadas se reescriben.

Y el orden importa en la primera: si la base cambia antes que el motor, el
motor lanza; y si el motor cambia antes que la base, no pasa nada. Lo que no
puede es cambiar la base sin que el motor la entienda.

## 6. Los dos guardianes que hay ahora para que esto no sea una sorpresa

Y se han añadido con este trabajo, y se han probado **contra el riesgo real**,
que no es un caso inventado sino la copia que ya está en el repo:

| guard | dónde | qué dice si la copia pasa a ser la canónica |
|---|---|---|
| el **vocabulario** | `motor/test_canal_manual.py` | `la base usa acciones que el motor no conoce: ['p']` |
| la **no vacuidad** | `motor/test_cm004.py` | `el motor reconoce la ciega en 6 de 1258 manos, y el declarado es 921` |

MEDIDO, y los dos se han probado **sustituyendo de verdad** la base por la
copia, ejecutándolos, y restaurándola. Los dos fallan, y con el número
concreto.

Y el primero **deriva** el vocabulario del motor del ARBOL de
`classify_first_action` —la función que lanza ante una acción que no
conoce—, y no de una lista escrita a mano. El motivo: la lista de acciones
es justo lo que va a cambiar, y un guardián que *declara* el vocabulario no lo
vigila: lo da por bueno.

> Y la diferencia entre los dos: el primero vigila que la base y el motor
> **hablen el mismo idioma**, y el segundo que el invariante **no se haya
> apagado solo**. Y los dos son el mismo fallo de siempre, aplicado al otro
> lado: **un instrumento que no puede ver lo que dice ver, en verde**.
