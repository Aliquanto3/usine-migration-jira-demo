# Travail différé

- source_spec: `_bmad-output/implementation-artifacts/spec-0-1-correctifs-revue-socle.md`
  summary: Mettre le spine à jour (AD-21 et tableau des couches) avec les tests plats `tests/unit/<dir>/test_<nom>.py`, `adaptateurs/cli` dans la lane 2 et la liste blanche des externes par couche.
  evidence: `ARCHITECTURE-SPINE.md:289` dit encore « `tests/unit/<chemin de ses répertoires source>` » seulement, alors que `controle_lanes.py` et `pyproject.toml` appliquent désormais ces règles ; une lane qui lit le spine voit une règle différente de celle de la CI. Passe par `bmad-correct-course` (artefact de planification).
  status: résolu le 2026-10-12 dans le spine (AD-21, tableau des couches avec colonne des externes, carte des lanes) par `sprint-change-proposal-2026-10-12.md`.
- source_spec: `_bmad-output/implementation-artifacts/spec-0-2-contrats-v0-et-ports.md`
  summary: Compléter les exclusions du Rejeu (AD-7) pour les traces et les coûts, et les qualifier par fichier.
  evidence: `contrats/passage.py:172-180` (`EXCLUSIONS_REJEU`) reprend la liste plate du spine et ignore `EntreeTrace.horodatage`, `depuis_cache`, `jetons_*`, `cout_estime_eur` et `ManifestePassage.cout_llm_eur`, qui varient d'un Passage à l'autre en Palier 2 ; exclure `horodatage` à plat le masquerait dans tous les fichiers (rétrospective de l'Epic 0, constat 16).
  status: spine amendé le 2026-10-12 (AD-7) par `sprint-change-proposal-2026-10-12.md` ; code à mettre en conformité en Story 0.9, avant le gel.
- source_spec: `_bmad-output/implementation-artifacts/spec-0-1-correctifs-revue-socle.md`
  summary: Tester `cles_sans_commentaire` sur des fins de ligne non LF (`\r`, `\r\n`, `\x85`, ` `).
  evidence: tous les tests sont en LF et `.gitattributes` force LF ; aucun consommateur réel aujourd'hui, à faire si le contrôle s'applique un jour à des YAML fournis par l'utilisateur.
- source_spec: `_bmad-output/implementation-artifacts/spec-0-9-gel-des-contrats-v1.md`
  summary: Vérifier si `entite` (et les attributs de rattachement) doivent rejoindre `non_nulles` dans `SCHEMA_INSTANTANE` et `SCHEMA_TICKET_ETAT`.
  evidence: Non vérifié (sévérité medium si avéré). D3 a déclaré un ensemble prudent ; si aucun producteur du domaine n'émet `entite` à null, le resserrer après le gel serait un changement majeur. À trancher en relisant `domaine/instantanes.py` et le générateur avant le premier ajout de colonne en L3.
- source_spec: `_bmad-output/implementation-artifacts/spec-5-1-etapes-deterministes-completes-et-passage-autoportant.md`
  summary: Câbler `EtapePrevision` dans le registre de `composition.py` dès que `domaine/prevision` (Stories 4.1 et 4.2) est sur `main`.
  evidence: l'étape `prevision` reste `EtapeBouchon()` ; un Passage réel n'a ni `previsions.json` ni `trace/previsions.jsonl`.
- source_spec: `_bmad-output/implementation-artifacts/spec-5-1-etapes-deterministes-completes-et-passage-autoportant.md`
  summary: Configurer la journalisation et l'encodage UTF-8 de la console de la CLI en Story 5.5 (rétrospective de l'Epic 0, constat 15).
  evidence: aucune configuration de `logging` ni de `sys.stdout` ; sortie « Journal �crit » sous Git Bash.
