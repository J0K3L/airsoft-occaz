"""Airsoft Occaz : agrégateur local d'annonces airsoft d'occasion.

Lancement :  python3 server.py   puis ouvrir http://localhost:8765
             (l'adresse à ouvrir sur l'iPhone, même Wi-Fi, s'affiche au démarrage)
Options   :  --port 8765  --pages N  (limite les pages lues par site ; défaut : toutes)
             --local  (accessible uniquement depuis ce Mac)
"""
import argparse
import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import scrapers

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT, "data", "annonces.json")
MAX_AGE = 30 * 60  # actualisation automatique si le cache a plus de 30 min

state = {"running": False, "log": [], "pages": None}
lock = threading.Lock()


def log(msg):
    line = f"{datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    state["log"] = (state["log"] + [line])[-60:]


def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"updated": None, "listings": [], "sources": {}}


def refresh():
    with lock:
        if state["running"]:
            return False
        state["running"] = True
    try:
        log("Actualisation lancée")
        previous = {x["id"]: x for x in load()["listings"]}
        listings, sources = [], {}
        with ThreadPoolExecutor(len(scrapers.SOURCES)) as pool:
            futures = {name: pool.submit(fn, state["pages"] or scrapers.DEFAULT_PAGES[name], log)
                       for name, fn in scrapers.SOURCES.items()}
            for name, fut in futures.items():
                try:
                    items = fut.result()
                    sources[name] = {"ok": True, "count": len(items)}
                except Exception as e:  # un site en panne ne bloque pas les autres
                    items = [x for x in previous.values() if x["source"] == name]
                    sources[name] = {"ok": False, "count": len(items), "error": str(e)}
                    log(f"{name} : échec ({e}), anciennes annonces conservées")
                listings.extend(items)
        # Une annonce qui change de page pendant la lecture peut être vue deux fois
        listings = list({x["id"]: x for x in reversed(listings)}.values())[::-1]
        now = datetime.now().isoformat(timespec="minutes")
        recent = (datetime.now() - timedelta(days=2)).isoformat(timespec="minutes")
        for x in listings:  # mémorise la 1re fois qu'on a vu l'annonce
            seen = previous.get(x["id"], {}).get("first_seen")
            if not seen:  # une annonce ancienne découverte tardivement n'est pas « nouvelle »
                seen = x["date"] if x.get("date") and x["date"] < recent else now
            x["first_seen"] = seen
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"updated": now, "listings": listings, "sources": sources}, f, ensure_ascii=False)
        os.replace(DATA_FILE + ".tmp", DATA_FILE)
        log(f"Terminé : {len(listings)} annonces")
        return True
    finally:
        state["running"] = False


def refresh_async():
    threading.Thread(target=refresh, daemon=True).start()


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=os.path.join(ROOT, "static"), **kw)

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/annonces"):
            data = load()
            data["running"] = state["running"]
            return self.send_json(data)
        if self.path.startswith("/api/status"):
            return self.send_json({"running": state["running"], "log": state["log"][-12:], "updated": load()["updated"]})
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            if not state["running"]:
                refresh_async()
            return self.send_json({"running": True})
        self.send_error(404)

    def log_message(self, *a):
        pass


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # aucun paquet envoyé : sert juste à choisir l'interface
            return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--pages", type=int, default=None, help="limite de pages par site (défaut : toutes)")
    ap.add_argument("--local", action="store_true", help="n'accepter que les connexions de ce Mac")
    args = ap.parse_args()
    state["pages"] = args.pages

    data = load()
    stale = not data["updated"] or time.time() - datetime.fromisoformat(data["updated"]).timestamp() > MAX_AGE
    if stale:
        refresh_async()

    srv = ThreadingHTTPServer(("127.0.0.1" if args.local else "0.0.0.0", args.port), Handler)
    print(f"Airsoft Occaz → http://localhost:{args.port}", flush=True)
    if not args.local:
        print(f"Sur l'iPhone (même Wi-Fi) → http://{lan_ip()}:{args.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
