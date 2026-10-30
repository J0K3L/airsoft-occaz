"""Enrichit les annonces après la collecte :
  brand  marque reconnue dans le titre (Tokyo Marui, G&G, Specna Arms…)
  model  modèle reconnu (M4/AR15, AK, Glock, MWS…), pour comparer des prix comparables
  deal   « bonne affaire » : % sous le prix médian du même modèle et de la même motorisation
  geo    [latitude, longitude] approximative (ville, sinon département) pour le filtre par distance
  dept   département, ex. « Yvelines (78) » (complète aussi la région quand le site ne la donne pas)
  also   annonce identique publiée sur d'autres sites (doublons) ; les copies portent dup_of
"""
import json
import re
import statistics
import unicodedata
from collections import defaultdict

import scrapers

BRANDS = [
    ("Tokyo Marui", r"tokyo ?marui|\bmarui\b|\btm\b"), ("G&G", r"\bg ?& ?g\b|\bg and g\b|\bg&g\b|\bgg armament"),
    ("Specna Arms", r"specna"), ("VFC", r"\bvfc\b|umarex ?/ ?vfc"), ("Cyma", r"\bcyma\b"), ("KWA", r"\bkwa\b"),
    ("WE", r"\bwe\b(?! ?(vend|propose|cherche))"), ("KJW", r"\bkjw\b"), ("ASG", r"\basg\b"), ("ICS", r"\bics\b"),
    ("LCT", r"\blct\b"), ("E&L", r"\be ?& ?l\b"), ("Ares", r"\bares\b"), ("Krytac", r"krytac"), ("Novritsch", r"novritsch"),
    ("Classic Army", r"classic ?army"), ("Double Bell", r"double ?bell"), ("Jing Gong", r"jing ?gong|\bjg\b"),
    ("Golden Eagle", r"golden ?eagle"), ("Umarex", r"umarex"), ("Cybergun", r"cybergun"), ("King Arms", r"king ?arms"),
    ("Bolt", r"\bbolt airsoft|\bbolt b4"), ("APS", r"\baps\b"), ("GHK", r"\bghk\b"), ("Arcturus", r"arcturus"),
    ("Evolution", r"\bevolution\b"), ("Nuprol", r"nuprol"), ("Lancer Tactical", r"lancer"), ("Well", r"\bwell\b"),
    ("Swiss Arms", r"swiss ?arms"), ("Action Army", r"action ?army"), ("Silverback", r"silverback"),
    ("Polarstar", r"polar ?star"), ("Wolverine", r"wolverine"), ("A&K", r"\ba ?& ?k\b"), ("SRC", r"\bsrc\b"),
    ("Dboys", r"d-?boys"), ("Army Armament", r"army ?armament"), ("Secutor", r"secutor"), ("Raven", r"\braven\b"),
    ("Elite Force", r"elite ?force"), ("S&T", r"\bs ?& ?t\b"), ("Snow Wolf", r"snow ?wolf"), ("Vorsk", r"vorsk"),
    ("Lonex", r"lonex"), ("Systema", r"systema"), ("Real Sword", r"real ?sword"), ("Galaxy", r"\bgalaxy\b"),
    ("BO Manufacture", r"bo manufacture"), ("Saigo", r"saigo"), ("Modify", r"\bmodify\b"), ("Echo1", r"echo ?1"),
]
BRAND_RX = [(name, re.compile(rx, re.I)) for name, rx in BRANDS]

MODELS = [
    ("HK416", r"hk ?416|\b416\b"), ("HK417 / SR-25", r"hk ?417|\b417\b|sr-?25|\bg28\b"),
    ("M4 / AR-15", r"\bm4|\bm16|ar-?15|\bmk ?18|\bmk ?16|\burgi\b|cqb-?r|ddm4|\bsr-?16|\bm733|\bmws\b"),
    ("AK", r"\bak-?\d*\b|\bakm|\baks|kalash|\bak ?(47|74|105|12|15|102|104)"), ("MP5", r"mp-?5"), ("MP7", r"mp-?7"),
    ("G36", r"g-?36"), ("SCAR", r"\bscar"), ("P90", r"p-?90"), ("Vector", r"vector"), ("Scorpion EVO", r"scorpion|evo ?3"),
    ("UMP", r"\bump"), ("Famas", r"famas"), ("AUG", r"\baug\b"), ("G3", r"\bg3\b"), ("MCX", r"\bmcx"),
    ("VSR-10", r"vsr"), ("L96 / AW", r"\bl96|\baw\b|\baw ?308"), ("SSG", r"ssg"), ("M40", r"\bm40"),
    ("M870", r"870"), ("Glock", r"glock|\bg ?1[789]\b|\bg ?34\b|\bg ?4[57]\b"), ("Hi-Capa", r"hi-?capa"),
    ("1911", r"1911|\bm45"), ("M9 / Beretta", r"\bm9\b|\bm92|beretta"), ("SIG P226/P320", r"p226|p320|m17|m18\b"),
    ("Desert Eagle", r"desert ?eagle"), ("USP", r"\busp"), ("MK23", r"mk ?23"), ("Revolver", r"revolver|python|\bm29\b"),
]
MODEL_RX = [(name, re.compile(rx, re.I)) for name, rx in MODELS]
WEAPONS = {"Réplique longue", "Réplique de poing", "Sniper", "Fusil à pompe"}
# Lots, répliques en panne et pièces détachées faussent la comparaison des prix
NOT_A_WEAPON = re.compile(r"\blot\b|\bpack\b|\bhs\b|panne|a reparer|pieces? detach|\bupper\b|\blower\b|garde-?main|"
                          r"\bcanon|crosse|marteau|hammer|chargeur|gearbox|hop-?up|piston|ressort|\bkit\b|silencieux|"
                          r"lunette|batterie|holster|\brail|\bpour\b|compatible|\bcarcasse|\bculasse\b|\bslide\b|barrel|\bouter\b|\binner\b")


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tag_brand_model(x):
    t = x.get("title") or ""
    x["brand"] = next((n for n, rx in BRAND_RX if rx.search(t)), None)
    x["model"] = next((n for n, rx in MODEL_RX if rx.search(t)), None) if x.get("category") in WEAPONS else None


def compute_deals(listings):
    """Bonne affaire = au moins 30 % sous la médiane des annonces comparables (8 minimum) :
    même modèle, même motorisation et, quand il y a assez d'annonces, même marque."""
    groups = defaultdict(list)
    candidates = []
    for x in listings:
        x.pop("deal", None); x.pop("median", None)
        if x.get("model") and x.get("price") and x["price"] >= 10 and x.get("kind") != "recherche" \
                and not NOT_A_WEAPON.search(norm(x["title"])):
            base = (x["model"], x.get("motor") or "?")
            groups[base].append(x["price"])
            if x.get("brand"):
                groups[base + (x["brand"],)].append(x["price"])
            candidates.append(x)
    medians = {k: statistics.median(v) for k, v in groups.items() if len(v) >= 8}
    for x in candidates:
        base = (x["model"], x.get("motor") or "?")
        median = medians.get(base + (x["brand"],)) if x.get("brand") else None
        median = median or medians.get(base)
        if median and 0.4 * median <= x["price"] <= 0.7 * median:
            x["deal"] = round((1 - x["price"] / median) * 100)
            x["median"] = round(median)


# --- Géolocalisation (API officielle geo.api.gouv.fr, une requête par collecte) ---

def load_communes():
    data = json.loads(scrapers.fetch("https://geo.api.gouv.fr/communes?fields=nom,codesPostaux,centre,codeDepartement,population&format=json"))
    by_cp, by_name, dept = {}, {}, defaultdict(lambda: [0.0, 0.0, 0])  # by_cp et by_name : (point, département)
    for c in sorted(data, key=lambda c: c.get("population") or 0):  # la plus peuplée l'emporte
        if not c.get("centre"):
            continue
        lon, lat = c["centre"]["coordinates"]
        pt = [round(lat, 3), round(lon, 3)]
        for cp in c.get("codesPostaux", []):
            by_cp[cp] = (pt, c["codeDepartement"])
        by_name[re.sub(r"[^a-z0-9]", "", norm(c["nom"]))] = (pt, c["codeDepartement"])
        w = max(c.get("population") or 1, 1)
        d = dept[c["codeDepartement"]]
        d[0] += lat * w; d[1] += lon * w; d[2] += w
    by_dept = {k: [round(v[0] / v[2], 3), round(v[1] / v[2], 3)] for k, v in dept.items()}
    names = {d["code"]: d["nom"] for d in json.loads(scrapers.fetch("https://geo.api.gouv.fr/departements?fields=nom,code"))}
    return by_cp, by_name, by_dept, names


def geocode(listings, log=print):
    try:
        by_cp, by_name, by_dept, names = load_communes()
    except Exception as e:
        log(f"géolocalisation indisponible : {e}")
        return
    found = 0
    for x in listings:
        loc = x.get("location") or ""
        geo = dept = None
        cp = re.search(r"\b(\d{5})\b", loc)
        if cp:
            geo, dept = by_cp.get(cp.group(1)) or (None, cp.group(1)[:2])
        elif x["source"] == "peew.fr" and loc:
            city = re.sub(r"\s+\d+(er|e) arrondissement$", "", norm(loc))  # « Paris 14e Arrondissement » → Paris
            geo, dept = by_name.get(re.sub(r"[^a-z0-9]", "", city), (None, None))
        elif x["source"] == "airsoftone.fr":
            d = re.search(r"\((\w{2,3})\)", loc)
            dept = d.group(1) if d else None
        elif x["source"] == "zn-airsoft.fr":
            geo, dept = by_name.get("vourles", (None, None))
        geo = geo or by_dept.get(dept)
        if geo:
            x["geo"] = geo
            found += 1
        else:
            x.pop("geo", None)
        if dept in names:
            x["dept"] = f"{names[dept]} ({dept})"
            x["region"] = x.get("region") or scrapers.DEPT_REGION.get(dept)
        else:
            x.pop("dept", None)
    log(f"géolocalisation : {found}/{len(listings)} annonces placées, "
        f"{sum(1 for x in listings if x.get('dept'))} avec leur département")


# --- Doublons entre sites -------------------------------------------------------

def mark_duplicates(listings):
    """Même titre (normalisé) et même prix sur deux sites différents = même annonce."""
    groups = defaultdict(list)
    for x in listings:
        x.pop("also", None); x.pop("dup_of", None)
        key = re.sub(r"[^a-z0-9]", "", norm(x.get("title")))
        if len(key) >= 8 and x.get("price"):
            groups[(key, x["price"])].append(x)
    n = 0
    for items in groups.values():
        if len({i["source"] for i in items}) < 2:
            continue
        items.sort(key=lambda i: (not i.get("date"), not i.get("image")))
        main = items[0]
        main["also"] = [{"source": i["source"], "url": i["url"]} for i in items[1:] if i["source"] != main["source"]]
        for i in items[1:]:
            i["dup_of"] = main["id"]
            n += 1
    return n


def enrich(listings, log=print):
    for x in listings:
        tag_brand_model(x)
    compute_deals(listings)
    geocode(listings, log)
    n = mark_duplicates(listings)
    log(f"enrichissement : {sum(1 for x in listings if x.get('brand'))} marques, "
        f"{sum(1 for x in listings if x.get('deal'))} bonnes affaires, {n} doublons regroupés")
