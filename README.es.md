# ArtCraft MCP Bridge

[![checks](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml/badge.svg)](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml)

[English](README.md) · [Italiano](README.it.md) · **Español** · [中文](README.zh.md)

Un puente entre las **Crafting Apps** (CADCraft, DeckCraft, DesignCraft, EffectCraft, FigCraft,
FilmCraft, GridCraft, LightCraft, PdfCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft) y los clientes
MCP: en lugar de recurrir a la CLI sin interfaz, la aplicación viva se guía a través de su
**canal de control**, de modo que las herramientas actúan sobre la ventana abierta.

## El problema

Cada Crafting App expone un servidor MCP headless (`<app>-cli.exe mcp`). Sin embargo, muchas
herramientas solo tienen sentido sobre la aplicación viva: dibujar, capturar el lienzo, mover un
cursor. En headless esas herramientas desaparecen o fallan, y el cliente no puede saber por qué.

## Cómo funciona

1. la aplicación se inicia con `--control <puerto>` (y, para PhotoCraft, `--control-token-file`);
2. el **shim** registrado en los conectores realiza un **handshake** en ese puerto;
3. si el interlocutor habla el protocolo **y es la aplicación correcta** (catálogo de comandos,
   umbral 0,9) pasa a **bridged** y reenvía las peticiones a la aplicación; si no, pasa a
   **headless** y lo declara en stderr. Con `--require-bridge` sale con 3 en lugar de recurrir.

PdfCraft es la excepción al punto 3: usa un *archivo* de control y su servidor MCP no tiene un flag
de bridge (`mcp --connect` → `unknown option`). Su ventana se guía igualmente, por **traducción**:
[craft-bridge-ui.py](tools/craft-bridge-ui.py) expone los 15 métodos que la aplicación declara como
otras tantas herramientas MCP, invocando `pdfcraft-cli ui --control FILE <método>` una vez por
llamada.

Sin repliegue silencioso: el modo elegido siempre se declara, y quien responde en el puerto queda
identificado (la aplicación **y** la build en ejecución). Lo mismo vale para la tabla: el flag de
enganche que cada aplicación requiere no es algo que recordemos — se lo preguntamos al help de la
CLI, y cuando no lo confirma el diagnóstico lo dice.

## Estructura

```
tools/     las herramientas (Python): shim, traductor de ventana, ident, doctor, config, launch, verify, sweep, tests, exploratorias
install/   install-craft-mcp.ps1 (registro multi-cliente del MCP generativo)
reports/   artefactos generados: informes de la suite y del sweep, inventario de herramientas, imágenes
docs/      documentación en formato OKF v0.2 (nodos y relaciones) - ver docs/index.md
```

## Inicio rápido

```bash
# 1. instala las copias del shim y reescribe las entradas de los conectores (con copia de seguridad)
python tools/craft-bridge-config.py --apply
# 2. en Freebuff: Connectors -> Refresh

# 3. inicia las aplicaciones con el canal de control (las ventanas permanecen abiertas)
python tools/craft-bridge-launch.py

# 4. verifica: un veredicto sobre el conjunto, luego cada entrada con su comando real
python tools/craft-bridge-doctor.py
python tools/craft-bridge-verify.py
```

Vuelta a headless: `python tools/craft-bridge-config.py --restore`.

## Los otros clientes MCP

Freebuff no es el único cliente. Un comando pone el mismo puente en los demás que tengas — Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, Cline, LM Studio, Zed, Codex (ChatGPT desktop) y DeepSeek Harness (`dsh`) — cada uno en su propio archivo y formato, desde una sola fuente y sin tocar lo que no es nuestro:

```bash
python tools/craft-bridge-connect.py --list     # quién está, y dónde lee
python tools/craft-bridge-connect.py            # dry-run: qué cambiaría
python tools/craft-bridge-connect.py --apply    # escribe, con copia de seguridad
```

La receta, cliente por cliente (incluidos los dos que no son JSON), está en
[docs/operations/connect-a-client.md](docs/operations/connect-a-client.md).

Para ver todo el estado de un vistazo — veredicto, entradas, clientes, baselines, feed, logs — en un JSON y una página que lo lee:

```bash
python tools/craft-bridge-report.py             # reports/bridge-status.json + .html
python tools/craft-bridge-report.py --serve     # + servidor local, abre la página (Ctrl+C para parar)
```

## Estado verificado (13 de octubre de 2026)

| Prueba | Resultado |
|---|---|
| Aplicaciones pilotables con una llamada correcta sobre la ventana | 13 de 13 (12 en bridged por el shim — `figcraft` incluido — PdfCraft por traducción) |
| Entradas de configuración ejecutadas con el comando real | 14/14 |
| Suite de fallos (28 casos, fallos inyectados) | 27 ejecutados + 1 omitido con la ventana de PdfCraft cerrada (el único caso en vivo dice por qué), 23+1 en `--static`, dos pasadas seguidas idénticas |
| Clientes en los que está registrado el puente | 13 conocidos, 4 presentes en esta máquina; tras `--apply` todos en **13/13** (antes: `agents` 13, `claude-desktop` y `antigravity` **12** como entradas headless, `windsurf` **0**) |
| Instalado frente a la release publicada por el launcher | 12 de 13 comparadas (feed del 13 de octubre): el feed aún no nombra `figcraft`, así que para ella no hay término de comparación y el diagnóstico lo dice |
| Bytes de la CLI instalada frente a los publicados | 1 de 12 probada: SoundCraft idéntico (`sha256 915ee3abb121…`); para las demás el archivo no está en disco |
| Rutas de aplicación y CLI | 12 de 12 desde el registro `App Paths` (la tabla confirma, no decide) |
| Métodos de la ventana PdfCraft | 15 de 15 como los declara la aplicación; 192 comandos, 107 widgets, captura de la ventana |
| Flags de enganche declarados por la tabla | 13 de 13 confirmados por el help de la CLI (11 enganches `--connect`/`--bridge` y 1 `--attach`, PdfCraft sin flag y con `--control`) |
| Inventario de herramientas de los servidores | 14/14 servidores, 636 herramientas (`pdfcraft`: los 15 métodos de la ventana; `figcraft`: 18) |
| Diagnóstico global | `tutto in ordine` |

## Documentación

La documentación está en [docs/index.md](docs/index.md): es un bundle **OKF v0.2**, un nodo por
concepto con relaciones explícitas entre los nodos (arquitectura, herramientas, operaciones,
defectos encontrados). El texto largo y completo, con todas las mediciones, está en
[docs/reference/craft-bridge.md](docs/reference/craft-bridge.md) (en inglés).

```bash
uvx okfgen validate docs --strict                      # conforme: 35 conceptos, 0 errores
uvx okfgen visualize docs -o reports/okf-graph.html    # grafo interactivo del bundle
```

El grafo generado está en [reports/okf-graph.html](reports/okf-graph.html): 35 nodos, 182
relaciones.

## Qué está instalado frente a qué está publicado

La versión de un ejecutable dice qué afirma ser, no si es la release que distribuye el proveedor.
El launcher de ArtCraft guarda en disco la lista que usa para actualizar las aplicaciones
(repositorio, última release, paquetes con su `sha256`): [craft-bridge-feed.py](tools/craft-bridge-feed.py)
pone esa lista junto a la build instalada y dice dónde no coinciden. Y con `--bytes` plantea la
única pregunta que la versión no puede responder: compara el ejecutable instalado con el que está
**dentro** del paquete publicado, leído en memoria sin extraer nada — `--download <slug>` descarga
el paquete (huella del feed verificada antes de usarlo, una aplicación por vez, solo desde los
hosts del feed). Dentro de `doctor` una versión atrasada es una `nota`, no un `FIX`: el puente
funciona también con la release anterior. Detalles en
[docs/tools/craft-bridge-feed.md](docs/tools/craft-bridge-feed.md).

## Controles automáticos

En cada push a `main` (y en cada pull request) se ejecuta
[checks.yml](.github/workflows/checks.yml): sintaxis de las herramientas, interfaces, coherencia de
la tabla de aplicaciones con los puertos documentados, determinismo del instalador, conformidad del
bundle OKF y la suite con `--ci` — que en un runner sin aplicaciones omite los casos de entorno
**explicando por qué**, mientras que un fallo real sigue siendo un FAIL. La suite completa se
ejecuta en un runner self-hosted donde el puente está instalado (variable de repo
`CRAFTBRIDGE_SELF_HOSTED=1`): está activa en los push a `main` y en las ejecuciones manuales,
nunca en las pull requests — el repositorio es público, y el código de un desconocido no se
ejecuta en la máquina que tiene las aplicaciones. Un caso que empeora respecto a la baseline
guardada sale con 3, así una regresión frena el push en lugar de esperar en un informe.
Detalles en [docs/operations/ci.md](docs/operations/ci.md).

## Límites declarados

- **Solo Windows**: la suite y el launcher usan `taskkill` y `DETACHED_PROCESS`.
- La captura de la ventana requiere que la ventana sea visible; una aplicación en segundo plano
  puede devolver un timeout que parece un fallo del puente y no lo es.
- La versión del ejecutable no es su contenido: dos builds con la misma versión y sin revisión en
  la línea de arranque son indistinguibles (ningún hash del binario).
- El uso real por parte de un agente dentro de Freebuff, a través de la interfaz, no se ha
  observado: las pruebas hablan con los binarios mediante el protocolo.

## Licencia

**MIT** — el texto completo está en [LICENSE](LICENSE): uso, modificación y redistribución libres,
incluso dentro de productos cerrados, siempre que el aviso de copyright y la licencia acompañen al
software. El software se ofrece tal cual, sin garantías.
