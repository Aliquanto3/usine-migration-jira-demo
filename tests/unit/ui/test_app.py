"""Page Streamlit (`AppTest`) : bandeau, navigation, carte, détail, lancement et progression."""

import re
import shutil
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import IO, Any, cast

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

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
from usine.ui import cli, detail, lancement
from usine.ui.carte import formater_regle, tendance
from usine.ui.cli import consultation_dernier_passage, mode_repli
from usine.ui.liens import echapper_markdown
from usine.ui.navigation import STORY_A_VENIR, Ecran

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


def _ligne(etape: Etape, statut: StatutEtape) -> str:
    instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
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
        + _ligne(Etape.extraction, StatutEtape.reussie)
        + _ligne(Etape.instantanes, StatutEtape.en_cours)
        + '{"partielle',
        encoding="utf-8",
    )
    page.run()
    textes = _textes(page)
    assert "**extraction** : Réussie" in textes
    assert "**instantanes** : En cours" in textes
    assert "**kpi** : En attente" in textes

    lanceur.processus.code = 1
    page.run()
    assert not page.exception
    assert "étape kpi en échec" in page.error[0].value
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
    page.run()
    assert not page.exception
    assert len(lanceur.appels) == 1
    _aller(page, Ecran.carte)
    assert _entites(_tableau(page)) == ["ENT-A", "ENT-B"]


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
