---
title: 'Story 6.11 : [BONUS] Détection de doublons'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - "Étape `doublons` de la Chaîne, fichier `llm/doublons.json`, lecture `Consultation.doublons()` et restitution (Excel, UI) : nouvel `Etape`, `FICHIERS_PASSAGE` et port, hors périmètre de la story (contrats 2.x ou PR dédiée)."
  - "Câblage dans `composition.py` et commande `usine ia doublons` : la détection n'est pour l'instant appelable que par `detecter_doublons`."
  - "Clé de cache de la tâche `doublons` : elle porte la Date d'arrêté (seule `classification` l'ignore dans `cle_cache`) ; un rejeu un autre jour relance les appels. Ignorer la date pour `doublons` touche `ia/passerelle.py`, hors périmètre."
  - "Comparaison en O(n²) des Anomalies ouvertes (index inversé des mots si le stock dépasse quelques milliers)."
---

<intent-contract>

## Intent

**Problem:** Le stock d'Anomalies contient des doublons que le Pilote ne voit pas (FR-36) ; aucune tâche LLM `doublons` ni contrat de sortie n'existe.

**Approach:** Ajouter aux contrats (1.9.0, additif, commit dédié) la tâche `doublons`, `ReponseDoublons` et `SortieDoublon` ; une tâche `ia/doublons.py` (prompt `ia/prompts/doublons.md`) en deux temps : un tri local retient les paires d'Anomalies ouvertes aux textes proches (Jaccard sur les mots, score local), puis un appel par paire via la passerelle demande au modèle de confirmer. Seules les paires confirmées sont publiées, avec le score local, à revoir par le Pilote : aucune fusion, aucune écriture dans Jira.

## Boundaries & Constraints

**Always:** passer par `Passerelle.executer_structure` (Pseudonymisation de toute l'entrée, cache, contrôle, trace) ; lectures via le port `Consultation` (`anomalies`, `textes_tickets`) ; score calculé localement (le modèle ne donne aucun chiffre, AD-14) ; paires bornées (`MAX_PAIRES`) ; prompt en français, données entre délimiteurs.

**Never:** modifier `ia/passerelle.py`, `rendu/`, `composition.py`, le port `Consultation` ; fusionner ou écrire dans Jira ; changement non additif des contrats.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Paire confirmée | 2 Anomalies ouvertes proches, modèle `doublon=true` | `SortieDoublon(cle_a, cle_b, score local, justification, conforme)` | — |
| Paire refusée | modèle `doublon=false` | rien publié, trace conservée | — |
| Anomalie fermée, Cas de test, Certification | hors `ouvertes` ou autre type | jamais comparée | — |
| Justification citant une autre clé | « Voir DEMO-3 » | phrase retirée, `corrige` | — |
| Données protégées | numéro de compte dans un texte | jeton dans le prompt et la trace ; restitué dans la sortie | — |
| Rejeu | même entrée, même Date d'arrêté | cache, aucun appel | — |
| Plafond de coût | `PlafondCoutAtteint` | paires restantes non demandées, warning | pas d'échec |
| Échec du fournisseur | `UsineErreur` isolé / 3 d'affilée | paire écartée (trace `en_echec`) / détection en erreur | `UsineErreur` |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `ReponseDoublons(doublon, justification)`, `SortieDoublon(cle_a, cle_b, score 0..1, justification, statut_controle)` ; `versions.py` → `1.9.0` ; tests de version et `test_inventaire.py` ; amendement du Spine (commit `b36b94a`).
- `src/usine/ia/doublons.py` (nouveau) -- `similarite`, `paires_candidates`, `detecter`, `detecter_doublons`, `ContexteDoublons`.
- `src/usine/ia/prompts/doublons.md` (nouveau) -- consigne de verdict, sans chiffre.
- `tests/unit/ia/test_doublons.py` (nouveau) -- matrice I/O.

## Tasks & Acceptance

**Execution:**
- Contrats 1.9 (commit dédié « Feat: contrats 1.8, détection de doublons » ; 1.8.0 étant déjà prise par la 6.10-b, la version est 1.9.0).
- `ia/doublons.py`, `ia/prompts/doublons.md`, `tests/unit/ia/test_doublons.py`.

**Acceptance Criteria:**
- Given les Anomalies ouvertes pseudonymisées, when la détection s'exécute, then elle produit des paires avec un score, à revoir par le Pilote, sans aucune fusion ni écriture dans Jira.
- Given la nouvelle tâche et son contrat de sortie, when la lane démarre, then ils sont déjà dans `contrats/` et dans la liste des tâches d'AD-12, par un commit dédié avant le code.

## Spec Change Log

- 2026-10-13 : version des contrats 1.9.0 et non 1.8 (1.8.0 prise par la 6.10-b). Pas d'étape de Chaîne : reportée (voir `deferred`).
