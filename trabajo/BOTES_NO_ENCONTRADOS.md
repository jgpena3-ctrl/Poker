# Botes no encontrados - revision manual

Generado por `tools/aritmetica_botes.py`.

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack: no se normaliza) | 1 |
| `NADA` (el bote no coincide con ninguna lectura) | 40 |
| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | 0 |

En las `STACK` el registro ya es imposible (un jugador compromete mas que su stack), asi que normalizarlo dispararia el bote: se dejan intactas. En las `NADA` el bote declarado no sale con ninguna combinacion de apuestas parciales/absolutas, con ni sin comision, ni con ni sin la ciega del SB.

De las `ACCION_AMBIGUA`: `REPARTO` 0 (mismo neto y bruto; cambia quien aporta), `NETO_IGUAL` 0 (mismo neto; cambian importes igualados), `REAL` 0 (el neto cambia; hay que decidir). Solo `REAL` afecta a la ganancia. Las `DEVUELTA` (subida no pagada; el neto no cambia) se resuelven solas eligiendo la lectura absoluta.

## STACK (1)

### H_0740 - 2026-09-15

- **Pot declarado**: 37.7
- **Combinaciones**: 2
- **Netos posibles**: [18.24, 19.66]
- **Brutos posibles**: [37.84, 39.27]
- **Coincidencia**: bruto = 37.84 (dif 0.14)
- **Stacks**: BB=136.0, UTG=102.1, MP=110.3, CO=183.6, BTN=52.1, SB=28.1
- **Supera stack**: SB total=28.2 stack=28.1 exceso=+0.10
- **Nota**: el exceso <= 0.2 esta dentro de la tolerancia del bote; puede ser redondeo, no un error de stack.
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB b 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB r 2.0 | BB c 1.0 | CO c 1.0
- **flop**: SB b 2.9 | BB c 2.9 | CO f 0.0
- **turn**: SB b 3.7 | BB c 3.7
- **river**: SB b 19.6 | BB f 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | BB b parcial 2.00 | UTG f | MP f | CO c 2.00 | BTN f | SB r absoluta 2.00 | BB c (check) | CO c (check) | SB b absoluta 2.90 | BB c 2.90 | CO f | SB b absoluta 3.70 | BB c 3.70 | BB f

## NADA (40)

### H_0043 - 2026-07-28

- **Pot declarado**: 9.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [9.28]
- **Neto mas cercano**: 4.28 (dif -5.22)
- **Stacks**: CO=45.4, BTN=139.7, SB=92.3, BB=172.0, UTG=48.9, MP=89.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN b 6.0 | SB f 0.0 | BB f 0.0 | MP f 0.0 | CO f 0.0

### H_0124 - 2026-07-29

- **Pot declarado**: 12.0
- **Combinaciones**: 1
- **Netos posibles**: [6.17]
- **Brutos posibles**: [11.68]
- **Neto mas cercano**: 6.17 (dif -5.83)
- **Stacks**: BB=118.5, UTG=51.5, MP=103.6, BTN=58.1, SB=38.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.5 | MP f 0.0 | BTN r 8.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0138 - 2026-07-29

- **Pot declarado**: 8.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [8.28]
- **Neto mas cercano**: 4.28 (dif -4.22)
- **Stacks**: UTG=35.1, MP=98.5, BTN=20.0, SB=95.2, BB=92.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN p 1.0 | UTG c 1.0 | MP r 5.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0152 - 2026-07-30

- **Pot declarado**: 13.0
- **Combinaciones**: 1
- **Netos posibles**: [6.17]
- **Brutos posibles**: [12.68]
- **Neto mas cercano**: 6.17 (dif -6.83)
- **Stacks**: BTN=52.9, SB=77.2, BB=15.1, UTG=71.0, MP=121.5, CO=165.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 2.5 | CO f 0.0 | BTN r 9.0 | SB f 0.0 | BB f 0.0 | MP f 0.0

### H_0247 - 2026-07-31

- **Pot declarado**: 14.0
- **Combinaciones**: 2
- **Netos posibles**: [4.75]
- **Brutos posibles**: [13.75, 14.25]
- **Neto mas cercano**: 4.75 (dif -9.25)
- **Stacks**: CO=115.2, BTN=29.6, SB=104.0, BB=20.0, UTG=100.0, MP=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 2.0 | CO f 0.0 | BTN f 0.0 | SB r 11.0 | BB f 0.0 | MP f 0.0

### H_0260 - 2026-07-31

- **Pot declarado**: 9.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [9.28]
- **Neto mas cercano**: 4.28 (dif -5.22)
- **Stacks**: BB=149.2, UTG=29.8, MP=102.2, CO=25.0, BTN=122.7, SB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO c 1.0 | BTN r 6.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0291 - 2026-07-31

- **Pot declarado**: 9.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [9.28]
- **Neto mas cercano**: 4.28 (dif -5.22)
- **Stacks**: UTG=159.2, MP=13.5, CO=111.6, BTN=22.3, SB=152.7, BB=113.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN p 1.0 | UTG f 0.0 | MP c 1.0 | CO r 6.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | MP f 0.0

### H_0303 - 2026-07-31

- **Pot declarado**: 9.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [9.28]
- **Neto mas cercano**: 4.28 (dif -5.22)
- **Stacks**: BB=166.5, UTG=49.9, MP=124.6, CO=20.0, BTN=152.5, SB=130.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO p 1.0 | UTG c 1.0 | MP r 6.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0380 - 2026-09-13

- **Pot declarado**: 18.91
- **Combinaciones**: 1
- **Netos posibles**: [12.16]
- **Brutos posibles**: [18.66]
- **Neto mas cercano**: 12.16 (dif -6.75)
- **Stacks**: BTN=101.5, SB=80.6, BB=119.5, UTG=28.4, MP=65.6, CO=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | CO b 1.9 | BTN f 0.0 | SB c 1.9 | BB f 0.0
- **turn**: SB b 2.5 | CO r 9.0 | SB f 0.0

### H_0428 - 2026-09-13

- **Pot declarado**: 13.0
- **Combinaciones**: 2
- **Netos posibles**: [5.22]
- **Brutos posibles**: [12.72, 13.72]
- **Neto mas cercano**: 5.22 (dif -7.78)
- **Stacks**: CO=97.0, BTN=181.4, SB=8.4, BB=242.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB r 10.0 | CO f 0.0

### H_0499 - 2026-09-14

- **Pot declarado**: 11.5
- **Combinaciones**: 2
- **Netos posibles**: [5.22]
- **Brutos posibles**: [11.22, 12.22]
- **Neto mas cercano**: 5.22 (dif -6.28)
- **Stacks**: BB=146.7, CO=106.2, BTN=105.4, SB=197.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB r 8.5 | CO f 0.0

### H_0532 - 2026-09-14

- **Pot declarado**: 25.61
- **Combinaciones**: 1
- **Netos posibles**: [11.97]
- **Brutos posibles**: [25.37]
- **Neto mas cercano**: 11.97 (dif -13.64)
- **Stacks**: BB=94.4, UTG=28.7, MP=115.8, CO=107.8, SB=40.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: SB x 0.0 | BB b 1.9 | UTG c 1.9 | MP f 0.0 | SB f 0.0
- **river**: BB b 2.4 | UTG r 15.8 | BB f 0.0

### H_0537 - 2026-09-15

- **Pot declarado**: 16.6
- **Combinaciones**: 1
- **Netos posibles**: [12.92]
- **Brutos posibles**: [16.22]
- **Neto mas cercano**: 12.92 (dif -3.68)
- **Stacks**: BTN=161.5, SB=68.4, BB=103.8, CO=104.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 3.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | CO b 3.3 | SB r 6.6 | CO f 0.0

### H_0577 - 2026-09-15

- **Pot declarado**: 119.5
- **Combinaciones**: 4
- **Netos posibles**: [63.0, 71.0]
- **Brutos posibles**: [117.0, 121.0, 128.0, 132.0]
- **Neto mas cercano**: 71.0 (dif -48.5)
- **Stacks**: BTN=166.3, SB=47.9, BB=64.6, UTG=75.9, MP=102.2, CO=50.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 4.0 | CO f 0.0 | BTN r 11.0 | SB f 0.0 | BB c 11.0 | MP r 27.0 | BTN r 81.0 | BB f 0.0 | MP f 0.0

### H_0585 - 2026-09-15

- **Pot declarado**: 33.6
- **Combinaciones**: 2
- **Netos posibles**: [20.71, 22.61]
- **Brutos posibles**: [32.71, 34.61]
- **Neto mas cercano**: 22.61 (dif -10.99)
- **Stacks**: BB=101.8, MP=21.9, CO=40.6, SB=39.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | SB c 1.0 | BB r 5.0 | MP c 5.0 | SB f 0.0
- **flop**: BB b 5.4 | MP c 5.4
- **turn**: BB b 12.0 | MP f 0.0

### H_0588 - 2026-09-15

- **Pot declarado**: 15.0
- **Combinaciones**: 2
- **Netos posibles**: [11.59, 13.49]
- **Brutos posibles**: [14.59, 16.49]
- **Neto mas cercano**: 13.49 (dif -1.51)
- **Stacks**: BTN=112.5, SB=13.0, BB=40.6, CO=37.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 2.5 | SB c 2.5
- **flop**: SB x 0.0 | BB x 0.0
- **turn**: SB x 0.0 | BB b 3.6 | SB c 3.6
- **river**: SB x 0.0 | BB b 3.0 | SB f 0.0

### H_0590 - 2026-09-15

- **Pot declarado**: 10.3
- **Combinaciones**: 1
- **Netos posibles**: [5.7]
- **Brutos posibles**: [10.1]
- **Neto mas cercano**: 5.7 (dif -4.6)
- **Stacks**: BB=108.5, BTN=48.8
- **Acciones**:
- **preflop**: BB p 1.0 | BTN c 1.0 | BB x 0.0
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB b 1.0 | BTN c 1.0
- **river**: BB b 1.0 | BTN r 5.4 | BB f 0.0

### H_0623 - 2026-09-15

- **Pot declarado**: 15.06
- **Combinaciones**: 1
- **Netos posibles**: [11.21]
- **Brutos posibles**: [14.71]
- **Neto mas cercano**: 11.21 (dif -3.85)
- **Stacks**: MP=228.8, CO=180.5, BTN=103.8, SB=21.1, BB=125.9, UTG=96.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 1.4 | SB c 1.4
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 3.5 | BB r 7.0 | SB f 0.0

### H_0636 - 2026-09-15

- **Pot declarado**: 15.5
- **Combinaciones**: 2
- **Netos posibles**: [5.22]
- **Brutos posibles**: [15.22, 16.23]
- **Neto mas cercano**: 5.22 (dif -10.28)
- **Stacks**: SB=239.7, BB=100.0, UTG=103.8, MP=10.0, CO=136.1, BTN=96.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.5 | SB f 0.0 | BB r 12.5 | BTN f 0.0

### H_0658 - 2026-09-15

- **Pot declarado**: 21.5
- **Combinaciones**: 1
- **Netos posibles**: [11.88]
- **Brutos posibles**: [20.88]
- **Neto mas cercano**: 11.88 (dif -9.62)
- **Stacks**: MP=109.2, CO=97.6, BTN=99.8, SB=140.8, BB=53.5, UTG=27.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 5.0 | CO r 14.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0 | MP f 0.0

### H_0676 - 2026-09-15

- **Pot declarado**: 33.9
- **Combinaciones**: 1
- **Netos posibles**: [28.12]
- **Brutos posibles**: [28.12]
- **Neto mas cercano**: 28.12 (dif -5.78)
- **Stacks**: BB=99.0, MP=103.8, CO=45.0, BTN=47.4, SB=34.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 2.4 | MP c 2.4 | CO f 0.0 | BTN c 2.4 | SB f 0.0
- **river**: BB b 5.8 | MP c 5.8 | BTN c 11.6 | BB f 0.0 | MP f 0.0

### H_0785 - 2026-09-15

- **Pot declarado**: 53.45
- **Combinaciones**: 2
- **Netos posibles**: [41.04]
- **Brutos posibles**: [51.74, 58.14]
- **Neto mas cercano**: 41.04 (dif -12.41)
- **Stacks**: CO=131.8, BTN=108.5, SB=52.3, BB=142.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 3.0 | SB c 3.0 | BB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 6.4 | BTN f 0.0 | SB r 17.1 | BB r 27.8 | SB f 0.0

### H_0825 - 2026-09-16

- **Pot declarado**: 11.5
- **Combinaciones**: 2
- **Netos posibles**: [4.28]
- **Brutos posibles**: [11.28, 12.28]
- **Neto mas cercano**: 4.28 (dif -7.22)
- **Stacks**: BB=101.9, UTG=23.0, MP=23.8, CO=101.5, BTN=110.2, SB=6.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN c 1.0 | SB f 0.0 | BB r 8.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0

### H_0868 - 2026-09-16

- **Pot declarado**: 92.825
- **Combinaciones**: 1
- **Netos posibles**: [52.2]
- **Brutos posibles**: [92.0]
- **Neto mas cercano**: 52.2 (dif -40.62)
- **Stacks**: CO=85.4, BTN=102.5, SB=43.2, BB=113.0, UTG=87.3, MP=70.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.5 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 3.6 | BTN r 13.0 | SB f 0.0 | BB c 13.0
- **river**: BB b 10.6 | BTN r 50.4 | BB f 0.0

### H_0888 - 2026-09-16

- **Pot declarado**: 9.0
- **Combinaciones**: 2
- **Netos posibles**: [5.22]
- **Brutos posibles**: [8.72, 9.72]
- **Neto mas cercano**: 5.22 (dif -3.78)
- **Stacks**: MP=95.4, CO=125.4, BTN=116.8, SB=100.2, BB=67.4, UTG=16.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB r 6.0 | CO f 0.0

### H_0910 - 2026-09-17

- **Pot declarado**: 113.3
- **Combinaciones**: 2
- **Netos posibles**: [3.8]
- **Brutos posibles**: [113.1, 114.1]
- **Neto mas cercano**: 3.8 (dif -109.5)
- **Stacks**: CO=101.7, BTN=39.2, SB=393.9, BB=110.3, UTG=98.2, MP=65.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB r 110.3 | MP f 0.0 | CO f 0.0 | SB f 0.0

### H_0912 - 2026-09-17

- **Pot declarado**: 71.7
- **Combinaciones**: 1
- **Netos posibles**: [71.9]
- **Brutos posibles**: [71.9]
- **Neto mas cercano**: 71.9 (dif 0.2)
- **Stacks**: UTG=95.7, MP=83.4, CO=353.8, BTN=112.8, SB=97.2, BB=63.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN r 3.0 | SB c 3.0 | BB c 3.0 | CO c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0 | BTN b 3.8 | SB f 0.0 | BB f 0.0 | CO c 3.8
- **turn**: CO x 0.0 | BTN b 9.3 | CO c 9.3
- **river**: CO b 18.1 | BTN c 18.1

### H_0916 - 2026-09-17

- **Pot declarado**: 121.3
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [121.08]
- **Neto mas cercano**: 4.28 (dif -117.02)
- **Stacks**: BB=92.2, MP=41.1, CO=366.5, BTN=117.8, SB=99.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN r 117.8 | SB f 0.0 | BB f 0.0

### H_0919 - 2026-09-17

- **Pot declarado**: 16.625
- **Combinaciones**: 1
- **Netos posibles**: [8.07]
- **Brutos posibles**: [16.38]
- **Neto mas cercano**: 8.07 (dif -8.55)
- **Stacks**: BB=184.4, UTG=79.3, MP=390.1, CO=136.4, BTN=74.2, SB=98.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG b 2.5 | MP r 10.8 | BB f 0.0 | UTG f 0.0

### H_0925 - 2026-09-17

- **Pot declarado**: 27.225
- **Combinaciones**: 1
- **Netos posibles**: [26.32]
- **Brutos posibles**: [26.32]
- **Neto mas cercano**: 26.32 (dif -0.91)
- **Stacks**: SB=173.0, BB=114.4, UTG=323.0, MP=108.1, CO=137.3, BTN=95.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 3.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB c 3.0 | UTG c 3.0
- **flop**: BB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: BB x 0.0 | UTG x 0.0 | MP x 0.0
- **river**: BB x 0.0 | UTG b 9.1 | MP c 9.1 | BB f 0.0 | MP f 0.0

### H_0945 - 2026-09-17

- **Pot declarado**: 190.2
- **Combinaciones**: 2
- **Netos posibles**: [4.75]
- **Brutos posibles**: [189.95, 190.45]
- **Neto mas cercano**: 4.75 (dif -185.45)
- **Stacks**: MP=170.6, CO=18.3, BTN=569.7, SB=186.2, BB=134.1, UTG=78.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB r 186.2 | BB f 0.0 | MP f 0.0

### H_0949 - 2026-09-17

- **Pot declarado**: 189.7
- **Combinaciones**: 2
- **Netos posibles**: [5.7]
- **Brutos posibles**: [189.4, 189.9]
- **Neto mas cercano**: 5.7 (dif -184.0)
- **Stacks**: CO=167.6, BTN=37.1, SB=186.2, BB=128.2, MP=68.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB r 186.2 | BB f 0.0 | CO f 0.0

### H_0958 - 2026-09-17

- **Pot declarado**: 10.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [10.28]
- **Neto mas cercano**: 4.28 (dif -6.22)
- **Stacks**: SB=128.5, BB=58.6, UTG=38.5, MP=187.4, CO=121.2, BTN=68.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN r 7.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0 | MP f 0.0

### H_1038 - 2026-09-17

- **Pot declarado**: 9.5
- **Combinaciones**: 1
- **Netos posibles**: [4.28]
- **Brutos posibles**: [9.28]
- **Neto mas cercano**: 4.28 (dif -5.22)
- **Stacks**: SB=116.5, BB=136.4, UTG=101.5, MP=71.3, CO=95.0, BTN=95.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN r 6.0 | SB f 0.0 | BB f 0.0 | MP f 0.0 | CO f 0.0

### H_1089 - 2026-09-17

- **Pot declarado**: 18.1
- **Combinaciones**: 1
- **Netos posibles**: [11.21]
- **Brutos posibles**: [17.81]
- **Neto mas cercano**: 11.21 (dif -6.89)
- **Stacks**: BB=87.8, MP=71.8, CO=98.3, BTN=135.6, SB=166.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.0 | BTN f 0.0 | SB c 2.0 | BB c 2.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0
- **turn**: SB x 0.0 | BB b 2.9 | CO f 0.0 | SB r 9.5 | BB f 0.0

### H_1130 - 2026-09-18

- **Pot declarado**: 40.2
- **Combinaciones**: 1
- **Netos posibles**: [21.66]
- **Brutos posibles**: [39.76]
- **Neto mas cercano**: 21.66 (dif -18.54)
- **Stacks**: SB=116.3, BB=81.5, UTG=116.1, MP=37.8, CO=148.4, BTN=45.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.0 | SB c 2.0 | BB c 2.0
- **flop**: SB x 0.0 | BB b 4.0 | BTN f 0.0 | SB c 4.0
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 4.4 | BB r 22.5 | SB f 0.0

### H_1135 - 2026-09-18

- **Pot declarado**: 15.5
- **Combinaciones**: 2
- **Netos posibles**: [5.22]
- **Brutos posibles**: [15.22, 16.23]
- **Neto mas cercano**: 5.22 (dif -10.28)
- **Stacks**: BTN=104.4, SB=93.7, BB=114.6, CO=193.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 2.5 | SB f 0.0 | BB r 12.5 | BTN f 0.0

### H_1145 - 2026-09-18

- **Pot declarado**: 41.43
- **Combinaciones**: 1
- **Netos posibles**: [27.17]
- **Brutos posibles**: [40.97]
- **Neto mas cercano**: 27.17 (dif -14.26)
- **Stacks**: MP=93.5, CO=105.5, BTN=41.3, SB=215.1, BB=60.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 2.5 | CO f 0.0 | BTN c 2.5 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | MP x 0.0 | BTN x 0.0
- **turn**: BB x 0.0 | MP x 0.0 | BTN b 5.7 | BB f 0.0 | MP c 5.7
- **river**: MP b 4.6 | BTN r 18.4 | MP f 0.0

### H_1172 - 2026-09-18

- **Pot declarado**: 13.2
- **Combinaciones**: 1
- **Netos posibles**: [10.45]
- **Brutos posibles**: [12.95]
- **Neto mas cercano**: 10.45 (dif -2.75)
- **Stacks**: UTG=94.6, MP=77.3, CO=101.7, BTN=100.0, SB=55.5, BB=41.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB c 2.5 | BB f 0.0
- **flop**: SB x 0.0 | CO b 2.5 | SB r 5.0 | CO f 0.0

### H_1255 - 2026-09-18

- **Pot declarado**: 14.84
- **Combinaciones**: 1
- **Netos posibles**: [11.21]
- **Brutos posibles**: [14.61]
- **Neto mas cercano**: 11.21 (dif -3.63)
- **Stacks**: BB=128.4, UTG=109.1, MP=100.0, CO=102.7, BTN=98.9, SB=97.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB b 1.4 | BB c 1.4 | UTG c 1.4
- **turn**: SB b 2.3 | BB r 5.7 | UTG f 0.0 | SB f 0.0
