# Pruebas manuales del recorder

Este directorio declara las manos históricas que se quieren repetir sin tocar
`data/hands_db.jsonl`, la base canónica.

1. Añade los IDs problemáticos a `objetivos.json`.
2. Ejecuta `python tools/iniciar_prueba_recorder.py` desde la raíz del repo.
3. En la GUI selecciona **Manual**, inicializa el lector y captura los frames
   relevantes; termina cada mano con **Save & New Hand**.

El comando crea una sesión nueva en `pruebas/recorder/sesiones/` (ignoradas por
Git), con esta estructura:

```text
<sesion>/
  sesion.json                       objetivos, hash de la base y rutas
  resultados/hands_db.jsonl         manos producidas, nunca las canónicas
  resultados/registro_sesion.jsonl  relación entre objetivos y resultado
  capturas/index.jsonl              índice ordenado de todos los frames
  capturas/H_0001/*.png + *.json    imagen, estado OCR y SHA-256 por frame
```

Cada captura guarda tanto el estado leído como los overrides manuales. El
índice global tiene una secuencia monotónica, por lo que una sesión puede
reproducirse y auditarse aunque se reinicie la GUI. Para una ejecución puntual
sin editar el fichero: `python tools/iniciar_prueba_recorder.py --id H_0141`.
