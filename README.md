# Veille PREMAR — SEACONTROL

Dépôt technique séparé de l'application Android SEACONTROL. Son seul rôle :
maintenir à jour, gratuitement et automatiquement, la liste des arrêtés du
préfet maritime de la Méditerranée en vigueur pour l'Hérault et le Gard,
consultée par l'application (menu *Aide au contrôle → Plaisance → Arrêtés
Préfet maritime*).

## Fonctionnement

- `scraper.py` récupère la liste sur premar-mediterranee.gouv.fr (filtre
  "en vigueur", départements Hérault et Gard) et écrit `data/arretes_premar.json`.
- Le workflow GitHub Actions (`.github/workflows/veille.yml`) exécute ce
  script chaque lundi à 3h du matin et republie le fichier automatiquement
  s'il a changé. Il peut aussi être lancé manuellement depuis l'onglet
  *Actions* du dépôt GitHub (bouton *Run workflow*).
- Coût : nul. Un dépôt GitHub public + GitHub Actions sont gratuits, et
  `data/arretes_premar.json` est servi gratuitement via
  `raw.githubusercontent.com` — pas d'hébergement à payer.

## URL utilisée par l'application

```
https://raw.githubusercontent.com/<votre-compte>/<nom-du-depot>/main/data/arretes_premar.json
```

À renseigner dans l'application une fois ce dépôt publié sur GitHub (voir
l'échange avec Claude pour la marche à suivre exacte).

## Lancer manuellement en local

```
pip install -r requirements.txt
python scraper.py
```
