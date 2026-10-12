"""Prévision statistique de sortie du rouge (FR-20, AD-18).

Une seule Baseline, dans `baseline`, sur le contrat gelé `SerieStock` : la Chaîne et
l'évaluation sur données réelles (`evaluation/zenodo`) l'appellent telle quelle. `serie`
construit la `SerieStock` de chaque Entité depuis l'état des tickets d'un Passage ; `risque`
projette le Risque d'entrée en rouge des Entités non rouges. Fonctions pures, déterministes,
en nombres exacts ; aucun chiffre n'est produit par un LLM.
"""
