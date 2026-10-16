# INC-003 — un barrido en modo escritura borró 44 ficheros

> **Tipo**: incidente de procedimiento, no de código.
> **Bloque**: el que añadió los contadores por etapa y la condición
> analítica de coherencia.
> **Estado**: cerrado. Recuperado íntegro y con un test que lo previene.

## Qué pasó

Escribí un script de «caracteres sospechosos» para revisar los ficheros del
proyecto, y lo puse en **modo escritura**. La intención era **informar**.

El rango que creía sospechoso empezaba en `U+00A0`:

```python
RANGOS_SOSPECHOSOS = ((0x0370, 0x04FF),   # cirilico
                      (0x0400, 0x04FF),
                      (0x00A0, 0x00BF),   # <-- empieza aqui
                      (0x3000, 0x9FFF),   # CJK
                      (0xFFFD, 0xFFFD))
```

Y **`U+00A7` es el signo de sección `§`**, que `U+00A0…U+00BF` incluye.

## Efecto

El script recorrió `tools/*.py`, `motor/*.py` y `DOCS/*.md`, y para cada
carácter no permitido hizo:

```python
limpio = limpio.replace(c, 'e' if 'Normalized' in s else '')
```

O sea: **borró** `§`, `·`, `«` y `»` de **44 ficheros**. Caracteres que el
proyecto usa en todas partes, desde los documentos hasta los docstrings.

Y las comillas «» desaparecieron justo de los documentos, que es donde
menos se nota a ojo y más se nota después.

## Recuperación

`git checkout -- tools/ DOCS/ motor/ recorder/` restauró los 44 ficheros.

**Coste real**: el `git checkout` también se llevó el trabajo **sin
commitear** del bloque — los contadores por etapa, el instrumento y los tres
documentos. Hubo que rehacerlo todo, unos cuarenta minutos de trabajo que no
estaban en ningún commit.

La lección secundaria: **`git checkout` es una recuperación destructiva si
hay trabajo sin commitear**. Es la misma clase de error que el barrido, con
otro nombre.

## Por qué el barrido estaba mal

Un barrido que no distingue **«esto estaba aquí antes»** de **«esto se ha
colado»** no es un barrido: es una costumbre que reescribe el pasado.

La comprobación correcta es **diferencial**, no absoluta:

| |_absolute_ | _diferencial_ |
|---|---|---|
| pregunta | ¿este carácter es raro? | ¿este carácter es **nuevo** respecto a `HEAD`? |
| requiere | una lista de permitidos | comparar con el commit |
| riesgo | borra lo que llevaba años ahí | solo señala lo que cambió |

Y si hay que escribir, **primero en memoria, luego un diff, y solo después al
disco**.

## La corrección

El chequeo que se quedó es **de solo lectura**:

```python
# lo que el proyecto USA de verdad, asi que no es contaminacion
PERMITIDOS = set('·§«»¿¡…—–áéíóúñÁÉÍÓÚÑüÜçÇãõâêô')

# y ademas se imprime sin tocar nada
print('caracteres sospechosos: %d' % n)
```

Y la única corrección que se aplica es la **cadena concreta** conocida:

```
seNormalized -> se normalizado
```

Una cadena con una `е` **cirílica** inyectada dentro, dos ficheros, y
se corrige por nombre.

> Ese `е` del ejemplo es **intencionado**, y
> `verificar_caracteres.py` lo señala como `NUEVO` a propósito: es la
> única forma de que quien lo lea sepa que es un ejemplo y no un
> resto del barrido.
corrige por nombre. Un caso conocido se corrige por nombre; lo desconocido se
señala.

## Cómo se previene, y no solo cómo se recuerda

Hay un test. Un archivo no puede contener caracteres fuera de un conjunto
explícito, y el conjunto está escrito:

```python
CJK = (0x3000, 0x9FFF)
CIRILICO = (0x0400, 0x04FF)
```

Más lo que este proyecto usa de verdad y no es contamination:
`·§«»¿¡…—–` y las vocales acentuadas.

Lo que **no** tiene el test, y es lo que de verdad hacía falta:

> **Ningún script de revisión escribe en ficheros.**

La regla es de procedimiento, no de código, y por eso vive aquí y no en un
`Makefile`.

## Lo que este incidente cuesta decir

Es el error más caro de diecisiete bloques. No porque borrara 44 ficheros —eso
se recupera con `git checkout`—, sino porque **el barrido se ejecutó,
encontró lo que buscaba, y no leyó que estaba borrando**.

Un instrumento que aplica su criterio sin mirar lo que toca es el mismo error
que un `L_prim` que ordena sin mirar: una medida sin la garantía de que la
medida es de lo que se cree.

## Reproducir el diagnóstico (sin escribir nada)

```
python tools/verificar_caracteres.py
```