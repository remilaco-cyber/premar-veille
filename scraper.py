"""
Veille automatique des arrêtés du préfet maritime de la Méditerranée en vigueur
pour l'Hérault (departement=41) et le Gard (departement=39).

Reproduit fidèlement le format de app/src/main/assets/arretes_premar_seed.json de
l'application SEACONTROL, pour que la sortie de ce script puisse être importée
telle quelle par ArretePremarRepository.importerDepuisJson().

Le site est rendu côté serveur (vérifié : le HTML brut contient déjà les
".arrete-box" sans JavaScript), donc un simple scraping par requests suffit —
pas besoin de navigateur headless.
"""

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.premar-mediterranee.gouv.fr"
LISTING_PATH = "/arretes"

# Hérault et Gard uniquement — seul périmètre demandé pour l'application.
DEPARTEMENTS = [41, 39]

HEADERS = {"User-Agent": "Mozilla/5.0 (SEACONTROL-veille-premar; +usage interne agent)"}

MOIS = {
    "janv": 1, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def sans_accents(texte: str) -> str:
    normalise = unicodedata.normalize("NFD", texte)
    return "".join(c for c in normalise if unicodedata.category(c) != "Mn")


def date_iso(date_affichage: str) -> str:
    # Ex: "4 sept. 2026" / "5 août 2026" / "1 juin 2026"
    parts = date_affichage.replace(".", "").split()
    jour, mois_texte, annee = int(parts[0]), parts[1], int(parts[2])
    cle = sans_accents(mois_texte.lower())
    mois = MOIS.get(cle)
    if mois is None:
        raise ValueError(f"Mois inconnu : '{mois_texte}' (date brute : '{date_affichage}')")
    return f"{annee:04d}-{mois:02d}-{jour:02d}"


def parser_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    resultats = []
    for box in soup.select(".arrete-box"):
        numero_tag = box.select_one("span.lead.font-weight-bold")
        if not numero_tag:
            continue
        numero = numero_tag.get_text(strip=True)

        entete = box.select_one(".d-flex.justify-content-between.flex-wrap p") or box.find("p")
        date_match = re.search(r"Date de signature\s*:\s*([^\n<]+)", entete.get_text(" ", strip=True)) if entete else None
        date_affichage = date_match.group(1).strip() if date_match else ""

        departements = [d.get_text(strip=True) for d in box.select(".acte-depts .dept")]

        contenu = box.select_one(".acte-content")
        # Le HTML source imbrique parfois des <p> les uns dans les autres (balisage
        # invalide) ; html.parser ne les auto-ferme pas comme un navigateur, donc
        # find_all("p") renvoie aussi le <p> englobant (texte dupliqué). On ne garde
        # que les <p> "feuilles", sans <p> descendant.
        paragraphes = (
            [p.get_text(" ", strip=True) for p in contenu.find_all("p") if not p.find("p")]
            if contenu else []
        )
        paragraphes = [p for p in paragraphes if p]
        titre = paragraphes[0] if paragraphes else ""
        note = " ".join(paragraphes[1:]) if len(paragraphes) > 1 else None

        lien_pdf = box.select_one("a.pm-btn")
        pdf_href = lien_pdf["href"] if lien_pdf and lien_pdf.has_attr("href") else None

        if not (numero and date_affichage and pdf_href):
            continue

        resultats.append({
            "numero": numero,
            "dateSignature": date_iso(date_affichage),
            "dateAffichage": date_affichage,
            "departements": departements,
            "titre": titre,
            "note": note,
            "pdfUrl": BASE_URL + pdf_href,
            "texteExtrait": None,
        })
    return resultats


def recuperer_departement(code: int) -> list[dict]:
    tous = []
    page = 1
    while True:
        url = (
            f"{BASE_URL}{LISTING_PATH}?departement={code}&thematique=&numero=&motcle="
            f"&envigueur=on&select-annee=&sort=a.dateSignature&direction=desc&page={page}"
        )
        reponse = requests.get(url, headers=HEADERS, timeout=20)
        reponse.raise_for_status()
        items = parser_page(reponse.text)
        if not items:
            break
        tous.extend(items)
        page += 1
        time.sleep(1)  # discret vis-à-vis du site source
    return tous


def fusionner(listes: list[list[dict]]) -> list[dict]:
    par_numero: dict[str, dict] = {}
    for liste in listes:
        for item in liste:
            existant = par_numero.get(item["numero"])
            if existant is None:
                par_numero[item["numero"]] = item
            else:
                fusion = list(dict.fromkeys(existant["departements"] + item["departements"]))
                existant["departements"] = fusion
    return sorted(par_numero.values(), key=lambda x: x["dateSignature"], reverse=True)


def main() -> None:
    listes = [recuperer_departement(code) for code in DEPARTEMENTS]
    final = fusionner(listes)

    if len(final) < 20:
        # Garde-fou : si le site change de structure, mieux vaut échouer bruyamment
        # que publier une liste vide/tronquée qui écraserait les données de l'appli.
        print(f"ERREUR : seulement {len(final)} arrêtés récupérés, structure probablement changée.", file=sys.stderr)
        sys.exit(1)

    sortie = Path(__file__).parent / "data" / "arretes_premar.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(final)} arrêtés écrits dans {sortie}")


if __name__ == "__main__":
    main()
