"""Collecteurs d'annonces airsoft d'occasion (France).

Chaque collecteur renvoie une liste de dicts normalisés :
  id, source, title, price, url, image, region, location, category,
  motor, condition, seller, kind ("offre" | "recherche"), date (ISO), date_text
Uniquement la bibliothèque standard Python.
"""
import html
import os
import re
import ssl
import time
import urllib.request
from datetime import datetime, timedelta

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
DELAY = 0.5  # pause entre deux pages d'un même site, par politesse

# Le Python de python.org sur macOS n'a pas toujours de certificats : on se rabat sur ceux du système.
SSL_CTX = ssl.create_default_context()
if not SSL_CTX.get_ca_certs() and os.path.exists("/etc/ssl/cert.pem"):
    SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")


def fetch(url, tries=2):
    try:
        return _fetch(url)
    except Exception:
        if tries <= 1:
            raise
        time.sleep(2)  # une erreur passagère ne doit pas couper la collecte en plein milieu
        return fetch(url, tries - 1)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
        raw = r.read()
        meta = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:3000])
        charset = r.headers.get_content_charset() or (meta.group(1).decode() if meta else None)
    try:
        return raw.decode(charset or "utf-8")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def clean(s):
    if s is None:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def grab(pattern, text, flags=re.S):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None


def parse_price(s):
    if not s:
        return None
    s = clean(s).replace(" ", "").replace(" ", "")
    m = re.search(r"(\d+(?:[.,]\d+)?)", s.replace(".", "") if re.search(r"\d\.\d{3}", s) else s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


# --- Dates ------------------------------------------------------------------

UNITS = {"minute": 60, "heure": 3600, "jour": 86400, "semaine": 604800, "mois": 2592000, "an": 31536000}


def parse_date(text):
    """Convertit "aujourd'hui à 20h50", "hier", "il y a 3 jours", "12/10/2026"... en ISO."""
    if not text:
        return None
    t = text.lower()
    now = datetime.now()
    hm = re.search(r"(\d{1,2})h(\d{2})", t)
    if "aujourd" in t or "hier" in t:
        d = now if "aujourd" in t else now - timedelta(days=1)
        if hm:
            d = d.replace(hour=int(hm.group(1)), minute=int(hm.group(2)), second=0, microsecond=0)
        return d.isoformat(timespec="minutes")
    m = re.search(r"il y a (\d+|un|une)\s*(minute|heure|jour|semaine|mois|an)", t)
    if m:
        n = 1 if m.group(1) in ("un", "une") else int(m.group(1))
        return (now - timedelta(seconds=n * UNITS[m.group(2)])).isoformat(timespec="minutes")
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        try:
            d = datetime(y, int(m.group(2)), int(m.group(1)))
            if hm:
                d = d.replace(hour=int(hm.group(1)), minute=int(hm.group(2)))
            return d.isoformat(timespec="minutes")
        except ValueError:
            return None
    months = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]
    m = re.search(r"(\d{1,2})\s+([a-zéû]+)\.?\s*(\d{4})?", t)
    if m:
        for i, mo in enumerate(months):
            if m.group(2).startswith(mo[:3]):
                y = int(m.group(3)) if m.group(3) else now.year
                try:
                    return datetime(y, i + 1, int(m.group(1))).isoformat(timespec="minutes")
                except ValueError:
                    return None
    return None


# --- Normalisation ----------------------------------------------------------

DEPT_REGION = {}
for region, depts in {
    "Auvergne-Rhône-Alpes": "01 03 07 15 26 38 42 43 63 69 73 74",
    "Bourgogne-Franche-Comté": "21 25 39 58 70 71 89 90",
    "Bretagne": "22 29 35 56",
    "Centre-Val de Loire": "18 28 36 37 41 45",
    "Corse": "2A 2B 20",
    "Grand Est": "08 10 51 52 54 55 57 67 68 88",
    "Hauts-de-France": "02 59 60 62 80",
    "Île-de-France": "75 77 78 91 92 93 94 95",
    "Normandie": "14 27 50 61 76",
    "Nouvelle-Aquitaine": "16 17 19 23 24 33 40 47 64 79 86 87",
    "Occitanie": "09 11 12 30 31 32 34 46 48 65 66 81 82",
    "Pays de la Loire": "44 49 53 72 85",
    "Provence-Alpes-Côte d'Azur": "04 05 06 13 83 84",
    "Outre-mer": "971 972 973 974 976",
}.items():
    for d in depts.split():
        DEPT_REGION[d] = region

REGION_ALIASES = {re.sub(r"[^a-z]", "", html.unescape(r).lower()
                         .translate(str.maketrans("éèêëîïôûüàç", "eeeeiiouuac"))): r
                  for r in set(DEPT_REGION.values())}


def norm_region(text):
    if not text:
        return None
    key = re.sub(r"[^a-z]", "", text.lower().translate(str.maketrans("éèêëîïôûüàçÉÎ", "eeeeiiouuacei")))
    for alias, region in REGION_ALIASES.items():
        if key.startswith(alias):
            return region
    return None


def region_from_postcode(cp):
    if not cp:
        return None
    if cp.startswith("97"):
        return DEPT_REGION.get(cp[:3])
    if cp.startswith("20"):
        return "Corse"
    return DEPT_REGION.get(cp[:2])


CATEGORIES = [
    ("Sniper", r"sniper|snipe|vsr|\bvds\b|bolt|verrou|l96|ssg|m40|ssr|mb0?\d|t-?10\b"),
    ("Fusil à pompe", r"pompe|shotgun|m870|\bm3\b|spas|franchi"),
    ("Réplique de poing", r"poing|pistol|glock|1911|hi-?capa|beretta|\bm9\b|\bp226|usp|revolver|desert eagle|\bcz ?75|vp9|aep|sig p"),
    ("Chargeurs", r"chargeur|mag(azine)?s?\b|midcap|hicap|mid-cap|hi-cap"),
    ("Batteries", r"batter|lipo|nimh"),
    ("Optiques & visée", r"optique|vis[ée]e|red ?dot|holo|lunette|scope|eotech|aimpoint|magnifier"),
    ("Pièces & upgrades", r"pi[eè]ces?|upgrade|gearbox|hop-?up|canon|cylindre|piston|moteur|mosfet|bushing|ressort|joint|n[eé]gociateur|bucking|nub|engrenage|interne|externe|garde-?main|crosse"),
    ("Équipement & tenues", r"gilet|plate ?carrier|jpc|chest|ceinture|belt|sac|tenue|treillis|v[eê]tement|habillement|casque|helmet|masque|gant|lunettes de protection|protection|chaussure|pouch|poche|holster|[ée]quipement|gear|multicam|camo"),
    ("Réplique longue", r"r[ée]plique|aeg|gbbr?|\bhpa\b|spring|\bm4\b|m16|ak-?\d*|akm|ar-?15|hk ?416|g36|mp5|mp7|scar|famas|aug|galil|vector|scorpion|mcx|p90|ump|\bsmg|carbine|fusil|rifle|dmr|lmg|m249|minimi|g3|sr-?25|417|mk18|urgi|lt-?\d+"),
]

MOTORS = [
    ("HPA", r"\bhpa\b|polar ?star|wolverine|inferno|f2\b|fusion engine"),
    ("GBB", r"gbbr?|gaz blowback|blowback|\bgbb"),
    ("CO2", r"co2|co²"),
    ("Gaz", r"\bgaz\b|\bgas\b|green gas"),
    ("Spring", r"spring|ressort|manuel|culasse|verrou|bolt"),
    ("AEP", r"\baep\b"),
    ("AEG", r"\baeg\b|[ée]lectrique|ebb|mosfet|gearbox|lipo"),
]


def classify(*texts):
    blob = " ".join(t for t in texts if t).lower()
    category = next((c for c, rx in CATEGORIES if re.search(rx, blob)), "Autre")
    motor = next((m for m, rx in MOTORS if re.search(rx, blob)), None)
    return category, motor


WEAPON_CATS = ("Sniper", "Fusil à pompe", "Réplique de poing")


def classify_listing(sub, title, desc=""):
    """La catégorie du site prime ; le titre précise (poing, sniper...) ; la description en dernier recours."""
    c_sub, m_sub = classify(sub)
    c_title, m_title = classify(title)
    long_rx = dict(CATEGORIES)["Réplique longue"]
    if c_sub in ("Réplique longue", "Autre") and c_title in WEAPON_CATS:
        category = c_title
    elif c_title == "Pièces & upgrades" and re.search(r"\b(aeg|gbbr?|hpa|spring)\b", title.lower()):
        category = "Réplique longue"  # ex. "M4 AEG full upgrade" : une réplique, pas une pièce
    elif c_sub in ("Réplique longue", "Autre") and c_title != "Autre" and not re.search(long_rx, title.lower()):
        category = c_title  # ex. un chargeur ou un gilet posté dans une rubrique "réplique"
    elif c_sub != "Autre":
        category = c_sub
    elif c_title != "Autre":
        category = c_title
    else:
        category = classify(desc)[0]
    motor = m_title or m_sub or classify(desc)[1]
    if category in ("Équipement & tenues", "Optiques & visée", "Batteries"):
        motor = None
    return category, motor


def is_wanted(title, cat_text=""):
    t = (title + " " + cat_text).lower()
    return bool(re.search(r"^\s*(je )?(re)?cherche|\[?(ach|wtb)\]|recherche\b|\bachète\b", t))


# --- airsoft-occasion.fr -----------------------------------------------------

def scrape_airsoft_occasion(pages=300, log=print):
    out = []
    for p in range(1, pages + 1):
        url = f"https://www.airsoft-occasion.fr/annonces?sort=1&type=1&page={p}"
        try:
            h = fetch(url)
        except Exception as e:
            log(f"airsoft-occasion.fr page {p}: {e}")
            break
        blocks = h.split('class="background-ads-listing-container"')[1:]
        if not blocks:
            break
        for b in blocks:
            href = grab(r'href="(https://www\.airsoft-occasion\.fr/annonce/[^"]+)"', b)
            if not href:
                continue
            title = clean(grab(r'class="title-listing">(.*?)</p>', b))
            cat_text = clean(grab(r'class="category-listing">(.*?)</p>', b))
            loc = clean(grab(r'class="localisation-listing">(.*?)</p>', b))
            cp = grab(r"\b(\d{5})\b", loc)
            date_text = clean(grab(r'class="date-listing">(.*?)</span>', b))
            desc = html.unescape(grab(r'title="([^"]*)"', b) or "")
            sub = cat_text.split("/", 1)[-1].strip()
            category, motor = classify_listing(sub, title, desc)
            out.append({
                "id": "ao-" + (grab(r"-(\d+)$", href) or href),
                "source": "airsoft-occasion.fr",
                "title": title,
                "price": parse_price(grab(r'class="price-listing">(.*?)</span>\s*</span>', b)),
                "url": href,
                "image": grab(r'<img\s+src="([^"]+)"', b),
                "region": region_from_postcode(cp),
                "location": loc,
                "category": category,
                "subcategory": sub,
                "motor": motor,
                "condition": None,
                "seller": None,
                "kind": "recherche" if cat_text.lower().startswith("recherche") or is_wanted(title) else "offre",
                "date": parse_date(date_text),
                "date_text": date_text.replace("Déposée ", ""),
            })
        log(f"airsoft-occasion.fr page {p}: {len(blocks)} annonces")
        time.sleep(DELAY)
    return out


# --- occasion-airsoft.fr -----------------------------------------------------

OA_SLUGS = {
    "repliques-longues": "Réplique longue", "repliques-de-poing": "Réplique de poing",
    "snipes": "Sniper", "fusil-a-pompe": "Fusil à pompe", "chargeurs": "Chargeurs",
    "pieces-internes": "Pièces & upgrades", "pieces-externes": "Pièces & upgrades",
    "optiques": "Optiques & visée", "equipements-tactiques": "Équipement & tenues",
    "habillement": "Équipement & tenues", "gear": "Équipement & tenues", "hpa": "Réplique longue",
}


def scrape_occasion_airsoft(pages=300, log=print):
    out = []
    for p in range(1, pages + 1):
        url = f"https://occasion-airsoft.fr/?oa_catalogue=all&oa_page={p}"
        try:
            h = fetch(url)
        except Exception as e:
            log(f"occasion-airsoft.fr page {p}: {e}")
            break
        blocks = h.split('<article class="listing-card')[1:]
        if not blocks:
            break
        for b in blocks:
            href = grab(r'class="card-link" href="([^"]+)"', b)
            if not href:
                continue
            title = clean(grab(r'class="card-title">(.*?)</h2>', b))
            path = [s for s in href.split("/annnonce/", 1)[-1].split("/") if s]
            slug_cats = [s for s in path[:-1]]
            category, motor = classify(" ".join(slug_cats), title)
            for s in reversed(slug_cats):
                if s in OA_SLUGS:
                    category = OA_SLUGS[s]
                    break
            if "hpa" in slug_cats:
                motor = "HPA"
            meta = grab(r'class="card-meta">(.*?)</p>', b) or ""
            spans = [clean(s) for s in re.findall(r"<span[^>]*>(.*?)</span>", meta, re.S)]
            region_txt = spans[0] if spans else ""
            date_text = clean(grab(r'class="age">(.*?)</span>', meta))
            out.append({
                "id": "oa-" + (grab(r'name="post_id" value="(\d+)"', b) or href),
                "source": "occasion-airsoft.fr",
                "title": title,
                "price": parse_price(grab(r'class="card-price">(.*?)</p>', b)),
                "url": href,
                "image": grab(r'data-src="([^"]+)"', b) or grab(r'<img[^>]*src="(http[^"]+)"', b),
                "region": norm_region(region_txt),
                "location": region_txt,
                "category": category,
                "subcategory": slug_cats[-1].replace("-", " ") if slug_cats else "",
                "motor": motor,
                "condition": clean(grab(r'class="card-condition">(.*?)</p>', b)) or None,
                "seller": None,
                "kind": "recherche" if is_wanted(title) else "offre",
                "date": parse_date(date_text),
                "date_text": date_text,
            })
        log(f"occasion-airsoft.fr page {p}: {len(blocks)} annonces")
        time.sleep(DELAY)
    return out


# --- naturabuy.fr (catégorie Airsoft, annonces "occasion" uniquement) --------

NB_CATS = [  # (url, part des pages lues) : toutes les répliques, le début des autres rubriques
    ("https://www.naturabuy.fr/Repliques-Airsoft-cat-1221.html", 1.0),
    ("https://www.naturabuy.fr/Accessoires-replique-Airsoft-cat-2615.html", 0.1),
    ("https://www.naturabuy.fr/Visee-Airsoft-cat-2595.html", 0.1),
    ("https://www.naturabuy.fr/Vetements-Airsoft-cat-2644.html", 0.1),
    ("https://www.naturabuy.fr/Protections-Airsoft-cat-2664.html", 0.1),
]


def scrape_naturabuy(pages=10, log=print):
    out, seen = [], set()
    for base, ratio in NB_CATS:
        for p in range(1, max(1, round(pages * ratio)) + 1):
            url = base + (f"?PAGE={p}" if p > 1 else "")
            try:
                h = fetch(url)
            except Exception as e:
                log(f"naturabuy.fr {url}: {e}")
                break
            cards = [(grab(r'^([^"]+)"', c), c) for c in re.split(r'<a\s+href="', h)[1:]
                     if re.match(r'[^"]+-item-\d+\.html"\s+class="itemCard', c)]
            if not cards:
                break
            kept = 0
            for href, b in cards:
                b = b.split("</a>", 1)[0]
                attrs = dict(re.findall(r'data-([\w-]+)="([^"]*)"', b))
                if attrs.get("dimension4") != "occasion" or attrs.get("id") in seen:
                    continue
                seen.add(attrs.get("id"))
                title = html.unescape(attrs.get("name", ""))
                sub = html.unescape(attrs.get("category", "")).split("/")[-1]
                category, motor = classify_listing(sub, title)
                date_text = clean(grab(r'class="starts-time">(.*?)</div>', b))
                try:
                    price = float(attrs.get("price"))
                except (TypeError, ValueError):  # enchères : prix affiché seulement dans la carte
                    price = parse_price(grab(r'class="bold[^"]*">\s*([\d\s.,]+)&euro;', b))
                out.append({
                    "id": "nb-" + attrs.get("id", href),
                    "source": "naturabuy.fr",
                    "title": title,
                    "price": price,
                    "url": href if href.startswith("http") else "https://www.naturabuy.fr/" + href,
                    "image": grab(r'<img[^>]*src="([^"]+)"', b),
                    "region": None,
                    "location": "",
                    "category": category,
                    "subcategory": sub,
                    "motor": motor,
                    "condition": "Occasion",
                    "seller": attrs.get("dimension6"),
                    "kind": "offre",
                    "date": parse_date(date_text),
                    "date_text": date_text.replace("ajout ", ""),
                })
                kept += 1
            log(f"naturabuy.fr {url.rsplit('/', 1)[-1]}: {kept}/{len(cards)} annonces d'occasion")
            time.sleep(DELAY)
    return out


# --- airsoft-entrepot.fr (rubrique Occasions, Magento) -----------------------

def scrape_airsoft_entrepot(pages=50, log=print):
    out, seen = [], set()
    for p in range(1, pages + 1):
        url = "https://www.airsoft-entrepot.fr/all-catalog/occasions.html" + (f"?p={p}" if p > 1 else "")
        try:
            h = fetch(url)
        except Exception as e:
            log(f"airsoft-entrepot.fr page {p}: {e}")
            break
        new = 0
        for b in h.split('class="product-item-box"')[1:]:
            href = grab(r'class="product-item-link"\s+href="([^"]+)"', b)
            pid = grab(r'data-product-id="(\d+)"', b) or href
            if not href or pid in seen:
                continue
            seen.add(pid)
            new += 1
            title = clean(grab(r'class="product-item-link"[^>]*>(.*?)</a>', b))
            title = re.sub(r"^Occasion\s*-\s*", "", title)
            final = grab(r'data-price-amount="([\d.]+)"\s+data-price-type="finalPrice"', b)
            old = grab(r'data-price-amount="([\d.]+)"\s+data-price-type="oldPrice"', b)
            category, motor = classify_listing("", title)
            out.append({
                "id": f"ae-{pid}",
                "source": "airsoft-entrepot.fr",
                "title": title,
                "price": float(final) if final else None,
                "price_new": float(old) if old and old != final else None,
                "url": href,
                "image": grab(r'class="product-image-photo"[^>]*src="([^"]+)"', b),
                "region": None,
                "location": "Boutique en ligne",
                "category": category,
                "subcategory": "Occasions",
                "motor": motor,
                "condition": clean(grab(r'class="sidebar-state">\s*<span>(.*?)</span>', b)) or "Occasion",
                "seller": "boutique",
                "kind": "offre",
                "date": None,
                "date_text": "",
            })
        log(f"airsoft-entrepot.fr page {p}: {new} articles")
        if not new:  # Magento renvoie la dernière page quand on dépasse
            break
        time.sleep(DELAY)
    return out


# --- ops-store.fr (rubrique Reconditionné « OPS-REFURB ») ---------------------

def scrape_ops_store(pages=20, log=print):
    out, seen = [], set()
    for p in range(1, pages + 1):
        url = "https://www.ops-store.fr/reconditionne-c1483.html" + (f"?numPage={p}" if p > 1 else "")
        try:
            h = fetch(url)
        except Exception as e:
            log(f"ops-store.fr page {p}: {e}")
            break
        new = 0
        for b in h.split('<div class="product_box')[1:]:
            href = grab(r'href="(https://www\.ops-store\.fr/[^"]*-a(\d+)\.html)"', b)
            pid = grab(r'-a(\d+)\.html"', b)
            if not href or pid in seen:
                continue
            seen.add(pid)
            new += 1
            title = clean(grab(r'class="bp_designation">(.*?)</h3>', b))
            prices = re.findall(r'([\d\s]+,\d{2})\s*&euro;', grab(r'class="bp_prix">(.*?)<!-- END PRICE -->', b) or "")
            category, motor = classify_listing("", title)
            out.append({
                "id": f"ops-{pid}",
                "source": "ops-store.fr",
                "title": title,
                "price": parse_price(prices[0]) if prices else None,
                "price_new": parse_price(prices[1]) if len(prices) > 1 else None,
                "url": href,
                "image": grab(r'<img[^>]*src="([^"]+)"', b),
                "region": None,
                "location": "Boutique en ligne",
                "category": category,
                "subcategory": "Reconditionné",
                "motor": motor,
                "condition": "Reconditionné",
                "seller": "boutique",
                "kind": "offre",
                "date": None,
                "date_text": "",
            })
        log(f"ops-store.fr page {p}: {new} articles reconditionnés")
        if not new:
            break
        time.sleep(DELAY)
    return out


# Nombre maximal de pages lues par site : les collecteurs s'arrêtent d'eux-mêmes à la dernière page.
# NaturaBuy mélange neuf et occasion sans filtre dans l'adresse : toutes les pages de répliques sont lues,
# seulement le début des autres rubriques (voir NB_CATS).
DEFAULT_PAGES = {
    "airsoft-occasion.fr": 300,
    "occasion-airsoft.fr": 300,
    "naturabuy.fr": 300,
    "airsoft-entrepot.fr": 50,
    "ops-store.fr": 20,
}

SOURCES = {
    "airsoft-occasion.fr": scrape_airsoft_occasion,
    "occasion-airsoft.fr": scrape_occasion_airsoft,
    "naturabuy.fr": scrape_naturabuy,
    "airsoft-entrepot.fr": scrape_airsoft_entrepot,
    "ops-store.fr": scrape_ops_store,
}
