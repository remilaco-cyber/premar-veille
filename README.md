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

## Second outil : veille des textes réglementaires (`veille_textes/`)

Distinct du scraper PREMAR ci-dessus. Il couvre tous les autres textes utilisés par
l'application (pêche professionnelle, RIPAM, pêche de loisir...) et fonctionne
différemment : il ne republie JAMAIS de contenu applicatif automatiquement, car un texte
réglementaire exige une relecture humaine avant toute modification du code de l'appli. Il se
contente de **signaler** qu'un texte mérite d'être revérifié.

- `veille_textes/instruments.json` : la liste des textes suivis (titre, URL source, type).
- `veille_textes/check_updates.py` : à chaque exécution, met à jour cette liste et ajoute des
  entrées dans `veille_textes/alertes.json` quand un texte doit être revérifié.
- `.github/workflows/veille_textes.yml` : exécute ce script chaque lundi à 4h et republie les
  deux fichiers JSON s'ils ont changé.
- L'application lit `veille_textes/alertes.json` (menu *Options → Veille des textes
  réglementaires*) et affiche chaque alerte avec un choix "Corrigé dans l'appli ?" (oui/non,
  non par défaut) que l'utilisateur coche lui-même une fois la mise à jour faite.

**Limite importante, à savoir avant d'utiliser cet outil** : Légifrance (protection
Cloudflare) et EUR-Lex (protection AWS WAF) bloquent tous les deux les requêtes automatiques
simples avec une page de vérification JavaScript — il n'existe donc **aucun moyen fiable de
détecter automatiquement un vrai changement de contenu** sur ces deux sites sans passer par
leurs API officielles (PISTE pour Légifrance, service Cellar pour EUR-Lex), qui demandent
chacune la création d'un compte séparé. En attendant une éventuelle intégration de ces API,
les textes hébergés sur Légifrance/EUR-Lex utilisent un **rappel par échéance** : le script
signale simplement qu'un texte n'a pas été revérifié depuis plus de `rappel_jours` jours (180
pour les règlements européens, 365 pour le reste, 300 pour l'arrêté annuel thon rouge) — ce
n'est pas une détection de changement réel, juste un rappel périodique fiable à 100 %.

Seul le PDF du RIPAM (hébergé sur ffvoile.fr, sans protection anti-robot) bénéficie d'une
vraie détection de changement par empreinte de contenu (`verification_auto: true` dans
`instruments.json`).

### Lancer manuellement en local

```
pip install -r requirements.txt
python veille_textes/check_updates.py
```
