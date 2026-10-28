"""Prépare la version « app web Claude » (artifact) dans ./artifact :
  index.html            l'interface
  annonces.json         les annonces collectées
  thumbs-NN.json        les miniatures en data: URI, en 60 paquets (une page artifact
                        ne peut pas charger d'images depuis d'autres sites)
  publish-files.json    la liste des fichiers à publier avec la page

    python3 build_artifact.py [--pages N] [--no-scrape]

Miniatures : téléchargées une seule fois par annonce, réduites avec `sips` (macOS)
et gardées dans data/thumbs/.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import scrapers
import server

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "artifact")
THUMBS = os.path.join(ROOT, "data", "thumbs")
CHUNKS = 60


def thumb_path(listing_id):
    return os.path.join(THUMBS, "".join(c if c.isalnum() or c in "-_" else "_" for c in listing_id) + ".jpg")


def make_thumb(x):
    dest = thumb_path(x["id"])
    if os.path.exists(dest) or not x.get("image"):
        return
    try:
        req = urllib.request.Request(x["image"], headers={"User-Agent": scrapers.UA, "Referer": x["url"]})
        with urllib.request.urlopen(req, timeout=20, context=scrapers.SSL_CTX) as r:
            raw = r.read()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(raw)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "40", "-Z", "200", tmp.name, "--out", dest],
                       check=True, capture_output=True, timeout=30)
    except Exception:
        pass  # pas de miniature : la carte affiche « Pas de photo »
    finally:
        if "tmp" in locals():
            os.unlink(tmp.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="limite de pages par site (défaut : toutes)")
    ap.add_argument("--no-scrape", action="store_true", help="réutilise data/annonces.json")
    args = ap.parse_args()

    if not args.no_scrape:
        server.state["pages"] = args.pages
        server.refresh()
    data = server.load()

    os.makedirs(THUMBS, exist_ok=True)
    with ThreadPoolExecutor(12) as pool:
        list(pool.map(make_thumb, data["listings"]))

    os.makedirs(OUT, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "static", "index.html"), OUT)

    # Miniatures réparties en CHUNKS fichiers (toujours les mêmes noms), des plus récentes aux plus
    # anciennes : la page ne charge que les paquets des annonces qu'elle affiche.
    listings = sorted(data["listings"], key=lambda x: x.get("date") or x.get("first_seen") or "", reverse=True)
    per_chunk = max(1, -(-len(listings) // CHUNKS))
    chunks = [{} for _ in range(CHUNKS)]
    for i, x in enumerate(listings):
        p = thumb_path(x["id"])
        if os.path.exists(p):
            with open(p, "rb") as f:
                x["t"] = i // per_chunk
                chunks[x["t"]][x["id"]] = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    for name in os.listdir(OUT):
        if name.startswith("thumbs-"):
            os.remove(os.path.join(OUT, name))
    for i, c in enumerate(chunks):
        with open(os.path.join(OUT, f"thumbs-{i:02d}.json"), "w") as f:
            json.dump(c, f, separators=(",", ":"))
    with open(os.path.join(OUT, "annonces.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # Liste des fichiers à publier, pour la tâche planifiée (paramètre `files` de l'outil Artifact)
    files = {name: name for name in sorted(os.listdir(OUT)) if name.endswith(".json") and name != "publish-files.json"}
    with open(os.path.join(OUT, "publish-files.json"), "w") as f:
        json.dump(files, f, indent=1)

    # Supprime les miniatures d'annonces disparues
    keep = {os.path.basename(thumb_path(x["id"])) for x in data["listings"]}
    for name in os.listdir(THUMBS):
        if name not in keep:
            os.remove(os.path.join(THUMBS, name))

    n_thumbs = sum(len(c) for c in chunks)
    print(f"artifact/ prêt : {len(data['listings'])} annonces, {n_thumbs} miniatures")
    counts = {}
    for x in data["listings"]:
        counts[x["source"]] = counts.get(x["source"], 0) + 1
    print("Par site :", ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
