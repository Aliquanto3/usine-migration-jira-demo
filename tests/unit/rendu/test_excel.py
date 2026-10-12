"""Excel du Rapport en 9 onglets : SM-1, Palier 1 et 2, liens Jira, propriétés fixes (Story 5.3).

Le test SM-1 recompose chaque onglet depuis les lectures de `ConsultationPassage` sur le même
Passage, nombres écrits par `contrats.format` : chaque cellule doit être égale.
"""

import io
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import time_machine
from openpyxl import load_workbook  # type: ignore[import-untyped]

from tests.unit.chaine.environnement import DATE_ARRETE
from tests.unit.rendu.conftest import (
    CONTEXTE_FICTIF,
    GRILLE,
    REGLE_JAUNE,
    REGLE_ROUGE,
    URL_JIRA,
    VERSION_MODELE,
    VERSION_PROMPT,
)
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calcul import PERIMETRE_PROGRAMME
from usine.contrats.format import (
    formater_date,
    formater_entier,
    formater_fraction,
    formater_pourcentage,
)
from usine.contrats.meteo import CodeIndicateur, Couleur, Operateur, RegleDeclenchante
from usine.contrats.passage import EnveloppeFichier
from usine.contrats.prevision import ContenuPrevisions, RisqueEntreeRouge
from usine.contrats.tickets import LIBELLES, Gravite
from usine.ports.consultation import Palier
from usine.rendu.commun import (
    ContexteRendu,
    depuis_manifeste,
    formater_prevision,
    formater_regle,
    libelle_kpi,
    texte_prevision,
    tickets_en_cause,
)
from usine.rendu.excel import ONGLETS, rendre_excel

NOM = f"rapport-{DATE_ARRETE.isoformat()}.xlsx"
COULEURS = {
    Couleur.vert: "Vert",
    Couleur.jaune: "Jaune",
    Couleur.orange: "Orange",
    Couleur.rouge: "Rouge",
}
SYMBOLES = {Operateur.superieur_ou_egal: "≥", Operateur.superieur: ">"}
MENTION = "commentaire non généré (Palier 1)"
POURCENTAGES = {CodeIndicateur.ind_4, CodeIndicateur.ind_8}

Lignes = list[list[Any]]


def _classeur(octets: bytes) -> Any:
    return load_workbook(io.BytesIO(octets))


def _valeurs(onglet: Any) -> Lignes:
    """Valeurs de chaque ligne, sans les cellules vides de fin."""
    lignes: Lignes = []
    for ligne in onglet.iter_rows(values_only=True):
        valeurs = list(ligne)
        while valeurs and valeurs[-1] is None:
            valeurs.pop()
        lignes.append(valeurs)
    return lignes


def _liens(classeur: Any) -> list[tuple[str, str, Any, str | None]]:
    """(onglet, coordonnée, valeur, cible du lien) de chaque cellule liée."""
    return [
        (onglet.title, cellule.coordinate, cellule.value, cellule.hyperlink.target)
        for onglet in classeur.worksheets
        for ligne in onglet.iter_rows()
        for cellule in ligne
        if cellule.hyperlink is not None
    ]


# --- Formatage attendu, recomposé avec `contrats.format` seulement ---


def _mesure(numerateur: int, denominateur: int, pourcentage: bool) -> str:
    if denominateur == 0:
        return "∞" if numerateur > 0 else "sans objet"
    if pourcentage:
        return formater_pourcentage(Fraction(numerateur, denominateur))
    if denominateur == 1:
        return formater_entier(numerateur)
    return formater_fraction(Fraction(numerateur, denominateur))


def _kpi(code: str, numerateur: int, denominateur: int) -> str:
    return _mesure(numerateur, denominateur, code.startswith("taux_"))


def _indicateur(code: CodeIndicateur, numerateur: int, denominateur: int) -> str:
    return _mesure(numerateur, denominateur, code in POURCENTAGES)


def _libelle(valeur: str | None) -> str | None:
    return LIBELLES[valeur] if valeur else None


def _perimetre(perimetre: str) -> str:
    return "Programme" if perimetre == PERIMETRE_PROGRAMME else perimetre


def _seuils(code: CodeIndicateur) -> str:
    seuils = GRILLE.indicateurs[code].seuils
    return " ; ".join(
        f"{COULEURS[c]} {SYMBOLES[seuils[c][0]]}"
        f" {_indicateur(code, seuils[c][1].numerator, seuils[c][1].denominator)}"
        for c in Couleur
        if c in seuils
    )


def _synthese(c: ConsultationPassage, contexte: ContexteRendu) -> Lignes:
    evolutions = {e.entite: e for e in c.evolution_meteo(DATE_ARRETE)}
    lignes: Lignes = []
    for meteo in c.meteo(DATE_ARRETE):
        evolution = evolutions[meteo.entite]
        lignes.append(
            [
                meteo.entite,
                COULEURS[meteo.couleur],
                COULEURS[evolution.couleur_j1] if evolution.couleur_j1 else "non couverte",
                COULEURS[evolution.couleur_j5] if evolution.couleur_j5 else "non couverte",
                "\n".join(formater_regle(r) for r in meteo.regles) or None,
                texte_prevision(c, meteo.entite, DATE_ARRETE, contexte.previsions_calculees),
                *tickets_en_cause(meteo.regles),
            ]
        )
    return lignes


def _meteo_detaillee(c: ConsultationPassage) -> Lignes:
    lignes: Lignes = []
    for ligne in c.indicateurs(DATE_ARRETE).iter_rows(named=True):
        code = CodeIndicateur(ligne["code"])
        evalue = ligne["statut"] == "evalue"
        lignes.append(
            [
                ligne["entite"],
                code.value,
                GRILLE.indicateurs[code].libelle,
                "Évalué" if evalue else "Non évaluable",
                _indicateur(code, ligne["numerateur"], ligne["denominateur"])
                if evalue
                else "non évaluable",
                COULEURS[Couleur(ligne["couleur"])],
                _seuils(code),
                *([ligne["motif"]] if ligne["motif"] else []),
            ]
        )
    return lignes


def _kpis(c: ConsultationPassage) -> Lignes:
    return [
        [
            _perimetre(m["perimetre"]),
            libelle_kpi(m["code_kpi"]),
            _libelle(m["dimension"]),
            _kpi(m["code_kpi"], m["numerateur"], m["denominateur"]),
        ]
        for m in c.kpi(DATE_ARRETE).iter_rows(named=True)
    ]


def _tendances(c: ConsultationPassage) -> Lignes:
    table = c.tendances()
    semaines = sorted(set(table.get_column("date").to_list()))
    lignes: dict[tuple[str, str, str], list[Any]] = {}
    for m in table.iter_rows(named=True):
        serie = (m["perimetre"], m["code_kpi"], m["dimension"])
        ligne = lignes.setdefault(
            serie,
            [_perimetre(serie[0]), libelle_kpi(serie[1]), _libelle(serie[2])]
            + [None] * len(semaines),
        )
        ligne[3 + semaines.index(m["date"])] = _kpi(
            m["code_kpi"], m["numerateur"], m["denominateur"]
        )
    entete = [
        "Périmètre",
        "KPI",
        "Dimension",
        *(f"Semaine au {formater_date(s)}" for s in semaines),
    ]
    return [entete, *lignes.values()]


def _anomalies(c: ConsultationPassage, palier: Palier) -> Lignes:
    lignes: Lignes = []
    for gravite in (Gravite.bloquante, Gravite.majeure):
        for a in c.anomalies(DATE_ARRETE, gravite=gravite, palier=palier).anomalies:
            if palier == 1:
                cause = MENTION
            elif a.cause_racine_proposee is None:
                cause = "non proposée"
            else:
                cause = LIBELLES[a.cause_racine_proposee]
            lignes.append(
                [
                    a.cle_ticket,
                    a.entite,
                    LIBELLES[a.gravite],
                    LIBELLES[a.phase],
                    a.domaine,
                    LIBELLES[a.statut],
                    formater_entier(a.age_jours_ouvres),
                    cause,
                ]
            )
    return lignes


def _pivot(c: ConsultationPassage, type_ticket: str, axes: tuple[str, ...]) -> dict[Any, Any]:
    pivot: dict[Any, dict[str, int]] = {}
    for i in c.instantanes(DATE_ARRETE).iter_rows(named=True):
        if i["type_ticket"] == type_ticket:
            pivot.setdefault(tuple(i[a] for a in axes), {})[i["statut"]] = i["nombre"]
    return pivot


def _tests(c: ConsultationPassage) -> Lignes:
    lignes: Lignes = [["Entité", "Vague", "Phase", "OK", "KO", "Non exécuté"]]
    for (entite, vague, phase), nombres in _pivot(
        c, "cas_de_test", ("entite", "vague", "phase")
    ).items():
        lignes.append(
            [
                entite,
                vague,
                LIBELLES[phase],
                *(formater_entier(nombres.get(s, 0)) for s in ("ok", "ko", "non_execute")),
            ]
        )
    lignes += [
        [],
        ["Taux par périmètre et Phase (KPI)"],
        ["Périmètre", "Phase", "Taux de KO", "Taux de non-exécution"],
    ]
    taux: dict[tuple[str, str], dict[str, str]] = {}
    for m in c.kpi(DATE_ARRETE).iter_rows(named=True):
        if m["code_kpi"] in ("taux_ko_cas_de_test", "taux_non_execution_cas_de_test"):
            taux.setdefault((m["perimetre"], m["dimension"]), {})[m["code_kpi"]] = _kpi(
                m["code_kpi"], m["numerateur"], m["denominateur"]
            )
    for (perimetre, phase), valeurs in taux.items():
        lignes.append(
            [
                _perimetre(perimetre),
                LIBELLES[phase],
                valeurs["taux_ko_cas_de_test"],
                valeurs["taux_non_execution_cas_de_test"],
            ]
        )
    return lignes


def _certifications(c: ConsultationPassage) -> Lignes:
    return [
        [
            entite,
            vague,
            *(formater_entier(n.get(s, 0)) for s in ("accordee", "reservee", "refusee")),
        ]
        for (entite, vague), n in _pivot(c, "certification", ("entite", "vague")).items()
    ]


# --- Classeur publié par `lancer_rapport` (Palier 1) ---


def test_onglets_dans_l_ordre(passage: Path) -> None:
    classeur = _classeur((passage / NOM).read_bytes())
    assert classeur.sheetnames == [
        "Synthèse",
        "Météo détaillée",
        "KPI",
        "Tendances",
        "Anomalies ouvertes",
        "Tests",
        "Certifications",
        "Commentaires",
        "Traçabilité",
    ]
    assert tuple(classeur.sheetnames) == ONGLETS


def test_sm1_chaque_onglet(passage: Path, consultation: ConsultationPassage) -> None:
    """SM-1 : chaque cellule = formatage `contrats.format` de la lecture `Consultation`."""
    classeur = _classeur((passage / NOM).read_bytes())
    contexte = depuis_manifeste(consultation.manifeste(), GRILLE)
    onglet = {nom: _valeurs(classeur[nom]) for nom in ONGLETS}

    synthese = onglet["Synthèse"]
    assert synthese[0] == [
        "Entité",
        "Météo J",
        "Météo J-1",
        "Météo J-5",
        "Règles déclenchantes",
        "Prévision ou Risque",
        "Tickets en cause",
    ]
    assert synthese[1:] == _synthese(consultation, contexte)
    assert len(synthese) == 3

    meteo = onglet["Météo détaillée"]
    assert meteo[0] == [
        "Entité",
        "Code",
        "Indicateur",
        "Statut",
        "Valeur",
        "Couleur",
        "Seuils",
        "Motif",
    ]
    assert meteo[1:] == _meteo_detaillee(consultation)
    assert any(ligne[3] == "Non évaluable" for ligne in meteo[1:])

    kpi = onglet["KPI"]
    assert kpi[0] == ["Périmètre", "KPI", "Dimension", "Valeur"]
    assert kpi[1:] == _kpis(consultation)
    assert {ligne[0] for ligne in kpi[1:]} == {"ENT-A", "ENT-B", "Programme"}

    assert onglet["Tendances"] == _tendances(consultation)
    assert len(onglet["Tendances"][0]) == 3 + 8  # 8 semaines

    anomalies = onglet["Anomalies ouvertes"]
    assert anomalies[1:] == _anomalies(consultation, 1)
    bloquantes = consultation.anomalies(gravite=Gravite.bloquante).total
    majeures = consultation.anomalies(gravite=Gravite.majeure).total
    assert len(anomalies) == 1 + bloquantes + majeures
    assert bloquantes > 0

    assert onglet["Tests"] == _tests(consultation)
    certifications = onglet["Certifications"]
    assert certifications[0] == ["Entité", "Vague", "Accordée", "Réservée", "Refusée"]
    assert certifications[1:] == _certifications(consultation)
    assert onglet["Commentaires"] == [["Commentaires"], [MENTION]]


def test_tracabilite_egale_le_manifeste(passage: Path, consultation: ConsultationPassage) -> None:
    manifeste = consultation.manifeste()
    lignes = _valeurs(_classeur((passage / NOM).read_bytes())["Traçabilité"])
    assert manifeste.nb_tickets == consultation.tickets_etats(DATE_ARRETE).height > 0
    assert lignes == [
        ["Libellé", "Valeur"],
        ["Date d'arrêté", formater_date(manifeste.date_arrete)],
        ["Palier", f"Palier {manifeste.palier}"],
        ["Source", manifeste.source],
        ["Horodatage d'extraction", "sans extraction Jira"],
        ["Nombre de tickets", formater_entier(manifeste.nb_tickets)],
        ["Version de la Grille", manifeste.version_grille],
        ["Version des données", manifeste.version_donnees],
        ["Version du prompt", "sans objet (Palier 1)"],
        ["Version du modèle", "sans objet (Palier 1)"],
        ["Version des contrats", manifeste.contrats_version],
    ]


def test_horodatage_d_extraction(consultation: ConsultationPassage) -> None:
    instant = datetime(2026, 10, 12, 7, 5, 9, tzinfo=UTC)
    contexte = ContexteRendu(
        palier=1, source="composite", version_grille="g", version_donnees="d",
        horodatage_extraction=instant,
    )  # fmt: skip
    lignes = _valeurs(_classeur(rendre_excel(consultation, DATE_ARRETE, contexte))["Traçabilité"])
    assert lignes[3] == ["Source", "composite"]
    assert lignes[4] == ["Horodatage d'extraction", "12/10/2026 07:05:09 UTC"]


def test_palier_1_mentions(passage: Path) -> None:
    """FR-28 : Commentaires et colonne Cause racine proposée en Palier 1."""
    classeur = _classeur((passage / NOM).read_bytes())
    assert _valeurs(classeur["Commentaires"]) == [["Commentaires"], [MENTION]]
    anomalies = _valeurs(classeur["Anomalies ouvertes"])
    assert anomalies[0][7] == "Cause racine proposée"
    assert anomalies[1:]
    assert {ligne[7] for ligne in anomalies[1:]} == {MENTION}


def test_synthese_previsions_du_passage(consultation: ConsultationPassage, passage: Path) -> None:
    """ENT-B rouge à D (seule, flux scripté des contrats 1.2) : sa Prévision Baseline est
    affichée."""
    synthese = _valeurs(_classeur((passage / NOM).read_bytes())["Synthèse"])
    previsions = consultation.previsions()
    assert [p.entite for p in previsions] == ["ENT-B"]
    assert [(ligne[0], ligne[1]) for ligne in synthese[1:]] == [
        ("ENT-A", "Vert"),
        ("ENT-B", "Rouge"),
    ]
    (ligne,) = [ligne for ligne in synthese[1:] if ligne[0] == "ENT-B"]
    attendu = "\n".join(
        formater_prevision(p) for p in consultation.previsions(DATE_ARRETE, "ENT-B")
    )
    assert ligne[5] == attendu


# --- Fixture Palier 2 ---


def test_palier_2(passage_palier_2: Path) -> None:
    consultation = ConsultationPassage(passage_palier_2, url_jira=URL_JIRA)
    contexte = depuis_manifeste(consultation.manifeste(), GRILLE)
    assert contexte.palier == 2
    classeur = _classeur(rendre_excel(consultation, DATE_ARRETE, contexte))
    commentaires = _valeurs(classeur["Commentaires"])
    explications = consultation.explications()
    assert commentaires[:2] == [
        ["Explications et Brouillons de commentaire"],
        ["Entité", "Explication", "Brouillon de commentaire", "Citations"],
    ]
    attendues = [
        [
            e.entite,
            e.texte,
            f"brouillon IA, à valider : {e.brouillon_commentaire}"
            if e.brouillon_commentaire
            else None,
            *e.citations,
        ]
        for e in explications
    ]
    assert commentaires[2 : 2 + len(explications)] == attendues
    assert commentaires[2][2] == "brouillon IA, à valider : Relancer l'équipe paramétrage."
    suite = commentaires[2 + len(explications) :]
    repartition = consultation.repartition_causes()
    assert suite == [
        [],
        ["Répartition des Causes racines"],
        ["Entité", "Cause racine", "Anomalies ouvertes"],
        *(
            [r["entite"], LIBELLES[r["cause_racine"]], formater_entier(r["nombre"])]
            for r in repartition.iter_rows(named=True)
        ),
    ]
    assert suite[-1] == ["ENT-B", "Reprise de données", "1 234"]
    # Citations liées.
    liens = {
        (coordonnee, valeur): cible
        for onglet, coordonnee, valeur, cible in _liens(classeur)
        if onglet == "Commentaires"
    }
    citations = [cle for e in explications for cle in e.citations]
    assert sorted(v for _, v in liens) == sorted(citations)
    assert all(cible == f"{URL_JIRA}/browse/{cle}" for (_, cle), cible in liens.items())
    # Colonne Cause racine proposée : la classification, sinon « non proposée ».
    anomalies = _valeurs(classeur["Anomalies ouvertes"])
    assert anomalies[1:] == _anomalies(consultation, 2)
    assert "Paramétrage" in {ligne[7] for ligne in anomalies[1:]}
    assert "non proposée" in {ligne[7] for ligne in anomalies[1:]}
    # Traçabilité : versions de prompt et de modèle des traces LLM.
    tracabilite = dict((ligne[0], ligne[1]) for ligne in _valeurs(classeur["Traçabilité"])[1:])
    assert tracabilite["Palier"] == "Palier 2"
    assert tracabilite["Version du prompt"] == VERSION_PROMPT
    assert tracabilite["Version du modèle"] == VERSION_MODELE


def test_palier_2_sans_sortie_llm(passage: Path) -> None:
    """Palier 2 sans fichier LLM : en-têtes seuls, « aucun appel LLM »."""
    consultation = ConsultationPassage(passage)
    contexte = ContexteRendu(palier=2, source="journal", version_grille="g", version_donnees="d")
    classeur = _classeur(rendre_excel(consultation, DATE_ARRETE, contexte))
    assert _valeurs(classeur["Commentaires"]) == [
        ["Explications et Brouillons de commentaire"],
        ["Entité", "Explication", "Brouillon de commentaire", "Citations"],
        [],
        ["Répartition des Causes racines"],
        ["Entité", "Cause racine", "Anomalies ouvertes"],
    ]
    tracabilite = _valeurs(classeur["Traçabilité"])
    assert tracabilite[8:10] == [
        ["Version du prompt", "aucun appel LLM"],
        ["Version du modèle", "aucun appel LLM"],
    ]
    anomalies = _valeurs(classeur["Anomalies ouvertes"])
    assert {ligne[7] for ligne in anomalies[1:]} == {"non proposée"}


# --- Prévision ou Risque (Synthèse) ---


def _ecrire_risque(consultation: ConsultationPassage) -> RisqueEntreeRouge:
    risque = RisqueEntreeRouge(
        date_arrete=DATE_ARRETE,
        entite="ENT-J",
        indicateur=CodeIndicateur.ind_4,
        date_franchissement_estimee=date(2026, 10, 14),
        horizon_jours_ouvres=5,
        numerateur=3,
        denominateur=20,
        seuil_numerateur=1,
        seuil_denominateur=5,
        version_grille="abc",
    )
    modele = EnveloppeFichier[ContenuPrevisions]
    enveloppe = modele(
        passage_id="20261012T073000Z-abcdef",
        date_arrete=DATE_ARRETE,
        contenu=ContenuPrevisions(previsions=(), risques=(risque,)),
    )
    (consultation.repertoire / "previsions.json").write_text(
        enveloppe.model_dump_json(), encoding="utf-8"
    )
    return risque


@pytest.mark.parametrize("calculees", [True, False])
def test_prevision_ou_risque(passage_jaune_rouge: ConsultationPassage, calculees: bool) -> None:
    """Jaune sans Risque : « Aucun Risque d'entrée en rouge » ; rouge sans Prévision ou étape
    `prevision` non réussie : « Prévision non calculée »."""
    contexte = ContexteRendu(
        palier=1, source="journal", version_grille="abc", version_donnees="def",
        previsions_calculees=calculees,
    )  # fmt: skip
    synthese = _valeurs(
        _classeur(rendre_excel(passage_jaune_rouge, DATE_ARRETE, contexte))["Synthèse"]
    )
    attendu_jaune = "Aucun Risque d'entrée en rouge" if calculees else "Prévision non calculée"
    assert [ligne[5] for ligne in synthese[1:]] == [attendu_jaune, "Prévision non calculée"]
    _ecrire_risque(passage_jaune_rouge)
    relu = ConsultationPassage(passage_jaune_rouge.repertoire, date_arrete=DATE_ARRETE)
    synthese = _valeurs(_classeur(rendre_excel(relu, DATE_ARRETE, contexte))["Synthèse"])
    attendu = (
        "Risque d'entrée en rouge IND-4 : franchissement estimé le 14/10/2026 (valeur 15 %,"
        " seuil rouge 20 %, horizon 5 Jours ouvrés)"
    )
    assert synthese[1][5] == (attendu if calculees else "Prévision non calculée")


def test_couleurs_des_cellules(passage_jaune_rouge: ConsultationPassage) -> None:
    """Teinte et texte de la cellule Météo : texte foncé sur le jaune, blanc sur le rouge."""
    octets = rendre_excel(passage_jaune_rouge, DATE_ARRETE, CONTEXTE_FICTIF)
    onglet = _classeur(octets)["Synthèse"]
    attendus = {2: ("Jaune", "F9A825", "212121"), 3: ("Rouge", "C62828", "FFFFFF")}
    for ligne, (libelle, teinte, texte) in attendus.items():
        cellule = onglet.cell(row=ligne, column=2)
        assert cellule.value == libelle
        assert cellule.fill.fill_type == "solid"
        assert cellule.fill.start_color.rgb[-6:] == teinte
        assert cellule.font.color.rgb[-6:] == texte
        # J-1 et J-5 hors du Passage réduit : « non couverte », sans teinte.
        for colonne in (3, 4):
            assert onglet.cell(row=ligne, column=colonne).value == "non couverte"
            assert onglet.cell(row=ligne, column=colonne).fill.fill_type is None
    assert onglet.cell(row=2, column=5).value == "IND-2 : 0,4 (seuil > 0,3)"
    assert onglet.cell(row=2, column=5).alignment.wrap_text is True


REGLE_INFINIE = RegleDeclenchante(
    code=CodeIndicateur.ind_3,
    couleur=Couleur.orange,
    operateur=Operateur.superieur_ou_egal,
    numerateur=2,
    denominateur=0,
    seuil_numerateur=1,
    seuil_denominateur=2,
    tickets_en_cause=(),
)

REGLE_TAUX = RegleDeclenchante(
    code=CodeIndicateur.ind_4,
    couleur=Couleur.rouge,
    operateur=Operateur.superieur_ou_egal,
    numerateur=3,
    denominateur=8,
    seuil_numerateur=1,
    seuil_denominateur=5,
    tickets_en_cause=("DEMO-9",),
)


@pytest.mark.parametrize(
    ("regle", "attendu"),
    [
        (REGLE_ROUGE, "IND-1 : 7 (seuil ≥ 3)"),
        (REGLE_JAUNE, "IND-2 : 0,4 (seuil > 0,3)"),
        (REGLE_INFINIE, "IND-3 : ∞ (seuil ≥ 0,5)"),
        (REGLE_TAUX, "IND-4 : 37,5 % (seuil ≥ 20 %)"),
    ],
)
def test_formater_regle(regle: RegleDeclenchante, attendu: str) -> None:
    assert formater_regle(regle) == attendu


# --- Liens Jira ---


def test_liens_jira(passage: Path) -> None:
    """Chaque clé affichée (Synthèse, Anomalies ouvertes) est liée à `url_ticket(cle)`."""
    consultation = ConsultationPassage(passage, url_jira=URL_JIRA)
    classeur = _classeur((passage / NOM).read_bytes())
    liens = _liens(classeur)
    assert {onglet for onglet, *_ in liens} == {"Synthèse", "Anomalies ouvertes"}
    for _, _, cle, cible in liens:
        assert cible == consultation.url_ticket(cle) == f"{URL_JIRA}/browse/{cle}"
    synthese = _valeurs(classeur["Synthèse"])
    attendues = [cle for m in consultation.meteo() for cle in tickets_en_cause(m.regles)]
    assert [v for o, _, v, _ in liens if o == "Synthèse"] == attendues
    assert [ligne[6:] for ligne in synthese[1:]] == [
        list(tickets_en_cause(m.regles)) for m in consultation.meteo()
    ]
    anomalies = _valeurs(classeur["Anomalies ouvertes"])
    assert [v for o, _, v, _ in liens if o == "Anomalies ouvertes"] == [
        ligne[0] for ligne in anomalies[1:]
    ]


@pytest.mark.parametrize("nom_passage", ["passage_repli", "passage_sans_jira"])
def test_cles_sans_lien(nom_passage: str, request: pytest.FixtureRequest) -> None:
    """Mode repli, ou pas de `config/jira.yaml` : Passage publié, clés sans hyperlien."""
    repertoire: Path = request.getfixturevalue(nom_passage)
    classeur = _classeur((repertoire / NOM).read_bytes())
    assert _liens(classeur) == []
    anomalies = _valeurs(classeur["Anomalies ouvertes"])
    assert anomalies[1:]
    assert all(
        isinstance(ligne[0], str) and ligne[0].startswith("DEMO-") for ligne in anomalies[1:]
    )


# --- Passage vide, propriétés, déterminisme ---


def test_passage_vide(tmp_path: Path) -> None:
    """Répertoire sans fichier : 9 onglets, en-têtes seuls, sans erreur."""
    octets = rendre_excel(ConsultationPassage(tmp_path), DATE_ARRETE, CONTEXTE_FICTIF)
    classeur = _classeur(octets)
    assert tuple(classeur.sheetnames) == ONGLETS
    lignes = {nom: _valeurs(classeur[nom]) for nom in ONGLETS}
    for nom in ("Synthèse", "Météo détaillée", "KPI", "Tendances", "Anomalies ouvertes"):
        assert len(lignes[nom]) == 1, nom
    assert lignes["Tendances"] == [["Périmètre", "KPI", "Dimension"]]
    assert lignes["Tests"] == [
        ["Entité", "Vague", "Phase", "OK", "KO", "Non exécuté"],
        [],
        ["Taux par périmètre et Phase (KPI)"],
        ["Périmètre", "Phase", "Taux de KO", "Taux de non-exécution"],
    ]
    assert len(lignes["Certifications"]) == 1
    assert lignes["Commentaires"] == [["Commentaires"], [MENTION]]
    assert lignes["Traçabilité"][5] == ["Nombre de tickets", "0"]
    assert len(lignes["Traçabilité"]) == 11
    proprietes = classeur.properties
    assert proprietes.title == "Rapport quotidien du 09/10/2026"


def test_proprietes_fixes(passage: Path) -> None:
    proprietes = _classeur((passage / NOM).read_bytes()).properties
    minuit = datetime(2026, 10, 9, tzinfo=UTC).replace(tzinfo=None)  # relu sans fuseau
    assert (proprietes.created, proprietes.modified) == (minuit, minuit)
    assert proprietes.creator == "Usine de migration (démonstrateur)"
    assert proprietes.title == "Rapport quotidien du 09/10/2026"


def test_rendu_deterministe(consultation: ConsultationPassage) -> None:
    """Mêmes octets, rendus à des jours d'écart, et égaux au classeur publié."""
    contexte = depuis_manifeste(consultation.manifeste(), GRILLE)
    with time_machine.travel(datetime(2026, 10, 12, 8, tzinfo=UTC), tick=False):
        premier = rendre_excel(consultation, DATE_ARRETE, contexte)
    with time_machine.travel(datetime(2026, 11, 3, 17, 45, tzinfo=UTC), tick=False):
        second = rendre_excel(consultation, DATE_ARRETE, contexte)
    assert premier == second
    publie = (consultation.repertoire / NOM).read_bytes()
    assert premier == publie
