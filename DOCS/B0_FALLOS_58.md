# Anexo A — Los 58 fallos originales de B0

Clasificación individual medida sobre la línea base `8594ed5`. Los cinco marcados como corregidos se arreglaron en B0; el resto queda para B1.

| # | Fallo | Clase | Causa / estado |
|---:|---|---|---|
| 1 | `motor/test_accion_p.py::test_la_base_de_hoy_ya_usa_p` | Pin de base | 2702 postas vs 2522 declaradas; la base ya normalizo ciegas a `p`. B1. |
| 2 | `motor/test_auditar_origen.py::test_el_volcado_json_no_toca_la_base` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 3 | `motor/test_auditar_origen.py::test_el_sha_del_disco_es_el_declarado` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 4 | `motor/test_auditar_origen.py::test_las_cifras_de_posiciones_estan_fijadas` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 5 | `motor/test_auditar_origen.py::test_un_jugador_sin_pos_es_uno_que_no_jugo` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 6 | `motor/test_auditar_origen.py::test_no_hay_mesa_corta_ni_ante_ni_straddle` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 7 | `motor/test_auditar_origen.py::test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 8 | `motor/test_auditar_origen.py::test_las_calls_que_no_llegan_a_la_viva` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 9 | `motor/test_auditar_origen.py::test_el_patron_del_bb_es_exacto_no_aproximado` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 10 | `motor/test_auditar_origen.py::test_el_bote_exacto_cuadra_en_373_de_1253` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 11 | `motor/test_auditar_origen.py::test_el_rake_no_explica_el_bote` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 12 | `motor/test_auditar_origen.py::test_aportar_mas_que_el_stack_no_depende_del_rake` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 13 | `motor/test_auditar_origen.py::test_el_json_y_el_informe_cuentan_lo_mismo` | Pin de base | 1344 lineas vs 1253 y SHA 3f0e... vs c317...; cambian conteos de posiciones, ciegas y botes. B1. |
| 14 | `motor/test_canal_manual.py::test_el_hash_de_la_base_es_el_declarado` | Manifiesto no redeclarado | SHA, lineas y commit del manifiesto; el script de reinterpretacion no reconoce la base actual. B1. |
| 15 | `motor/test_canal_manual.py::test_el_numero_de_lineas_es_el_declarado` | Manifiesto no redeclarado | SHA, lineas y commit del manifiesto; el script de reinterpretacion no reconoce la base actual. B1. |
| 16 | `motor/test_canal_manual.py::test_el_ultimo_commit_que_toco_la_base_tiene_el_hash_declarado` | Manifiesto no redeclarado | SHA, lineas y commit del manifiesto; el script de reinterpretacion no reconoce la base actual. B1. |
| 17 | `motor/test_canal_manual.py::test_aplicar_reinterpretacion_no_puede_sobrescribir_un_ajeno` | Manifiesto no redeclarado | SHA, lineas y commit del manifiesto; el script de reinterpretacion no reconoce la base actual. B1. |
| 18 | `motor/test_cm004.py::test_el_invariante_de_cm004_puede_dispararse` | Pin de base | 1344 ciegas reconocidas vs 1253 declaradas. B1. |
| 19 | `motor/test_decision_log.py::test_recommendation_step_writes_sidecar_and_deduplicates_repeated_frame` | Aislamiento de tests | `recorder_live` duplicado: los playback mutaban `PLAYER_NAMES` de `recorder.recorder_live` y el test usaba esa copia. **Corregido en B0.** |
| 20 | `motor/test_diagnostico_grabador.py::test_la_base_son_dos_grabadores` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 21 | `motor/test_diagnostico_grabador.py::test_la_apertura_cambia_tras_la_normalizacion` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 22 | `motor/test_diagnostico_grabador.py::test_las_42_calls_por_debajo_de_la_viva` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 23 | `motor/test_diagnostico_grabador.py::test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 24 | `motor/test_diagnostico_grabador.py::test_la_clasificacion_sobre_la_base` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 25 | `motor/test_diagnostico_grabador.py::test_el_desglose_por_accion_por_resultado_es_coherente` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 26 | `motor/test_diagnostico_grabador.py::test_el_reparto_por_accion_suma_el_total_de_la_base` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 27 | `motor/test_diagnostico_grabador.py::test_los_ids_se_resuelven_con_el_boton` | Pin de base | 1344 vs 1253; recuentos de acciones, resultados y reparto por accion. B1. |
| 28 | `motor/test_lista_saneamiento.py::test_por_defecto_cubre_toda_la_base` | Pin de base | 1344 vs 1253. B1. |
| 29 | `motor/test_lista_saneamiento.py::test_el_rango_por_defecto_sigue_siendo_toda_la_base` | Pin de base | 1344 vs 1253. B1. |
| 30 | `motor/test_quien_escribe.py::test_el_inventario_coincide_con_el_instrumento` | Contrato de integridad real | Inventario: 11 escritores no declarados; manifiesto: c317/1253 vs disco 3f0e/1344. B1. |
| 31 | `motor/test_quien_escribe.py::test_el_manifiesto_y_el_disco_coinciden` | Contrato de integridad real | Inventario: 11 escritores no declarados; manifiesto: c317/1253 vs disco 3f0e/1344. B1. |
| 32 | `motor/test_rango_fiable.py::test_las_cifras_publicadas_coinciden_con_la_ventana_vigente` | Metrica publicada obsoleta | 512/211/41,2 %/235 publicados vs 506/210/41,5 %/234 medidos; ventana de 877. B1. |
| 33 | `tools/test_auditoria_frentes.py::test_los_tests_de_motor_que_dependen_del_matrix_no_se_han_tocado` | Declaracion real | `motor/test_asistente_live.py` modificado y no declarado. **Corregido en B0.** |
| 34 | `tools/test_barrido_documentos.py::test_ningun_documento_afirma_una_frase_retirada` | Documentacion obsoleta | `pruebas/recorder/sesiones/sesion_validacion_1_20261104/informe_sesion_1.md:394` afirma una frase retirada. B1. |
| 35 | `tools/test_bloqueo_orden_filtros.py::test_los_76_cortes_preflop_solo_dos_tienen_etiqueta` | Dato derivado obsoleto | Poblacion B: 74 vs 76 cortes; 72 vs 74 sin board. B1. |
| 36 | `tools/test_bloqueo_orden_filtros.py::test_el_motivo_de_no_tener_etiqueta_es_que_la_mano_no_tiene_board` | Dato derivado obsoleto | Poblacion B: 74 vs 76 cortes; 72 vs 74 sin board. B1. |
| 37 | `tools/test_contrato_etiqueta.py::test_el_board_se_mira_en_las_dos_representaciones` | Dato derivado obsoleto | Poblacion B: 74 vs 76. B1. |
| 38 | `tools/test_decision_y_guardias.py::test_los_conteos_de_la_tabla_salen_de_las_filas` | Dato derivado obsoleto | Poblacion B jugada: 326 vs 328. B1. |
| 39 | `tools/test_ejecutar_pytest.py::test_no_ha_desaparecido_ningun_test` | Inventario/higiene real | 889/4/616 tests vs 918/47/635; declaracion de linea 1365 vs 1908; 48 asignaciones vs 113. **Corregido en B0.** |
| 40 | `tools/test_ejecutar_pytest.py::test_el_docstring_descuadrado_declarado_esta_donde_dice` | Inventario/higiene real | 889/4/616 tests vs 918/47/635; declaracion de linea 1365 vs 1908; 48 asignaciones vs 113. **Corregido en B0.** |
| 41 | `tools/test_ejecutar_pytest.py::test_las_asignaciones_que_sobrescriben_estan_revisadas` | Inventario/higiene real | 889/4/616 tests vs 918/47/635; declaracion de linea 1365 vs 1908; 48 asignaciones vs 113. **Corregido en B0.** |
| 42 | `tools/test_etiqueta_se_lee.py::test_las_cifras_de_la_herramienta_son_las_de_la_muestra` | Dato derivado obsoleto | Poblacion B: 210 vs 212; 864 vs 866; AUC 13 vs 14. B1. |
| 43 | `tools/test_etiqueta_se_lee.py::test_la_tabla_y_las_filas_no_pueden_ser_cosas_distintas` | Dato derivado obsoleto | Poblacion B: 210 vs 212; 864 vs 866; AUC 13 vs 14. B1. |
| 44 | `tools/test_etiqueta_se_lee.py::test_el_auc_publicado_se_reproduce` | Dato derivado obsoleto | Poblacion B: 210 vs 212; 864 vs 866; AUC 13 vs 14. B1. |
| 45 | `tools/test_fixture_duro.py::test_el_fixture_duro_no_toca_los_antes_ni_los_straddles` | Fixture a redisenar | 0 conversiones vs 915; la base ya normalizo las ciegas a `p`. B1. |
| 46 | `tools/test_inc004_cerrado.py::test_el_fichero_esta_commiteado_y_su_manifiesto_es_el_declarado` | Manifiesto no redeclarado | SHA de la base 3f0e... vs c317.... B1. |
| 47 | `tools/test_integrar_copia.py::test_el_flujo_completo_pasa_contra_el_fixture_suave` | Fixture/controles obsoletos | 1344 vs 1253; categorias +32/+52/+141/...; el control semantico bloquea. B1. |
| 48 | `tools/test_integrar_copia.py::test_el_flujo_completo_pasa_contra_el_fixture_duro` | Fixture/controles obsoletos | 1344 vs 1253; categorias +32/+52/+141/...; el control semantico bloquea. B1. |
| 49 | `tools/test_integrar_copia.py::test_los_dos_fixtures_tienen_umbrales_distintos` | Fixture/controles obsoletos | 1344 vs 1253; categorias +32/+52/+141/...; el control semantico bloquea. B1. |
| 50 | `tools/test_integrar_copia.py::test_una_diferencia_semantica_no_bloquea_la_integridad` | Fixture/controles obsoletos | 1344 vs 1253; categorias +32/+52/+141/...; el control semantico bloquea. B1. |
| 51 | `tools/test_integrar_copia.py::test_camino_completo_los_dos_controles_declarados` | Fixture/controles obsoletos | 1344 vs 1253; categorias +32/+52/+141/...; el control semantico bloquea. B1. |
| 52 | `tools/test_que_representa.py::test_a_y_b_no_son_un_recorte` | Dato derivado obsoleto | Cortes 631/233 vs 633/233; rivales 137 vs 139. B1. |
| 53 | `tools/test_que_representa.py::test_la_prediccion_no_es_un_numero_por_mano` | Dato derivado obsoleto | Cortes 631/233 vs 633/233; rivales 137 vs 139. B1. |
| 54 | `tools/test_reduccion_auc.py::test_la_mediana_reproduce_el_auc_publicado` | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333. B1. |
| 55 | `tools/test_reduccion_auc.py::test_sin_el_filtro_se_reproduce_el_numero_malo` | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333. B1. |
| 56 | `tools/test_reduccion_auc.py::test_cuantas_observaciones_tienen_mas_de_un_rival` | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333. B1. |
| 57 | `tools/test_reduccion_auc.py::test_el_recorrido_entre_reducciones_es_menor_que_el_ic` | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333. B1. |
| 58 | `tools/test_reduccion_auc.py::test_las_seis_reducciones_son_una_de_ellas_o_otra` | Dato derivado obsoleto | AUC 0,8271 vs 0,8308; 10 observaciones; recorrido 0,0000 vs 0,0333. B1. |
