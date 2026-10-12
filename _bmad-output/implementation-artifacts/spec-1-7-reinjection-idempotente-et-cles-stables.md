---
title: 'Story 1.7 : Réinjection idempotente et clés stables'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '6ae6233f023be0c8fbc3eee6625282c6b7eebcce'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Ticket créé sans clé rendue sur un site à numérotation décalée : refusé comme étranger au lieu d'être repris.
    evidence: |-
      La reprise sans correspondance ne cherche que la clé générée ; cas cumulant numérotation décalée et réponse POST /issue perdue. Sortie : retirer le ticket à la main.
    location: >-
      src/usine/generateur/injecteur/injection.py (rapprocher)
    severity: low
  - summary: >-
      État partiel au format 1.6 (sans url_site) : branche de _partiel_du_site non testée en CLI.
    evidence: |-
      L'injection réelle 1.6 a abouti sans état partiel ; aucun fichier de ce format n'existe à reprendre.
    location: >-
      src/usine/generateur/injecteur/cli.py (_partiel_du_site)
    severity: low
  - summary: >-
      Contrôle de la liaison H-17 d'un projet trouvé par nom (différé 1.6 n° 2) toujours absent.
    evidence: |-
      Un projet mal câblé échoue à la première transition avec état partiel ; la réinjection reprend après correction.
    location: >-
      src/usine/generateur/injecteur/site.py (controler)
    severity: low
  - summary: >-
      Garde de date avant préparation : un projet recréé (même URL et clé) avec un Journal de date différente est refusé.
    evidence: |-
      _verifier_date ne connaît pas encore id_projet ; le message indique de déplacer donnees/injection/.
    location: >-
      src/usine/generateur/injecteur/cli.py (_verifier_date)
    severity: low
---

<intent-contract>

## Intent

**Problem:** L'injecteur de la Story 1.6 refuse tout projet peuplé ou tout manifeste existant : impossible de relancer l'injection (démo à refaire, reprise après interruption, site Jira Free recréé) sans casser les clés. Le projet `DEMO` réel porte déjà 3 384 tickets (DEMO-1 à DEMO-3384, manifeste dans `donnees/injection/`). Par ailleurs `config/jira.yaml` porte des identifiants `champs` fictifs : `usine rapport` ne peut pas lire le projet réel.

**Approach:** Avant toute écriture de ticket, l'injecteur liste exactement les tickets du projet (`POST /rest/api/3/search/jql`, paginé par `nextPageToken`) et les rapproche du plan : un ticket déjà présent (clé connue par le manifeste ou l'état partiel du même site, sinon clé générée) est repris, amené à son statut cible s'il n'y est pas, jamais recréé ; seuls les tickets absents sont créés, dans l'ordre des clés, et leur clé réelle entre dans `correspondance_cles`. Tâche préalable : `champs` de `config/jira.yaml` alignés sur les identifiants réels (10043 à 10049), fixtures et tests L2 adaptés.

## Boundaries & Constraints

**Always:**
- Rapprochement entièrement calculé (fonction pure) avant la première écriture de ticket : toute incohérence lève une `UsineErreur` sans rien créer ni transitionner.
- Identité d'un ticket repris : même type Jira et même `summary` (espaces de bord ignorés) que le ticket planifié ; statut d'une Anomalie lu par son nom Jira (`config.valeurs.statut`).
- Même site = même `url_site`, `cle_projet` et `id_projet` que le `site_jira.json` précédent (absent : même site présumé). Même site : correspondance du manifeste et de l'état partiel appliquée, Date d'injection du manifeste = celle du Journal, `debut_injection` d'origine conservé. Nouveau site : état précédent ignoré, injection complète, nouveau manifeste.
- Réinjection sans aucune écriture de ticket sur le même site : `manifeste_injection.json` et `site_jira.json` ne sont pas réécrits (contenu identique ⇒ fichier intact).
- Tests sans réseau (faux Jira `httpx.MockTransport`) ; cœur de l'injecteur n'important que `contrats` ; débit plafonné inchangé.

**Never:**
- Supprimer, modifier les champs ou recréer un ticket existant ; toucher un autre projet que `cle_projet` (jamais `KAN`).
- Modifier `contrats/`, `ports/`, `adaptateurs/jira_http`.
- Remettre un ticket en arrière par une transition hors H-17 (statut cible inaccessible : erreur, rien d'écrit).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Réinjection complète | projet injecté, manifeste et `site_jira.json` présents | 0 création, 0 transition ; fichiers intacts ; résumé « 0 créé, N repris » | — |
| Reprise après interruption | k tickets créés, état partiel, ticket k au statut intermédiaire | tickets 1..k repris (k amené à son statut), k+1..N créés ; manifeste écrit, `debut` d'origine | — |
| Ticket créé sans clé enregistrée | ticket présent à la clé générée, absent de la correspondance | repris (identité vérifiée) | — |
| Second site vierge | `site_jira.json` d'un autre site, manifeste ancien | injection complète ; clés identiques au premier site | — |
| Numérotation décalée | site vierge dont la numérotation ne part pas de 1 | `correspondance_cles` du manifeste porte les clés réelles ; `SourceJournal(journal, manifeste)` relit le Journal sous ces clés | — |
| Ticket étranger | ticket du projet sans correspondant dans le plan, ou d'identité différente | rien n'est écrit | `UsineErreur` nommant la clé |
| Ticket connu absent | clé de la correspondance (même site) absente de la liste | rien n'est écrit | `UsineErreur` (index en retard ou ticket supprimé) |
| Journal différent | Date d'injection du manifeste ≠ celle du Journal, même site | rien n'est envoyé | `UsineErreur` nommant les deux dates |
| Interruption de la réinjection | erreur HTTP en cours | état partiel = correspondance complète connue (reprises + créations) | `InjectionInterrompue` |

</intent-contract>

## Code Map

- `src/usine/generateur/injecteur/injection.py` -- `injecter` : remplacer `_compter_tickets` (garde « projet peuplé », approximative) par liste exacte + rapprochement ; `_Transitions` (cache par statut de départ) réutilisable tel quel ; `EtatInjectionPartielle`, `InjectionInterrompue`.
- `src/usine/generateur/injecteur/plan.py` -- `TicketPlanifie.statut_final`, `chemin_statuts` (BFS H-17 ; « Nouvelle » inaccessible), `noms_jira`, `STATUT_INITIAL`.
- `src/usine/generateur/injecteur/site.py` -- `ClientJira` (Protocol `requete`/`requete_liste`), `SiteDemo` (`url_site`, `cle_projet`, `id_projet`, `types`), `API`.
- `src/usine/generateur/injecteur/cli.py` -- `executer_injection` : garde du manifeste existant à retirer ; lecture de l'état précédent (manifeste, `etat_injection_partielle.json`, `site_jira.json`) ; écriture atomique ; `ecarts_champs`.
- `src/usine/contrats/evenements.py` (gelé) -- `ManifesteInjection` (`correspondance_cles` injective) : relu par `ManifesteInjection.model_validate`.
- `src/usine/adaptateurs/journal/__init__.py` (L2) -- `SourceJournal(journal, manifeste)` applique la correspondance à la lecture (AD-4) : rien à changer.
- `tests/unit/generateur/injecteur/faux_jira.py` -- ajouter `POST /search/jql` (pages par `nextPageToken`, champs `summary`, `issuetype`, `status`) et un numéro de départ des clés réglable ; `ecritures()` doit exclure la recherche.
- `config/jira.yaml`, `tests/fixtures/jira_cloud/*`, `tests/fixtures/jira_dc/*`, `tests/unit/adaptateurs/jira_{cloud,dc,http}/*`, `tests/unit/generateur/injecteur/test_cli.py` -- identifiants fictifs `customfield_10001` à `10007` (entite → statut_certification) à remplacer par `10043` à `10049` dans le même ordre (aucune collision : `10046` n'apparaît que dans `test_cli.py`, comme valeur de site).

## Tasks & Acceptance

**Execution:**
- `config/jira.yaml` + fixtures et tests L2 listés -- remplacement mécanique `customfield_1000{1..7}` → `customfield_100{43..49}` ; commentaire d'en-tête mis à jour -- `usine rapport` lit le projet réel (File humaine 1.6).
- `src/usine/generateur/injecteur/injection.py` -- `TicketExistant` (clé, id de type, summary, nom de statut) ; `lister_tickets(client, cle_projet)` (search/jql paginé, `maxResults` 100) ; `EtatPrecedent` (debut, fin éventuelle, correspondance) ; `rapprocher(plan, existants, site, config, precedent) -> Rapprochement` pur (repris avec chemin de statuts, à créer) ; `injecter(..., precedent=None) -> BilanInjection` (manifeste, créés, repris, transitions).
- `src/usine/generateur/injecteur/cli.py` -- état précédent du même site, garde de la Date d'injection, écriture « si changé » du manifeste et de `site_jira.json`, état partiel enrichi, résumé « créés / repris / transitions ».
- `src/usine/generateur/injecteur/__init__.py` -- exports.
- `tests/unit/generateur/injecteur/` -- faux Jira étendu ; tests de chaque ligne de la matrice ; tests existants « projet non vide » et « manifeste existant » remplacés par la réinjection.

**Acceptance Criteria:**
- Given un faux Jira injecté par `executer_injection`, when on relance `executer_injection` avec les mêmes fichiers, then aucune requête d'écriture de ticket n'est émise, chaque ticket garde son statut et le manifeste et `site_jira.json` sont octet pour octet identiques.
- Given deux faux Jira vierges successifs, when on injecte le même Journal dans chacun (même `donnees/injection/`), then les clés Jira sont identiques ; et sur un site à numérotation décalée la `correspondance_cles` relue par `SourceJournal` donne les clés réelles.
- Given `config/jira.yaml`, when on le compare à `site_jira.json` du site réel, then `champs` est identique (10043 à 10049) et toute la suite passe.

## Design Notes

**Points différés de la 1.6 :** (1) garde « projet peuplé » approximative → remplacée par la liste exacte et le rapprochement, avant toute écriture de ticket, tous types ; (2) contrôle de la liaison H-17 d'un projet trouvé par nom → non traité : un projet mal câblé échoue à la première transition, avec état partiel, et la réinjection reprend après correction (risque borné à un ticket) ; (3) `champs` fictifs → tâche préalable ; (4) état partiel sans statut par ticket, ticket ambigu → la liste exacte donne le statut réel et la reprise par clé générée couvre le ticket créé sans clé rendue ; (5) champs obligatoires, contextes, statuts réutilisés → clos par l'injection réelle du 2026-10-12 (3 384 tickets, 8 993 transitions, aucun échec) ; (6) conformité du faux Jira → éprouvée par cette injection réelle ; la recherche `search/jql` le sera par la réinjection réelle après intégration.

**Index de recherche :** `search/jql` est à cohérence différée. Un ticket connu absent de la liste fait refuser (jamais créer) ; un ticket créé sans clé enregistrée et pas encore indexé serait recréé : attendre une minute avant de relancer après une interruption (consigné dans l'aide de la commande).

**Fichiers hors lane :** `config/jira.yaml`, `tests/fixtures/jira_cloud/*.json`, `tests/fixtures/jira_dc/*.json`, `tests/unit/adaptateurs/jira_cloud/test_conversion.py`, `tests/unit/adaptateurs/jira_cloud/test_source.py`, `tests/unit/adaptateurs/jira_dc/test_source.py`, `tests/unit/adaptateurs/jira_http/test_transport.py` (L2) : alignement des identifiants de champs sur le site réel, demandé par Anaël (File humaine de la 1.6) ; remplacement mécanique d'identifiants, sans changement de logique.

**Environnement :** worktree `C:/Users/Utilisateur/Documents/GitHub/usine-lanes/lane-1-donnees` ; aucun `.env`, aucun réseau. La réinjection réelle et `usine rapport` sont lancés après intégration, depuis `main`.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe.
- `uv run python .github/scripts/controle_lanes.py --branche lane/1-donnees --base main` -- expected: seuls les fichiers hors lane consignés.

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 37 findings — high 0, medium 5, low 20, false 5, maybe-false 7
- findings:
  - `[low]` `reject` (intent 1) AC1 éprouvé sur faux Jira seulement — imposé par « sans réseau » ; réinjection réelle après intégration.
  - `[false]` `reject` (intent 2) Convergence plutôt que gel — sur un projet intact, 0 écriture (testé) ; seul un ticket en retard est avancé.
  - `[medium]` `patch` (intent 3) Site recréé avec même `id_projet` traité comme même site → blocage « ticket connu absent » — projet vide ⇒ état précédent ignoré ; tests `test_projet_vide_*`.
  - `[maybe-false]` `reject` (intent 4) Correspondance non prouvée jusqu'à `usine rapport` — `SourceJournal` est le seul lecteur du Journal (L2, inchangé) ; vérifié par la relance réelle.
  - `[low]` `reject` (intent 5) AC3 sans test automatique — `donnees/` non versionné ; vérifié par script contre `site_jira.json`.
  - `[false]` `reject` (intent 6) Point différé 2 non résolu — disposition explicite consignée (différé).
  - `[false]` `reject` (intent 7) Fichiers réécrits si contenu changé — lecture voulue : intacts sur une réinjection sans écriture (testé octet pour octet).
  - `[false]` `reject` (intent 8) Fichiers hors lane — demandés et consignés.
  - `[medium]` `patch` (vgap 1) Fusion manifeste + état partiel ultérieur non testée — tests `test_manifeste_et_etat_partiel_ulterieur_fin_relue`, `..._en_conflit`.
  - `[low]` `patch` (vgap 2) Garde de date par l'état partiel seul non testée — test `test_journal_different_par_etat_partiel_seul`.
  - `[low]` `defer` (vgap 3) État partiel au format 1.6 non testé en CLI — aucun fichier de ce format n'existe.
  - `[low]` `reject` (vgap autre) AC3 sans test — même raison que intent 5.
  - `[medium]` `patch` (edge 1) Page non terminale sans `nextPageToken` tronque la liste → doublons — `UsineErreur` ; test ajouté.
  - `[low]` `defer` (edge 2) Ticket sans clé rendue sur site décalé refusé comme étranger — cumul rare, sortie manuelle.
  - `[false]` `reject` (edge 3) Dérive des clés si une clé générée manque — c'est le comportement AC2 : clé réelle portée par `correspondance_cles`.
  - `[maybe-false]` `reject` (edge 4) Titres en double → mauvais ticket adopté — ne survient que si un autre ticket occupe la clé générée hors correspondance ; type + résumé vérifiés.
  - `[low]` `reject` (edge 5) Conflit de correspondance détecté après la préparation — préparation idempotente par nom, aucune écriture de ticket.
  - `[medium]` `patch` (edge 6) Manifeste d'un autre site sans `site_jira.json`, projet vierge → blocage — même correctif que intent 3.
  - `[low]` `patch` (edge 7) `unlink` de l'état partiel peut lever `OSError` après le manifeste — `contextlib.suppress(OSError)`.
  - `[low]` `defer` (edge 8) Garde de date sans `id_projet` refuse un projet recréé — message indique de déplacer `donnees/injection/`.
  - `[low]` `defer` (edge 9, claim) Même constat que edge 8.
  - `[low]` `defer` (edge 10, claim) Même constat que edge 2.
  - `[maybe-false]` `reject` (edge 11, claim) `fin` relue sans écriture après interruption — voulu : `fin` inconnue tant qu'un état partiel existe ; jamais sur le cas AC1.
  - `[medium]` `patch` (blind 1) Même site décidé par `id_projet` répétable — même correctif que intent 3.
  - `[low]` `defer` (blind 2) Garde de date et contrôle de site divergent — même entrée que edge 8.
  - `[low]` `reject` (blind 3) Nouveau site remplace les fichiers sans alerte — l'ancien site n'est plus lisible de toute façon ; démo à site unique.
  - `[low]` `defer` (blind 4) Reprise sans clé seulement si la numérotation part de 1 — même entrée que edge 2.
  - `[maybe-false]` `reject` (blind 5) Identité type + résumé faible — même raison que edge 4.
  - `[maybe-false]` `reject` (blind 6) `debut` d'origine conservé — la coupure de la Source composite se fait sur `fin`, pas sur `debut`.
  - `[low]` `patch` (blind 7) Commentaire faux dans `test_numerotation_decalee`, comptes non vérifiés — commentaire corrigé, `repris`/`crees` vérifiés.
  - `[low]` `patch` (blind 8) Branches CLI non testées — fusion, conflit, date par état partiel couverts ; format 1.6 différé.
  - `[low]` `patch` (blind 9) Commentaire périmé dans `test_injection_ecrit_manifeste_et_site` — reformulé.
  - `[low]` `patch` (blind 10) Ticket étranger bloquant sans issue indiquée — message complété.
  - `[maybe-false]` `reject` (blind 11) `depuis_json` trop permissif — fichier écrit par l'injecteur lui-même ; l'injectivité est contrôlée dans `rapprocher`.
  - `[low]` `patch` (blind 12) `assert` en production — `UsineErreur`.
  - `[low]` `reject` (blind 13) `ecarts_champs` déplacé — bruit de diff sans effet.
  - `[maybe-false]` `reject` (blind 14) Spec décalée du code — correction = éditer la spec de ce build.

## Auto Run Result

**Statut : done** (mode économique : revue unique, pas de revue de suivi).

**Résumé :** réinjection idempotente : liste exacte du projet par `search/jql`, rapprochement pur avant toute écriture (reprise par clé connue ou générée, identité type + résumé, convergence du statut H-17), création des seuls tickets absents, correspondance mise à jour, manifeste et `site_jira.json` intacts quand rien n'est écrit ; projet vide = nouveau site. Identifiants `champs` de `config/jira.yaml` alignés sur le site réel (10043 à 10049).

**Fichiers :** `src/usine/generateur/injecteur/{injection,cli,__init__}.py` (réinjection) ; `config/jira.yaml`, `tests/fixtures/jira_{cloud,dc}/*.json`, `tests/unit/adaptateurs/jira_{cloud,dc,http}/test_*.py` (identifiants réels, hors lane) ; `tests/unit/generateur/injecteur/{faux_jira,test_cli,test_injection,test_site,test_reinjection}.py` (doublure et tests).

**Revue :** 3 entrées medium patchées (même site / projet vide, fusion manifeste + état partiel, pagination tronquée), 8 low patchées ; 4 entrées différées ; rejets motivés ci-dessus.

**Revue de suivi recommandée : true** -- trois medium patchés ; risque non vérifié nommé : le comportement réel de `search/jql` (pagination, cohérence d'index) sur 3 384 tickets, éprouvé seulement par la réinjection réelle. Non lancée (mode économique demandé par Anaël).

**Vérification :** ruff, ruff format, mypy, lint-imports, pytest (2261 passed, 1 skipped).

**Risques résiduels :** index de recherche en retard juste après une interruption (attendre une minute) ; `search/jql` réel.
