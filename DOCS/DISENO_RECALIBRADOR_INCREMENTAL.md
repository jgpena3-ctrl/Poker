# DISEÑO DEL RECALIBRADOR INCREMENTAL — propuesta, NO implementada

> Y antes que nada, su **estado** ✓, que es lo primero que hay que saber de
> este documento ✓:
>
> **Esto NO se implementa hasta que R1 y R2 resuelvan la discrepancia** ✓.
> Y la discrepancia es real ✓, y está declarada en
> `ESTADO_DEL_TRABAJO.md` ✓, y la resuelve **R1 y R2** ✓ y no A2 ✓.
>
> Y el motivo por el que este documento existe **aun sin implementarse** ✓:
> **un diseño declarado no es un frente abierto** ✓; es una propuesta que
> espera decisión ✓. Y una discrepancia entre dos revisiones **no se resuelve
> abriendo el frente**, se resuelve pidiendo la aclaración ✓ —y el diseño es
> lo que permite decidir **con información** ✓ y no con una intuición ✓.
>
> Y R2 pidió, exactamente, este bloque ✓: «documenta que este es un
> experimento acotado, no la apertura de una nueva vía de producción» ✓. Y
> R1 pidió que no se escribiera código ✓. Y las dos cosas son la misma ✓: un
> documento ✓.

## 1. QUÉ RECIBE

Y lo recibe como una **población explícita** ✓, y eso significa dos cosas ✓:

- una **lista de identificadores de mano** ✓, que decide **quien llama** ✓ y no
  el recalibrador ✓;
- y **el contenido** de esas manos ✓, que puede venir de un fichero que el
  llamador ha autorizado ✓ —la copia de trabajo ✓, una copia filtrada ✓, o un
  conjunto sintético ✓— ✓.

Y el recalibrador **no decide** qué registros son válidos ✓, **no lee
automáticamente** toda la base para decidirlo ✓, y **no conoce los estados**
de la cuarentena ✓ —que son de A1 ✓—. Si el llamador le pasa una población,
eso es lo que recalcula ✓, y lo que no le pase no existe para él ✓.

> Y el motivo de que la población sea **explícita** y no «la base de
> hoy» ✓: una población implícita convierte al recalibrador en el que decide
> qué es válido ✓, y esa decisión es de A1 ✓.

## 2. CÓMO MIDE EN CADA EJECUCIÓN

Y mide, y **no guarda** ✓:

- el **número de manos** de la población recibida ✓;
- el **hash del contenido** de la población ✓, para que dos ejecuciones con
  la misma población se puedan comparar ✓;
- el **hash de los identificadores** ✓, que es lo que distingue «las mismas
> manos» de «las mismas manos en otro orden» ✓;
- y la **versión del validador** y del código con el que se produjo ✓, porque
> un número sin versión no se puede comparar con otro ✓.

Y **ninguno de esos números se escribe en el código ni en un test** ✓: se
miden en cada ejecución ✓. Y la razón ✓ es la de siempre ✓: **una cifra que
pertenece a otro se mide, no se fija** ✓ —y el de la población también es de
quien la autoriza ✓.

> Y una consecuencia ✓: el informe de cada ejecución es **autodescriptivo** ✓
> —con su población y su hash ✓—, de modo que dos resultados se pueden
> comparar sin saber nada del historial ✓.

## 3. CÓMO SEPARA LA SALIDA CANDIDATA DE LA OFICIAL

Y son **dos destinos distintos** ✓, y no un modo:

- la **salida candidata** ✓ va a un directorio **de prueba** ✓ —el de trabajo
  ✓—, y **no** a `data/` ✓ ni a ningún sitio donde viva lo publicado ✓;
- la **salida oficial** ✓ **no se toca** ✓: en esta fase no se escribe nunca
  ✓, ni siquiera con un flag ✓, porque un flag es una puerta ✓.

Y además, el informe de la ejecución dice **qué cambia** respecto de la
salida oficial ✓: qué cifras se mueven ✓, cuánto ✓ y **qué registros las
mueven** ✓ —que es lo que convierte un cambio en algo explicable ✓—.

> Y el motivo de que la separación sea por **destino** y no por bandera ✓:
> una bandera se puede pasar por error ✓, y un destino equivocado **se ve en
> el informe** ✓.

## 4. CÓMO SE COMPRUEBA

Y con poblaciones **sintéticas** ✓, y sin tocar nada real ✓:

- la **misma población** dos veces → **la misma salida** ✓, con el mismo
  hash ✓;
- **una mano más elegible** → el recuento sube ✓ y los cálculos afectados se
  mueven ✓, **sin duplicar contribuciones** ✓ —que es lo que exige que la
  reconstrucción sea **desde la población** y no un acumulado a ciegas ✓;
- **una mano repetida** → **no** cuenta dos veces ✓, porque la población se
  identifica por identificador ✓ y no por posición ✓;
- **una población incompleta** → el recalibrador **no inventa** ✓: dice que no
  hay datos suficientes ✓, en vez de devolver un número que parece bueno ✓.

Y el **prototipo no decide** la elegibilidad ✓ ni **reproduce** la lógica de
la cuarentena ✓: recibe manos ya autorizadas ✓.

## 5. QUÉ NO TOCA

| | |
|---|---|
| las **cifras oficiales** | no se escriben en esta fase ✓, ni siquiera opcionalmente ✓ |
| la **base canónica** | `data/hands_db.jsonl` ✓, y su manifiesto ✓ |
| los **ficheros de A1** en `trabajo/` ✓ | ni para leerlos como población sin permiso ✓ |
| el **grafo de `preflop_matrices.json`** ✓ | y los siete módulos que dependen de él ✓ |
| la **herramienta de equity preflop** ✓ | porque cambiaría el AUC publicado ✓ |
| el **contador de subidas** ✓ | porque arreglarlo recalibra ✓ |
| la **reducción estadística** ✓ | porque es de quien decide el objetivo ✓ |

Y una cosa más ✓, que es la que más se parece a un límite suyo ✓: **el
prototipo no declara nada oficial** ✓. En particular **no declara que la base
filtrada sea la nueva referencia** ✓ —que es una decisión de A1 ✓— ni que las
cifras recalculadas sustituyan a las publicadas ✓.

## 6. LO QUE FALTA PARA QUE SE ABRA

| | |
|---|---|
| **R1 y R2 resuelven la discrepancia** ✓ | y la resolución tiene que ser **explícita** ✓, no inferida del texto de una revisión ✓ |
| **R2 confirma el alcance** ✓ | que el experimento es acotado ✓, que no toca las cifras oficiales ✓ y que no depende de datos de A1 ✓ —porque recibe una población explícita ✓— ✓ |
| **A1 define los criterios** ✓ | de qué es una población autorizada ✓ —que es lo suyo ✓— ✓ |

Y hasta que eso pase ✓, este documento **se queda como está** ✓: una
propuesta ✓, con su condición de apertura escrita ✓, y sin una línea de
código ✓.

> Y la nota que importa para quien lo lea dentro de seis meses ✓: **este
> documento no es un retraso, es una frontera** ✓. Y la frontera la pusimos
> para que la recalibración **no se parezca** a la adopción ✓ —que es una
> operación que cambia la base canónica y tiene sus propios controles ✓— y
> para que **nadie confunda** «hemos recalculado sobre una población de
> prueba» ✓ con «las cifras oficiales han cambiado» ✓.
