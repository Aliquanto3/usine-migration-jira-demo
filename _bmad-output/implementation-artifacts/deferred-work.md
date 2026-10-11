# Travail différé

- source_spec: `_bmad-output/implementation-artifacts/spec-0-1-correctifs-revue-socle.md`
  summary: Mettre le spine à jour (AD-21 et tableau des couches) avec les tests plats `tests/unit/<dir>/test_<nom>.py`, `adaptateurs/cli` dans la lane 2 et la liste blanche des externes par couche.
  evidence: `ARCHITECTURE-SPINE.md:289` dit encore « `tests/unit/<chemin de ses répertoires source>` » seulement, alors que `controle_lanes.py` et `pyproject.toml` appliquent désormais ces règles ; une lane qui lit le spine voit une règle différente de celle de la CI. Passe par `bmad-correct-course` (artefact de planification).
- source_spec: `_bmad-output/implementation-artifacts/spec-0-1-correctifs-revue-socle.md`
  summary: Tester `cles_sans_commentaire` sur des fins de ligne non LF (`\r`, `\r\n`, `\x85`, ` `).
  evidence: tous les tests sont en LF et `.gitattributes` force LF ; aucun consommateur réel aujourd'hui, à faire si le contrôle s'applique un jour à des YAML fournis par l'utilisateur.
