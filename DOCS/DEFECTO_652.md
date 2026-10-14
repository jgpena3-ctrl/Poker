# DEFECTO 652 — el BB y la subida que cierra el preflop

**Estado:** cerrado como error de interpretación. **Grabación**, y son 4 manos
en el rango declarado fiable.
**Fecha:** 2026-10-14
**Instrumento:** `tools/auditar_rango.py`, clase `SIN_RESPUESTA_BB`.
**Consecuencia para Fase D:** **no bloquea.**

---

## 1. Qué se publicó y por qué está mal

La cifra de 652 salió de una regla escrita como:

> «el BB tiene entrada en el preflop y no vuelve a actuar»

Medida, esa frase y la regla que la produce no son lo mismo. La regla real
—la que da 652, y que `e314f74` reproduce— es:

> **la última entrada `b` o `r` del preflop es una subida de alguien que no
> es el BB**

Y eso ocurre en **el 50,9 % de la base** porque es una situación normal: una
subida que nadie responde porque el resto ya foldeó. En la mayoría de esos
casos **el BB respondió antes**.

### La descomposición

| | e314f74 (1280) | H_0001..H_1014 (991) |
|---|---:|---:|
| la regla estructural se cumple | 652 | 486 |
| ├ el BB **responde** después (call, fold, check) | 613 | 471 |
| ├ el BB **ya estaba foldeado** antes de esa subida | 16 | 10 |
| ├ **el BB no actúa tras la subida** | **22** | **4** |
| └ **el BB no tiene ninguna entrada preflop** | **1** | **1** |
| **SUBTOTAL REAL** | **23** | **5** |
| **falsos positivos** | **629** | **481** |

**El error fue de un factor de 44.** No por un detalle del detector: por no
preguntarse qué significaba la regla que se estaba contando.

---

## 2. Los cinco del rango declarado fiable

### `H_0399` — falta la acción del BB

```
mesa : BB=Jarduan, MP=Onix22, CO=Pechugo, BTN=man1, fuera=Isagomez, SB=LUIS-DIAZ
preflop  BB:b1.0  MP:f0.0  CO:f0.0  BTN:r2.5  SB:f0.0
pot 4.0   winner=['p3']   allin=[]
```

El BB postea, el BTN sube a 2,5, el SB foldea y el BB no aparece. Tenía que
llamar o foldear. **No hay entrada suya.**

### `H_0404` — falta la acción del BB

```
mesa : BB=Jarduan, MP=Onix22, CO=Pechugo, BTN=man1, fuera=Iker69, SB=LUIS-DIAZ
preflop  BB:b1.0  MP:f0.0  CO:f0.0  BTN:r3.0  SB:f0.0
pot 4.5   winner=['p3']   allin=[]
```

Idéntico. Misma mesa, tres minutos después.

### `H_0633` — falta la acción del BB

```
mesa : MP=Jarduan, CO=mommya, BTN=N.E.O, SB=Hector1320, BB=Davi-Ari, UTG=Juris55
preflop  BB:b1.0  UTG:r2.5  MP:f0.0  CO:f0.0  BTN:f0.0  SB:f0.0
pot 4.0   winner=['p5']   allin=[]
```

El BB postea, el UTG sube a 2,5, todos foldean y el BB no aparece.

### `H_0196` — el BB no aparece en el preflop

```
mesa : MP=Johan Otero, CO=KappaxSlayer, BTN=Maicolp, SB=Elyessi27, BB=Jarduan, UTG=MegustanLas...
preflop  UTG:r17.0  MP:f0.0  CO:f0.0  BTN:f0.0  SB:f0.5
pot 2.5   winner=['p5']   allin=['p5']
```

Único caso de la base completa en el que el BB **no tiene ninguna entrada
preflop** y el preflop sí se desarrolla. Es el mismo defecto que CM-003
trató para 26 manos por inferencia, y aquí no hay entrada que inferir.

### `H_0883` — **no es de este defecto**

```
mesa : CO=Jarduan, BTN=Davi-Ari, SB=Woons, BB=BigPapi., UTG=Santiagoea10, MP=HarryPoker18
preflop  BB:b1.0  UTG:c1.0  MP:f0.0  CO:f0.0  BTN:f0.0  SB:c1.0  BB:r7.0  UTG:f0.0  SB:r7.0
pot 26.4   winner=['p2']   allin=[]
```

El BB subió a 7.0. Después el SB tiene `r 7.0`, que **no supera** el 7.0: es
una llamada etiquetada como subida. El BB sí actuó y no le faltaba nada. Esto
es `IMPORTE_SUBIDA`, y está en la lista de 36.

---

## 3. Veredicto: es un hueco de grabación, no un error de poker

| | |
|---|---|
| **Clasificación** | **grabación.** El recorder no escribió la acción del BB |
| **Alcance real** | 4 manos en el rango declarado fiable; 23 en la base completa de 1280 |
| **Por qué no es poker** | en las cuatro el BB estaba en la mesa y tenía algo que decidir: una subida viva contra él y todos los demás fuera. No hay lectura de poker que haga que no actuara |
| **Por qué no es más grande** | 481 de las 486 casos del rango son falsos positivos. El BB respondió |

---

## 4. Qué se puede hacer

**El recorder**, no los datos. Si la omisión viene de cómo se cierra el
preflop —por ejemplo, si la mano termina cuando el SB foldea y la del BB se
escribe aparte—, el arreglo es de una línea hacia adelante y la pérdida
histórica se declara como se declaró la de las 73 sin `allin`.

**No se corrigen las cuatro a mano.** Cuatro no son un patrón: no hay regla
que las produced. Y lo que vaut la pena arreglar es el recorder, no estas
cuatro.

---

## 5. Consecuencia para Fase D

> **No bloquea.** El perfil del BB se puede calibrar con 4 huecos
> declarados en 991 manos, no con «la mitad de la base sin responder».

Lo que sí queda por decidir, y es otra cosa:

- Los **36** de `IMPORTE_SUBIDA`, que sí affects cómo se leen las frecuencias
  del BB. Ver `DEFECTO_45.md`.
- Los **73** sin `allin`, que ya se conocían.