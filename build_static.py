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


def slim(x):
    """Allège annonces.json pour les téléphones : sans champs vides ni doublons d'information."""
    y = {k: v for k, v in x.items() if v not in (None, "", [], False)}
    if y.get("date"):
        y.pop("date_text", None)
    if y.get("kind") == "offre":
        y.pop("kind")
    if y.get("location") == y.get("region"):
        y.pop("location", None)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="limite de pages par site (défaut : toutes)")
    args = ap.parse_args()

    # Reprend le dernier annonces.json publié (dates « vue pour la 1re fois », annonces d'un site en panne)
    prev_path = os.path.join(OUT, "annonces.json")
    if os.path.exists(prev_path):
        os.makedirs(os.path.dirname(server.DATA_FILE), exist_ok=True)
        shutil.copy(prev_path, server.DATA_FILE)

    server.state["pages"] = args.pages
    server.refresh()
    data = server.load()

    shutil.copytree(os.path.join(ROOT, "static"), OUT, dirs_exist_ok=True)
    data["listings"] = [slim(x) for x in data["listings"]]
    with open(prev_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{datetime.now():%H:%M} site/ prêt : {len(data['listings'])} annonces, {os.path.getsize(prev_path) // 1024} Ko")


if __name__ == "__main__":
    main()
