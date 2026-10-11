---
type: review
lens: adversaire (paires d'unités conformes mais incompatibles) + checklist du bon spine
cible: ARCHITECTURE-SPINE.md (status draft, 2026-10-10)
date: 2026-10-10
---

# Revue adverse du spine d'architecture

## Verdict

**Non prêt pour l'ouverture des 8 lanes.** Le spine est solide sur l'essentiel (contrats d'abord, domaine pur, Passage immuable, passerelle LLM unique), mais un adversaire peut construire au moins **14 paires d'unités** qui respectent chaque AD à la lettre et qui pourtant ne s'assemblent pas. Les trous les plus graves ne sont pas des oublis de détail. Ce sont des **contradictions internes** : le graphe d'imports interdit des appels que d'autres AD rendent obligatoires, ce qui pousse chaque lane à contourner à sa façon. Trois correctifs (graphe d'imports, clé de cache, boucle de l'Agent) sont à trancher **avant E0-9** ; les autres peuvent l'être pendant E0.

Échelle : **Critique** (bloque l'assemblage ou viole un NFR indispensable), **Majeur** (divergence probable entre lanes, correctible au prix d'un rebase coûteux), **Mineur** (friction ou ambiguïté locale).

---

## 1. Paires incompatibles conformes aux AD

### T-1 [Critique] Le graphe d'imports interdit des appels que les AD exigent

Le diagramme dit : `chaine → domaine, ports, consultation` ; `ia → ports, consultation, domaine` ; `ui → consultation, composition` ; `adaptateurs → ports`. « Toute importation absente du diagramme est interdite. » Or :

| Appel exigé | Par | Interdit par le diagramme |
| --- | --- | --- |
| La Chaîne exécute les étapes `classification`, `explications`, `narration` (code dans `ia/`) et `rendu` (code dans `rendu/`) | AD-8 | `chaine ↛ ia`, `chaine ↛ rendu` |
| `controler_nombres` utilise les formes formatées par `rendu.format` | AD-14 | `ia ↛ rendu` |
| L'UI formate via `rendu.format` | AD-11 | `ui ↛ rendu` |
| `SourceComposite` coupe « jusqu'à la Date d'injection incluse », donc rattache un horodatage à un jour, ce qui ne se fait que dans `domaine.calendrier` | AD-4, AD-17 | `adaptateurs ↛ domaine` |
| Le tableau des couches autorise `consultation → domaine`, le diagramme non | tableau vs diagramme | incohérence interne |

**Paire adverse.** L5 (Chaîne) découvre qu'elle ne peut pas importer `ia` : elle définit un `Callable[[Path], None]` par étape et attend que `composition.py` le lui passe. L6, dans le même temps, expose `ia.taches.executer_classification(consultation, passerelle, date_arrete) -> SortieClassification` et suppose que la Chaîne écrit le JSON. Les deux respectent AD-1 et AD-8 ; aucune n'écrit le fichier `llm/classification.json`, ou les deux l'écrivent. Côté L2, `SourceComposite` recode un `astimezone(ZoneInfo("Europe/Paris")).date()` local parce qu'elle n'a pas le droit d'importer le calendrier, ce qui recrée exactement la divergence qu'AD-17 veut empêcher. L6 recopie un formateur de nombres pour `controler_nombres` : « 1 234 » (espace insécable fine) d'un côté, « 1 234 » (espace normale) de l'autre, et le contrôle retire des phrases correctes.

**Correctif.**
- Nouvel AD « Étapes injectées » : *Chaque étape implémente le port `ports.Etape` (`executer(ctx: ContextePassage) -> ResultatEtape`), `composition.py` construit le registre `dict[contrats.Etape, ports.Etape]`, et `chaine` n'importe jamais le code d'une étape.*
- AD-11/AD-14 resserré : *Le formatage français vit dans `usine.contrats.format` (pur, sans dépendance), importable par toutes les couches ; `rendu.format` disparaît.*
- AD-17 resserré : *Le rattachement horodatage → jour local est `contrats.temps.jour_local(ts)` ; `domaine.calendrier` garde Jour ouvré, Fenêtre glissante, J-1, J-5.* (Ou ajouter l'arête explicite `adaptateurs → domaine.calendrier`.)
- Aligner tableau et diagramme : une seule source (le `[tool.importlinter]` de E0-1), le diagramme du spine en est une copie.

### T-2 [Critique] La clé de cache change à chaque Passage

AD-16 : `version_donnees = SHA-256 du Journal + horodatage_extraction`. AD-12 : la clé de cache contient `version_donnees`, y compris pour la classification. Comme `horodatage_extraction` change à chaque Passage, **aucune entrée de cache n'est jamais réutilisée** : FR-14 (Rejeu qui réutilise les sorties LLM), FR-35 (classification incrémentale) et NFR-9/H-15 (coût) tombent. Deux lanes conformes divergent aussi : L6 lit `version_donnees` dans le manifeste du Passage, L5 la calcule avant l'extraction ; les empreintes diffèrent.

Aggravant, l'`Evenement` `nature=alignement` (AD-4) est « horodaté de l'extraction » et son `id_evenement` n'est pas défini par AD-3 (seuls `J-<rang>` et `<id changelog>-<rang>` le sont). Un Rejeu ré-émet un alignement avec un autre horodatage et, selon l'implémentation, un autre identifiant : le dédoublonnage échoue et l'égalité de Rejeu (AD-7) aussi.

**Correctif.**
- AD-16 resserré : *`version_donnees` = SHA-256 du flux canonique d'`Evenement` (trié par `id_evenement`) restreint à la cible (ticket pour la classification, Entité pour les autres tâches) et aux jours locaux ≤ Date d'arrêté ; aucun horodatage d'exécution n'y entre.*
- AD-3 complété : *`id_evenement` d'un alignement = `A-<cle>-<champ>-<sha8(vers)>` ; d'une création Jira sans changelog = `C-<id ticket Jira>` ; un alignement est horodaté à `horodatage_fin_injection` s'il porte sur l'état post-injection, sinon au `updated` Jira du ticket.*

### T-3 [Critique] La boucle d'outils de l'Agent contourne la passerelle

AD-12 exige la Pseudonymisation de « toute l'entrée, y compris les résultats d'outils ». AD-13 donne au port `executer_agent(messages, outils, parametres)`. Avec Pydantic AI, la boucle tool-call → résultat → nouvel appel tourne **dans l'adaptateur** : les résultats d'outils repartent vers le fournisseur sans repasser par la passerelle, donc sans Pseudonymisation, sans trace par tour et sans cache. L7 qui écrit des outils sur `Consultation` et L6 qui écrit l'adaptateur respectent tous deux la lettre ; l'ensemble fuit des données identifiantes (NFR-5, SM-7).

Corollaire : l'ordre `fournisseur → contrôle → ré-identification` fait tourner `controler_nombres` sur un texte pseudonymisé. `COMPTE_12` contient « 12 » ; selon que L6 ou L7 implémente le filtre, le nombre est vu comme inventé ou non.

**Correctif.**
- AD-13 resserré : *`executer_agent` exécute un seul tour et renvoie les appels d'outils demandés ; la boucle d'outils vit dans `ia.passerelle`, qui pseudonymise chaque résultat d'outil avant le tour suivant.* (Variante : la passerelle enveloppe chaque outil avant de le passer au port, et un test de contrat le vérifie.)
- AD-14 complété : *`controler_nombres` ignore les jetons de Pseudonymisation (motif `[A-Z]+_\d+`) et les clés de ticket.*

### T-4 [Critique] Vocabulaire canonique de `champ`, `de`, `vers` non figé

AD-3 fige les colonnes d'`Evenement`, pas leurs **valeurs**. L1 écrit `champ="entite"`, `vers="ENT-A"`, `vers="En cours"`, `champ="gravite"`, `vers="bloquante"`. L2 normalise le changelog Jira en `champ="customfield_10031"` ou `"Entité"`, `vers="In Progress"`, `champ="priority"`, `vers="Highest"`. Les deux valident `SCHEMA_EVENEMENT` (ce sont des chaînes). L3 calcule des Instantanés justes sur le Journal et faux sur Jira, et le test de cohérence de FR-49 casse à l'intégration. Le spike « workflow créé à la main » placé sous *Différé* rend la chose pire : les noms de statuts Jira ne sont connus qu'après L1.

**Correctif.** *`contrats.evenements` définit l'énumération `Champ` et, pour chaque champ, le domaine de valeurs canonique (statuts H-17, `Gravite`, codes d'Entité, Phases, Domaines) ; la correspondance Jira → canonique est une table de `config/jira.yaml`, appliquée uniquement dans les adaptateurs, et la suite de contrat `SourceTickets` vérifie que toute valeur émise appartient au domaine.*

### T-5 [Critique] Plusieurs écrivains dans le Passage en cours ; l'Agent écrit dans un Passage immuable

- AD-16 met la trace LLM dans `<Passage>/trace/llm.jsonl`, écrite par la passerelle (L6), et la trace de Prévision dans `trace/previsions.jsonl`, avec pour producteur « passerelle, prévision ». Le domaine est pur (AD-1), donc ce n'est ni `domaine.prevision` ni la passerelle : L4 et L5 peuvent chacun l'écrire, ou aucun.
- La passerelle doit connaître le chemin du Passage en cours, alors que la Chaîne (L5) en possède le cycle de vie : deux écrivains, deux politiques de fsync et d'erreur.
- **L'Agent** tourne dans l'UI, après publication. Sa trace ne peut aller ni dans un Passage publié (AD-7 : jamais modifié) ni dans un Passage en cours (il n'y en a pas). L6 écrira dans le dernier Passage publié, L7 nulle part : l'un viole AD-7, l'autre viole FR-34.

**Correctif.** *Seule `chaine` écrit dans `.en-cours-<id>/`, via un `EcrivainPassage` qu'elle passe aux étapes ; les étapes renvoient leurs sorties et leurs `EntreeTrace`. Les traces de l'Agent vont dans `sorties/agent/<AAAAMMJJ>/<session>.jsonl`, hors de tout Passage.*

### T-6 [Majeur] Renommage atomique et suivi de progression sous Windows

Le poste est sous Windows. L'UI « suit `progression.jsonl` du Passage en cours » (AD-8). Si L7 garde le fichier ouvert en lecture (`tail -f` naturel), le `os.replace` du répertoire `.en-cours-<id>` par L5 échoue (`PermissionError`, partage de fichier), donc le Passage échoue **uniquement quand l'UI le regarde**, c'est-à-dire pendant la démo. Le même problème touche un Excel ouvert par Claire. La CI (GitHub Actions, sans OS précisé) ne le voit pas.

**Correctif.** *La progression s'écrit dans `sorties/progression/<passage_id>.jsonl`, hors du répertoire renommé ; tout lecteur ouvre, lit et ferme à chaque sondage ; la CI tourne aussi sur `windows-latest` pour les tests de `chaine`.*

### T-7 [Majeur] Événements hors Jours ouvrés et Date d'arrêté non ouvrée

AD-17 fixe le jour local d'un horodatage, pas son **Jour ouvré**. Un ticket créé un samedi est une Entrée : L3 la compte dans les KPI du lundi (report en avant), L4 construit `SerieStock` en l'attribuant au vendredi (report en arrière) ou en la perdant (seuls les Jours ouvrés sont des lignes). L'âge « en Jours ouvrés depuis la dernière Entrée » (FR-11) diverge aussi. Par ailleurs `usine rapport --date-arrete 2026-10-11` (un dimanche) : L5 le refuse, L3 calcule quand même, L7 propose la date dans un sélecteur.

**Correctif.** *`domaine.calendrier.jour_ouvre_de(ts)` rattache tout événement au premier Jour ouvré ≥ son jour local, et c'est la seule fonction utilisée par KPI, `SerieStock` et âges ; une Date d'arrêté non ouvrée est rejetée par la CLI avec une `UsineErreur` nommant la date.*

### T-8 [Majeur] Coupure d'injection : deux repères de nature différente

`SourceComposite` prend le Journal « jusqu'à la Date d'injection incluse » (une **date**, sans fuseau précisé) puis Jira « strictement après `horodatage_fin_injection` » (un **instant**). L'intervalle entre la fin de la Date d'injection et `horodatage_fin_injection` n'appartient à aucune source : une modification faite en direct dans Jira pendant une injection longue (ou le week-end entre une Date d'injection au vendredi et une injection le lundi) disparaît. À l'inverse, L1 peut interpréter « Date d'injection incluse » en UTC et L2 en heure de Paris : les événements de 23 h 30 UTC basculent.

De plus, le test de cohérence de FR-49 compare à `Instantané(état Jira juste après injection)`, alors qu'AD-3 impose que les Instantanés ne se calculent **que** depuis un flux d'`Evenement`. L2 écrira une fonction « état courant → Instantané » dans les adaptateurs (calcul métier hors domaine, contre AD-9), ou L3 l'écrira dans le domaine sur une entrée qui n'est pas un contrat.

**Correctif.** *La coupure est un instant unique : Journal si `horodatage < debut_injection`, Jira si `horodatage > horodatage_fin_injection`, et l'injecteur refuse toute écriture concurrente (projet verrouillé) ; l'état Jira post-injection est converti en `Evenement` `nature=alignement` par l'adaptateur, puis l'Instantané est calculé par le domaine comme pour toute source.*

### T-9 [Majeur] `Consultation` : un port figé, trois lanes qui doivent l'étendre

`Consultation` est un port de `ports/` (main) et un paquet de L5. L6 a besoin de nouvelles lectures (texte des tickets en cause pour les prompts, répartition des Causes racines) ; L7 a besoin des filtres de `list_anomalies` et des dates disponibles (FR-39) ; L5 en a besoin pour les 9 onglets. Chaque lane ajoute une méthode : trois PR concurrentes sur `ports/`, et chacune ajoute sa propre forme de retour (`dict`, `DataFrame`, modèle ad hoc), ce qu'AD-2 interdit mais que rien n'empêche avant la revue. Les signatures des outils de l'Agent sont dites « gelées » mais vivent dans `ia.agent.outils` (L7), pas dans `contrats` : AD-2 et le tableau des contrats se contredisent.

**Correctif.** *Le port `Consultation` est gelé à E0-9 avec toutes les lectures exigées par FR-17, FR-19, FR-26, FR-27, FR-39, FR-43 à FR-46 et les prompts de L6, chacune typée par un contrat ; les signatures des outils de l'Agent et leurs modèles de résultat vivent dans `contrats.agent`.*

### T-10 [Majeur] Palier 1 / Palier 2 : qui décide qu'une étape est « sautée » ?

AD-8 : les étapes LLM sont « sautées en Palier 1 ». FR-25 : « si un LLM est configuré ». AD-12 : fournisseur injoignable → échec. L5 lit un `palier: 1` dans `config/chaine.yaml` ; L6 considère qu'un `config/llm.yaml` présent active le Palier 2. Avec `palier: 1` et `llm.yaml` présent, L5 saute, L6 attend des sorties. Avec `llm.yaml` présent mais clé API absente, l'un saute, l'autre échoue.

**Correctif.** *Le Palier est un champ unique `ConfigChaine.palier` ∈ {1, 2}, lu seulement par la composition, qui enregistre l'étape `sautee` ou réelle ; `llm.yaml` ne décide de rien d'autre que le fournisseur et le modèle.*

### T-11 [Majeur] « Dernier Passage réussi » après un Rejeu

AD-7 : le dernier Passage réussi est le plus récent par `horodatage_fin`. Un Rejeu du 2026-09-15 lancé aujourd'hui devient donc le « dernier » : le Mode repli (L7) affiche septembre, FR-44 affiche la durée du Rejeu, et L5 (rapport par défaut) pourrait s'en servir comme repère. L7 interprétera « dernier » par Date d'arrêté, L5 par horodatage : deux écrans, deux Passages.

**Correctif.** *Le dernier Passage réussi est le maximum de `(date_arrete, horodatage_fin)` ; la fonction `consultation.dernier_passage()` est la seule à le déterminer.*

### T-12 [Majeur] Pseudonymes dépendants de l'ordre de rencontre

AD-15 : jetons « stables » par une table persistante. L'attribution `CLIENT_7` dépend de l'ordre de première rencontre. Chaque worktree a son propre `donnees/` (ignoré par git), donc sa propre table : L6 et L7 enregistrent des réponses de répétition (`demo/repli/`, versionné) et des fixtures d'évaluation avec des jetons différents. Une table supprimée ou une classification lancée dans un autre ordre change toutes les empreintes d'entrée, donc invalide le cache. Rien ne dit non plus ce qui se passe si deux processus (CLI et Agent dans l'UI) écrivent la table en même temps (DuckDB : un seul écrivain).

**Correctif.** *Le jeton est dérivé, pas attribué : `<TYPE>_<n>` avec `n` = rang de `HMAC(cle_locale, valeur)` dans un espace fixe, la table ne servant qu'à la ré-identification ; tout accès en écriture à une base DuckDB passe par un verrou de fichier `donnees/.verrou-<base>`.*

### T-13 [Majeur] Concurrence sur les bases locales et sur le site Jira partagé

- L'UI lance `usine rapport` en sous-processus ; rien n'empêche un deuxième lancement (double clic, CLI en parallèle). Deux extractions ouvrent `entrepot.duckdb` en écriture : l'une échoue, ou pire, AD-6 « écrivain unique » est vrai par module mais faux par processus.
- Le site Jira Cloud Free est **unique** pour 8 worktrees. L1 réinjecte (site vierge, FR-5) pendant que L2 enregistre ses fixtures ou que L5 fait une recette : chacun respecte AD-5, et l'état partagé change sous les pieds des autres.

**Correctif.** *`usine rapport` prend un verrou exclusif `donnees/.verrou-passage` et échoue proprement s'il est pris ; l'injection sur le site partagé ne se lance que depuis `main`, et chaque worktree qui a besoin d'écrire utilise sa propre clé de projet Jira (`DEMO_L1`, …), fixée dans `.env`.*

### T-14 [Mineur] Forme des fichiers d'un Passage hors contrat

AD-7 exige l'historique complet (Météo de chaque Jour ouvré) dans le Passage, mais le tableau des fichiers ne liste qu'un `meteo.json`, `previsions.json`, `llm/*.json`. L3 peut écrire `{date: MeteoEntite[]}`, L5 attendre une liste plate avec `date_arrete` dans chaque élément. AD-2 dit que toute forme qui franchit une frontière **de fichier** est un contrat, mais aucune enveloppe de fichier n'est listée dans *Contrats v1*.

**Correctif.** *Chaque fichier JSON d'un Passage a son modèle d'enveloppe dans `contrats.passage` (`FichierMeteo`, `FichierPrevisions`, `FichierSortiesLLM`), avec `contrats_version` ; `Consultation` refuse un Passage dont la version majeure diffère.*

---

## 2. Propriété des fichiers : trous et chevauchements de la Carte des lanes

| Chemin | Problème | Proposition |
| --- | --- | --- |
| `cli.py` | Absent d'AD-21 (seul `composition.py` est cité) et d'aucune lane. L1 a besoin de `usine generer` / `usine injecter`, L4 de l'évaluation, L7 de la répétition, L5 de `usine rapport` | `cli.py` à `main` ; chaque lane possède un sous-module `<paquet>/cli.py` exposant une sous-app typer, enregistrée une fois à E0 |
| `composition.py` | À `main`, mais chaque étape nouvelle (L4, L5, L6) doit y être câblée : PR à `main` à chaque story | Registre d'étapes créé à E0 avec un emplacement par étape (T-1) ; une lane ne modifie la composition que pour remplacer son bouchon, une seule fois |
| `src/usine/config/` (chargeur) | Aucune lane | `main` (comme `contrats/`) |
| `config/chaine.yaml` | Aucune lane ; L2 y met la marge d'extraction (AD-6), L5 le Palier, L4 l'horizon (H-7) | Fichier à `main` ; chaque clé nouvelle passe par la PR qui touche `contrats.config` |
| `jira.url_base` | Cité par AD-11, mais aucun fichier `config/jira.yaml` dans AD-19 | Ajouter `config/jira.yaml` (URL, projet, correspondances T-4), propriété de L2 |
| `domaine/calendrier` | Propriété de L3, mais L1 (ancrage du générateur) et L4 (Jours ouvrés de la Prévision) en dépendent | Figé à E0 avec E0-4 ; propriété de `main` après le gel |
| `tests/unit/<paquet>/` | Seule L1 liste ses tests ; L3 et L4 écrivent tous deux sous `tests/unit/domaine/` (un `conftest.py` commun) ; `tests/conftest.py` racine sans propriétaire | Règle : *une lane possède `tests/unit/<chemin de ses répertoires source>` ; `tests/conftest.py` et `tests/unit/conftest.py` sont à `main`* |
| `tests/contrat/fournisseur_llm`, `tests/contrat/consultation`, `tests/contrat/pseudonymiseur` | Non attribués (seul `source_tickets` l'est) | `tests/contrat/<port>/` appartient à `main` (le port y vit), les adaptateurs l'exécutent |
| `evals/` | L6 « hors Agent », L7 `evals/agent` : le lanceur et les utilitaires communs sont à qui ? | `evals/commun/` à L6, `evals/agent/` à L7, interdiction pour L7 de modifier `evals/commun/` |
| `FournisseurFactice` | Créé en E0-7, dans `adaptateurs/llm` (L6), mais utilisé par les tests de L5 et L7 | Le placer dans `tests/fakes/` (à `main`) ou le geler avec les contrats |
| Clients HTTP Jira | L1 (injecteur, écriture) et L2 (lecture) écrivent chacun pagination, authentification Cloud/DC, reprise sur 429 | Une couche HTTP commune `adaptateurs/jira_http` (L2) que l'injecteur réutilise en mode écriture, la liste blanche restant côté lecture |
| `demo/repli/` | Les réponses de l'Agent sont versionnées, mais « le dernier Passage enregistré » est sous `sorties/`, ignoré par git : un clone frais n'a pas de Mode repli | Un Passage de repli versionné dans `demo/repli/passage/`, produit par la répétition |

---

## 3. Checklist du bon spine

### Chaque Rule est-elle vérifiable, et empêche-t-elle sa divergence ?

| AD | Vérifiable ? | Empêche sa divergence ? |
| --- | --- | --- |
| AD-1 | Oui (import-linter) | Partiellement : `ui → composition → adaptateurs` est un import indirect ; selon `allow_indirect_imports`, import-linter le signale ou non. À préciser |
| AD-2 | Oui (CODEOWNERS / règle de branche à décrire) | Non pour les valeurs (T-4) et les enveloppes de fichiers (T-14) |
| AD-3 | Oui (schéma) | Non : `id_evenement` d'alignement et de création Jira absent (T-2) ; vocabulaire libre (T-4) |
| AD-4 | Test de cohérence | Non : coupure mixte date/instant (T-8) ; rattachement au jour hors calendrier (T-1) |
| AD-5 | Oui (liste blanche testée) | Oui |
| AD-6 | Partiellement | Non par processus (T-13) |
| AD-7 | Oui | Non : « dernier » ambigu (T-11) ; écrivains multiples (T-5) ; Windows (T-6) |
| AD-8 | Oui | Non : câblage des étapes impossible tel quel (T-1) ; Palier (T-10) |
| AD-9 | Revue seulement | Oui sur le principe ; ajouter un test « aucun `SUM`/`AVG`/`COUNT` dans le SQL » |
| AD-10 | Oui | Oui. Préciser la sérialisation de `infini` en Parquet (colonnes `num`, `den`, `den=0`) |
| AD-11 | Partiellement | Non : `rendu.format` inaccessible (T-1) ; port à étendre (T-9) |
| AD-12 | Partiellement | Non : boucle de l'Agent (T-3) ; clé de cache (T-2). Préciser si un succès de cache repasse le contrôle |
| AD-13 | Oui | Non (T-3) |
| AD-14 | Oui | Partiellement (jetons, T-3) |
| AD-15 | Oui (balayage SM-7) | Non (T-12) |
| AD-16 | Oui | Non (T-2) |
| AD-17 | Oui | Non (Jour ouvré d'un événement hors ouvré, T-7) |
| AD-18 | Oui | Oui |
| AD-19 | Oui | Partiellement : fichier manquant (`jira.yaml`), `chaine.yaml` sans propriétaire |
| AD-20 | Oui | Oui ; ajouter les suites de `Consultation` et `Pseudonymiseur` |
| AD-21 | Non (aucun outil) | Non : trous listés en § 2. Ajouter un contrôle CI « fichiers modifiés ⊆ répertoires de la lane » sur les branches `lane/*` |

### Rien sous *Différé* ne doit pouvoir faire diverger deux unités

- **Workflow Jira créé par API ou à la main** : peut faire diverger L1 et L2 sur les noms de statuts. Acceptable **seulement** si T-4 est adopté (la correspondance est en configuration, côté L2).
- **Champs des contrats au-delà des invariants** : acceptable, car gelés en E0-9 ; mais E0-9 doit couvrir T-9 et T-14, sinon le gel est incomplet.
- **Modèles LLM par tâche** : sans risque, sauf que `version_modele` entre dans la clé de cache (normal).
- **Mise en page UI / PPT / Excel** : sans risque si le formatage est commun (T-1).
- **Polars 2.x** : sans risque tant que `uv.lock` est sur `main` (AD-21).
- **Hystérésis, seuils par Phase** : sans risque, la Grille est versionnée.
- Rien de différé sur la **rétention des Passages** : chaque Passage contient tout l'historique, donc `sorties/` croît vite. Pas de divergence entre lanes, mais à ranger sous *Différé* explicitement.

### Toutes les dimensions sont-elles décidées, différées ou ouvertes ?

| Dimension | État | Commentaire |
| --- | --- | --- |
| Déploiement | Décidé (poste local, pas de conteneur) | OK |
| Environnements | Décidé (poste + CI) | **Manque** : l'environnement par worktree (`donnees/`, `.env`, clé de projet Jira) et le site Jira partagé (T-13) |
| CI | Décidé (outils listés) | **Manque** : OS de la CI (Windows, T-6) ; installation de `fr_core_news_md` (pas sur PyPI : URL dans `pyproject` ou `spacy download`) ; déclencheurs sur les branches de lane ; contrôle de propriété AD-21 |
| Concurrence / verrous | Non traité | T-12, T-13 |
| Données de démo hors réseau | Partiellement | Passage de repli non versionné (§ 2) |
| Observabilité | Décidé (logging, traces JSONL ; Langfuse en bonus) | OK |
| Sécurité / secrets | Décidé (env, gitleaks) | Ajouter : jeton d'injection jamais chargé par la Chaîne (`composition` ne lit pas `JIRA_TOKEN_INJECTION`) |
| Évolution des contrats | Décidé (PR sur main, `CONTRATS_VERSION`) | Manque la lecture des anciens Passages (T-14) |
| Ops / rétention | Absent | À ranger en *Différé* |
| Performance | NFR-2 cité | Aucun AD ne dit comment rester sous 5 min alors que chaque Passage recalcule tout l'historique (AD-7) ; à mesurer en E0-5 sur la volumétrie cible |

---

## 4. Règles proposées (une ligne chacune)

1. **AD-22 Étapes injectées** : chaque étape implémente `ports.Etape` ; `composition.py` construit le registre ; `chaine` n'importe aucun code d'étape.
2. **AD-11/14** : le formatage français est `contrats.format`, pur, importable par toutes les couches.
3. **AD-17** : `contrats.temps.jour_local` rattache au jour ; `domaine.calendrier.jour_ouvre_de` rattache au premier Jour ouvré ≥ ; une Date d'arrêté non ouvrée est rejetée.
4. **AD-16** : `version_donnees` = empreinte du flux canonique restreint à la cible et ≤ Date d'arrêté, sans horodatage d'exécution.
5. **AD-3** : identifiants déterministes pour l'alignement (`A-<cle>-<champ>-<sha8>`) et la création Jira (`C-<id>`).
6. **AD-3 bis** : `Champ` et domaines de valeurs canoniques dans `contrats` ; correspondance Jira dans `config/jira.yaml`, appliquée par les adaptateurs seulement.
7. **AD-4** : coupure par instants (`debut_injection`, `horodatage_fin_injection`) ; état post-injection converti en `Evenement` avant tout calcul.
8. **AD-13** : `executer_agent` exécute un seul tour ; la boucle d'outils vit dans la passerelle.
9. **AD-14** : `controler_nombres` ignore les jetons de Pseudonymisation et les clés.
10. **AD-7 bis** : seule `chaine` écrit dans le Passage en cours ; les traces de l'Agent vont sous `sorties/agent/`.
11. **AD-8** : progression hors du répertoire renommé ; lecture ouvrir-lire-fermer ; CI sur Windows.
12. **AD-7** : dernier Passage = max `(date_arrete, horodatage_fin)`, calculé par `consultation.dernier_passage()` seulement.
13. **AD-10 bis** : Palier = `ConfigChaine.palier`, lu par la composition seulement.
14. **AD-15** : jeton dérivé par HMAC ; la table ne sert qu'à la ré-identification.
15. **AD-6 bis** : verrou de fichier exclusif pour `usine rapport` et pour toute écriture DuckDB.
16. **AD-21** : `cli.py`, `usine/config/`, `config/chaine.yaml`, `tests/conftest.py`, `tests/contrat/<port>/` à `main` ; une lane possède `tests/unit/<ses répertoires>` ; contrôle CI des chemins modifiés par lane.
17. **AD-2 bis** : `Consultation` complet et signatures des outils de l'Agent gelés dans `contrats` à E0-9 ; enveloppes de fichiers du Passage avec `contrats_version`.
18. **Environnements** : une clé de projet Jira par worktree qui écrit ; injection sur le projet partagé depuis `main` uniquement.
