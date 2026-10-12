"""Page Streamlit (`AppTest`) : bandeau, navigation, carte, détail, lancement, avant / après,
outillage."""

import re
import shutil
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import IO, Any, cast

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

from tests.unit.ui.test_avant_apres import manifeste, publier
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_date, formater_pourcentage
from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import Etape, EvenementProgression, ManifestePassage, StatutEtape
from usine.contrats.prevision import (
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.ui import avant_apres, cli, detail, lancement, outillage
from usine.ui.carte import formater_regle, tendance
from usine.ui.cli import consultation_dernier_passage, mode_repli
from usine.ui.liens import echapper_markdown
from usine.ui.navigation import STORY_A_VENIR, Ecran
from usine.ui.progression import AUCUN_RAPPORT, texte_duree

REPERTOIRE_UI = Path(lancement.__file__).parent
APP = REPERTOIRE_UI / "app.py"
LIEN = re.compile(r"\[((?:\\.|[^\]\\])+)\]\(([^)]+)\)")


def _page(ecran: Ecran = Ecran.carte) -> AppTest:
    page = AppTest.from_file(str(APP), default_timeout=60).run()
    if ecran is not Ecran.carte:
        _aller(page, ecran)
    return page


def _aller(page: AppTest, ecran: Ecran) -> None:
    """Un clic dans la navigation latérale."""
    page.sidebar.radio[0].set_value(ecran.value).run()


def _textes(page: AppTest) -> str:
    return "\n".join(str(m.value) for m in page.markdown)


def _tableau(page: AppTest) -> str:
    """Tableau Markdown de la carte météo (une seule occurrence attendue)."""
    (tableau,) = [str(m.value) for m in page.markdown if str(m.value).startswith("| Entité |")]
    return tableau


def _entites(tableau: str) -> list[str]:
    return [ligne.split("|")[1].strip() for ligne in tableau.splitlines()[2:]]


def _sans_tableau(page: AppTest) -> bool:
    return not any(str(m.value).startswith("| Entité |") for m in page.markdown)


def _bandeau_en_tete(page: AppTest) -> bool:
    premier = page.main.children[0]
    return getattr(premier, "type", None) == "warning" and "Mode repli" in str(
        getattr(premier, "value", "")
    )


def test_carte_meteo(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page()
    assert not page.exception
    assert not page.warning
    assert page.sidebar.radio[0].value == Ecran.carte.value  # écran par défaut
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    tableau = _tableau(page)
    assert _entites(tableau) == [m.entite for m in consultation.meteo()]
    for ligne, meteo in zip(tableau.splitlines()[2:], consultation.meteo(), strict=True):
        assert LIBELLES_COULEURS[meteo.couleur] in ligne.split("|")[2]
    evolutions = {e.entite: e for e in consultation.evolution_meteo()}
    for ligne, meteo in zip(tableau.splitlines()[2:], consultation.meteo(), strict=True):
        assert tendance(evolutions[meteo.entite]) in ligne
    assert "09/10/2026" in page.caption[0].value
    assert "aggravation" in page.caption[1].value  # légende des flèches
    assert [bouton.label for bouton in page.button] == ["Détail ENT-A", "Détail ENT-B"]


def test_liens_jira_de_la_carte(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page()
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    tableau = _tableau(page)
    cellules = [ligne.split("|")[5] for ligne in tableau.splitlines()[2:]]
    texte_visible = re.sub(r"\]\([^)]*\)", "]", " ".join(cellules))  # sans les destinations
    visibles = re.findall(r"[A-Z]+-\d+", texte_visible)
    liens = LIEN.findall(tableau)
    assert visibles
    assert visibles == [cle for cle, _ in liens]  # chaque clé visible est un lien
    for cle, url in liens:
        assert url == consultation.url_ticket(cle)
        assert url.endswith(f"/browse/{cle}")


def test_carte_en_mode_repli(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    page = _page()
    assert not page.exception
    assert _bandeau_en_tete(page)
    tableau = _tableau(page)
    assert "](http" not in tableau
    assert "DEMO-" in tableau


@pytest.mark.parametrize("ecran", list(Ecran))
def test_navigation(ecran: Ecran, racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    page = _page(ecran)
    assert not page.exception
    assert not page.error
    assert _bandeau_en_tete(page)
    assert page.sidebar.radio[0].value == ecran.value
    assert page.sidebar.radio[0].options == [e.value for e in Ecran]
    if ecran is Ecran.carte:
        assert _tableau(page)
    else:
        assert _sans_tableau(page)
    if ecran is Ecran.lancement:
        assert page.subheader[-1].value == "Chaîne de reporting"
        assert page.button[0].label == "Lancer la Chaîne"
    elif ecran is Ecran.detail:
        assert page.subheader[0].value == ecran.value
        assert detail.EXPLICATION_PALIER_1 in _textes(page)
        assert not page.info  # plus un emplacement
    elif ecran is Ecran.avant_apres:
        assert page.subheader[0].value == ecran.value
        assert _tableau_avant_apres(page)
        assert not page.info  # plus un emplacement
    elif ecran is Ecran.outillage:
        assert page.subheader[0].value == ecran.value
        assert _fiche(page) == _fiche_attendue(racine_publiee)
        assert not page.info  # plus un emplacement
    elif ecran is not Ecran.carte:
        assert page.subheader[0].value == ecran.value
        assert f"Story {STORY_A_VENIR[ecran]}" in page.info[-1].value


def test_bouton_entite(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page()
    page.button(key="detail_ENT-B").click().run()  # un seul clic
    assert not page.exception
    assert page.sidebar.radio[0].value == Ecran.detail.value
    assert page.selectbox[0].value == "ENT-B"
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    (meteo_b,) = consultation.meteo(entite="ENT-B")
    assert LIBELLES_COULEURS[meteo_b.couleur] in _textes(page)
    assert detail.EXPLICATION_PALIER_1 in _textes(page)
    page.selectbox[0].set_value("ENT-A").run()
    assert not page.exception
    assert page.selectbox[0].value == "ENT-A"
    _aller(page, Ecran.carte)
    page.button(key="detail_ENT-B").click().run()
    assert page.selectbox[0].value == "ENT-B"


def _tableau_regles(page: AppTest) -> str:
    (tableau,) = [str(m.value) for m in page.markdown if str(m.value).startswith("| Règle |")]
    return tableau


def test_detail_entite_rouge(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page()
    page.button(key="detail_ENT-A").click().run()
    assert not page.exception
    assert not page.error
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    (meteo_a,) = consultation.meteo(entite="ENT-A")
    assert meteo_a.regles
    tableau = _tableau_regles(page)
    liens = LIEN.findall(tableau)
    for regle in meteo_a.regles:
        assert formater_regle(regle) in tableau
    attendus = [cle for regle in meteo_a.regles for cle in regle.tickets_en_cause]
    assert [cle for cle, _ in liens] == attendus  # chaque ticket en cause, en lien
    for cle, url in liens:
        assert url == consultation.url_ticket(cle)
    textes = _textes(page)
    for ligne in detail.lignes_kpi(consultation.kpi(entite="ENT-A")):
        assert f"| {ligne['KPI']} | {ligne['Valeur']} |" in textes
    (prevision,) = consultation.previsions(entite="ENT-A")  # Prévision réelle (Story 5.3)
    if prevision.statut is StatutPrevision.regle_non_projetable:
        codes = ", ".join(c.value for c in prevision.regles_non_projetables)
        assert f"règle non projetable ({codes})" in textes
    elif prevision.statut is StatutPrevision.pas_de_sortie_projetee:
        assert detail.PAS_DE_SORTIE in textes
    else:
        assert prevision.date_sortie_estimee is not None
        assert formater_date(prevision.date_sortie_estimee) in textes
    assert prevision.facteurs
    for facteur in prevision.facteurs:
        assert echapper_markdown(facteur.libelle) in textes
    assert detail.PREVISION_NON_CALCULEE_PASSAGE not in textes
    assert detail.RISQUE_SANS_OBJET in textes
    assert detail.EXPLICATION_PALIER_1 in textes


def test_detail_en_mode_repli(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    page = _page()
    page.button(key="detail_ENT-A").click().run()
    assert not page.exception
    assert _bandeau_en_tete(page)
    assert "DEMO-" in _tableau_regles(page)
    assert "](http" not in _textes(page)


class _Doublure:
    """`Consultation` réelle, avec Prévision pour ENT-A, Risque et Météo orange pour ENT-B."""

    def __init__(self, reelle: Any, palier: int = 1) -> None:
        self._reelle = reelle
        self._palier = palier
        manifeste = reelle.manifeste()
        self._jour = manifeste.date_arrete

    def __getattr__(self, nom: str) -> Any:
        return getattr(self._reelle, nom)

    def manifeste(self) -> ManifestePassage:
        manifeste: ManifestePassage = self._reelle.manifeste()
        return manifeste.model_copy(update={"palier": self._palier})

    def meteo(self, date_arrete: Any = None, entite: str | None = None) -> tuple[MeteoEntite, ...]:
        orange = MeteoEntite(
            date_arrete=self._jour,
            entite="ENT-B",
            couleur=Couleur.orange,
            regles=(
                RegleDeclenchante(
                    code=CodeIndicateur.ind_1,
                    couleur=Couleur.orange,
                    operateur=Operateur.superieur_ou_egal,
                    numerateur=6,
                    denominateur=1,
                    seuil_numerateur=5,
                    seuil_denominateur=1,
                    tickets_en_cause=("DEMO-10",),
                ),
            ),
            version_grille="abc",
        )
        meteos = tuple(
            orange if m.entite == "ENT-B" else m for m in self._reelle.meteo(date_arrete)
        )
        return tuple(m for m in meteos if entite is None or m.entite == entite)

    def previsions(self, date_arrete: Any = None, entite: str | None = None) -> tuple[Any, ...]:
        prevision = Prevision(
            date_arrete=self._jour,
            entite="ENT-A",
            methode=MethodePrevision.baseline,
            statut=StatutPrevision.sortie_projetee,
            date_sortie_estimee=self._jour + timedelta(days=11),
            date_sortie_optimiste=self._jour + timedelta(days=7),
            date_sortie_pessimiste=self._jour + timedelta(days=14),
            probabilite_numerateur=3,
            probabilite_denominateur=4,
            horizon_jours_ouvres=10,
            facteurs=(
                FacteurExplicatif(
                    nom="stock", libelle="Stock d'Anomalies", numerateur=2, denominateur=1
                ),
            ),
            version_grille="abc",
        )
        return tuple(p for p in (prevision,) if entite is None or p.entite == entite)

    def risques(self, date_arrete: Any = None, entite: str | None = None) -> tuple[Any, ...]:
        risque = RisqueEntreeRouge(
            date_arrete=self._jour,
            entite="ENT-B",
            indicateur=CodeIndicateur.ind_1,
            date_franchissement_estimee=self._jour + timedelta(days=6),
            horizon_jours_ouvres=10,
            numerateur=6,
            denominateur=1,
            seuil_numerateur=10,
            seuil_denominateur=1,
            version_grille="abc",
            valeur_projetee_numerateur=11,
            valeur_projetee_denominateur=1,
        )
        return tuple(r for r in (risque,) if entite is None or r.entite == entite)


def _avec_doublure(
    monkeypatch: pytest.MonkeyPatch, palier: int = 1, classe: type[_Doublure] | None = None
) -> _Doublure:
    reelle = consultation_dernier_passage(Path.cwd())
    assert reelle is not None
    doublure = (classe or _Doublure)(reelle, palier)
    monkeypatch.setattr(cli, "consultation_dernier_passage", lambda _racine: doublure)
    return doublure


def test_detail_avec_prevision_et_risque(
    racine_publiee: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    doublure = _avec_doublure(monkeypatch)
    page = _page()
    page.button(key="detail_ENT-A").click().run()
    assert not page.exception
    textes = _textes(page)
    (prevision,) = doublure.previsions(entite="ENT-A")
    assert formater_date(prevision.date_sortie_estimee) in textes
    fourchette = (
        f"{formater_date(prevision.date_sortie_optimiste)}"
        f" – {formater_date(prevision.date_sortie_pessimiste)}"
    )
    assert fourchette in textes
    assert formater_pourcentage(Fraction(3, 4)) in textes
    assert "Stock d'Anomalies : 2" in textes
    assert detail.RISQUE_SANS_OBJET in textes

    page.selectbox[0].set_value("ENT-B").run()
    assert not page.exception
    textes = _textes(page)
    (risque,) = doublure.risques(entite="ENT-B")
    assert "| IND-1 | 6 | 10 |" in textes
    assert "10 jours ouvrés | 11 |" in textes  # valeur projetée (contrats 1.1)
    assert formater_date(risque.date_franchissement_estimee) in textes
    assert "10 jours ouvrés" in textes
    assert detail.PREVISION_SANS_OBJET in textes


class _DoublureNonCalculee(_Doublure):
    """Passage dont l'étape `prevision` est sautée : rien n'est publié."""

    def manifeste(self) -> ManifestePassage:
        manifeste = super().manifeste()
        etapes = tuple(
            e.model_copy(update={"statut": StatutEtape.sautee}) if e.etape is Etape.prevision else e
            for e in manifeste.etapes
        )
        return manifeste.model_copy(update={"etapes": etapes})

    def previsions(self, date_arrete: Any = None, entite: str | None = None) -> tuple[Any, ...]:
        return ()

    def risques(self, date_arrete: Any = None, entite: str | None = None) -> tuple[Any, ...]:
        return ()


def test_detail_prevision_non_calculee(
    racine_publiee: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    _avec_doublure(monkeypatch, classe=_DoublureNonCalculee)
    page = _page()
    page.button(key="detail_ENT-B").click().run()
    assert not page.exception
    textes = _textes(page)
    assert detail.PREVISION_NON_CALCULEE_PASSAGE in textes
    assert detail.RISQUE_NON_CALCULE_PASSAGE in textes


class _DoublureVerte(_Doublure):
    """ENT-B verte : aucune Règle déclenchante."""

    def meteo(self, date_arrete: Any = None, entite: str | None = None) -> tuple[MeteoEntite, ...]:
        return tuple(
            m.model_copy(update={"couleur": Couleur.vert, "regles": ()})
            if m.entite == "ENT-B"
            else m
            for m in super().meteo(date_arrete, entite)
        )


def test_detail_entite_verte(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    _avec_doublure(monkeypatch, classe=_DoublureVerte)
    page = _page()
    page.button(key="detail_ENT-B").click().run()
    assert not page.exception
    textes = _textes(page)
    assert detail.AUCUNE_REGLE in textes
    assert detail.PREVISION_SANS_OBJET in textes


class _DoublureIllisible(_Doublure):
    """`meteo.json` lisible, `previsions.json` illisible."""

    def previsions(self, date_arrete: Any = None, entite: str | None = None) -> tuple[Any, ...]:
        raise UsineErreur("previsions.json illisible")


def test_detail_lecture_entite_illisible(
    racine_publiee: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    _avec_doublure(monkeypatch, classe=_DoublureIllisible)
    page = _page()
    page.button(key="detail_ENT-A").click().run()
    assert not page.exception
    assert any("Lecture du dernier Passage impossible" in e.value for e in page.error)
    assert detail.EXPLICATION_PALIER_1 not in _textes(page)


def test_detail_palier_2(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    _avec_doublure(monkeypatch, palier=2)
    page = _page(Ecran.detail)
    assert not page.exception
    textes = _textes(page)
    assert detail.EXPLICATION_PALIER_2 in textes
    assert detail.EXPLICATION_PALIER_1 not in textes


def test_racine_introuvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absente = tmp_path / "absente"
    monkeypatch.setenv("USINE_RACINE", str(absente))
    page = _page()
    assert not page.exception
    assert any(str(absente) in erreur.value for erreur in page.error)
    assert not page.info
    _aller(page, Ecran.lancement)
    assert not page.exception
    assert page.button[0].disabled


def test_sans_passage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    page = _page()
    assert not page.exception
    assert "Aucun Passage publié" in page.info[0].value
    assert _sans_tableau(page)
    assert not page.button
    _aller(page, Ecran.detail)
    assert not page.exception
    assert "Aucun Passage publié" in page.info[0].value
    assert not page.selectbox


def test_mode_repli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    assert mode_repli(tmp_path)
    page = _page()
    assert "Mode repli" in page.warning[0].value
    assert _bandeau_en_tete(page)


def test_racine_par_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("USINE_MODE_REPLI=1\n", encoding="utf-8")
    monkeypatch.setenv("USINE_RACINE", str(tmp_path))
    page = _page()
    assert "Mode repli" in page.warning[0].value


def test_mode_repli_illisible(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-etre")
    page = _page(Ecran.lancement)
    assert not page.exception
    assert not page.warning
    assert any("USINE_MODE_REPLI" in erreur.value for erreur in page.error)
    assert page.subheader[-1].value == "Chaîne de reporting"  # le lancement reste affiché
    assert not page.button[0].disabled


def test_passage_illisible(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(racine_publiee / "sorties" / "passages", tmp_path / "sorties" / "passages")
    for meteo in (tmp_path / "sorties" / "passages").glob("*/*/meteo.json"):
        meteo.write_text("{illisible", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    page = _page()
    assert not page.exception
    assert "Lecture du dernier Passage impossible" in page.error[0].value
    assert _sans_tableau(page)
    _aller(page, Ecran.detail)
    assert not page.exception
    assert "Lecture du dernier Passage impossible" in page.error[0].value


class _ProcessusFactice:
    def __init__(self) -> None:
        self.code: int | None = None

    def poll(self) -> int | None:
        return self.code


class _Lanceur:
    """`Popen` factice : note chaque appel et écrit `message` dans l'erreur standard reçue."""

    def __init__(self, message: str = "") -> None:
        self.processus = _ProcessusFactice()
        self.appels: list[tuple[list[str], dict[str, Any]]] = []
        self.message = message

    def __call__(self, commande: list[str], **options: Any) -> _ProcessusFactice:
        self.appels.append((commande, options))
        erreurs: IO[bytes] = options["stderr"]
        erreurs.write(self.message.encode("utf-8"))
        return self.processus

    @property
    def erreurs(self) -> IO[bytes]:
        fichier: IO[bytes] = self.appels[-1][1]["stderr"]
        return fichier


def _installer(monkeypatch: pytest.MonkeyPatch, lanceur: Any) -> None:
    monkeypatch.setattr(
        lancement,
        "lancer_chaine",
        partial(lancement.lancer_chaine, popen=cast(lancement.Lanceur, lanceur)),
    )


def _ligne(etape: Etape, statut: StatutEtape, secondes: float = 0.0) -> str:
    instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC) + timedelta(seconds=secondes)
    evenement = EvenementProgression(
        passage_id="20261012T073000Z-aaaaaa", etape=etape, statut=statut, horodatage=instant
    )
    return evenement.model_dump_json() + "\n"


def test_lancement_et_progression(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur("Erreur : étape kpi en échec")
    _installer(monkeypatch, lanceur)
    ancien = tmp_path / "sorties" / "progression" / "20261008T070000Z-111111.jsonl"
    ancien.parent.mkdir(parents=True)
    ancien.write_text(_ligne(Etape.extraction, StatutEtape.echouee), encoding="utf-8")

    page = _page(Ecran.lancement)
    page.button[0].click().run()
    assert not page.exception
    ((commande, options),) = lanceur.appels
    assert commande[1:] == ["-m", "usine", "rapport"]
    assert options["cwd"] == tmp_path
    assert page.button[0].disabled
    assert "**extraction** : En attente" in _textes(page)

    nouveau = ancien.with_name("20261012T073000Z-aaaaaa.jsonl")
    nouveau.write_text(
        _ligne(Etape.extraction, StatutEtape.en_cours)
        + _ligne(Etape.extraction, StatutEtape.reussie, 0.5)
        + _ligne(Etape.instantanes, StatutEtape.en_cours, 0.5)
        + '{"partielle',
        encoding="utf-8",
    )
    page.run()
    lignes = _textes(page).splitlines()
    assert "- **extraction** : Réussie (0,5 s)" in lignes
    assert "- **instantanes** : En cours" in lignes
    assert "- **kpi** : En attente" in lignes

    lanceur.processus.code = 1
    page.run()
    assert not page.exception
    assert "étape kpi en échec" in page.error[0].value
    assert page.error[0].value.startswith("Échec de la Chaîne hors d'une étape (code 1) : ")
    assert any(info.value == AUCUN_RAPPORT for info in page.info)
    assert not page.button[0].disabled
    assert lanceur.erreurs.closed


def test_lancement_succes(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    lanceur = _Lanceur()
    lanceur.processus.code = 0
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    assert not page.exception
    assert "Chaîne terminée" in page.success[0].value
    assert lanceur.erreurs.closed
    # carte du dernier Passage sous le succès, sans changer d'écran
    assert page.sidebar.radio[0].value == Ecran.lancement.value
    assert page.subheader[-1].value == "Carte météo du dernier Passage"
    assert "09/10/2026" in page.caption[0].value
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]
    assert not any(info.value == AUCUN_RAPPORT for info in page.info)
    page.run()
    assert not page.exception
    assert len(lanceur.appels) == 1
    _aller(page, Ecran.carte)
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]
    assert page.sidebar.success[0].value == "Dernier lancement : Passage publié."


def _racine_copiee(racine_publiee: Path, tmp_path: Path) -> Path:
    """Copie du Passage d'essai : les tests qui y écrivent une progression restent isolés."""
    shutil.copytree(racine_publiee / "sorties" / "passages", tmp_path / "sorties" / "passages")
    return tmp_path


def _progression(racine: Path, *lignes: str) -> None:
    fichier = racine / "sorties" / "progression" / "20261012T073000Z-aaaaaa.jsonl"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text("".join(lignes), encoding="utf-8")


def test_echec_nomme_sans_carte(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = _racine_copiee(racine_publiee, tmp_path)
    monkeypatch.chdir(racine)
    lanceur = _Lanceur("Erreur : division par zéro")
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    _progression(
        racine,
        _ligne(Etape.extraction, StatutEtape.en_cours),
        _ligne(Etape.extraction, StatutEtape.reussie, 0.3),
        _ligne(Etape.instantanes, StatutEtape.en_cours, 0.3),
        _ligne(Etape.instantanes, StatutEtape.reussie, 0.4),
        _ligne(Etape.kpi, StatutEtape.en_cours, 0.4),
        _ligne(Etape.kpi, StatutEtape.echouee, 1.4),
    )
    lanceur.processus.code = 1
    page.run()
    assert not page.exception
    (erreur,) = page.error
    assert erreur.value == (
        "Échec de la Chaîne à l'étape « kpi » (code 1) : Erreur : division par zéro"
    )
    lignes = _textes(page).splitlines()
    assert "- **extraction** : Réussie (0,3 s)" in lignes
    assert "- **kpi** : Échec (1 s)" in lignes
    assert [info.value for info in page.info] == [AUCUN_RAPPORT]
    assert _sans_tableau(page)
    assert page.subheader[-1].value == "Chaîne de reporting"
    _aller(page, Ecran.carte)  # la carte reste celle du dernier Passage publié
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]
    assert page.sidebar.error[0].value == "Dernier lancement en échec à l'étape « kpi »."


def test_resume_lateral_et_relance_unique(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = _racine_copiee(racine_publiee, tmp_path)
    monkeypatch.chdir(racine)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    assert not page.sidebar.info  # aucun lancement dans cette session : aucun résumé
    page.button[0].click().run()
    _aller(page, Ecran.carte)
    assert not page.exception
    assert page.sidebar.info[0].value == "Chaîne en cours…"
    _progression(racine, _ligne(Etape.extraction, StatutEtape.en_cours))
    page.run()
    assert page.sidebar.info[0].value == "Chaîne en cours : étape « extraction »"
    _progression(
        racine,
        _ligne(Etape.extraction, StatutEtape.en_cours),
        _ligne(Etape.extraction, StatutEtape.reussie, 0.5),
    )
    page.run()
    assert "étape « extraction »" not in page.sidebar.info[0].value  # étape déjà finie
    assert page.sidebar.info[0].value == "Chaîne en cours…"
    _progression(
        racine,
        _ligne(Etape.extraction, StatutEtape.en_cours),
        _ligne(Etape.extraction, StatutEtape.reussie, 0.5),
        _ligne(Etape.instantanes, StatutEtape.en_cours, 0.5),
    )
    page.run()
    assert page.sidebar.info[0].value == "Chaîne en cours : étape « instantanes »"
    assert page.sidebar.radio[0].value == Ecran.carte.value

    relances: list[object] = []
    monkeypatch.setattr(streamlit, "rerun", lambda *args, **kwargs: relances.append(args))
    lanceur.processus.code = 0
    page.run()
    assert not page.exception
    assert len(relances) == 1
    assert lanceur.erreurs.closed
    assert page.sidebar.success[0].value == "Dernier lancement : Passage publié."
    page.run()
    assert len(relances) == 1
    assert page.sidebar.radio[0].value == Ecran.carte.value  # l'écran ne change pas
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]


def test_resume_lateral_progression_invalide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    _aller(page, Ecran.carte)
    _progression(tmp_path, '{"etape": "inconnue"}\n')
    page.run()
    assert not page.exception
    assert page.sidebar.info[0].value == "Chaîne en cours…"


def test_resume_lateral_relit_la_carte(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    _aller(page, Ecran.carte)
    assert "Aucun Passage publié" in page.main.info[0].value
    _racine_copiee(racine_publiee, tmp_path)  # le sous-processus publie son Passage
    lanceur.processus.code = 0
    page.run()  # fin vue par le résumé latéral : relance réelle de la page
    assert not page.exception
    assert page.sidebar.success[0].value == "Dernier lancement : Passage publié."
    assert page.sidebar.radio[0].value == Ecran.carte.value
    assert "09/10/2026" in page.caption[0].value
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]


def test_resume_lateral_echec_hors_etape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur("Erreur : configuration illisible")
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    _aller(page, Ecran.detail)
    lanceur.processus.code = 2
    page.run()
    assert not page.exception
    assert page.sidebar.error[0].value == "Dernier lancement en échec hors d'une étape."
    assert lanceur.erreurs.closed
    _aller(page, Ecran.lancement)
    assert page.error[0].value == (
        "Échec de la Chaîne hors d'une étape (code 2) : Erreur : configuration illisible"
    )
    assert not page.sidebar.error  # pas de résumé latéral sur l'écran Lancement


def test_rerun_unique_en_fin_de_chaine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    assert "Chaîne en cours" in page.info[-1].value
    relances: list[object] = []
    monkeypatch.setattr(streamlit, "rerun", lambda *args, **kwargs: relances.append(args))
    lanceur.processus.code = 0
    page.run()
    assert len(relances) == 1
    page.run()
    assert len(relances) == 1


def test_erreur_tronquee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur("".join(f"trace {n:02d}\n" for n in range(30)))
    lanceur.processus.code = 1
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    message = page.error[0].value
    assert "trace 29" in message
    assert "trace 10" in message
    assert "trace 09" not in message


def test_progression_invalide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    fichier = tmp_path / "sorties" / "progression" / "20261012T073000Z-aaaaaa.jsonl"
    fichier.parent.mkdir(parents=True)
    fichier.write_text('{"etape": "inconnue"}\n', encoding="utf-8")
    page.run()
    assert not page.exception
    assert any(fichier.name in erreur.value and "ligne 1" in erreur.value for erreur in page.error)


def test_pas_de_second_lancement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page(Ecran.lancement)  # bouton encore actif dans cet onglet périmé
    page.session_state["processus"] = _ProcessusFactice()  # Chaîne déjà en cours
    page.session_state["racine_lancement"] = tmp_path
    page.session_state["fichiers_avant"] = frozenset()
    page.button[0].click().run()
    assert not page.exception
    assert lanceur.appels == []


def test_lancement_impossible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def popen(commande: list[str], **_options: Any) -> Any:
        raise FileNotFoundError(2, "répertoire introuvable", str(tmp_path / "absent"))

    _installer(monkeypatch, popen)
    page = _page(Ecran.lancement)
    page.button[0].click().run()
    assert not page.exception
    assert "Lancement de la Chaîne impossible" in page.error[0].value
    assert not page.button[0].disabled


def test_ui_sans_acces_interdit() -> None:
    interdits = ("entrepot.duckdb", ".en-cours", "duckdb")
    for chemin in sorted(REPERTOIRE_UI.glob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        assert [m for m in interdits if m in texte] == [], chemin.name


# --- Avant / après (Story 7.4) ---


def _tableau_avant_apres(page: AppTest) -> list[str]:
    """Lignes du tableau avant / après (une seule occurrence attendue), ou liste vide."""
    tableaux = [str(m.value) for m in page.markdown if str(m.value).startswith("| Rapport |")]
    assert len(tableaux) <= 1
    return tableaux[0].splitlines() if tableaux else []


def _demo(
    racine: Path, contenu: str = "# Temps manuel.\ntemps_manuel_minutes_par_rapport: 120\n"
) -> None:
    (racine / "config").mkdir(parents=True, exist_ok=True)
    (racine / "config" / "demo.yaml").write_text(contenu, encoding="utf-8")


def test_avant_apres_passage_publie(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    assert not page.error
    assert not page.warning
    mesure, _ = cli.manifestes_avant_apres(racine_publiee)
    assert mesure is not None
    duree = avant_apres.duree_mesuree(mesure)
    lignes = _tableau_avant_apres(page)
    assert lignes[0] == "| Rapport | Reporting manuel (déclaré) | Chaîne (mesuré) |"
    assert lignes[2] == f"| Par Rapport quotidien | 120 min | {texte_duree(duree)} |"
    assert lignes[3] == f"| Cumulé sur 5 Rapports | 600 min | {texte_duree(duree * 5)} |"
    legende = page.caption[0].value
    assert "09/10/2026" in legende
    assert mesure.passage_id in legende
    assert avant_apres.MENTION_FICTIVE in legende


def test_avant_apres_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _demo(tmp_path)
    publier(tmp_path, manifeste(3.4))
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    assert _tableau_avant_apres(page)[2:] == [
        "| Par Rapport quotidien | 120 min | 3,4 s |",
        "| Cumulé sur 5 Rapports | 600 min | 17 s |",
    ]
    assert "20261012T073000Z-aaaaaa" in page.caption[0].value


def test_avant_apres_classification_initiale_plus_recente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo(tmp_path)
    publier(
        tmp_path,
        manifeste(2.0, passage_id="20261011T073000Z-bbbbbb", date_arrete=date(2026, 10, 8)),
    )
    publier(tmp_path, manifeste(9.0, classification_initiale=True))
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    assert not page.warning
    assert _tableau_avant_apres(page)[2] == "| Par Rapport quotidien | 120 min | 2 s |"
    assert "20261011T073000Z-bbbbbb" in page.caption[0].value
    assert "08/10/2026" in page.caption[0].value


def test_avant_apres_seule_classification_initiale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo(tmp_path)
    publier(tmp_path, manifeste(9.0, classification_initiale=True))
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    assert [w.value for w in page.warning] == [avant_apres.SEULE_CLASSIFICATION_INITIALE]
    assert not _tableau_avant_apres(page)
    assert not page.caption
    assert "9 s" not in _textes(page)


def test_avant_apres_sans_passage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _demo(tmp_path)
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    assert [i.value for i in page.info] == [
        "Aucun Passage publié : lancer la Chaîne pour mesurer son temps."
    ]
    assert not page.warning
    assert not _tableau_avant_apres(page)


def test_avant_apres_config_absente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    publier(tmp_path, manifeste(3.4))
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    (avertissement,) = page.warning
    assert "config/demo.yaml" in avertissement.value
    assert "temps_manuel_minutes_par_rapport" in avertissement.value
    assert not _tableau_avant_apres(page)


def test_avant_apres_config_invalide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _demo(tmp_path, "# Temps manuel.\ntemps_manuel_minutes_par_rapport: 0\n")
    publier(tmp_path, manifeste(3.4))
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    with pytest.raises(UsineErreur) as attendue:
        cli.config_demo(tmp_path)
    assert [e.value for e in page.error] == [
        f"Configuration de la démo invalide : {attendue.value}"
    ]
    assert "temps_manuel_minutes_par_rapport" in page.error[0].value
    assert not _tableau_avant_apres(page)


def test_avant_apres_racine_introuvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absente = tmp_path / "absente"
    monkeypatch.setenv("USINE_RACINE", str(absente))
    page = _page()
    message_carte = page.error[0].value
    _aller(page, Ecran.avant_apres)
    assert not page.exception
    assert [e.value for e in page.error] == [message_carte]
    assert str(absente) in message_carte
    assert not page.info
    assert not page.warning
    assert not _tableau_avant_apres(page)


def test_avant_apres_passages_illisibles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _demo(tmp_path)

    def illisibles(racine: Path) -> Any:
        raise PermissionError(13, "accès refusé", str(racine / "sorties" / "passages"))

    monkeypatch.setattr(cli, "manifestes_avant_apres", illisibles)  # importé par app.py
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.avant_apres)
    assert not page.exception
    (erreur,) = page.error
    assert erreur.value.startswith("Lecture des Passages publiés impossible : ")
    assert "accès refusé" in erreur.value
    assert not _tableau_avant_apres(page)


# --- Ce qu'il faut pour le faire en vrai (Story 7.5) ---


def _fiche_attendue(racine: Path) -> str:
    """Contenu de la fiche tel que `st.markdown` le garde (Streamlit retire les blancs finaux)."""
    return (racine / outillage.FICHIER_FICHE).read_text(encoding="utf-8").strip()


def _fiche(page: AppTest) -> str:
    """Seul bloc Markdown de l'écran outillage (la fiche), ou chaîne vide."""
    blocs = [str(m.value) for m in page.main.markdown]
    assert len(blocs) <= 1
    return blocs[0] if blocs else ""


def test_outillage_nominal(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page(Ecran.outillage)
    assert not page.exception
    assert not page.error
    assert not page.warning
    assert not page.info
    assert page.subheader[0].value == Ecran.outillage.value
    assert _fiche(page) == _fiche_attendue(racine_publiee)
    assert [c.value for c in page.caption] == [outillage.LEGENDE]
    assert not page.text_input
    assert not page.text_area  # lecture seule


def test_outillage_mode_repli(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    page = _page(Ecran.outillage)
    assert not page.exception
    assert not page.error
    assert _bandeau_en_tete(page)
    assert _fiche(page) == _fiche_attendue(racine_publiee)
    assert [c.value for c in page.caption] == [outillage.LEGENDE]


def test_outillage_fiche_absente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.outillage)
    assert not page.exception
    assert not page.error
    assert [w.value for w in page.warning] == [outillage.FICHE_ABSENTE]
    assert "docs/fiche-outillage.md" in page.warning[0].value
    assert "Story 8.1" in page.warning[0].value
    assert not _fiche(page)
    assert not page.caption


def test_outillage_fiche_illisible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / outillage.FICHIER_FICHE).write_bytes(b"\xff\xfe\xfa illisible")
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.outillage)
    assert not page.exception
    (erreur,) = page.error
    assert erreur.value.startswith("Lecture de la fiche outillage impossible : ")
    assert not page.warning
    assert not _fiche(page)
    assert not page.caption


def test_outillage_fiche_inaccessible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def inaccessible(racine: Path) -> Any:
        raise PermissionError(13, "accès refusé", str(racine / outillage.FICHIER_FICHE))

    monkeypatch.setattr(outillage, "lire_fiche", inaccessible)  # module importé par app.py
    monkeypatch.chdir(tmp_path)
    page = _page(Ecran.outillage)
    assert not page.exception
    (erreur,) = page.error
    assert erreur.value.startswith("Lecture de la fiche outillage impossible : ")
    assert "accès refusé" in erreur.value
    assert not page.warning
    assert not _fiche(page)
    assert not page.caption


def test_outillage_racine_introuvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absente = tmp_path / "absente"
    monkeypatch.setenv("USINE_RACINE", str(absente))
    page = _page()
    message_carte = page.error[0].value
    _aller(page, Ecran.outillage)
    assert not page.exception
    assert [e.value for e in page.error] == [message_carte]
    assert str(absente) in message_carte
    assert not page.warning
    assert not _fiche(page)
