"""Indicateurs de météo IND-1 à IND-8 et Météo par Entité, selon la Grille (FR-11, FR-15 à FR-17).

Fonctions pures : Date d'arrêté, Entités, Grille, `version_grille`, Programme et ancrage des
semaines arrivent en paramètre. Un indicateur que la donnée ou un garde-fou de volume ne permet
pas d'évaluer est `non_evaluable`, de valeur `0/0`, avec un motif : il ne change pas la Météo.
`verifier_grille` contrôle la cohérence des seuils entre couleurs (FR-18).

L'évolution de la Météo à J-1 et J-5 (FR-19) n'est pas calculée ici : elle se lit par
`Consultation.evolution_meteo` sur la Météo de chaque Jour ouvré publiée (D8, dérivation de
lecture).
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR, StatutIndicateur
from usine.contrats.calendrier import (
    est_jour_ouvre,
    fenetre_glissante,
    jour_ouvre_precedent,
    jours_ouvres,
    semaine_programme,
    verifier_lundi,
)
from usine.contrats.config import (
    ConfigProgramme,
    EntiteProgramme,
    GardeFous,
    GrilleMeteo,
    RegleIndicateur,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.schemas import valider
from usine.contrats.tickets import (
    SCHEMA_TICKET_ETAT,
    STATUTS_FERMES,
    Gravite,
    Phase,
    StatutCertification,
    StatutTest,
    TypeTicket,
    rang_cle,
)

_COMPARAISONS: Mapping[Operateur, Callable[[Fraction, Fraction], bool]] = {
    Operateur.superieur_ou_egal: lambda valeur, seuil: valeur >= seuil,
    Operateur.superieur: lambda valeur, seuil: valeur > seuil,
}

_COULEURS_DE_REGLE: tuple[Couleur, ...] = tuple(
    couleur for couleur in sorted(Couleur, reverse=True) if couleur is not Couleur.vert
)
"""Couleurs portant un seuil, de la plus grave à la moins grave."""

DECALAGE_IND8 = 5
"""IND-8 compare IND-4 à la Date d'arrêté et à J-5 (Jours ouvrés)."""

_FERMES = [statut.value for statut in STATUTS_FERMES]
_GRAVITES_IND7 = [Gravite.bloquante.value, Gravite.majeure.value]
_EXECUTES = [StatutTest.ok.value, StatutTest.ko.value]


def _severite(seuil: tuple[Operateur, Fraction]) -> tuple[Fraction, int]:
    """Clé de sévérité : plus elle est grande, plus le seuil est difficile à franchir.

    `>= v` se déclenche sur `[v, ∞)`, `> v` sur `(v, ∞)` : à valeur égale, `>` est plus sévère.
    """
    operateur, valeur = seuil
    return (valeur, 1 if operateur is Operateur.superieur else 0)


def _decimal_exact(valeur: Fraction) -> str:
    """Écriture décimale exacte d'un seuil (`Fraction(1, 5)` → `0.2`), fraction sinon."""
    if valeur.denominator == 1:
        return str(valeur.numerator)
    for chiffres in range(1, 64):
        mise_a_l_echelle = valeur * 10**chiffres
        if mise_a_l_echelle.denominator == 1:
            signe = "-" if valeur < 0 else ""
            entier = str(abs(mise_a_l_echelle.numerator)).rjust(chiffres + 1, "0")
            return f"{signe}{entier[:-chiffres]}.{entier[-chiffres:]}"
    return str(valeur)


def _ecrire_seuil(seuil: tuple[Operateur, Fraction]) -> str:
    operateur, valeur = seuil
    return f"{operateur.value} {_decimal_exact(valeur)}"


def verifier_grille(grille: GrilleMeteo, source: str) -> GrilleMeteo:
    """Refuse une Grille où une couleur est plus sévère qu'une couleur plus grave (FR-18).

    Toutes les règles sont vérifiées, actives ou non, sur chaque paire de couleurs présentes.
    Des seuils égaux sont acceptés. `source` (nom du fichier) préfixe le message d'erreur.
    Renvoie la Grille inchangée.
    """
    for code, regle in grille.indicateurs.items():
        presentes = [c for c in _COULEURS_DE_REGLE if c in regle.seuils]
        for rang_grave, plus_grave in enumerate(presentes):
            for moins_grave in presentes[rang_grave + 1 :]:
                seuil_moins = regle.seuils[moins_grave]
                seuil_plus = regle.seuils[plus_grave]
                if _severite(seuil_moins) > _severite(seuil_plus):
                    raise UsineErreur(
                        f"{source} : règle {code.value} : seuil {moins_grave.value}"
                        f" « {_ecrire_seuil(seuil_moins)} » plus sévère que le seuil"
                        f" {plus_grave.value} « {_ecrire_seuil(seuil_plus)} » (une couleur"
                        " moins grave doit se déclencher avant une plus grave)"
                    )
    return grille


# --- Programme : Entité, Vague en cours, Phase en cours ---


def _entite_du_programme(programme: ConfigProgramme, entite: str) -> EntiteProgramme:
    for candidate in programme.entites:
        if candidate.code == entite:
            return candidate
    raise UsineErreur(f"Entité {entite} absente du Programme « {programme.nom} »")


def phase_en_cours(programme: ConfigProgramme, entite: str, d: date, ancrage: date) -> Phase | None:
    """Phase en cours de l'Entité en `d` : Phase du calendrier de sa Vague contenant la semaine.

    La semaine est `semaine_programme(d, ancrage)`. Si plusieurs Phases la contiennent
    (chevauchement), celle au début le plus tardif, puis au rang le plus élevé dans la
    configuration (règle du générateur). Aucune Phase ne la contient, ou `d` est antérieur à
    l'ancrage : `None` (pas de repli sur la dernière Phase commencée). Lève une `UsineErreur`
    si l'Entité est absente du Programme ou si l'ancrage n'est pas un lundi.
    """
    code_vague = _entite_du_programme(programme, entite).vague
    verifier_lundi(ancrage)
    if d < ancrage:
        return None
    semaine = semaine_programme(d, ancrage)
    vague = next(v for v in programme.vagues if v.code == code_vague)
    en_cours = [
        (periode.semaine_debut, rang)
        for rang, periode in enumerate(vague.phases)
        if periode.semaine_debut <= semaine <= periode.semaine_fin
    ]
    if not en_cours:
        return None
    return vague.phases[max(en_cours)[1]].phase


# --- Mesures ---


@dataclass(frozen=True)
class _Mesure:
    """Valeur d'un indicateur pour une Entité, tickets en cause, statut et motif."""

    numerateur: int
    denominateur: int
    tickets_en_cause: tuple[str, ...]
    statut: StatutIndicateur = StatutIndicateur.evalue
    motif: str = ""

    @property
    def evaluee(self) -> bool:
        return self.statut is StatutIndicateur.evalue


def _non_evaluable(motif: str) -> _Mesure:
    """Indicateur non évaluable : `0/0`, sans ticket, avec un motif."""
    return _Mesure(0, 0, (), StatutIndicateur.non_evaluable, motif)


def _tries(cles: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(cles), key=rang_cle))


@dataclass(frozen=True)
class _Contexte:
    """Données communes au calcul des indicateurs à une Date d'arrêté."""

    etats: pl.DataFrame
    """État des tickets validé, réduit aux lignes de date ≤ Date d'arrêté."""
    date_arrete: date
    programme: ConfigProgramme
    ancrage: date
    garde_fous: GardeFous


def _anomalies_ouvertes(ctx: _Contexte, entite: str, gravite: Gravite) -> pl.DataFrame:
    """Anomalies de `gravite` ouvertes de l'Entité à la Date d'arrêté."""
    return ctx.etats.filter(
        (pl.col("date") == ctx.date_arrete)
        & (pl.col("entite") == entite)
        & (pl.col("type_ticket") == TypeTicket.anomalie.value)
        & (pl.col("gravite") == gravite.value)
        & pl.col("statut").is_not_null()
        & ~pl.col("statut").cast(pl.Utf8).is_in(_FERMES)
    )


def _nombre_ouvertes(ctx: _Contexte, entite: str, gravite: Gravite) -> _Mesure:
    """IND-1 (bloquantes) et IND-3 (majeures) : nombre d'Anomalies ouvertes, `n/1`."""
    cles = _anomalies_ouvertes(ctx, entite, gravite).get_column("cle_ticket").to_list()
    return _Mesure(len(cles), 1, _tries(cles))


def _ind2(ctx: _Contexte, entite: str) -> _Mesure:
    """IND-2 : âge maximal, en Jours ouvrés depuis la dernière Entrée, des bloquantes ouvertes.

    Tickets en cause : la ou les bloquantes de cet âge. Sans bloquante ouverte : non évaluable.
    """
    ouvertes = _anomalies_ouvertes(ctx, entite, Gravite.bloquante)
    if ouvertes.is_empty():
        return _non_evaluable("aucune Anomalie bloquante ouverte")
    ages: dict[str, int] = {}
    for cle, entree in ouvertes.select("cle_ticket", "date_derniere_entree").iter_rows():
        if entree is None:
            raise UsineErreur(
                f"IND-2 : Anomalie {cle} ouverte le {ctx.date_arrete.isoformat()} sans date de"
                " dernière Entrée"
            )
        ages[cle] = len(jours_ouvres(entree, ctx.date_arrete)) - 1
    age_max = max(ages.values())
    return _Mesure(age_max, 1, _tries(cle for cle, age in ages.items() if age == age_max))


def _taux_ko(ctx: _Contexte, entite: str, d: date) -> _Mesure:
    """IND-4 en `d` : `KO / (OK + KO)` des Cas de test de l'Entité dans la Phase en cours.

    Tickets en cause : les Cas de test KO. Non évaluable hors calendrier ou sous le garde-fou.
    """
    phase = phase_en_cours(ctx.programme, entite, d, ctx.ancrage)
    if phase is None:
        vague = _entite_du_programme(ctx.programme, entite).vague
        return _non_evaluable(
            f"aucune Phase en cours le {d.isoformat()} dans le calendrier de la Vague {vague}"
        )
    executes = ctx.etats.filter(
        (pl.col("date") == d)
        & (pl.col("entite") == entite)
        & (pl.col("type_ticket") == TypeTicket.cas_de_test.value)
        & (pl.col("phase") == phase.value)
        & pl.col("statut_test").cast(pl.Utf8).is_in(_EXECUTES)
    )
    nombre = executes.height
    minimum = ctx.garde_fous.ind4_min_tests_executes
    if nombre == 0:
        return _non_evaluable(
            f"aucun Cas de test exécuté en Phase {phase.value} le {d.isoformat()}"
        )
    if nombre < minimum:
        return _non_evaluable(
            f"{nombre} Cas de test exécuté(s) en Phase {phase.value} le {d.isoformat()},"
            f" en deçà du garde-fou de {minimum}"
        )
    ko = executes.filter(pl.col("statut_test") == StatutTest.ko.value)
    return _Mesure(ko.height, nombre, _tries(ko.get_column("cle_ticket").to_list()))


def _certifications(ctx: _Contexte, entite: str, statut: StatutCertification) -> _Mesure:
    """IND-5 (refusées) et IND-6 (réservées) : Certifications de l'Entité, Vague en cours."""
    vague = _entite_du_programme(ctx.programme, entite).vague
    cles = (
        ctx.etats.filter(
            (pl.col("date") == ctx.date_arrete)
            & (pl.col("entite") == entite)
            & (pl.col("type_ticket") == TypeTicket.certification.value)
            & (pl.col("vague") == vague)
            & (pl.col("statut_certification") == statut.value)
        )
        .get_column("cle_ticket")
        .to_list()
    )
    return _Mesure(len(cles), 1, _tries(cles))


def _ind7(ctx: _Contexte, entite: str) -> _Mesure:
    """IND-7 : Entrées / Sorties des Anomalies bloquantes ou majeures, Fenêtre glissante.

    Formules des KPI : Entrée en d si `date_derniere_entree == d` ; Sorties en d =
    `entrée − (ouvert(d) − ouvert(d-1))`. La gravité est celle du jour ; un jour absent de la
    table ou antérieur à l'ancrage ne compte rien. Tickets en cause : entrés ou sortis.
    """
    jours = [jour for jour in fenetre_glissante(ctx.date_arrete) if jour >= ctx.ancrage]
    lendemains = {jour_ouvre_precedent(jour): jour for jour in jours}
    anomalies = ctx.etats.filter(pl.col("type_ticket") == TypeTicket.anomalie.value).with_columns(
        (pl.col("statut").is_not_null() & ~pl.col("statut").cast(pl.Utf8).is_in(_FERMES))
        .cast(pl.Int64)
        .alias("ouvert")
    )
    du_jour = anomalies.filter(
        pl.col("date").is_in(jours)
        & (pl.col("entite") == entite)
        & pl.col("gravite").cast(pl.Utf8).is_in(_GRAVITES_IND7)
    ).with_columns(
        (pl.col("date_derniere_entree") == pl.col("date"))
        .fill_null(False)
        .cast(pl.Int64)
        .alias("entree")
    )
    veille = anomalies.filter(pl.col("date").is_in(list(lendemains))).select(
        "cle_ticket",
        pl.col("date")
        .replace_strict(
            list(lendemains), list(lendemains.values()), default=None, return_dtype=pl.Date()
        )
        .alias("date"),
        pl.col("ouvert").alias("ouvert_veille"),
    )
    mouvements = du_jour.join(veille, on=["cle_ticket", "date"], how="left").with_columns(
        (pl.col("entree") - pl.col("ouvert") + pl.col("ouvert_veille").fill_null(0))
        .clip(lower_bound=0)
        .alias("sortie")
    )
    entrees = int(mouvements.get_column("entree").sum())
    sorties = int(mouvements.get_column("sortie").sum())
    minimum = ctx.garde_fous.ind7_min_entrees_fenetre_glissante
    if entrees < minimum:
        return _non_evaluable(
            f"{entrees} Entrée(s) d'Anomalies bloquantes ou majeures sur la Fenêtre glissante,"
            f" en deçà du garde-fou de {minimum}"
        )
    if entrees == 0 and sorties == 0:
        return _non_evaluable(
            "aucune Entrée ni Sortie d'Anomalie bloquante ou majeure sur la Fenêtre glissante"
        )
    en_cause = mouvements.filter((pl.col("entree") > 0) | (pl.col("sortie") > 0))
    return _Mesure(entrees, sorties, _tries(en_cause.get_column("cle_ticket").to_list()))


def _ind8(ctx: _Contexte, entite: str, ind4: _Mesure) -> _Mesure:
    """IND-8 : `IND-4(D) − IND-4(J-5)` en fraction réduite ; tickets en cause : KO de D.

    Non évaluable si J-5 est antérieur à l'ancrage ou si IND-4 l'est à l'une des deux dates.
    """
    j5 = jour_ouvre_precedent(ctx.date_arrete, DECALAGE_IND8)
    if j5 < ctx.ancrage:
        return _non_evaluable(
            f"J-5 ({j5.isoformat()}) antérieur à l'ancrage des semaines"
            f" ({ctx.ancrage.isoformat()}) : IND-4 non évaluable le {j5.isoformat()}"
        )
    if not ind4.evaluee:
        return _non_evaluable(
            f"IND-4 non évaluable le {ctx.date_arrete.isoformat()} ({ind4.motif})"
        )
    ind4_j5 = _taux_ko(ctx, entite, j5)
    if not ind4_j5.evaluee:
        return _non_evaluable(f"IND-4 non évaluable le {j5.isoformat()} ({ind4_j5.motif})")
    hausse = Fraction(ind4.numerateur, ind4.denominateur) - Fraction(
        ind4_j5.numerateur, ind4_j5.denominateur
    )
    return _Mesure(hausse.numerator, hausse.denominator, ind4.tickets_en_cause)


def _mesures_entite(
    ctx: _Contexte, entite: str, codes: Sequence[CodeIndicateur]
) -> dict[CodeIndicateur, _Mesure]:
    """Mesure de chaque indicateur de `codes` pour l'Entité."""
    ind4: _Mesure | None = None

    def taux_ko() -> _Mesure:
        nonlocal ind4
        if ind4 is None:
            ind4 = _taux_ko(ctx, entite, ctx.date_arrete)
        return ind4

    calculs: dict[CodeIndicateur, Callable[[], _Mesure]] = {
        CodeIndicateur.ind_1: lambda: _nombre_ouvertes(ctx, entite, Gravite.bloquante),
        CodeIndicateur.ind_2: lambda: _ind2(ctx, entite),
        CodeIndicateur.ind_3: lambda: _nombre_ouvertes(ctx, entite, Gravite.majeure),
        CodeIndicateur.ind_4: taux_ko,
        CodeIndicateur.ind_5: lambda: _certifications(ctx, entite, StatutCertification.refusee),
        CodeIndicateur.ind_6: lambda: _certifications(ctx, entite, StatutCertification.reservee),
        CodeIndicateur.ind_7: lambda: _ind7(ctx, entite),
        CodeIndicateur.ind_8: lambda: _ind8(ctx, entite, taux_ko()),
    }
    return {code: calculs[code]() for code in codes}


# --- Contrôles et orchestration ---


def _indicateurs_actifs(grille: GrilleMeteo) -> list[tuple[CodeIndicateur, RegleIndicateur]]:
    """Indicateurs actifs de la Grille, dans l'ordre de `CodeIndicateur`."""
    return [
        (code, grille.indicateurs[code])
        for code in CodeIndicateur
        if code in grille.indicateurs and grille.indicateurs[code].active
    ]


def _verifier_entites(entites: Sequence[str], programme: ConfigProgramme) -> None:
    doublons = sorted({e for e in entites if list(entites).count(e) > 1})
    if doublons:
        raise UsineErreur(f"Entités demandées en double : {', '.join(doublons)}")
    connues = {entite.code for entite in programme.entites}
    inconnues = [e for e in entites if e not in connues]
    if inconnues:
        raise UsineErreur(
            f"Entité(s) absente(s) du Programme « {programme.nom} » : {', '.join(inconnues)}"
        )


def _verifier_dates(etats: pl.DataFrame, date_arrete: date, ancrage: date) -> None:
    """Refuse une Date d'arrêté non ouvrée, non calculée, ou un trou entre J-5 et D.

    Un ticket créé reste dans l'état de chaque date suivante : une date sans ligne n'est
    « aucun ticket créé » que si la table n'a aucune ligne antérieure. Sinon, la date n'a pas
    été calculée (postérieure à la dernière date ou trou) : refusée. De J-5 à J-1, les dates
    antérieures à l'ancrage ne sont pas exigées ; la Date d'arrêté est toujours contrôlée.
    """
    if not est_jour_ouvre(date_arrete):
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} : pas un Jour ouvré (week-end), état des"
            " tickets non calculé à cette date"
        )
    dates = etats.get_column("date")
    derniere = dates.max()
    if isinstance(derniere, date) and date_arrete > derniere:
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} postérieure à la dernière date de l'état"
            f" des tickets reçu ({derniere.isoformat()}) : états non calculés jusque-là"
        )
    debut = jour_ouvre_precedent(date_arrete, DECALAGE_IND8)
    for jour in jours_ouvres(debut, date_arrete):
        if jour < ancrage and jour != date_arrete:
            continue
        if not (dates == jour).any() and (dates < jour).any():
            raise UsineErreur(
                f"Date {jour.isoformat()} absente de l'état des tickets reçu, qui a des dates"
                f" antérieures : état non calculé à cette date (trou) ; la table doit couvrir"
                f" les Jours ouvrés de {debut.isoformat()} (J-5) à la Date d'arrêté"
                f" {date_arrete.isoformat()}"
            )


def _mesures(
    etats: pl.DataFrame,
    date_arrete: date,
    entites: Sequence[str],
    grille: GrilleMeteo,
    programme: ConfigProgramme,
    ancrage: date,
) -> tuple[list[tuple[CodeIndicateur, RegleIndicateur]], dict[str, dict[CodeIndicateur, _Mesure]]]:
    """Indicateurs actifs et mesure de chacun, par Entité."""
    actifs = _indicateurs_actifs(grille)
    _verifier_entites(entites, programme)
    verifier_lundi(ancrage)
    etats = valider(etats, SCHEMA_TICKET_ETAT)
    _verifier_dates(etats, date_arrete, ancrage)
    ctx = _Contexte(
        etats=etats.filter(pl.col("date") <= date_arrete),
        date_arrete=date_arrete,
        programme=programme,
        ancrage=ancrage,
        garde_fous=grille.garde_fous,
    )
    codes = [code for code, _ in actifs]
    return actifs, {entite: _mesures_entite(ctx, entite, codes) for entite in entites}


def _franchit(mesure: _Mesure, seuil: tuple[Operateur, Fraction]) -> bool:
    if mesure.denominateur == 0:
        return mesure.numerateur > 0
    operateur, valeur_seuil = seuil
    return _COMPARAISONS[operateur](Fraction(mesure.numerateur, mesure.denominateur), valeur_seuil)


def _couleur_franchie(regle: RegleIndicateur, mesure: _Mesure) -> Couleur:
    """Couleur la plus grave dont le seuil est franchi ; vert sinon ou si non évaluable."""
    if not mesure.evaluee:
        return Couleur.vert
    for couleur in _COULEURS_DE_REGLE:
        seuil = regle.seuils.get(couleur)
        if seuil is not None and _franchit(mesure, seuil):
            return couleur
    return Couleur.vert


def indicateurs(
    tickets_etats: pl.DataFrame,
    date_arrete: date,
    entites: Sequence[str],
    grille: GrilleMeteo,
    *,
    programme: ConfigProgramme,
    ancrage: date,
) -> pl.DataFrame:
    """`SCHEMA_INDICATEUR` : une ligne par Entité et par indicateur actif, à `date_arrete`.

    Ordre : Entités dans l'ordre de `entites`, indicateurs dans l'ordre de `CodeIndicateur`.
    Un indicateur non évaluable vaut `0/0`, couleur verte, avec un `motif` non vide.

    Précondition : `tickets_etats` couvre chaque Jour ouvré de J-5 à la Date d'arrêté (dès
    l'ancrage des semaines), comme le fait `EtapeMeteo` ; seules les lignes de date ≤ Date
    d'arrêté comptent. Une date sans ligne n'est « aucun ticket créé » que si la table n'a
    aucune ligne antérieure ; sinon (postérieure à sa dernière date ou trou), elle est refusée,
    comme une Date d'arrêté hors Jour ouvré ou une Entité absente de `programme`.
    """
    actifs, mesures = _mesures(tickets_etats, date_arrete, entites, grille, programme, ancrage)
    lignes: dict[str, list[object]] = {colonne: [] for colonne in SCHEMA_INDICATEUR.colonnes}
    for entite in entites:
        for code, regle in actifs:
            mesure = mesures[entite][code]
            lignes["date"].append(date_arrete)
            lignes["entite"].append(entite)
            lignes["code"].append(code.value)
            lignes["statut"].append(mesure.statut.value)
            lignes["motif"].append(mesure.motif)
            lignes["numerateur"].append(mesure.numerateur)
            lignes["denominateur"].append(mesure.denominateur)
            lignes["couleur"].append(_couleur_franchie(regle, mesure).value)
    table = pl.DataFrame(lignes, schema=dict(SCHEMA_INDICATEUR.colonnes))
    return valider(table, SCHEMA_INDICATEUR)


def meteo(
    tickets_etats: pl.DataFrame,
    date_arrete: date,
    entites: Sequence[str],
    grille: GrilleMeteo,
    version_grille: str,
    *,
    programme: ConfigProgramme,
    ancrage: date,
) -> tuple[MeteoEntite, ...]:
    """Météo de chaque Entité (ordre de `entites`) : la couleur la plus grave l'emporte (FR-16).

    La couleur retenue est la pire des couleurs franchies par les indicateurs actifs évalués ;
    un indicateur non évaluable ne déclenche jamais. La `MeteoEntite` porte toutes les Règles
    déclenchantes de cette couleur, dans l'ordre de `CodeIndicateur`, chacune avec sa valeur
    (`numerateur`/`denominateur` ; `n/0` avec `n > 0` vaut l'infini, cas d'IND-7 sans
    Sortie), l'opérateur et le seuil franchis, et `version_grille` ; elle est verte, sans
    règle, si aucun seuil actif n'est franchi.

    Tickets en cause (FR-17), triés par `rang_cle` : IND-1, IND-2, IND-3 → Anomalies ouvertes
    concernées (IND-2 : la ou les plus anciennes) ; IND-4, IND-8 → Cas de test KO de la Phase
    en cours à la Date d'arrêté ; IND-5, IND-6 → Certifications de la Vague en cours ; IND-7 →
    Anomalies bloquantes ou majeures entrées ou sorties sur la Fenêtre glissante.

    Sans état d'un jour à l'autre (pas d'hystérésis) : la Météo d'une date ne dépend d'aucune
    Météo antérieure, seulement des entrées de l'appel (état des tickets, Grille, Programme,
    ancrage).
    Précondition : celle d'`indicateurs`.
    """
    actifs, mesures = _mesures(tickets_etats, date_arrete, entites, grille, programme, ancrage)
    resultat: list[MeteoEntite] = []
    for entite in entites:
        franchies = [
            (code, regle, mesures[entite][code], _couleur_franchie(regle, mesures[entite][code]))
            for code, regle in actifs
        ]
        couleur_retenue = max((couleur for *_, couleur in franchies), default=Couleur.vert)
        regles: list[RegleDeclenchante] = []
        if couleur_retenue is not Couleur.vert:
            for code, regle, mesure, couleur in franchies:
                if couleur is not couleur_retenue:
                    continue
                operateur, valeur_seuil = regle.seuils[couleur]
                regles.append(
                    RegleDeclenchante(
                        code=code,
                        couleur=couleur,
                        operateur=operateur,
                        numerateur=mesure.numerateur,
                        denominateur=mesure.denominateur,
                        seuil_numerateur=valeur_seuil.numerator,
                        seuil_denominateur=valeur_seuil.denominator,
                        tickets_en_cause=mesure.tickets_en_cause,
                    )
                )
        resultat.append(
            MeteoEntite(
                date_arrete=date_arrete,
                entite=entite,
                couleur=couleur_retenue,
                regles=tuple(regles),
                version_grille=version_grille,
            )
        )
    return tuple(resultat)
