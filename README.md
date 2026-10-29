# Airsoft Occaz

Web app qui regroupe les annonces airsoft d'occasion de plusieurs sites français, avec filtres et tri.
Elle s'installe sur l'iPhone comme une vraie app (icône sur l'écran d'accueil, plein écran, hors ligne).

## Deux façons de l'utiliser

### 1. Depuis le Mac (et l'iPhone sur le même Wi-Fi)

```
python3 server.py
```

- Mac : http://localhost:8765
- iPhone : l'adresse s'affiche au démarrage (`Sur l'iPhone (même Wi-Fi) → http://192.168.x.x:8765`).
  Ouvrez-la dans Safari → bouton Partager → **Sur l'écran d'accueil**.

Le Mac doit rester allumé avec le serveur lancé. `--local` limite l'accès à ce Mac uniquement.

### 2. En ligne, accessible partout (gratuit, GitHub Pages)

Le workflow `.github/workflows/update.yml` collecte les annonces toutes les heures et publie le site,
sans Mac allumé ni compte Claude.

1. Sur github.com, créer un dépôt **public** (Pages et les minutes d'Actions sont gratuits pour un dépôt public),
   par exemple `airsoft-occaz`, sans README.
2. Page du dépôt → **uploading an existing file** → glisser **tout le contenu** du dossier
   `a-envoyer-sur-github` (dans le Finder, ⌘⇧. affiche le dossier caché `.github`, indispensable)
   → **Commit changes**.
3. **Settings → Pages → Build and deployment → Source : GitHub Actions**.
4. **Actions → Mise à jour des annonces → Run workflow** (la première collecte prend ~10 min).
5. Ouvrir `https://<votre-compte>.github.io/airsoft-occaz/` sur le Mac et l'iPhone
   (Safari → Partager → Sur l'écran d'accueil).

Le bouton « Actualiser » est masqué en ligne : les annonces se mettent à jour toutes seules.
GitHub suspend les tâches planifiées d'un dépôt public resté 60 jours sans modification. Pour l'éviter,
la mise à jour écrit la date dans `maintenance.txt` une fois par mois (début du mois). Si elle était
quand même suspendue : onglet Actions → « Mise à jour des annonces » → « Enable workflow ».

## Sources

| Site | Ce qui est récupéré |
|---|---|
| airsoft-occasion.fr | annonces de particuliers (offres et recherches), département → région |
| occasion-airsoft.fr | annonces de particuliers, état, région |
| naturabuy.fr | rubriques Airsoft, **annonces marquées « occasion » uniquement** |
| airsoft-entrepot.fr | rubrique **Occasions** de la boutique (état, prix neuf barré) |
| ops-store.fr | rubrique **Reconditionné (OPS-REFURB)** : neuf à emballage abîmé / micro-défauts |
| peew.fr | toutes les annonces de particuliers (pas de date de publication) |
| airsoftone.fr | les 24 annonces les plus récentes de chaque rubrique (le reste se charge en JavaScript) |
| zn-airsoft.fr | rubrique **Les occasions** de la boutique ZN Airsoft (testées avant vente) |

Liens directs seulement (lecture automatique bloquée, compte requis ou annonces chargées en JavaScript) : Leboncoin, Phénix Airsoft, Airsoft-Occas, JR Soft, France-Airsoft
(forum Occaz), Vinted, eBay, Facebook Marketplace.

## Alertes

Réglez vos filtres puis touchez **🔔 Créer une alerte**. À chaque visite, le bouton 🔔 indique le nombre de
nouvelles annonces correspondant à vos alertes ; « Voir » réapplique les filtres de l'alerte.
Les alertes sont enregistrées dans le navigateur de chaque appareil (pas de notification sur le téléphone).

## Fonctionnement

- **Marque** et **modèle** sont reconnus dans le titre ; **bonne affaire** = au moins 30 % sous le prix médian
  des annonces comparables (même modèle, même motorisation, même marque si possible), pièces et lots exclus.
- **Distance** : code postal ou 📍, à partir de la ville (airsoft-occasion.fr, Peew) ou du département
  (AirsoftOne). occasion-airsoft.fr, NaturaBuy et les boutiques en ligne n'ont pas de position précise.
- **Doublons** : même titre et même prix sur deux sites = une seule carte « Aussi sur … ».
- **Surveillance** : si un site renvoie soudain moins de la moitié de ses annonces, les anciennes sont
  gardées et le site est marqué ⚠️ dans le filtre Site (la raison s'affiche au survol).

- Cache local dans `data/annonces.json` ; nouvelle collecte au démarrage si le cache a plus de 30 min,
  ou via « Actualiser ».
- Catégorie (réplique longue, poing, sniper…) et motorisation (AEG, GBB, HPA…) sont déduites de la
  rubrique du site et du titre : elles peuvent parfois se tromper.
- Filtre Vendeur : « Boutiques » = zones occasion des magasins + vendeurs pros de NaturaBuy.
- Page **Favoris** (bouton ♥ en haut, ou lien `#favoris`) : suivi du prix depuis l'ajout, annonces retirées du site
  gardées et signalées « Plus en ligne ». Favoris, annonces masquées et filtres sont enregistrés dans le
  navigateur de chaque appareil.
- Ajouter un site : écrire une fonction `scrape_xxx(pages, log)` dans `scrapers.py` qui renvoie des
  annonces au même format, puis l'ajouter à `SOURCES`.

Collectes espacées (0,5 s entre deux pages). Si un site change sa mise en page, son collecteur devra
être adapté ; un site en panne n'empêche pas les autres de fonctionner.
