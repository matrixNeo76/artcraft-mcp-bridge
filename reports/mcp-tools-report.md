# Report dei tool MCP disponibili

**Generato:** 13/10/2026 23:01
**Configurazione:** `C:\Users\auresystem\.agents\mcp.json` (la stessa del pannello **Connectors** di Freebuff)
**Server configurati:** 14 · **connessi:** 14 · **tool totali esposti:** 636

## Riepilogo

| Server | Trasporto | Stato | Protocollo | Tool |
|---|---|---|---|---|
| `artcraft` | stdio | connesso | 2025-03-26 | 61 |
| `cadcraft` | stdio | connesso | 2025-03-26 | 11 |
| `deckcraft` | stdio | connesso | 2025-03-26 | 25 |
| `designcraft` | stdio | connesso | 2025-03-26 | 25 |
| `effectcraft` | stdio | connesso | 2025-03-26 | 27 |
| `figcraft` | stdio | connesso | 2025-03-26 | 18 |
| `filmcraft` | stdio | connesso | 2025-03-26 | 17 |
| `gridcraft` | stdio | connesso | 2025-03-26 | 21 |
| `lightcraft` | stdio | connesso | 2025-03-26 | 326 |
| `pdfcraft` | stdio | connesso | 2025-03-26 | 15 |
| `photocraft` | stdio | connesso | 2025-03-26 | 25 |
| `soundcraft` | stdio | connesso | 2025-03-26 | 17 |
| `vectorcraft` | stdio | connesso | 2025-03-26 | 32 |
| `wordcraft` | stdio | connesso | 2025-03-26 | 16 |

## Tool per server

### `artcraft` (61 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\artcraft-mcp\artcraft-mcp-proxy.py`

- `artcraft_generate_image`
- `artcraft_generate_video`
- `artcraft_generate_audio`
- `artcraft_generate_3d_object`
- `artcraft_generate_splat`
- `artcraft_edit_image`
- `artcraft_remove_background`
- `artcraft_inpaint_image`
- `artcraft_edit_image_angle`
- `artcraft_edit_video`
- `artcraft_estimate_cost`
- `artcraft_estimate_splat_cost`
- `artcraft_list_image_models`
- `artcraft_list_video_models`
- `artcraft_upload_image`
- `artcraft_upload_video`
- `artcraft_upload_audio`
- `artcraft_get_media_file`
- `artcraft_download_media_file`
- `artcraft_list_media_files`
- `artcraft_search_media`
- `artcraft_delete_media_file`
- `artcraft_rename_media_file`
- `artcraft_set_media_visibility`
- `artcraft_get_job_status`
- `artcraft_list_jobs`
- `artcraft_terminate_job`
- `artcraft_create_character`
- `artcraft_list_characters`
- `artcraft_get_character`
- `artcraft_delete_character`
- `artcraft_create_prompt`
- `artcraft_get_prompt`
- `artcraft_tts_generate`
- `artcraft_tts_search_models`
- `artcraft_voice_convert`
- `artcraft_list_voice_conversion_models`
- `artcraft_create_voice`
- `artcraft_list_voices`
- `artcraft_create_voice_dataset`
- `artcraft_upload_voice_sample`
- `artcraft_list_weights`
- `artcraft_search_weights`
- `artcraft_get_weight`
- `artcraft_delete_weight`
- `artcraft_studio_gen2`
- `artcraft_get_session_info`
- `artcraft_get_credits`
- `artcraft_get_subscription`
- `artcraft_create_checkout_session`
- `artcraft_create_subscription_checkout`
- `artcraft_get_billing_portal_url`
- `artcraft_create_bookmark`
- `artcraft_list_bookmarks`
- `artcraft_rate_media`
- `artcraft_create_comment`
- `artcraft_list_comments`
- `artcraft_list_tags`
- `artcraft_set_tags`
- `artcraft_create_referral_code`
- `artcraft_list_referral_codes`

### `cadcraft` (11 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug cadcraft --port 7971`

- `command_line`
- `script`
- `execute`
- `list_commands`
- `inspect_drawing`
- `query_entities`
- `render`
- `new_drawing`
- `open`
- `save`
- `cancel`

### `deckcraft` (25 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug deckcraft --port 7972`

- `list_commands`
- `run_command`
- `batch`
- `new_presentation`
- `open_presentation`
- `save_presentation`
- `export`
- `inspect_document`
- `inspect_slide`
- `render_slide`
- `add_slide`
- `go_to_slide`
- `add_shape`
- `add_text_box`
- `set_text`
- `insert_picture`
- `insert_table`
- `insert_chart`
- `select`
- `pointer`
- `select_tool`
- `key`
- `type_text`
- `screenshot`
- `call_app`

### `designcraft` (25 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug designcraft --port 7973`

- `list_commands`
- `execute`
- `batch`
- `inspect_document`
- `get_story`
- `set_story_text`
- `new_document`
- `open_document`
- `save_document`
- `place_image`
- `render_page`
- `export_png`
- `screenshot`
- `select_tool`
- `pointer`
- `key`
- `type_text`
- `click`
- `drag`
- `menu_list`
- `ui_inspect`
- `ui_set`
- `dialog_set`
- `dialog_confirm`
- `dialog_cancel`

### `effectcraft` (27 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug effectcraft --port 9877`

- `list_commands`
- `describe_command`
- `execute_command`
- `run_script`
- `get_project`
- `get_comp`
- `get_layer`
- `get_property`
- `set_property`
- `add_keyframe`
- `add_effect`
- `list_effects`
- `list_fonts`
- `get_state`
- `render_frame`
- `open_project`
- `save_project`
- `undo`
- `redo`
- `history`
- `script_ui`
- `batch`
- `command_list`
- `command_run`
- `render_preview`
- `command_batch`
- `doc_inspect`

### `figcraft` (18 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug figcraft --port 7981`

- `list_commands`
- `run_command`
- `batch`
- `create_node`
- `set_properties`
- `inspect_document`
- `get_node`
- `select`
- `export`
- `screenshot`
- `open_file`
- `save_file`
- `undo`
- `redo`
- `pointer`
- `key`
- `type_text`
- `inspect_ui`

### `filmcraft` (17 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug filmcraft --port 7974`

- `command_batch`
- `command_list`
- `command_run`
- `doc_inspect`
- `media_import`
- `project_inspect`
- `render_frame`
- `render_preview`
- `sequence_inspect`
- `ui_click`
- `ui_control`
- `ui_drag`
- `ui_elements`
- `ui_inspect`
- `ui_key`
- `ui_screenshot`
- `ui_type`

### `gridcraft` (21 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug gridcraft --port 7975`

- `execute_command`
- `list_commands`
- `inspect_workbook`
- `read_range`
- `write_range`
- `set_cell`
- `get_cell`
- `evaluate_formula`
- `select`
- `format_range`
- `insert_chart`
- `create_table`
- `sort_range`
- `filter`
- `open_workbook`
- `save_workbook`
- `new_workbook`
- `undo`
- `redo`
- `screenshot`
- `list_functions`

### `lightcraft` (326 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug lightcraft --port 7980`

- `command_list`
- `command_run`
- `command_batch`
- `doc_inspect`
- `render_preview`
- `list_commands`
- `run_command`
- `import`
- `query_photos`
- `select_photos`
- `list_controls`
- `get_develop`
- `set_develop`
- `apply_preset`
- `crop`
- `render_photo`
- `export`
- `cmd_edit_undo`
- `cmd_edit_redo`
- `cmd_library_source`
- `cmd_library_filter`
- `cmd_library_folders`
- `cmd_library_removeFolder`
- `cmd_folder_label`
- `cmd_library_clearFilter`
- `cmd_library_sort`
- `cmd_library_shuffle`
- `cmd_library_groups`
- `cmd_library_select`
- `cmd_library_selectAll`
- `cmd_library_devices`
- `cmd_photo_copyMetadata`
- `cmd_photo_pasteMetadata`
- `cmd_library_selectBy`
- `cmd_library_selectNone`
- `cmd_library_next`
- `cmd_library_previous`
- `cmd_photo_rate`
- `cmd_photo_decreaseRating`
- `cmd_photo_increaseRating`
- `cmd_photo_flag`
- `cmd_photo_pick`
- `cmd_photo_reject`
- `cmd_photo_unflag`
- `cmd_photo_label`
- `cmd_photo_rotateLeft`
- `cmd_photo_rotateRight`
- `cmd_photo_flipHorizontal`
- `cmd_photo_flipVertical`
- `cmd_photo_removeRegion`
- `cmd_photo_setRegion`
- `cmd_photo_delete`
- `cmd_photo_restore`
- `cmd_library_emptyRecentlyDeleted`
- `cmd_photo_deletePermanently`
- `cmd_photo_setMeta`
- `cmd_album_create`
- `cmd_album_createSmart`
- `cmd_album_ruleFields`
- `cmd_album_setRules`
- `cmd_album_rename`
- `cmd_album_delete`
- `cmd_album_move`
- `cmd_album_reorder`
- `cmd_album_sort`
- `cmd_album_addPhotos`
- `cmd_album_toggleTarget`
- `cmd_album_setTarget`
- `cmd_album_clearQuick`
- `cmd_library_autoImport`
- `cmd_library_autoImportScan`
- `cmd_album_removePhotos`
- `cmd_album_setCover`
- `cmd_library_inspectLightroom`
- `cmd_library_importLightroom`
- `cmd_library_importPreview`
- `cmd_library_import`
- `cmd_library_info`
- `cmd_library_compact`
- `cmd_library_clearPreviews`
- `cmd_develop_set`
- `cmd_develop_adjust`
- `cmd_develop_merge`
- `cmd_develop_reset`
- `cmd_develop_updateProcess`
- `cmd_develop_resetSection`
- `cmd_develop_resetControl`
- `cmd_develop_sectionEnabled`
- `cmd_develop_autoBwMix`
- `cmd_develop_auto`
- `cmd_develop_wb`
- `cmd_develop_wbPick`
- `cmd_develop_treatment`
- `cmd_develop_profile`
- `cmd_profile_favorite`
- `cmd_develop_curve`
- `cmd_crop_set`
- `cmd_crop_drag`
- `cmd_crop_straighten`
- `cmd_crop_autoStraighten`
- `cmd_crop_aspect`
- `cmd_crop_rotateAspect`
- `cmd_crop_reset`
- `cmd_develop_hdr`
- `cmd_geometry_upright`
- `cmd_geometry_guides`
- `cmd_develop_copy`
- `cmd_develop_pastePrevious`
- `cmd_develop_paste`
- `cmd_develop_sync`
- `cmd_develop_quickAdjust`
- `cmd_develop_matchExposure`
- `cmd_develop_autoSync`
- `cmd_preset_apply`
- `cmd_preset_create`
- `cmd_preset_delete`
- `cmd_preset_favorite`
- `cmd_preset_rename`
- `cmd_preset_move`
- `cmd_preset_update`
- `cmd_version_create`
- `cmd_version_restore`
- `cmd_version_delete`
- `cmd_version_rename`
- `cmd_version_update`
- `cmd_history_clear`
- `cmd_history_restore`
- `cmd_develop_beginInteraction`
- `cmd_develop_endInteraction`
- `cmd_develop_cancelInteraction`
- `cmd_pointColor_pick`
- `cmd_develop_targeted`
- `cmd_pointColor_delete`
- `cmd_curve_reset`
- `cmd_curve_presets`
- `cmd_curve_applyPreset`
- `cmd_curve_savePreset`
- `cmd_curve_deletePreset`
- `cmd_curve_importPresets`
- `cmd_curve_exportPresets`
- `cmd_mask_add`
- `cmd_mask_addComponent`
- `cmd_mask_brushStroke`
- `cmd_mask_update`
- `cmd_mask_sampleColor`
- `cmd_mask_objectPoint`
- `cmd_mask_refineDetail`
- `cmd_segment_prepare`
- `cmd_segment_model_status`
- `cmd_segment_model_download`
- `cmd_segment_model_cancel`
- `cmd_mask_refine`
- `cmd_mask_adjust`
- `cmd_mask_select`
- `cmd_mask_delete`
- `cmd_mask_deleteAll`
- `cmd_mask_rename`
- `cmd_mask_invert`
- `cmd_mask_visible`
- `cmd_mask_duplicate`
- `cmd_mask_component`
- `cmd_mask_move`
- `cmd_spot_findDust`
- `cmd_spot_findBlemishes`
- `cmd_spot_add`
- `cmd_spot_select`
- `cmd_spot_update`
- `cmd_spot_refreshSource`
- `cmd_spot_delete`
- `cmd_redeye_add`
- `cmd_redeye_catchlight`
- `cmd_redeye_delete`
- `cmd_photo_virtualCopy`
- `cmd_stack_group`
- `cmd_stack_ungroup`
- `cmd_stack_remove`
- `cmd_stack_setTop`
- `cmd_stack_moveUp`
- `cmd_stack_moveDown`
- `cmd_stack_split`
- `cmd_stack_toggle`
- `cmd_stack_expandAll`
- `cmd_stack_collapseAll`
- `cmd_stack_auto`
- `cmd_keyword_sets`
- `cmd_keyword_useSet`
- `cmd_keyword_saveSet`
- `cmd_keyword_deleteSet`
- `cmd_keyword_toggleFromSet`
- `cmd_keyword_list`
- `cmd_keyword_suggest`
- `cmd_keyword_info`
- `cmd_keyword_create`
- `cmd_keyword_edit`
- `cmd_keyword_move`
- `cmd_keyword_purgeUnused`
- `cmd_keyword_setDefaultParent`
- `cmd_keyword_export`
- `cmd_keyword_import`
- `cmd_keyword_rename`
- `cmd_keyword_delete`
- `cmd_keyword_merge`
- `cmd_photo_renameTokens`
- `cmd_photo_renamePreview`
- `cmd_photo_rename`
- `cmd_photo_setCaptureTime`
- `cmd_photo_autoTagTracklog`
- `cmd_label_names`
- `cmd_label_setNames`
- `cmd_label_sets`
- `cmd_label_applySet`
- `cmd_label_saveSet`
- `cmd_label_deleteSet`
- `cmd_library_smartPreviews`
- `cmd_library_smartPreviewsLocation`
- `cmd_photo_smartPreview`
- `cmd_library_buildPreviews`
- `cmd_library_previewProgress`
- `cmd_library_cancelPreviews`
- `cmd_profile_import`
- `cmd_profile_deleteImported`
- `cmd_library_findSimilar`
- `cmd_photo_analyze`
- `cmd_photo_convertToDng`
- `cmd_photo_duplicate`
- `cmd_photo_reload`
- `cmd_photo_editExternal`
- `cmd_merge_hdr`
- `cmd_merge_panorama`
- `cmd_merge_hdrPanorama`
- `cmd_catalog_query`
- `cmd_catalog_stats`
- `cmd_library_state`
- `cmd_photo_allMetadata`
- `cmd_albums_list`
- `cmd_photo_inspect`
- `cmd_develop_get`
- `cmd_develop_controls`
- `cmd_presets_list`
- `cmd_profiles_list`
- `cmd_profiles_menu`
- `cmd_history_list`
- `cmd_app_gpu`
- `cmd_library_memory`
- `cmd_app_memoryBudget`
- `cmd_journal_list`
- `cmd_photo_saveMetadataToFile`
- `cmd_photo_readMetadataFromFile`
- `cmd_library_xmpPreferences`
- `cmd_library_toggleAutoWriteXmp`
- `cmd_preset_import`
- `cmd_preset_export`
- `cmd_library_preferences`
- `cmd_export_contactSheet`
- `cmd_export_presets`
- `cmd_export_savePreset`
- `cmd_export_deletePreset`
- `cmd_export_checkTarget`
- `cmd_export_addToPhotos`
- `cmd_export_photosImports`
- `cmd_beforeAfter_setBefore`
- `cmd_beforeAfter_copyAfterToBefore`
- `cmd_beforeAfter_copyBeforeToAfter`
- `cmd_beforeAfter_swap`
- `cmd_beforeAfter_resetBefore`
- `cmd_folder_rename`
- `cmd_folder_move`
- `cmd_folder_create`
- `cmd_photo_moveToFolder`
- `cmd_library_browse`
- `cmd_library_forgetLocal`
- `cmd_photo_addToLibrary`
- `cmd_library_missing`
- `cmd_photo_relink`
- `cmd_library_findMissing`
- `cmd_folder_scanChanges`
- `cmd_folder_synchronize`
- `cmd_metadata_presets`
- `cmd_metadata_savePreset`
- `cmd_metadata_deletePreset`
- `cmd_metadata_applyPreset`
- `cmd_metadata_reverseGeocode`
- `cmd_metadata_placeNamesStatus`
- `cmd_metadata_downloadPlaceNames`
- `cmd_filter_presets`
- `cmd_filter_savePreset`
- `cmd_filter_applyPreset`
- `cmd_filter_deletePreset`
- `cmd_denoise_models_list`
- `cmd_denoise_models_inspect`
- `cmd_denoise_models_install`
- `cmd_denoise_models_download`
- `cmd_denoise_models_downloads`
- `cmd_denoise_models_downloadCancel`
- `cmd_denoise_models_test`
- `cmd_denoise_models_remove`
- `cmd_denoise_models_select`
- `cmd_denoise_settings`
- `cmd_denoise_toggle`
- `cmd_denoise_queue`
- `cmd_denoise_cancel`
- `cmd_denoise_status`
- `cmd_denoise_pump`
- `cmd_denoise_clear`
- `cmd_faces_models_list`
- `cmd_faces_models_inspect`
- `cmd_faces_models_install`
- `cmd_faces_models_download`
- `cmd_faces_models_downloads`
- `cmd_faces_models_downloadCancel`
- `cmd_faces_models_test`
- `cmd_faces_models_remove`
- `cmd_faces_models_select`
- `cmd_faces_enable`
- `cmd_faces_detect`
- `cmd_faces_index`
- `cmd_faces_suggest`
- `cmd_faces_pump`
- `cmd_faces_evaluate`
- `cmd_faces_unnamed`
- `cmd_faces_nameFaces`
- `cmd_faces_person`
- `cmd_faces_setName`
- `cmd_activity_list`
- `cmd_activity_cancel`
- `cmd_app_export`

### `pdfcraft` (15 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-ui.py --slug pdfcraft --control C:\Users\auresystem\.craft-bridge\pdfcraft-control.json`

- `ui_state`
- `ui_inspect`
- `ui_commands`
- `ui_screenshot`
- `ui_click`
- `ui_focus`
- `ui_resize`
- `ui_move`
- `ui_drag`
- `ui_type`
- `ui_key`
- `ui_command`
- `ui_set`
- `ui_open`
- `ui_quit`

### `photocraft` (25 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug photocraft --port 7976 --token-file C:\Users\auresystem\.craft-bridge\photocraft.token`

- `command_batch`
- `command_list`
- `command_run`
- `control_call`
- `doc_close`
- `doc_export`
- `doc_export_data_sets`
- `doc_export_layers`
- `doc_import_data_sets`
- `doc_inspect`
- `doc_new`
- `doc_open`
- `doc_place`
- `doc_render_preview`
- `doc_save`
- `doc_select`
- `jobs_cancel`
- `jobs_list`
- `render_preview`
- `session_list`
- `ui_inspect`
- `ui_menu_invoke`
- `ui_pointer`
- `ui_screenshot`
- `ui_set`

### `soundcraft` (17 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug soundcraft --port 7977`

- `list_commands`
- `execute`
- `batch`
- `inspect_session`
- `new_session`
- `open_session`
- `save_session`
- `import_audio`
- `bounce_mix`
- `parity`
- `screenshot`
- `ui_inspect`
- `ui_set`
- `menu_invoke`
- `click`
- `drag`
- `key`

### `vectorcraft` (32 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug vectorcraft --port 7979`

- `command_list`
- `command_run`
- `command_batch`
- `doc_inspect`
- `render_preview`
- `ui_inspect`
- `ui_screenshot`
- `list_commands`
- `run_command`
- `inspect_document`
- `inspect_ui`
- `select_tool`
- `pointer_gesture`
- `draw_path`
- `draw_shape`
- `set_paint`
- `press_key`
- `type_text`
- `invoke_menu`
- `open_panel`
- `screenshot`
- `open_file`
- `save_file`
- `export`
- `add_text`
- `apply_effect`
- `pathfinder`
- `transform`
- `create_graph`
- `text_wrap`
- `undo`
- `redo`

### `wordcraft` (16 tool)

`C:\Users\auresystem\AppData\Local\Programs\Python\Python312\python.exe C:\Users\auresystem\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py --slug wordcraft --port 7978`

- `list_commands`
- `execute`
- `batch`
- `new_document`
- `open_document`
- `save_document`
- `type_text`
- `select_text`
- `get_text`
- `inspect_document`
- `render_page`
- `parity`
- `screenshot`
- `click`
- `key`
- `ui_inspect`
