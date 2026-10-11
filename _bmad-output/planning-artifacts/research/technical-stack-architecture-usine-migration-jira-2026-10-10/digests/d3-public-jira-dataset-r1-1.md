# d3 - Public Jira Dataset (Montgomery et al.) - digest r1.1
Accessed 2026-10-10 for all items. class: F = fact (primary), I = inference.

## Findings
1. Latest version is v7, published 2025-06-23 (record 15719919; concept DOI 10.5281/zenodo.5882881 resolves to it); no newer version; within 12 months of today. | https://zenodo.org/records/5882881 and https://zenodo.org/api/records/15719919 | Zenodo (Univ. Hamburg authors) | 2025-06-23 | high | F
2. Single file `2025-06-23 ThePublicJiraDataset.zip`, 5,813,135,238 bytes (~5.8 GB), md5 02f85309d966092ea130ca0797aea795. Uncompressed size not stated on the page (paper says ~15 GB total download, unclear whether that is the raw or dump size). | same | Zenodo / ar5iv paper | 2025-06-23 / 2022 | high (zip size), low (uncompressed) | F
3. Zip contains a MongoDB dump + download scripts + interpretation scripts + qualitative work. Exact dump layout (mongodump BSON dir vs archive, DB/collection names) NOT stated in any source I could read. | Zenodo record above | Zenodo | 2025-06-23 | high that it is "a MongoDB dump"; format detail unknown | F
4. Licence CC BY 4.0. | Zenodo API | Zenodo | 2025-06-23 | high | F
5. v7 anonymises user info (assignees, creators, reporters, comment authors, change authors) with UUID4 masks preserving uniqueness. Old v3 (record 5901804) is restricted/disabled; use v7. | Zenodo API; search summary of https://zenodo.org/doi/10.5281/zenodo.5882881 | Zenodo | 2025-06-23 | medium-high | F
6. No dataset-specific GitHub repo found; Zenodo page lists none. Scripts live inside the zip. | Zenodo record; web search | - | medium (absence) | F
7. Data model: MongoDB documents, schemaless per repo; each issue embeds `fields` (current attributes) and `changelog` (list of histories, each with items = changed attributes). Field examples: created, updated, resolutiondate, duedate, status, priority, resolution, issuetype, project, fixVersions, issuelinks, etc. Links stored on both issues; comments attached to issues. Whether changelog.histories is embedded in the same doc: paper says nested in issue document (medium); exact sub-field names (histories[].items[].field/fromString/toString) not confirmed this run (unverified belief, standard Jira API v2 shape). | https://ar5iv.labs.arxiv.org/html/2201.08368 | arXiv/MSR 2022 | 2022-01 | medium | F/I
8. Per-instance issue counts (Table 1, 2022 snapshot; v7 may differ): Apache 1,014,926 (657 projects); Mojang 420,819; RedHat 353,000; JIRA 274,545; Qt 148,579; MongoDB 137,172; Sonatype 87,284; Spring 69,156 (81 proj); Sakai 50,550; JiraEcosystem 41,866; MariaDB 31,229; Hyperledger 28,146 (36 proj); JFrog 15,535; IntelDAOS 9,474; Mindville 2,134; SecondLife 1,867. Total 2,686,282 issues, ~32M changes, 9M comments, 1M links. Per-instance byte sizes not found. | ar5iv paper | 2022 | high | F
9. Limitations: data unfiltered (many unresolved issues); heavy Jira customisation (workflows, types, fields vary per instance); MariaDB and Mindville no longer reachable (only May 2021 data). | ar5iv paper | 2022 | high | F
10. No Hugging Face copy found via HF hub search ("jira issues dataset" returned zero datasets). No Kaggle/Parquet/CSV derivative found. | HF connector, web search | - | medium (absence) | F
11. Related resolution-time work: Nastos et al., EASE '25, "Towards an Interpretable Analysis for Estimating the Resolution Time of Software Issues" (arXiv 2505.01108, 2025-05-02): abstract does not name the dataset; a search snippet (unverified) said it uses 1M+ issues across 656 Apache projects, which would match this dataset's Apache instance. | https://arxiv.org/abs/2505.01108 | arXiv | 2025-05-02 | low-medium | F/I
12. A search snippet reported a study on Hyperledger, JFrog and Mojang finding process-related characteristics contribute most to resolution-time prediction; source paper not opened (title seen: "The influence of software development characteristics on the accuracy of models for predicting issue resolution time", mshj.ru). | https://mshj.ru/en/nauka/article/126527/view | MSHJ | undated | low | F
13. Separate, different dataset: "Spring Jira Bug Dataset" on IEEE DataPort for priority/resolution-time prediction (not the Zenodo one). | https://ieee-dataport.org/documents/spring-jira-bug-dataset | IEEE DataPort | undated | low | F

## Bottom line
- Download the single 5.8 GB zip (Zenodo v7); no per-instance download exists. Unzip into an empty dir, inspect the layout first (`unzip -l`) to learn if it is a mongodump directory (*.bson + *.metadata.json) or `--archive`.
- If a mongodump directory: restore only needed collections with `mongorestore --nsInclude "<db>.<Instance>"` (check names after listing), or skip Mongo and read the .bson with `pymongo`'s `bson.decode_file_iter` / `bsondump`, filtering to a few projects and exporting to Parquet/JSONL once.
- Choose small instances for the demo: Hyperledger (28k issues), Spring (69k), or MongoDB (137k); Apache only if needed (1M issues). Avoid restoring all (~15 GB).
- Keep fields: fields.created, fields.resolutiondate, fields.priority, fields.status, fields.issuetype, fields.project, changelog (status/priority transitions); filter out unresolved issues carefully (right-censoring: unresolved issues matter for a "resolved within N days" forecast, do not drop them silently).
- Cite Montgomery, Lüders, Maalej, MSR 2022 + Zenodo DOI; CC BY 4.0 attribution; data anonymised, so no user-level features.

## Leads not chased
- Open the zip's README / Jupyter notebook (needs download, prohibited here) for exact DB/collection names.
- Full text of arXiv 2505.01108 (PDF unreadable via fetch; local copy saved by tool) to confirm dataset and features.
- Google Scholar for other uses (Hyperledger/JFrog/Mojang study).
- Zenodo version history v1-v6 (changelog of what changed).

## Looked for but not found
- GitHub repo (ThePublicJiraDataset or similar) with scripts.
- Collection names, dump format (BSON dir vs archive), uncompressed size, per-instance sizes.
- HF / Kaggle / CSV / Parquet mirrors.
- Detailed anonymisation or per-instance licence caveats (only CC BY 4.0 global; Jira instances' own terms not discussed in sources read).
