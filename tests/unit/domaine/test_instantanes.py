"""État des tickets et Instantané (Stories 0.4 et 3.1, FR-10, FR-14, AD-3, AD-17)."""

import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tests.unit.domaine.constructeur import Flux
from usine.config import charger_yaml
from usine.contrats.calcul import SCHEMA_INSTANTANE
from usine.contrats.calendrier import est_jour_ouvre, jour_local, jour_ouvre_de, jours_ouvres
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, SCHEMA_TICKET_TEXTE, Champ, TypeTicket
from usine.domaine.instantanes import instantane, tickets_etats, tickets_textes
from usine.generateur.journal import Generation, generer

RACINE = Path(__file__).resolve().parents[3]

VENDREDI = date(2026, 10, 2)
LUNDI = date(2026, 10, 5)
MARDI = date(2026, 10, 6)


def _ts(jour: int, heure: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, jour, heure, minute, tzinfo=UTC)


def _ligne(etats: pl.DataFrame, d: date, cle: str) -> dict[str, object]:
    lignes = etats.filter((pl.col("date") == d) & (pl.col("cle_ticket") == cle)).to_dicts()
    assert len(lignes) == 1, f"{cle} en {d} : {len(lignes)} ligne(s)"
    return lignes[0]


def test_schema_et_ticket_cree_au_plus_tard_en_d() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.anomalie("DEMO-2", _ts(6, 9))  # mardi : après le lundi D
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI, MARDI])
    valider(etats, SCHEMA_TICKET_ETAT)
    assert etats.filter(pl.col("date") == LUNDI)["cle_ticket"].to_list() == ["DEMO-1"]
    assert etats.filter(pl.col("date") == MARDI)["cle_ticket"].to_list() == ["DEMO-1", "DEMO-2"]


def test_coupure_week_end_rattachee_au_lundi() -> None:
    flux = Flux()
    # Samedi 23 h UTC = dimanche 1 h à Paris : Jour ouvré = lundi.
    flux.anomalie("DEMO-1", _ts(3, 23))
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    assert _ligne(etats, LUNDI, "DEMO-1")["date_derniere_entree"] == LUNDI


def test_vendredi_soir_utc_rattache_au_lundi() -> None:
    flux = Flux()
    # Vendredi 22 h 30 UTC = samedi 0 h 30 à Paris.
    flux.anomalie("DEMO-1", _ts(2, 22, 30))
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    assert etats.filter(pl.col("date") == LUNDI).height == 1


def test_derniere_valeur_et_fermeture() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "en_correction")
    flux.transition("DEMO-1", _ts(5, 9), "en_correction", "fermee")
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["statut"] == "en_correction"
    assert _ligne(etats, LUNDI, "DEMO-1")["statut"] == "fermee"
    assert _ligne(etats, LUNDI, "DEMO-1")["date_derniere_entree"] == date(2026, 10, 1)


def test_reouverture_fixe_la_derniere_entree() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(1, 10), "nouvelle", "en_correction")
    flux.transition("DEMO-1", _ts(1, 11), "en_correction", "a_retester")
    flux.transition("DEMO-1", _ts(2, 9), "a_retester", "fermee")
    flux.transition("DEMO-1", _ts(5, 9), "fermee", "en_analyse")
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["date_derniere_entree"] == date(2026, 10, 1)
    lundi = _ligne(etats, LUNDI, "DEMO-1")
    assert lundi["statut"] == "en_analyse"
    assert lundi["date_derniere_entree"] == LUNDI


def test_meme_horodatage_ordre_du_flux() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9), gravite="mineure")
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(1, 9), Champ.gravite, "mineure", "majeure")
    etats = tickets_etats(flux.evenements, [VENDREDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["gravite"] == "majeure"


def test_ordre_d_arrivee_indifferent_hors_egalite() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "en_analyse")
    melange = list(reversed(flux.evenements[-1:])) + flux.evenements[:-1]
    assert tickets_etats(melange, [VENDREDI]).equals(tickets_etats(flux.evenements, [VENDREDI]))


def test_colonnes_sans_objet_nulles() -> None:
    flux = Flux()
    flux.creer(
        "DEMO-1",
        TypeTicket.cas_de_test,
        _ts(1, 9),
        {
            Champ.statut_test: "non_execute",
            Champ.entite: "ENT-A",
            Champ.vague: "V1",
            Champ.domaine: "paie",
            Champ.phase: "tnr",
        },
    )
    flux.creer(
        "DEMO-2",
        TypeTicket.certification,
        _ts(1, 9),
        {Champ.statut_certification: "accordee", Champ.entite: "ENT-A", Champ.vague: "V1"},
    )
    flux.modifier(
        "DEMO-1", TypeTicket.cas_de_test, _ts(2, 9), Champ.statut_test, "non_execute", "ko"
    )
    etats = tickets_etats(flux.evenements, [VENDREDI])
    test = _ligne(etats, VENDREDI, "DEMO-1")
    assert test["statut_test"] == "ko"
    assert test["statut"] is None and test["gravite"] is None
    assert test["statut_certification"] is None and test["date_derniere_entree"] is None
    certification = _ligne(etats, VENDREDI, "DEMO-2")
    assert certification["statut_certification"] == "accordee"
    assert certification["domaine"] is None and certification["phase"] is None


def test_sans_evenement_ni_date() -> None:
    assert tickets_etats([], [LUNDI]).is_empty()
    assert tickets_etats([], []).schema == pl.Schema(dict(SCHEMA_TICKET_ETAT.colonnes))
    assert instantane(tickets_etats([], [LUNDI])).is_empty()


def test_instantane_compte_par_attributs() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.anomalie("DEMO-2", _ts(1, 10))
    flux.anomalie("DEMO-3", _ts(1, 11), entite="ENT-B", gravite="majeure")
    flux.transition("DEMO-2", _ts(2, 9), "nouvelle", "rejetee")
    table = instantane(tickets_etats(flux.evenements, [VENDREDI]))
    valider(table, SCHEMA_INSTANTANE)
    comptes = {
        (ligne["entite"], ligne["gravite"], ligne["statut"]): ligne["nombre"]
        for ligne in table.to_dicts()
    }
    assert comptes == {
        ("ENT-A", "bloquante", "nouvelle"): 1,
        ("ENT-A", "bloquante", "rejetee"): 1,
        ("ENT-B", "majeure", "nouvelle"): 1,
    }


@pytest.fixture(scope="module")
def generation() -> Generation:
    config = charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


def test_journal_genere_instantane_complet(generation: Generation) -> None:
    entete = generation.entete
    jours = jours_ouvres(entete.ancrage_semaines, entete.date_injection)
    etats = tickets_etats(generation.evenements, jours)
    tickets = {e.cle_ticket for e in generation.evenements if e.nature is NatureEvenement.creation}
    finaux = etats.filter(pl.col("date") == entete.date_injection)
    assert set(finaux["cle_ticket"]) == tickets
    table = instantane(etats)
    par_date = table.group_by("date").agg(pl.col("nombre").sum()).sort("date")
    attendu = etats.group_by("date").len().sort("date")
    assert par_date["nombre"].to_list() == attendu["len"].cast(pl.Int64).to_list()
    assert table.filter(pl.col("statut").is_null()).is_empty()


def test_dates_en_double_refusees() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    with pytest.raises(UsineErreur, match="2026-10-02"):
        tickets_etats(flux.evenements, [VENDREDI, LUNDI, VENDREDI])


def test_tickets_textes_dernieres_valeurs_en_d() -> None:
    flux = Flux()
    flux.creer(
        "DEMO-1",
        TypeTicket.anomalie,
        _ts(1, 9),
        {Champ.entite: "ENT-A", Champ.titre: "Titre initial", Champ.description: "Desc"},
    )
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(5, 10), Champ.titre, "Titre initial", "Lundi")
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(6, 10), Champ.titre, "Lundi", "Mardi")
    flux.anomalie("DEMO-2", _ts(5, 11), entite="ENT-B")  # ni titre ni description
    flux.anomalie("DEMO-3", _ts(6, 9))  # créé après le lundi D
    textes = tickets_textes(flux.evenements, LUNDI)
    valider(textes, SCHEMA_TICKET_TEXTE)
    assert textes.to_dicts() == [
        {
            "cle_ticket": "DEMO-1",
            "type_ticket": "anomalie",
            "entite": "ENT-A",
            "titre": "Lundi",
            "description": "Desc",
        },
        {
            "cle_ticket": "DEMO-2",
            "type_ticket": "anomalie",
            "entite": "ENT-B",
            "titre": None,
            "description": None,
        },
    ]


def test_tickets_textes_vide() -> None:
    textes = tickets_textes([], LUNDI)
    assert textes.is_empty()
    assert textes.schema == dict(SCHEMA_TICKET_TEXTE.colonnes)


# --- Story 3.1 : dédoublonnage, Jours ouvrés, ordre canonique, déterminisme, futur ajouté ---


def test_doublon_d_id_ignore() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "fermee")
    flux.transition("DEMO-1", _ts(5, 9), "fermee", "en_analyse")
    # Recouvrement d'extraction : la réouverture et la création reviennent une seconde fois.
    avec_doublons = [*flux.evenements, flux.evenements[-1], *flux.evenements[:3]]
    dates = [VENDREDI, LUNDI, MARDI]
    attendu = tickets_etats(flux.evenements, dates)
    assert tickets_etats(avec_doublons, dates).equals(attendu)
    assert tickets_textes(avec_doublons, MARDI).equals(tickets_textes(flux.evenements, MARDI))
    assert attendu.height == 3


def test_doublon_d_id_premiere_occurrence_gardee() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "en_analyse")
    divergente = flux.evenements[-1].model_copy(update={"vers": "en_correction"})
    etats = tickets_etats([*flux.evenements, divergente], [VENDREDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["statut"] == "en_analyse"


def test_date_non_ouvree_refusee() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    with pytest.raises(UsineErreur, match="2026-10-03"):
        tickets_etats(flux.evenements, [VENDREDI, date(2026, 10, 3)])


def test_ordre_des_lignes_par_rang_cle() -> None:
    flux = Flux()
    flux.anomalie("DEMO-10", _ts(1, 9))
    flux.anomalie("DEMO-2", _ts(1, 10))
    flux.anomalie("DEMO-1", _ts(5, 9))
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats["date"].to_list() == [VENDREDI, VENDREDI, LUNDI, LUNDI, LUNDI]
    assert etats["cle_ticket"].to_list() == ["DEMO-2", "DEMO-10", "DEMO-1", "DEMO-2", "DEMO-10"]
    textes = tickets_textes(flux.evenements, LUNDI)
    assert textes["cle_ticket"].to_list() == ["DEMO-1", "DEMO-2", "DEMO-10"]


def test_ordre_des_dates_celui_fourni() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    etats = tickets_etats(flux.evenements, [LUNDI, VENDREDI])
    assert etats["date"].to_list() == [LUNDI, VENDREDI]


def test_alignement_n_est_jamais_une_entree() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(1, 10), "nouvelle", "fermee")
    alignement = flux.evenements[-1].model_copy(
        update={
            "id_evenement": "J-X",
            "nature": NatureEvenement.alignement,
            "horodatage": _ts(5, 9),
            "de": "fermee",
            "vers": "en_analyse",
        }
    )
    etats = tickets_etats([*flux.evenements, alignement], [LUNDI])
    lundi = _ligne(etats, LUNDI, "DEMO-1")
    assert lundi["statut"] == "en_analyse"
    assert lundi["date_derniere_entree"] == date(2026, 10, 1)


_DEBUT_ALEATOIRE = datetime(2026, 9, 28, 6, tzinfo=UTC)  # lundi
_JOURS_ALEATOIRES = jours_ouvres(date(2026, 9, 28), date(2026, 10, 23))
_STATUTS_ANOMALIE = ("nouvelle", "en_analyse", "en_correction", "a_retester", "fermee", "rejetee")
_STATUTS_SUIVIS = {
    TypeTicket.anomalie: (Champ.statut, _STATUTS_ANOMALIE),
    TypeTicket.cas_de_test: (Champ.statut_test, ("non_execute", "ok", "ko")),
    TypeTicket.certification: (Champ.statut_certification, ("reservee", "accordee", "refusee")),
}


def _flux_aleatoire(graine: int) -> list[Evenement]:
    """Flux à horodatages tous distincts : trois types, réouvertures, week-ends, alignements."""
    rng = random.Random(graine)
    pris: set[datetime] = set()
    evenements: list[Evenement] = []

    def instant(apres: datetime) -> datetime:
        while True:
            ts = apres + timedelta(minutes=rng.randint(1, 3 * 24 * 60))
            if ts not in pris:
                pris.add(ts)
                return ts

    def ajouter(
        cle: str,
        type_ticket: TypeTicket,
        ts: datetime,
        nature: NatureEvenement,
        champ: Champ | None = None,
        de: str | None = None,
        vers: str | None = None,
    ) -> None:
        evenements.append(
            Evenement(
                id_evenement=f"A-{len(evenements) + 1}",
                cle_ticket=cle,
                type_ticket=type_ticket,
                horodatage=ts,
                nature=nature,
                champ=champ,
                de=de,
                vers=vers,
                source=SourceEvenement.journal,
            )
        )

    modification = NatureEvenement.modification_champ
    for numero in rng.sample(range(1, 200), rng.randint(4, 12)):
        cle = f"DEMO-{numero}"
        type_ticket = rng.choice(list(TypeTicket))
        champ_statut, statuts = _STATUTS_SUIVIS[type_ticket]
        statut = statuts[0]
        ts = instant(_DEBUT_ALEATOIRE + timedelta(days=rng.randint(0, 20)))
        ajouter(cle, type_ticket, ts, NatureEvenement.creation)
        attributs: dict[Champ, str] = {
            champ_statut: statut,
            Champ.entite: rng.choice(["ENT-A", "ENT-B"]),
            Champ.vague: "V1",
        }
        if type_ticket is not TypeTicket.certification:
            attributs |= {Champ.domaine: "paie", Champ.phase: rng.choice(["recette", "tnr"])}
        if type_ticket is TypeTicket.anomalie:
            attributs[Champ.gravite] = rng.choice(["bloquante", "majeure", "mineure"])
        for champ, valeur in attributs.items():
            ts = instant(ts)
            ajouter(cle, type_ticket, ts, modification, champ, None, valeur)
        for _ in range(rng.randint(0, 6)):
            ts = instant(ts)
            vers = rng.choice([s for s in statuts if s != statut])
            if type_ticket is TypeTicket.anomalie:
                nature = rng.choice([NatureEvenement.transition] * 4 + [NatureEvenement.alignement])
            else:
                nature = modification
            ajouter(cle, type_ticket, ts, nature, champ_statut, statut, vers)
            statut = vers
    return evenements


GRAINES = range(20)


def test_flux_aleatoires_couvrent_les_cas() -> None:
    evenements = [e for graine in GRAINES for e in _flux_aleatoire(graine)]
    assert {e.type_ticket for e in evenements} == set(TypeTicket)
    assert any(e.nature is NatureEvenement.alignement for e in evenements)
    assert any(
        e.nature is NatureEvenement.transition
        and e.de in ("fermee", "rejetee")
        and e.vers not in ("fermee", "rejetee")
        for e in evenements
    )
    assert any(not est_jour_ouvre(jour_local(e.horodatage)) for e in evenements)


@pytest.mark.parametrize("graine", GRAINES)
def test_deux_calculs_identiques_et_arrivee_permutee(graine: int) -> None:
    evenements = _flux_aleatoire(graine)
    melange = list(evenements)
    random.Random(1000 + graine).shuffle(melange)
    etats = tickets_etats(evenements, _JOURS_ALEATOIRES)
    table = instantane(etats)
    for autre in (evenements, melange):
        autres_etats = tickets_etats(autre, _JOURS_ALEATOIRES)
        assert autres_etats.equals(etats)
        assert instantane(autres_etats).equals(table)
        for d in (_JOURS_ALEATOIRES[4], _JOURS_ALEATOIRES[-1]):
            assert tickets_textes(autre, d).equals(tickets_textes(evenements, d))


@pytest.mark.parametrize("graine", GRAINES)
def test_futur_ajoute_sans_effet(graine: int) -> None:
    evenements = _flux_aleatoire(graine)
    etats = tickets_etats(evenements, _JOURS_ALEATOIRES)
    valider(etats, SCHEMA_TICKET_ETAT)
    table = instantane(etats)
    valider(table, SCHEMA_INSTANTANE)
    valider(tickets_textes(evenements, _JOURS_ALEATOIRES[-1]), SCHEMA_TICKET_TEXTE)
    for i, d in enumerate(_JOURS_ALEATOIRES):
        coupe = [e for e in evenements if jour_ouvre_de(e.horodatage) <= d]
        etats_coupes = tickets_etats(coupe, _JOURS_ALEATOIRES[: i + 1])
        assert etats_coupes.filter(pl.col("date") == d).equals(etats.filter(pl.col("date") == d))
        coupes = instantane(etats_coupes).filter(pl.col("date") == d)
        assert coupes.equals(table.filter(pl.col("date") == d))


def test_journal_genere_futur_ajoute_et_deterministe(generation: Generation) -> None:
    entete = generation.entete
    jours = jours_ouvres(entete.ancrage_semaines, entete.date_injection)
    etats = tickets_etats(generation.evenements, jours)
    assert etats.equals(tickets_etats(generation.evenements, jours))
    table = instantane(etats)
    valider(table, SCHEMA_INSTANTANE)
    assert set(etats["type_ticket"].cast(pl.Utf8).unique()) == {t.value for t in TypeTicket}
    for d in (jours[0], jours[len(jours) // 3], jours[(2 * len(jours)) // 3], jours[-2]):
        coupe = [e for e in generation.evenements if jour_ouvre_de(e.horodatage) <= d]
        etats_coupes = tickets_etats(coupe, [d])
        assert etats_coupes.equals(etats.filter(pl.col("date") == d))
        assert instantane(etats_coupes).equals(table.filter(pl.col("date") == d))
