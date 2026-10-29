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

#### Mise à jour vraiment horaire (cron-job.org)

GitHub retarde ou saute souvent ses tâches planifiées sur les comptes gratuits : sa propre planification
ne sert que de secours (toutes les 2 heures). Le rythme horaire vient de cron-job.org, qui demande à GitHub
de lancer la mise à jour :

1. GitHub → photo → **Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token** : accès au seul dépôt `airsoft-occaz`, permission **Actions : Read and write**.
2. cron-job.org → **Create cronjob** : URL
   `https://api.github.com/repos/<compte>/airsoft-occaz/actions/workflows/update.yml/dispatches`,
   toutes les heures ; onglet **Advanced** : méthode **POST**, en-têtes `Authorization: Bearer <clé>`,
   `Accept: application/vnd.github+json`, corps `{"ref":"main"}`. Un « Test run » doit répondre **204**.
3. Quand la clé expire, cron-job.org signale des erreurs 401 : en créer une nouvelle et la remplacer.
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

## Comptes (facultatif) : favoris et alertes sur tous les appareils

Sans configuration, le site fonctionne sans connexion (tout reste dans le navigateur de chaque appareil).
Avec un projet Firebase gratuit, un bouton 👤 permet de se connecter (Google ou e-mail + mot de passe) :
favoris (avec suivi de prix), alertes et annonces masquées sont alors synchronisés en direct.

1. https://console.firebase.google.com → **Créer un projet** (Google Analytics inutile).
2. **Authentication → Commencer → Sign-in method** : activer **Google** et **Adresse e-mail/Mot de passe**.
3. **Authentication → Paramètres → Domaines autorisés** : ajouter `votre-nom.github.io`.
4. **Firestore Database → Créer une base de données** (emplacement en Europe, mode production),
   puis onglet **Règles** : coller le contenu de `firestore.rules` → **Publier**.
5. **Paramètres du projet → Vos applications → Web (</>)** : enregistrer l'app, copier l'objet `firebaseConfig`.
6. Dans `static/firebase-config.js`, remplacer `null` par cet objet.

Chaque compte ne peut lire et modifier que ses propres données (règles Firestore). À la première connexion
sur un appareil, ce qui y était enregistré est ajouté au compte ; à la déconnexion, l'appareil est vidé.

## Alertes

Réglez vos filtres puis touchez **🔔 Créer une alerte**. À chaque visite, le bouton 🔔 indique le nombre de
nouvelles annonces correspondant à vos alertes ; « Voir » réapplique les filtres de l'alerte.
Les alertes sont enregistrées dans le navigateur (et dans le compte si vous êtes connecté) ; pas de notification sur le téléphone.

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
