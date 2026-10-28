"""Construit la version hébergée (site statique) dans ./site :
l'interface + annonces.json fraîchement collecté. Utilisé par GitHub Actions.

    python3 build_static.py [--pages N]
"""
import argparse
import json
import os
import shutil
from datetime import datetime

import server

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="limite de pages par site (défaut : toutes)")
    args = ap.parse_args()

    # Reprend le dernier annonces.json publié (pour garder les dates "vue pour la 1re fois")
    prev = os.path.join(OUT, "annonces.json")
    if os.path.exists(prev):
        os.makedirs(os.path.dirname(server.DATA_FILE), exist_ok=True)
        shutil.copy(prev, server.DATA_FILE)

    server.state["pages"] = args.pages
    server.refresh()

    shutil.copytree(os.path.join(ROOT, "static"), OUT, dirs_exist_ok=True)
    shutil.copy(server.DATA_FILE, prev)
    with open(prev, encoding="utf-8") as f:
        n = len(json.load(f)["listings"])
    print(f"{datetime.now():%H:%M} site/ prêt : {n} annonces")


if __name__ == "__main__":
    main()
