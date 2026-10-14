#!/usr/bin/env python3
"""Fotografia dello stato del ponte: un JSON macchina e una pagina HTML che lo legge.

I report del progetto (suite, sweep, feed, doctor) sono tanti e ognuno con la sua
forma: giusto, perche' ognuno risponde a una domanda diversa. Ma per *guardare* il
ponte oggi serve un posto solo. Questo strumento raccoglie le fonti **senza
duplicarle** - il verdetto di `craft-bridge-doctor.py`, le entry della config che i
client leggono, i client MCP rilevati su questa macchina, l'ultima baseline della
suite, il confronto col feed e la coda dei log di avvio - e scrive:

    reports/bridge-status.json     il dato, per una macchina (schema craft-bridge-status/1)
    reports/bridge-status.html     la pagina che lo legge e lo mostra

La pagina **legge** il JSON che le sta accanto (`fetch('bridge-status.json')`) e, se
il browser non glielo lascia fare (aperta come `file://`), usa la copia che ha dentro:
cosi' si vede sempre, e servita da un'origine la pagina resta aggiornata al file.

    python craft-bridge-report.py                  # scrive i due file in reports/
    python craft-bridge-report.py --json           # solo il JSON a video, non scrive
    python craft-bridge-report.py --no-doctor      # salta la diagnosi (~2.4 s), il resto resta
    python craft-bridge-report.py --no-live        # la diagnosi senza le porte delle app aperte
    python craft-bridge-report.py --out-html X.html --out-json X.json

Esito:
    0  report scritto (anche se il ponte ha cose da sistemare: quello lo dice il verdetto)
    2  errore d'uso
    3  non e' stato possibile scrivere i file
"""
from __future__ import annotations

import argparse
import functools
import http.server
import importlib.util
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORTS = ROOT / "reports"
SCHEMA = "craft-bridge-status/1"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise SystemExit(f"strumento non caricabile: {HERE / filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG = _load("craft_bridge_config", "craft-bridge-config.py")
try:
    CONNECT = _load("craft_bridge_connect", "craft-bridge-connect.py")
except SystemExit:
    CONNECT = None


def run_json(tool: str, *extra: str) -> tuple[int, dict | None, str]:
    """Esegue uno strumento del progetto con --json e ne legge l'uscita."""
    proc = subprocess.run([sys.executable, str(HERE / tool), "--json", *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return proc.returncode, json.loads(proc.stdout), ""
    except json.JSONDecodeError:
        return proc.returncode, None, (proc.stderr or proc.stdout or "").strip()[:400]


def verdict(live: bool) -> dict:
    extra = () if live else ("--no-live",)
    code, data, why = run_json("craft-bridge-doctor.py", *extra)
    if data is None:
        return {"ok": None, "problems": None, "checks": [], "actions": [],
                "exit": code, "error": why or "diagnosi illeggibile"}
    data["exit"] = code
    return data


def servers() -> dict:
    path = CONFIG.DEFAULT_CONFIG
    cfg = CONFIG.load_config(path)
    out = []
    for slug, entry in sorted(cfg.get("mcpServers", {}).items()):
        args = entry.get("args") or []
        mode = "traduttore" if any("craft-bridge-ui.py" in str(a) for a in args) else "shim"
        out.append({"slug": slug, "mode": mode, "command": entry.get("command"),
                    "args": args})
    return {"path": str(path), "count": len(out), "servers": out}


def clients(entries_config: dict | None) -> list[dict]:
    """La tabella dei client MCP, con quante entry del ponte vedrebbero."""
    if CONNECT is None:
        return []
    plan = CONNECT.plan(CONFIG.DEFAULT_INSTALL_DIR,
                        str(Path.home() / ".craft-bridge" / "photocraft.token"),
                        str(Path.home() / ".craft-bridge" / "pdfcraft-control.json"))
    expected = set(plan)
    rows = []
    for c in CONNECT.clients():
        path = c["path"]
        row = {"id": c["id"], "title": c["title"], "kind": c["kind"],
               "path": str(path) if path else None,
               "present": bool(path and path.parent.is_dir())}
        if row["present"]:
            have = CONNECT.bridge_slugs(c, path, expected)
            row["bridge_entries"] = None if have is None else len(have)
            row["missing"] = None if have is None else len(expected - have)
        rows.append(row)
    return rows


def tests() -> dict:
    out = {}
    for name in ("craft-bridge-tests.json", "craft-bridge-tests.static.json"):
        path = REPORTS / name
        if not path.is_file():
            out[name] = None
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out[name] = None
            continue
        out[name] = {k: data.get(k) for k in
                     ("when", "passed", "failed", "skipped", "regressed", "gate", "seconds")}
    return out


def feed() -> dict | None:
    code, data, _ = run_json("craft-bridge-feed.py")
    if data is None:
        return None
    rows = data.get("checks") or []
    return {"exit": code, "apps": rows, "count": len(rows),
            "off_feed": sum(1 for r in rows if r.get("state") != "ok"),
            "generated": (data.get("feed") or {}).get("fetched_at")
                         or (data.get("feed") or {}).get("dir")}


def logs(tail: int = 30) -> list[dict]:
    base = Path.home() / ".craft-bridge" / "launch-logs"
    if not base.is_dir():
        return []
    rows = []
    for path in sorted(base.glob("*.log")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rows.append({"name": path.name, "path": str(path),
                     "lines": lines[-tail:], "total": len(lines)})
    return rows


def collect(live: bool, with_clients: bool, with_feed: bool,
            with_verdict: bool = True) -> dict:
    return {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "host": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()}",
        "project": str(ROOT),
        "verdict": verdict(live) if with_verdict else {"ok": None, "problems": None,
                                                        "checks": [], "actions": [],
                                                        "skipped": "--no-doctor"},
        "config": servers(),
        "clients": clients(None) if with_clients else [],
        "tests": tests(),
        "feed": feed() if with_feed else None,
        "logs": logs(),
    }


# ---------------------------------------------------------------------------------
# La pagina: una sola, autonoma. Legge il JSON accanto; senza, usa la copia dentro.
# ---------------------------------------------------------------------------------

def html(status: dict) -> str:
    payload = json.dumps(status, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", payload)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="it">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Craft Bridge - stato</title>
<style>
:root{--bg:#0f1216;--fg:#e6e9ee;--mut:#9aa4b2;--card:#171c22;--line:#242b33;
      --ok:#33d17a;--warn:#f5c451;--bad:#ff6b6b;--acc:#6aa6ff}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
     background:var(--bg);color:var(--fg);padding:24px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px;color:var(--acc)}
.sub{color:var(--mut);font-size:12px;margin-bottom:18px}
.banner{padding:12px 16px;border-radius:10px;margin:14px 0;font-weight:600;border:1px solid}
.b-ok{background:#12291d;border-color:#1d5c39;color:var(--ok)}
.b-warn{background:#2a230f;border-color:#5c4a1d;color:var(--warn)}
.b-bad{background:#2a1414;border-color:#5c1d1d;color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600}
code,pre{font-family:ui-monospace,Consolas,monospace;font-size:12px}
pre{background:#0b0e12;border:1px solid var(--line);border-radius:8px;padding:10px;
    overflow:auto;max-height:260px}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;border:1px solid}
.p-ok{color:var(--ok);border-color:var(--ok)}.p-no{color:var(--mut);border-color:var(--mut)}
.p-nota{color:var(--warn);border-color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.kpi .n{font-size:22px;font-weight:700}.kpi .l{color:var(--mut);font-size:12px}
details summary{cursor:pointer;color:var(--acc)}
</style>
<body>
<h1>Craft Bridge &mdash; stato attuale</h1>
<div class="sub" id="sub">carico&hellip;</div>
<div id="app"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
function Esc(s){return String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
function render(d){
  const v=d.verdict||{};
  const bcls = v.ok===true?"b-ok": v.ok===false?"b-bad":"b-warn";
  const btxt = v.ok===true?"tutto in ordine (nessuna azione)"
             : v.ok===false? (v.problems+" cose da sistemare")
             : "diagnosi non disponibile";
  const checks=(v.checks||[]).map(c=>`<tr><td><span class="pill p-${c.state==='ok'?'ok':c.state==='fail'?'no':'nota'}">${Esc(c.state)}</span></td>
      <td><b>${Esc(c.check)}</b></td><td>${Esc(c.detail)}</td><td>${c.action?`<code>${Esc(c.action)}</code>`:''}</td></tr>`).join("");
  const actions=(v.actions||[]).map(a=>`<li><code>${Esc(a)}</code></li>`).join("");
  const srvs=(d.config?.servers||[]).map(s=>`<tr><td><b>${Esc(s.slug)}</b></td><td>${Esc(s.mode)}</td>
      <td><code>${Esc(s.command)}</code></td></tr>`).join("");
  const cls=(d.clients||[]).map(c=>`<tr><td>${Esc(c.id)}</td><td>${Esc(c.title)}</td>
      <td><span class="pill p-${c.present?'ok':'no'}">${c.present?'presente':'assente'}</span></td>
      <td>${c.bridge_entries==null?'-':Esc(c.bridge_entries)}</td><td>${c.missing==null?'-':Esc(c.missing)}</td>
      <td><code>${Esc(c.path||'-')}</code></td></tr>`).join("");
  const t=d.tests||{};
  const trow=Object.entries(t).map(([k,r])=>r?`<tr><td>${Esc(k)}</td><td>${r.passed}</td><td>${r.failed}</td>
      <td>${r.skipped}</td><td>${r.regressed}</td><td>${Esc(r.gate?.why||'applicato')}</td><td>${Esc(r.when||'')}</td></tr>`
      :`<tr><td>${Esc(k)}</td><td colspan="6" class="sub">assente</td></tr>`).join("");
  const feed=d.feed;
  const feedHtml = feed? `<div class="card"><b>${Esc(feed.count)}</b> app dal feed del launcher &middot; uscita ${Esc(feed.exit)}` +
      (feed.generated?` &middot; ${Esc(feed.generated)}`:'') + `</div>` : `<div class="card sub">feed non letto</div>`;
  const logHtml=(d.logs||[]).map(l=>`<details class="card"><summary>${Esc(l.name)} (${l.total} righe)</summary>
      <pre>${Esc((l.lines||[]).join("\n"))}</pre></details>`).join("") || `<div class="card sub">nessun log di avvio in ~/.craft-bridge/launch-logs</div>`;
  document.getElementById("sub").textContent =
    `generato ${d.generated} · host ${d.host} · ${d.platform}`;
  document.getElementById("app").innerHTML = `
    <div class="banner ${bcls}">${Esc(btxt)}</div>
    ${actions?`<div class="card"><b>Azioni</b><ul>${actions}</ul></div>`:''}
    <div class="grid">
      <div class="kpi"><div class="n">${d.config?.count||0}</div><div class="l">entry nella config</div></div>
      <div class="kpi"><div class="n">${(d.clients||[]).filter(c=>c.present).length}</div><div class="l">client MCP presenti</div></div>
      <div class="kpi"><div class="n">${(d.logs||[]).length}</div><div class="l">log di avvio</div></div>
      <div class="kpi"><div class="n">${feed?feed.count:'-'}</div><div class="l">app dal feed</div></div>
    </div>
    <h2>Diagnosi (doctor)</h2>
    <div class="card"><table><tr><th></th><th>controllo</th><th>dettaglio</th><th>azione</th></tr>${checks}</table></div>
    <h2>Entry nella config</h2>
    <div class="card"><table><tr><th>slug</th><th>modo</th><th>command</th></tr>${srvs}</table></div>
    <h2>Client MCP</h2>
    <div class="card"><table><tr><th>id</th><th>client</th><th>stato</th><th>entry ponte</th><th>mancanti</th><th>file</th></tr>${cls}</table></div>
    <h2>Suite (baseline)</h2>
    <div class="card"><table><tr><th>report</th><th>passati</th><th>falliti</th><th>saltati</th><th>regressioni</th><th>cancello</th><th>quando</th></tr>${trow}</table></div>
    <h2>Pubblicato dal launcher</h2>
    ${feedHtml}
    <h2>Log di avvio</h2>
    ${logHtml}
  `;
}
(async function(){
  let d=null;
  try{ const r=await fetch('bridge-status.json',{cache:'no-store'}); if(r.ok) d=await r.json(); }catch(e){}
  if(!d){ try{ d=JSON.parse(document.getElementById('data').textContent); }catch(e){ document.getElementById('app').innerHTML='<div class="banner b-bad">JSON illeggibile</div>'; return; } }
  render(d);
})();
</script>
</html>
"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """Il server di cortesia: serve i file e non riempie il terminale di log."""

    def log_message(self, *args) -> None:      # niente righe per ogni richiesta
        pass


def serve(directory: Path, page: str, bind: str, port: int, do_open: bool) -> int:
    """Serve `directory` con un server locale e apre `page`, restando in ascolto.

    Cosi' la pagina legge il suo `bridge-status.json` accanto (via `fetch`, come in un
    browser servito) invece di ripiegare sulla copia incorporata. Si ferma con Ctrl+C.
    """
    handler = functools.partial(_Quiet, directory=str(directory))
    try:
        httpd = http.server.ThreadingHTTPServer((bind, port), handler)
    except OSError as exc:
        print(f"server non avviato su {bind}:{port}: {exc}", file=sys.stderr)
        return 3
    actual = httpd.server_address[1]
    host = bind if ":" not in bind else f"[{bind}]"
    url = f"http://{host}:{actual}/{urllib.parse.quote(page)}"
    print(f"server   : {directory}")
    print(f"url      : {url}")
    print("ferma con Ctrl+C")
    if do_open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nserver fermato")
    finally:
        httpd.server_close()
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-json", "--out", dest="out_json",
                        default=str(REPORTS / "bridge-status.json"))
    parser.add_argument("--out-html", default=str(REPORTS / "bridge-status.html"))
    parser.add_argument("--no-doctor", action="store_true",
                        help="non eseguire la diagnosi (il resto del report resta)")
    parser.add_argument("--no-live", action="store_true",
                        help="diagnosi senza le porte delle app aperte")
    parser.add_argument("--no-clients", action="store_true")
    parser.add_argument("--no-feed", action="store_true")
    parser.add_argument("--json", action="store_true",
                        help="solo il JSON a video, non scrive file")
    parser.add_argument("--serve", action="store_true",
                        help="serve i file con un server locale e apre la pagina (resta in "
                             "ascolto finche' non premi Ctrl+C)")
    parser.add_argument("--bind", default="127.0.0.1", help="indirizzo del server (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0,
                        help="porta del server (default 0 = una porta libera scelta dal sistema)")
    parser.add_argument("--no-open", action="store_true",
                        help="con --serve, non aprire il browser: stampa solo l'URL")
    args = parser.parse_args()

    if args.serve and args.json:
        print("--serve scrive i file: non si combina con --json", file=sys.stderr)
        return 2

    status = collect(live=not args.no_live, with_clients=not args.no_clients,
                     with_feed=not args.no_feed, with_verdict=not args.no_doctor)

    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    try:
        jp, hp = Path(args.out_json), Path(args.out_html)
        jp.parent.mkdir(parents=True, exist_ok=True)
        hp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        hp.write_text(html(status), encoding="utf-8")
    except OSError as exc:
        print(f"report non scritto: {exc}", file=sys.stderr)
        return 3

    v = status["verdict"]
    state = "tutto in ordine" if v.get("ok") else (f"{v.get('problems')} da sistemare"
                                                   if v.get("ok") is False else "diagnosi assente")
    print(f"craft-bridge report - {state}")
    print(f"  json: {jp}")
    print(f"  html: {hp}")
    if args.serve:
        return serve(hp.parent, hp.name, args.bind, args.port, do_open=not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
