# Contrôle des citations de research.md (digests uniquement, 0 WebFetch)

Périmètre : phrases portant un marqueur [n] ou [W], de « Synthèse » à « Recommandations » (les Recommandations ne portent aucun [n]). Versions, dates et tailles du § 7 : toutes concordantes avec d7-pypi-check-r2-lead.txt. Bloc [W] : concordant avec d4-wavestack-code-r1-1.md.

Phrases supportées : environ 80 (sur environ 95 phrases ou cellules citées). Problèmes : 15, listés ci-dessous.

| section | [n] | extrait | verdict | note |
|---|---|---|---|---|
| Synthèse 5 | [12][14] | « n'est pas documenté (10 ou 20 selon les sources) [12][14] » | wrong number | Le « 20 » vient de la RFC-61, soit [13]. La spec OpenAPI [12] ne donne aucun chiffre. Corriger en [13][14]. |
| Synthèse 2 | [9] | « Ils restent soumis aux limites de rafale ... et d'écriture par ticket » | partially | La page dit seulement que le trafic par jeton n'est pas concerné par les points. Les limites de rafale et par ticket s'appliquent à tous les appelants par inférence du vérificateur, sans phrase explicite d'Atlassian. |
| §1 tableau (API REST) | [1] | « Résolution passée : Non (lecture seule) » | partially | [1] (JRACLOUD-38572) ne parle que de `created`. « Resolved en lecture seule » vient d'un extrait de la communauté Atlassian, non lu en entier. |
| §1 tableau (nouvelle interface CSV) | [8] | « manque le mappage des valeurs, l'import dans un projet existant et la mise à jour [8] » | partially | JRACLOUD-84562 ne couvre que le mappage des valeurs. L'import dans un projet existant relève de JRACLOUD-84385, la mise à jour de JRACLOUD-84516. |
| §1 puces | [8] | « Atlassian recommande ... Son retrait est annoncé, sans date [8] » | partially | Le retrait vient d'une réponse communautaire (« sera déprécié quand la nouvelle couvrira tout »), pas d'une annonce Atlassian. Le conseil « Switch to the old experience » vient d'un article KB, pas de JRACLOUD-84562. |
| §2 Cloud v3 | [12][13] | « `/search` est retiré et renvoie 410 » | partially | La spec [12] indique « deprecated, currently being removed ». Le 410 vient de rapports tiers (GitHub, Adobe), et [13] (RFC 2024) n'en parle pas. |
| §2 dernière puce | [17] | « validation JQL modifiée le 2026-10-08, dépréciation effective le 2026-11-16 » | partially | Le 2026-11-16 concerne la dépréciation des recherches par propriétés d'entité utilisateur (annoncée le 2026-10-07), pas la validation JQL du 2026-10-08. |
| §4 Mistral | [41] | « Les données peuvent servir à l'entraînement. » | partially | L'extrait de l'aide Mistral ne donne que les limites. L'opt-in d'entraînement vient de sources secondaires. |
| §4/§5 tableau Qwen | [48-51] | « appels d'outils cassés quand le raisonnement est actif, dans llama.cpp comme dans Ollama » | partially | Ceci est établi pour llama.cpp (#20837). Le ticket Ollama #14493 attribue l'instabilité à un décalage de parseur (Hermes JSON contre XML) et n'est pas lié au raisonnement. Un mainteneur conteste aussi « non fonctionnel ». |
| §5 tableau Ministral | [46] | « MMMLU 0,706 (éditeur) » | partially | 0,706 est le score du modèle **base**, pas de l'Instruct. Aucun score français n'est donné. |
| §5 tableau Granite | [53] | « 5,35 Go » | partially | La taille vient du dépôt `granite-4.2-8b-GGUF`, absent de l'annexe. [53] pointe vers le dépôt `granite-4.2-8b`. |
| §5 Service | [45] | « Ne pas quantifier le cache KV en dessous de q8_0 » | partially | La doc avertit seulement des quantifications extrêmes (par exemple `-ctk q4_0`). « en dessous de q8_0 » extrapole. |
| §5 Risques | [45] | « classe Ministral en analyseur « Generic » » | partially | La doc cite « Ministral-3b » (ancien modèle). Qu'elle s'applique à Ministral 3 8B est une inférence. Pour le risque, écrire « peut classer ». |
| §6 | [59] | « Reconnaisseurs maison (PatternRecognizer ... déclarés en YAML) [59] » | partially | [59] (customizing_nlp_models) couvre le moteur NLP. Les reconnaisseurs YAML viennent de `analyzer/analyzer_engine_provider` et la liste de refus de `tutorial/01_deny_list`, deux pages absentes de l'annexe. |
| Enseignements croisés | [38][54] | « Groq [38], llama.cpp et Ollama [54] en souffrent » | not supported | Pour llama.cpp, la combinaison schéma + outils est seulement non documentée (README muet), pas constatée cassée. [54] ne porte que sur Ollama (#13750). |
