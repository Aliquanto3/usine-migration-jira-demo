# D6-D7 Presidio (FR) + versions to pin — r1.1 (accessed 2026-10-10)

Classes: F = fact from primary source; I = inference; U = unverified belief.
Note: Presidio docs moved (microsoft.github.io -> data-privacy-stack.github.io -> presidio.dataprivacystack.org, via 301s).

## Findings

1. presidio-analyzer and presidio-anonymizer are both 2.2.364, released 2026-07-22; requires_python <3.15,>=3.10; classifiers 3.10-3.14 (3.12 OK). Source: https://pypi.org/pypi/presidio-analyzer/json and .../presidio-anonymizer/json; PyPI JSON API; 2026-07-22; accessed 2026-10-10; high; F
2. Predefined recognizers include NO French-specific entity (no FR_*). Country lists: US, UK, ES, IT, PL, SG, AU, IN, FI, KR, NG, PH, CA, SE, ZA, TH, TR, DE. Generic: CREDIT_CARD, CRYPTO, DATE_TIME, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS, MAC_ADDRESS, NRP, LOCATION, PERSON, PHONE_NUMBER, MEDICAL_LICENSE, URL. Source: https://presidio.dataprivacystack.org/supported_entities/; Presidio docs; undated; accessed 2026-10-10; high; F (page gives no per-language support table). Consequence: NIR/SIRET/SIREN/plates/ticket IDs need custom recognizers (I).
3. Regex/checksum detection is language-agnostic but context words are not; docs say create one recognizer instance per language with supported_language and localized context (Spanish example: EmailRecognizer(supported_language="es", context=[...]) added to a RecognizerRegistry; AnalyzerEngine(registry=..., supported_languages=[...], nlp_engine=...)). Source: https://presidio.dataprivacystack.org/analyzer/languages/; Presidio docs; undated; 2026-10-10; high; F
4. Non-English NLP engine: NlpEngineProvider(nlp_configuration={"nlp_engine_name":"spacy","models":[{"lang_code":"es","model_name":"es_core_news_md"},...]}) or conf_file=YAML with models + ner_model_configuration (labels_to_ignore [O]; model_to_presidio_entity_mapping PER->PERSON, LOC->LOCATION, ORG->ORGANIZATION, DATE->DATE_TIME; low_confidence_score_multiplier 0.4; low_score_entity_names [ID, ORG]). French = substituting lang_code "fr" / fr_core_news_md (my substitution; docs show Spanish only). Source: https://presidio.dataprivacystack.org/analyzer/customizing_nlp_models/; Presidio docs; undated; 2026-10-10; high (pattern) / medium (French); F/I
5. YAML: recognizer_registry.global_regex_flags (e.g. 26); top-level supported_languages must equal the registry's; predefined recognizers accept per-recognizer supported_languages and enabled: false (e.g. disable SpacyRecognizer); custom pattern recognizers: name, supported_entity, supported_language, patterns[{name, regex, score}], context[]; context words boost score only with a context enhancer. Source: https://presidio.dataprivacystack.org/analyzer/analyzer_engine_provider/; Presidio docs; undated; 2026-10-10; high; F
6. Deny-list: PatternRecognizer(supported_entity="TITLE", deny_list=titles_list); analyze(text, language=...). Regex+context and ad_hoc_recognizers examples were not on the fetched page. Source: https://presidio.dataprivacystack.org/tutorial/01_deny_list/; Presidio docs; undated; 2026-10-10; high; F
7. Anonymizer operators: replace, redact, hash (sha256 salted), mask, encrypt (reversible with key), custom (lambda must return str), keep, surrogate_ahds. DeanonymizeEngine with OperatorConfig("decrypt", {"key": ...}) reverses encrypt. EngineResult.items hold start/end/entity_type/text/operator per span. Source: https://presidio.dataprivacystack.org/anonymizer/; Presidio docs; undated; 2026-10-10; medium-high (fetch-tool summary); F
8. Design for consistent reversible pseudonyms: encrypt is reversible but gives opaque ciphertext (poor LLM readability). A "custom" lambda mapping (entity, normalized text) -> stable token (PERSON_1, TICKET_3) via an app-side dict, then string-replace on the LLM output, fits. Docs fetched do not show this pattern; custom is not reversible by DeanonymizeEngine so keep your own mapping. I; medium
9. GLiNER: pip install 'presidio-analyzer[gliner]'; GLiNERRecognizer(model_name="urchade/gliner_multi_pii-v1", entity_mapping={person/name->PERSON, organization->ORGANIZATION, location->LOCATION}, flat_ner=False, multi_label=True, map_location="cpu"); registry.add_recognizer(...). Sample still loads a small spaCy model, removes SpacyRecognizer; tests English only; no French benchmark. Source: https://presidio.dataprivacystack.org/samples/python/gliner/; Presidio docs; undated; 2026-10-10; medium; F
10. spaCy fr_core_news_md/lg exist (news-genre, include NER); page failed to load version/NER scores. Source: https://spacy.io/models/fr; Explosion; undated; 2026-10-10; high on existence only; F
11. No primary-source evidence found on French NER quality or false positives in Presidio. Third-party only (PrivAiTe on PyPI: misses unusual single-word names, self-reported). U
12. Another library (MaskMe) uses fr_core_news_lg for French masking; third-party, not Presidio. https://maskme.readthedocs.io/en/latest/reference/ner.html; undated; low; F

## Versions table (PyPI JSON API, read live 2026-10-10)

| package | latest | release date | Python support | notable change | ref |
|---|---|---|---|---|---|
| presidio-analyzer | 2.2.364 | 2026-07-22 | >=3.10,<3.15; 3.12 yes | docs domain moved | pypi.org/project/presidio-analyzer/ |
| presidio-anonymizer | 2.2.364 | 2026-07-22 | same | - | pypi.org/project/presidio-anonymizer/ |
| duckdb | 1.5.6 | 2026-09-28 | >=3.10; 3.12 yes | still 1.x: 1.3.0 (2025-05-21), 1.4.0 (2025-09-16), 1.5.0 (2026-03-09); no 2.0 | pypi.org/project/duckdb/ |
| polars | 2.0.0 | 2026-10-06 | >=3.10; 3.12 yes | MAJOR 2.0, 4 days old: SQL window/QUALIFY and Decimal literal changes, Parquet ENUM read as String, cut/qcut deprecated; previous 1.44.0 (2026-08-24) | pypi.org/project/polars/ ; github.com/pola-rs/polars/releases/tag/py-2.0.0 |
| python-pptx | 1.0.2 | 2024-08-07 | classifiers 3.8-3.12 | no release for >2 years | pypi.org/project/python-pptx/ |
| openpyxl | 3.1.5 | 2024-06-28 | classifiers up to 3.12 | no release for >2 years | pypi.org/project/openpyxl/ |
| lightgbm | 4.7.0 | 2026-07-18 | >=3.10; 3.12 yes | requires numpy>=1.21.3, scipy | pypi.org/project/lightgbm/ |
| shap | 0.53.0 | 2026-10-09 | >=3.12 (3.12-3.15) | requires numpy>=2; 1 day old (prev 0.52.0 2026-05-28) | pypi.org/project/shap/ |
| streamlit | 1.65.0 | 2026-10-02 | >=3.10; 3.12 yes | ~bi-weekly 1.x minors, no 2.0 | pypi.org/project/streamlit/ |

Polars 2.0 breaking list is from a fetch-tool summary of the GitHub release page; PyPI date confirms.

## Bottom line (Presidio, French)

- Pin presidio-analyzer/anonymizer 2.2.364 on Python 3.12; install fr_core_news_md (or lg); NlpEngineProvider with models=[{"lang_code":"fr","model_name":"fr_core_news_md"}]; AnalyzerEngine(supported_languages=["fr"]); always analyze(language="fr").
- Re-register each kept predefined recognizer (EMAIL_ADDRESS, PHONE_NUMBER, IBAN_CODE, URL, IP_ADDRESS, CREDIT_CARD) with supported_language="fr" and French context words; test +33/06 phone formats (not verified here).
- No FR_* exists: add PatternRecognizers (regex + context + score) for ticket keys, NIR, SIREN/SIRET, plates, plus deny-lists for known client/app/entity names; declare in YAML for reviewability.
- Pseudonymise via operator "custom" (stable token from an app-side dict keyed by entity+normalized text), keep mapping per session, reverse by replacement on the LLM output; use encrypt/DeanonymizeEngine only if opaque tokens are acceptable.
- Treat spaCy French PER/LOC/ORG as a backstop (news-trained, ORG already down-weighted); evaluate on a small labelled sample; GLiNER multi recognizer is an optional second opinion, unvalidated for French.
- Polars 2.0 and shap 0.53 are days old: consider pinning polars 1.44.x unless 2.0 features are needed; shap forces numpy>=2 and Python>=3.12.

## Leads not chased
- Presidio regex-with-context and ad_hoc_recognizers tutorials; Faker custom-operator sample; transformers/stanza pages; languages-config.yml.
- GitHub microsoft/presidio issues on French and release notes 2.2.35x-364.
- spaCy fr model scores (explosion/spacy-models releases); CamemBERT NER via transformers engine.
- DuckDB 1.5 and Streamlit changelogs; python-pptx/openpyxl on Python 3.13.

## Looked for but not found
- Primary-source French NER quality or false-positive rates in Presidio.
- Any French predefined recognizer.
- Per-recognizer language support table.
- Explicit SHAP/LightGBM numpy-2 compatibility note (only requires_dist metadata).
- DuckDB/Streamlit breaking-change details for the last 12 months.
