"""
Veille des textes réglementaires utilisés par l'application SEACONTROL.

Contrairement au scraper PREMAR (scraper.py), cet outil ne met JAMAIS à jour le contenu de
l'application automatiquement : les textes réglementaires (Code rural, règlements européens,
arrêtés...) demandent une relecture humaine avant toute modification du code de l'appli. Ce
script se contente de signaler qu'un texte "mérite d'être revérifié", dans data/alertes.json,
que l'application lit pour afficher une liste avec un choix oui/non par texte (non coché par
défaut) que l'utilisateur coche lui-même une fois la vérification/mise à jour faite dans l'appli.

DEUX mécanismes de détection, selon la source :

1. verification_auto = true (empreinte de contenu) — utilisé uniquement pour le PDF RIPAM
   (hébergé sans protection anti-robot). Le script télécharge le fichier, calcule une empreinte
   SHA-256 et la compare à la dernière connue : empreinte différente => alerte.

   IMPORTANT : Légifrance (Cloudflare) et EUR-Lex (AWS WAF) renvoient tous les deux une page de
   défi JavaScript ("Just a moment...", code 403/202) à toute requête HTTP simple — ce que fait
   ce script. Il n'existe donc PAS de moyen fiable de détecter automatiquement un changement de
   contenu sur ces deux sites sans passer par leurs API officielles (PISTE pour Légifrance,
   service web Cellar pour EUR-Lex), qui demandent chacune un compte et une clé d'accès. Tant que
   ces intégrations ne sont pas faites, ces sources utilisent le mécanisme n°2 ci-dessous.

2. verification_auto = false (rappel par échéance) — le script regarde simplement depuis combien
   de temps la source n'a pas été revérifiée manuellement (last_checked) ; si ce délai dépasse
   rappel_jours (défini par instrument dans instruments.json), une alerte "à revérifier" est
   créée. Ce n'est pas une détection de changement réel, seulement un rappel périodique — mais
   c'est fiable à 100 %, contrairement à une tentative de contournement des protections
   anti-robot des deux sites.
"""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup  # noqa: F401 — conservé pour une future intégration API/HTML

ICI = Path(__file__).parent
FICHIER_INSTRUMENTS = ICI / "instruments.json"
FICHIER_ALERTES = ICI / "alertes.json"

EN_TETE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def empreinte_pdf(url: str) -> str:
    reponse = requests.get(url, headers=EN_TETE, timeout=60)
    reponse.raise_for_status()
    return hashlib.sha256(reponse.content).hexdigest()


def verifier_par_empreinte(instrument: dict) -> dict | None:
    try:
        nouvelle_empreinte = empreinte_pdf(instrument["url"])
    except Exception as exc:  # noqa: BLE001
        print(f"[ERREUR] {instrument['id']} ({instrument['url']}) : {exc}", file=sys.stderr)
        return None

    ancienne_empreinte = instrument.get("last_hash")
    instrument["last_hash"] = nouvelle_empreinte
    instrument["last_checked"] = maintenant_iso()

    if ancienne_empreinte is None:
        print(f"[BASELINE] {instrument['id']} : empreinte initiale enregistrée")
        return None

    if ancienne_empreinte != nouvelle_empreinte:
        print(f"[CHANGEMENT DÉTECTÉ] {instrument['id']}")
        return alerte_pour(instrument, motif="Le contenu du document a changé.")

    print(f"[INCHANGÉ] {instrument['id']}")
    return None


def verifier_par_echeance(instrument: dict) -> dict | None:
    rappel_jours = instrument.get("rappel_jours", 365)
    dernier_controle = instrument.get("last_checked")

    if dernier_controle is None:
        # Premher passage : on part du principe qu'il vient d'être ajouté/vérifié à l'instant.
        instrument["last_checked"] = maintenant_iso()
        print(f"[BASELINE] {instrument['id']} : échéance initialisée")
        return None

    date_dernier_controle = datetime.strptime(dernier_controle, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    echeance = date_dernier_controle + timedelta(days=rappel_jours)

    if datetime.now(timezone.utc) >= echeance:
        instrument["last_checked"] = maintenant_iso()
        print(f"[ÉCHÉANCE DÉPASSÉE] {instrument['id']}")
        return alerte_pour(
            instrument,
            motif=f"Pas revérifié depuis plus de {rappel_jours} jours (vérification "
                  f"automatique impossible sur cette source — Légifrance/EUR-Lex bloquent le "
                  f"scraping).",
        )

    print(f"[OK] {instrument['id']} : prochaine échéance {echeance.date()}")
    return None


def alerte_pour(instrument: dict, motif: str) -> dict:
    return {
        "instrument_id": instrument["id"],
        "titre": instrument["titre"],
        "domaine": instrument["domaine"],
        "url": instrument["url"],
        "motif": motif,
        "date_detection": instrument["last_checked"],
        "traite": False,
    }


def maintenant_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    instruments = json.loads(FICHIER_INSTRUMENTS.read_text(encoding="utf-8"))
    alertes_existantes = []
    if FICHIER_ALERTES.exists():
        alertes_existantes = json.loads(FICHIER_ALERTES.read_text(encoding="utf-8"))

    nouvelles_alertes = []
    for instrument in instruments:
        if instrument.get("verification_auto"):
            alerte = verifier_par_empreinte(instrument)
        else:
            alerte = verifier_par_echeance(instrument)
        if alerte is not None:
            nouvelles_alertes.append(alerte)

    # On ne duplique pas une alerte pour un instrument déjà signalé et non traité.
    ids_deja_signales_non_traites = {
        a["instrument_id"] for a in alertes_existantes if not a.get("traite", False)
    }
    alertes_a_ajouter = [
        a for a in nouvelles_alertes if a["instrument_id"] not in ids_deja_signales_non_traites
    ]

    toutes_les_alertes = alertes_existantes + alertes_a_ajouter

    FICHIER_INSTRUMENTS.write_text(
        json.dumps(instruments, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    FICHIER_ALERTES.write_text(
        json.dumps(toutes_les_alertes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{len(alertes_a_ajouter)} nouvelle(s) alerte(s), {len(toutes_les_alertes)} au total.")


if __name__ == "__main__":
    main()
