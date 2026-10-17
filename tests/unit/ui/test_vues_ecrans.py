"""Vues JSON de la carte, du détail et des livrables, et leurs routes (Story 7.14, AD-25)."""

import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Literal

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.unit.ui.test_detail import (
    DATE,
    _explication,
    _meteo,
    _narration,
    _prevision,
    _regle,
    _risque,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_pourcentage
from usine.contrats.llm import SortieExplication, SortieNarration, StatutControle
from usine.contrats.meteo import CodeIndicateur, Couleur, EvolutionMeteo, MeteoEntite
from usine.contrats.passage import Etape, ExecutionEtape, ManifestePassage, StatutEtape
from usine.contrats.prevision import Prevision, RisqueEntreeRouge, StatutPrevision
from usine.ports.consultation import Consultation
from usine.ui import carte, detail
from usine.ui.cli import application_web, lecture_consultation
from usine.ui.detail import EXPLICATION_PALIER_1, vue_detail
from usine.ui.liens import vue_ticket
from usine.ui.serveur import HOTE, LectureEcrans, creer_application
from usine.ui.textes import REPLI_ABSENT

NomLivrable = Literal["rapport_xlsx", "rapport_pptx"]
XLSX = b"PK\x03\x04xlsx" + bytes(2000)


def _url(cle: str) -> str:
    return f"https://jira.example.invalid/browse/{cle}"


class _Double:
    """`Consultation` figée : ENT-A verte, ENT-B rouge (5 tickets), ENT-C orange."""

    def __init__(
        self,
        *,
        palier: Literal[1, 2] = 2,
        avec_url: bool = True,
        livrables: dict[str, bytes] | None = None,
        meteos: tuple[MeteoEntite, ...] | None = None,
        prevision_calculee: bool = True,
    ) -> None:
        self.palier = palier
        self.avec_url = avec_url
        self.fichiers = {"rapport_xlsx": XLSX} if livrables is None else livrables
        cinq = tuple(f"DEMO-{n}" for n in range(1, 6))
        orange = _meteo("ENT-C", regles=(_regle(CodeIndicateur.ind_3, ("DEMO-9",)),))
        orange = orange.model_copy(update={"couleur": Couleur.orange})
        self.meteos = (
            meteos
            if meteos is not None
            else (
                _meteo("ENT-A"),
                _meteo("ENT-B", regles=(_regle(CodeIndicateur.ind_2, cinq),)),
                orange,
            )
        )
        self.prevision_calculee = prevision_calculee
        self.appels_palier: list[int] = []

    def manifeste(self) -> ManifestePassage:
        instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
        etapes = (
            (
                ExecutionEtape(
                    etape=Etape.prevision,
                    statut=StatutEtape.reussie,
                    horodatage_debut=instant,
                    horodatage_fin=instant,
                ),
            )
            if self.prevision_calculee
            else ()
        )
        return ManifestePassage(
            passage_id="20261012T073000Z-aaaaaa",
            date_arrete=DATE,
            palier=self.palier,
            source="journal",
            horodatage_debut=instant,
            horodatage_fin=instant,
            version_grille="abc",
            version_donnees="def",
            cout_llm_eur=Decimal(0),
            nb_alignements=0,
            nb_tickets=0,
            etapes=etapes,
        )

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        return self.meteos

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        return ()

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "date": [DATE, DATE],
                "perimetre": ["ENT-B", "ENT-B"],
                "code_kpi": ["anomalies_ouvertes", "taux_ko_cas_de_test"],
                "dimension": ["", "tnr"],
                "numerateur": [40, 1],
                "denominateur": [1, 4],
            }
        )

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        return (_prevision(StatutPrevision.sortie_projetee, "ENT-B"),)

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        return (_risque("ENT-C"),)

    def explications(
        self, entite: str | None = None, palier: Literal[1, 2] = 2
    ) -> tuple[SortieExplication, ...]:
        self.appels_palier.append(palier)
        if palier == 1:
            return ()
        texte = "ENT-B est rouge : DEMO-1 bloque la recette."
        return (_explication(texte=texte, citations=("DEMO-1", "DEMO-2")),)

    def narrations(
        self, entite: str | None = None, palier: Literal[1, 2] = 2
    ) -> tuple[SortieNarration, ...]:
        if palier == 1:
            return ()
        return (_narration(StatutControle.conforme, "ENT-B"),)

    def url_ticket(self, cle: str) -> str | None:
        return _url(cle) if self.avec_url else None

    def livrable(self, nom: NomLivrable) -> bytes | None:
        return self.fichiers.get(nom)


def client(double: _Double | None = None, *, repli: bool = False) -> TestClient:
    consultation = _Double() if double is None else double
    application = creer_application(
        repli=repli, lire_manifeste=lambda _repli: None, lire_consultation=lambda _: consultation
    )
    return TestClient(application, base_url=f"http://{HOTE}")


# --- Carte ---


def test_lecture_vue_carte_alignee_sur_le_port() -> None:
    port = {nom for nom, _ in inspect.getmembers(Consultation, inspect.isfunction)}
    for nom in ("manifeste", "meteo", "evolution_meteo", "url_ticket", "livrable"):
        assert nom in port
        assert hasattr(carte.LectureVueCarte, nom)
    assert isinstance(LectureEcrans, type)


def test_carte_tri_comptages_et_lignes() -> None:
    vue = client().get("/api/carte").json()
    assert [ligne["entite"] for ligne in vue["lignes"]] == ["ENT-B", "ENT-C", "ENT-A"]
    assert [(c["meteo"]["couleur"], c["nombre"]) for c in vue["comptages"]] == [
        ("rouge", 1),
        ("orange", 1),
        ("jaune", 0),
        ("vert", 1),
    ]
    premiere = vue["lignes"][0]
    assert premiere["meteo"] == {"couleur": "rouge", "libelle": "Rouge"}
    assert premiere["regle_principale"] == "IND-2 : 11 (seuil ≥ 10)"
    assert [t["cle"] for t in premiere["tickets"]] == ["DEMO-1", "DEMO-2", "DEMO-3"]
    assert premiere["tickets_restants"] == 2
    assert premiere["url_detail"] == "/entites/ENT-B"
    assert premiere["libelle_detail"] == "Détail ENT-B"
    assert vue["sous_titre"] == "Date d'arrêté : 09/10/2026"
    assert vue["legende"] == carte.LEGENDE
    assert vue["vide"] == "—"


def test_carte_filtre_et_annonces() -> None:
    filtre = client().get("/api/carte").json()["filtre"]
    assert filtre["libelle"] == "Filtrer par météo"
    assert [o["valeur"] for o in filtre["options"]] == [
        "toutes",
        "rouge",
        "orange",
        "jaune",
        "vert",
    ]
    assert filtre["annonce_une"] == "1 Entité affichée"
    assert filtre["annonce_plusieurs"] == "{n} Entités affichées"
    jaune = next(o for o in filtre["options"] if o["valeur"] == "jaune")
    assert jaune["message_vide"] == "Aucune Entité en jaune à cette Date d'arrêté."


def test_carte_tickets_liens_ou_texte_simple() -> None:
    avec = client().get("/api/carte").json()["lignes"][0]["tickets"][0]
    assert avec == {
        "cle": "DEMO-1",
        "url": _url("DEMO-1"),
        "nom_accessible": "DEMO-1 (nouvel onglet)",
    }
    sans = client(_Double(avec_url=False)).get("/api/carte").json()["lignes"][0]["tickets"][0]
    assert sans == {"cle": "DEMO-1", "url": None, "nom_accessible": None}
    assert vue_ticket("A", None).nom_accessible is None


def test_carte_livrables_presents_et_absents() -> None:
    xlsx, pptx = client().get("/api/carte").json()["livrables"]
    assert xlsx["url"] == "/livrables/rapport_xlsx"
    assert xlsx["fichier"] == "rapport-2026-10-09.xlsx"
    assert xlsx["libelle"] == "Rapport quotidien"
    assert xlsx["description"] == "Excel (.xlsx) · 2 Ko"
    assert xlsx["absent"] is None
    assert pptx["libelle"] == "Comité de pilotage"
    assert pptx["url"] is None
    assert pptx["absent"] == "Non généré pour ce Passage"
    assert pptx["description"] == ""


def test_taille_lisible() -> None:
    assert carte.taille_lisible(512) == "512 o"
    assert carte.taille_lisible(34842) == "34 Ko"
    assert carte.taille_lisible(1_300_000) == "1,2 Mo"


def test_carte_sans_meteo() -> None:
    vue_vide = client(_Double(meteos=())).get("/api/carte").json()
    assert vue_vide["message"] == carte.AUCUNE_METEO
    assert vue_vide["lignes"] == []
    assert vue_vide["livrables"] == []


def test_carte_sans_passage_et_erreurs() -> None:
    def aucun(_repli: bool) -> None:
        return None

    http = TestClient(creer_application(repli=False, lire_manifeste=aucun, lire_consultation=aucun))
    vue = http.get("/api/carte").json()
    assert vue["message"] == carte.AUCUN_PASSAGE
    assert vue["lien_message"] == {"libelle": "Lancer la Chaîne", "url": "/chaine"}

    def casse(_repli: bool) -> LectureEcrans:
        raise UsineErreur("manifeste illisible")

    def illisible(_repli: bool) -> LectureEcrans:
        raise PermissionError(13, "accès refusé", "sorties/passages")

    for lire, attendu in ((casse, "manifeste illisible"), (illisible, "Lecture du Passage")):
        application = creer_application(repli=False, lire_manifeste=aucun, lire_consultation=lire)
        reponse = TestClient(application).get("/api/carte")
        assert reponse.status_code == 200
        assert attendu in reponse.json()["erreur"]
        assert reponse.json()["message"] is None


# --- Détail ---


def test_detail_palier_2_complet() -> None:
    vue = client().get("/api/entites/ENT-B").json()
    assert vue["entite"] == "ENT-B"
    assert vue["palier"] == 2
    assert [e["libelle"] for e in vue["entites"]] == ["ENT-B", "ENT-C", "ENT-A"]
    assert vue["lien_carte"] == {"libelle": "← Carte météo", "url": "/"}
    assert [(o["valeur"], o["actif"]) for o in vue["segment_palier"]["options"]] == [
        (2, True),
        (1, False),
    ]
    assert vue["segment_palier"]["legende"] == "Palier 1 : la même Entité sans aucune sortie LLM."
    assert vue["meteo"]["couleur"] == "rouge"
    (regle,) = vue["regles"]
    assert regle["regle"] == "IND-2 : 11 (seuil ≥ 10)"
    assert len(regle["tickets"]) == 5
    assert regle["visibles"] == 3
    assert [(k["libelle"], k["valeur"]) for k in vue["kpi"]] == [
        ("Anomalies ouvertes", "40"),
        ("Taux KO des Cas de test (tnr)", formater_pourcentage(Fraction(1, 4))),
    ]
    assert vue["prevision"]["blocs"][0]["texte"] is not None  # narration conforme
    assert vue["risque"]["message"] == detail.RISQUE_SANS_OBJET
    (explication,) = vue["explication"]["explications"]
    assert [s["ticket"]["cle"] if s["ticket"] else None for s in explication["segments"]] == [
        None,
        "DEMO-1",
        None,
    ]
    assert [t["cle"] for t in explication["citations"]] == ["DEMO-1", "DEMO-2"]
    assert explication["statut_code"] == "corrige"
    assert explication["phrases_retirees"] == "Phrases retirées au contrôle : 1"
    assert "".join(s["texte"] for s in explication["segments"]) == (
        "ENT-B est rouge : DEMO-1 bloque la recette."
    )


def test_detail_palier_1_sur_passage_palier_2() -> None:
    http = client()
    deux = http.get("/api/entites/ENT-B?palier=2").json()
    un = http.get("/api/entites/ENT-B?palier=1").json()
    assert un["palier"] == 1
    assert un["explication"]["message"] == EXPLICATION_PALIER_1
    assert un["explication"]["explications"] == []
    assert un["prevision"] is None
    assert deux["prevision"] is not None
    for bloc in ("meteo", "regles", "kpi", "risque"):
        assert un[bloc] == deux[bloc]
    assert [(o["valeur"], o["actif"]) for o in un["segment_palier"]["options"]] == [
        (2, False),
        (1, True),
    ]
    assert http.get("/api/entites/ENT-B?palier=abc").json()["palier"] == 2


def test_detail_passage_palier_1_sans_segment() -> None:
    double = _Double(palier=1)
    vue = client(double).get("/api/entites/ENT-B?palier=2").json()
    assert vue["segment_palier"] is None
    assert vue["palier"] == 1
    assert vue["explication"]["message"] == EXPLICATION_PALIER_1
    assert vue["prevision"] is not None  # Prévision brute : pas une sortie LLM
    assert double.appels_palier == [1]


def test_detail_entite_absente() -> None:
    vue = client().get("/api/entites/ENT-INCONNUE").json()
    assert vue["message"] == "Entité ENT-INCONNUE absente du Passage affiché."
    assert vue["lien_message"] == {"libelle": "Voir la carte météo", "url": "/"}
    assert vue["meteo"] is None
    assert len(vue["entites"]) == 3


def test_detail_entite_verte_et_non_calcule() -> None:
    vue = client().get("/api/entites/ENT-A").json()
    assert vue["aucune_regle"] == detail.AUCUNE_REGLE
    assert vue["regles"] == []
    assert vue["prevision"]["message"] == detail.PREVISION_SANS_OBJET
    sans_calcul = client(_Double(prevision_calculee=False)).get("/api/entites/ENT-C").json()
    assert sans_calcul["prevision"]["message"] == detail.PREVISION_NON_CALCULEE_PASSAGE
    assert sans_calcul["risque"]["message"] == detail.RISQUE_NON_CALCULE_PASSAGE


def test_detail_risque_tableau() -> None:
    vue = client().get("/api/entites/ENT-C").json()
    tableau = vue["risque"]["tableau"]
    assert tableau["colonnes"][0] == "Indicateur"
    assert tableau["lignes"][0][0] == "IND-1"
    assert vue["risque"]["message"] is None


def test_detail_mode_repli_cles_en_texte_simple() -> None:
    vue = client(_Double(avec_url=False), repli=True).get("/api/entites/ENT-B").json()
    assert all(t["url"] is None for t in vue["regles"][0]["tickets"])
    explication = vue["explication"]["explications"][0]
    assert all(s["ticket"]["url"] is None for s in explication["segments"] if s["ticket"])


def test_detail_explication_rejetee() -> None:
    class _Rejetee(_Double):
        def explications(
            self, entite: str | None = None, palier: Literal[1, 2] = 2
        ) -> tuple[SortieExplication, ...]:
            return (_explication(texte="Explication indisponible.", statut=StatutControle.rejete),)

    (explication,) = (
        client(_Rejetee()).get("/api/entites/ENT-B").json()["explication"]["explications"]
    )
    assert explication["segments"] == [{"texte": "Explication indisponible.", "ticket": None}]
    assert explication["citations"] == []
    assert explication["phrases_retirees"] is None
    assert explication["statut_code"] == "rejete"


def test_detail_entite_a_caracteres_speciaux() -> None:
    double = _Double(meteos=(_meteo("ENT A&é"),))
    vue = client(double).get("/api/entites/ENT%20A%26%C3%A9").json()
    assert vue["entite"] == "ENT A&é"
    assert vue["entites"][0]["url"] == "/entites/ENT%20A%26%C3%A9"


def test_detail_sans_passage_ni_meteo_et_erreur() -> None:
    def aucun(_repli: bool) -> None:
        return None

    http = TestClient(creer_application(repli=False, lire_manifeste=aucun, lire_consultation=aucun))
    vue = http.get("/api/entites/ENT-A").json()
    assert vue["message"] == carte.AUCUN_PASSAGE
    assert vue["lien_message"]["url"] == "/chaine"
    sans = client(_Double(meteos=())).get("/api/entites/ENT-A").json()
    assert sans["message"] == carte.AUCUNE_METEO

    def casse(_repli: bool) -> LectureEcrans:
        raise UsineErreur("manifeste illisible")

    erreur = TestClient(
        creer_application(repli=False, lire_manifeste=aucun, lire_consultation=casse)
    ).get("/api/entites/ENT-A")
    assert erreur.json()["erreur"] == "manifeste illisible"


def test_vue_detail_directe() -> None:
    vue = vue_detail(_Double(), "ENT-B", 1)
    assert vue.palier == 1
    assert vue.prevision is None


# --- Navigation « Détail d'une Entité » ---


def test_navigation_detail_premiere_entite_du_tableau() -> None:
    reponse = client().get("/entites", follow_redirects=False)
    assert reponse.status_code == 307
    assert reponse.headers["location"] == "/entites/ENT-B"


def test_navigation_detail_sans_passage_retourne_a_la_carte() -> None:
    def aucun(_repli: bool) -> None:
        return None

    http = TestClient(creer_application(repli=False, lire_manifeste=aucun, lire_consultation=aucun))
    assert http.get("/entites", follow_redirects=False).headers["location"] == "/"

    def casse(_repli: bool) -> LectureEcrans:
        raise UsineErreur("illisible")

    cassee = TestClient(
        creer_application(repli=False, lire_manifeste=aucun, lire_consultation=casse)
    )
    assert cassee.get("/entites", follow_redirects=False).headers["location"] == "/"


# --- Livrables ---


def test_livrable_telechargement() -> None:
    reponse = client().get("/livrables/rapport_xlsx")
    assert reponse.status_code == 200
    assert reponse.content == XLSX
    assert reponse.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert reponse.headers["content-disposition"] == (
        'attachment; filename="rapport-2026-10-09.xlsx"'
    )
    assert client().head("/livrables/rapport_xlsx").status_code == 200


def test_livrable_pptx_type_mime() -> None:
    double = _Double(livrables={"rapport_pptx": b"PK\x03\x04"})
    reponse = client(double).get("/livrables/rapport_pptx")
    assert reponse.headers["content-type"].endswith("presentationml.presentation")
    assert 'filename="rapport-2026-10-09.pptx"' in reponse.headers["content-disposition"]


def test_livrable_absent_page_d_erreur() -> None:
    reponse = client().get("/livrables/rapport_pptx")
    assert reponse.status_code == 404
    assert reponse.headers["content-type"].startswith("text/html")
    assert "rapport-2026-10-09.pptx" in reponse.text
    assert 'href="/"' in reponse.text
    assert "attachment" not in reponse.headers.get("content-disposition", "")


def test_livrable_nom_hors_liste() -> None:
    for nom in ("manifeste", "..%2Fsecret", "rapport_docx", "RAPPORT_XLSX"):
        assert client().get(f"/livrables/{nom}").status_code == 404


def test_livrable_sans_passage_et_lecture_impossible() -> None:
    def aucun(_repli: bool) -> None:
        return None

    http = TestClient(creer_application(repli=False, lire_manifeste=aucun, lire_consultation=aucun))
    reponse = http.get("/livrables/rapport_xlsx")
    assert reponse.status_code == 404
    assert "rapport_xlsx" in reponse.text

    class _Illisible(_Double):
        def livrable(self, nom: NomLivrable) -> bytes | None:
            raise UsineErreur("fichier illisible <b>&")

    erreur = client(_Illisible()).get("/livrables/rapport_xlsx")
    assert erreur.status_code == 500
    assert "rapport-2026-10-09.xlsx" in erreur.text
    assert "&lt;b&gt;&amp;" in erreur.text  # message échappé


# --- Lecture réelle par les services de `ui/cli.py` ---


def test_application_reelle_carte_detail_livrables(racine_publiee: Path) -> None:
    http = TestClient(application_web(racine_publiee, False), base_url=f"http://{HOTE}")
    vue = http.get("/api/carte").json()
    assert vue["lignes"]
    assert [livrable["url"] for livrable in vue["livrables"]] == [
        "/livrables/rapport_xlsx",
        "/livrables/rapport_pptx",
    ]
    for ligne in vue["lignes"]:
        for ticket in ligne["tickets"]:
            assert ticket["url"].endswith(f"/browse/{ticket['cle']}")
    entite = vue["lignes"][0]["entite"]
    assert http.get(f"/api/entites/{entite}").json()["entite"] == entite
    xlsx = http.get("/livrables/rapport_xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"


def test_application_repli_livrables_de_la_copie(racine_publiee: Path) -> None:
    http = TestClient(application_web(racine_publiee, True), base_url=f"http://{HOTE}")
    vue = http.get("/api/carte").json()
    assert all(livrable["url"] for livrable in vue["livrables"])
    assert all(t["url"] is None for ligne in vue["lignes"] for t in ligne["tickets"])
    assert http.get("/livrables/rapport_pptx").status_code == 200


def test_application_repli_absent(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="introuvable"):
        lecture_consultation(tmp_path)(True)
    http = TestClient(application_web(tmp_path, True), base_url=f"http://{HOTE}")
    assert http.get("/api/carte").json()["erreur"] == REPLI_ABSENT
    assert http.get("/livrables/rapport_xlsx").status_code == 500


def test_lecture_consultation_sans_passage(tmp_path: Path) -> None:
    assert lecture_consultation(tmp_path)(False) is None


# --- Script sans innerHTML pour les données ---


@pytest.mark.parametrize("script", ["carte.js", "detail.js"])
def test_scripts_sans_innerhtml_ni_url_externe(script: str) -> None:
    texte = client().get(f"/statique/{script}").text
    assert "innerHTML" not in texte
    assert "http://" not in texte
    assert "https://" not in texte


def test_pages_chargent_leur_script() -> None:
    assert "/statique/carte.js" in client().get("/").text
    assert "/statique/detail.js" in client().get("/entites/ENT-B").text
    assert 'role="status"' in client().get("/").text
    assert 'href="/entites"' in client().get("/").text
