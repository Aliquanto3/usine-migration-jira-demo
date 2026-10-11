# Verification digest d1-d2, round 2, verifier 1

Accessed: 2026-10-10 for every source. Budget used: about 20 tool calls, 14 sources.

## C1. The REST API cannot set `created` (JRACLOUD-38572 open). **VERIFIED**
- JRACLOUD-38572, "Allow setting the creation/update date of an issue when creating them via the REST api". Status: Gathering Interest, Unresolved. Created 02/Jun/2014 and updated in the last day. The ticket gives CSV import as the workaround. https://jira.atlassian.com/browse/JRACLOUD-38572 (Atlassian public tracker).

## C2. CSV External System Import can set Date created / Date resolved. **VERIFIED, with one correction about the "new import experience"**
- KB "Retaining Creation Date During Work Item Import in Jira Cloud" (Cloud only, updated 2025-09-26): start the import through "External System Import", enter the date format on the project-selection page, and "map the Created field with the 'Date created' Jira field". Example: `dd/MM/yy hh:mm`. https://support.atlassian.com/jira/kb/how-to-retain-created-date-while-importing-issues/ (Atlassian Support)
- Resolved date: JRACLOUD-65502, "Import from CSV to Jira does not update Resolved Date field". The resolution date is not imported unless the Resolution field is imported too. The workaround CSV maps Resolution plus Resolved, with Resolved mapped to "Date Resolved". https://jira.atlassian.com/browse/JRACLOUD-65502. A related KB: https://support.atlassian.com/jira/kb/how-to-bulk-update-the-resolved-date-field-using-csv-import/ (seen in search snippets only).
- **New import experience:** yes, there is one. Its gaps are tracked as tickets: JRACLOUD-84562 (the new CSV method has no field value mapping), JRACLOUD-84516 (no overwrite/update of existing issues), JRACLOUD-84520 (no configuration file) and JRACLOUD-84385 (cannot import into an existing project). The KB "Jira Import Wizard message 'A project with that name already exists'" says to click **"Switch to the old experience"**. https://support.atlassian.com/jira/kb/jira-import-wizard-message-a-project-with-that-name-already-exists/ and https://jira.atlassian.com/browse/JRACLOUD-84562 (search snippets; these tickets date from about 2024). I did not confirm whether the new wizard specifically lacks Date created / Date resolved mapping. **The corrected point:** the plan should go through "Switch to the old experience" (System > External System Import > old experience > CSV). A community answer says the old experience will be deprecated once the new one can fully replace it, but gives no date.
- **Free plan / site-admin availability in 2026:** UNVERIFIED. No source in this run states plan gating.

## C3. CSV cannot import history; JSON history is not real status transitions. **VERIFIED, with nuance**
- JRACLOUD-64575 (Gathering Interest, Unresolved): "Currently the CSV import does not allow for importing issue history". It says history can be imported with the JSON import instead. https://jira.atlassian.com/browse/JRACLOUD-64575
- JRACLOUD-81943, "Import status changed history through JSON does not display as status changed in issue history". Status: Long Term Backlog, Unresolved, created 13/Aug/2020. The imported items are stored as a generic map and show as "updated" instead of a status change. "It's not possible to fetch for these imported issues when performing a JQL search based on the status." No known workaround. https://jira.atlassian.com/browse/JRACLOUD-81943
- Nuance: the ticket does not name `WAS` or `CHANGED` explicitly. Applying it to those operators is an inference, though a strong one.
- **Does a CSV Status column write a changelog entry?** UNVERIFIED. No Atlassian statement was found. The old Cloud admin doc says the importer only offers existing Status values. Recommend testing in a sandbox.

## C4. Rate limits and API tokens. **VERIFIED**
- Rate limiting page: https://developer.atlassian.com/cloud/jira/platform/rate-limiting/ (Atlassian Developer)
  - The points-based quota "will apply to all Forge, Connect, and OAuth 2.0 (3LO) apps". "API token-based traffic is not affected by this change." Enforcement starts **2026-03-02**.
  - Burst limits are per tenant, per endpoint, per second: GET 100, POST 100, PUT 50, DELETE 50. Custom limits apply to some endpoints, for example GET issue and GET user at 150.
  - Per-issue write limits: **20 writes per 2 s and 100 writes per 30 s**.
  - Points: Tier 1 Global Pool is 65,000 points/h. Tier 2 Per-Tenant gives Free 65,000/h, Standard 100,000 + 10/user, Premium 130,000 + 20/user and Enterprise 150,000 + 30/user, capped at 500,000/h.
  - Caveat: the page summary did not clearly say whether burst and per-issue limits apply to API-token traffic. They are described as per-tenant and per-endpoint, so they apply to all callers. I infer that rather than quote it.
- API token expiry: Atlassian Support "Manage API tokens for your Atlassian account". Expiry can be set from 1 day to 1 year, and the default is 1 year. Tokens created before 2024-12-15 were due to expire between 2026-03-14 and 2026-05-12. https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/ (via search summary, page not fetched directly).

## C5. Search, changelog and bulkfetch. **Split verdict**
Source: OpenAPI spec https://developer.atlassian.com/cloud/jira/platform/swagger-v3.v3.json, version `1001.0.0-SNAPSHOT-0c0db68a…`, downloaded and parsed on 2026-10-10.
- `/rest/api/3/search` GET and POST are still in the spec, with `deprecated: true` and "Endpoint is currently being removed. [More details](…changelog/#CHANGE-2046)". Third-party reports say it returns **410 Gone**: the Strategy KB489535, the Adobe Workfront known issue (a regional rollout), and community posts saying it was removed globally around 2025-09-16. Verdict: **VERIFIED** (removed and returning 410; the official CHANGE-2046 date was not retrieved).
- `/rest/api/3/search/jql` uses `nextPageToken`. The first page has null, and on the last page the token is **absent** from the response. `maxResults` defaults to 50, and the parameter description says "It returns max 5000 issues", with fewer per page when many fields are requested. **VERIFIED.**
- **"expand=changelog on search/jql returns at most 20 entries": UNVERIFIED and disputed.** The spec only says "Returns a list of recent updates to an issue, sorted by date, starting from the most recent", with no number. A non-staff community post (vit1, 2026-07-28) claims "Atlassian apparently decided to serve just top 10 changelog entries" (https://community.developer.atlassian.com/t/complete-change-log-is-not-returning-by-api-rest-api-3-search-jql-expand-changelog/101256). An older community thread and an OBSS blog cite 100 for the old `/search`. No source gives 20. Treat the cap as truncated and undocumented, and do not rely on it.
- Related figure from the spec: `BulkFetchIssueRequestBean` (POST /rest/api/3/issue/bulkfetch) with expand changelog "returns a maximum of 40 changelogs", and such requests "can include at most 100 issues".
- `POST /rest/api/3/changelog/bulkfetch`: "You can request the changelogs of up to **1000 issues** and can filter them by up to **10 field IDs**." `maxResults` defaults to 1000 (range 1–10000). Results are paginated and ordered oldest first, then by smallest issue ID. Scope: `read:jira-work`. `x-atlassian-connect-scope: INACCESSIBLE`, so Connect apps cannot use it. **The current spec carries no `x-experimental` flag.** The experimental label came from the developer forum (Atlassian's glewandowski, 2025-01-02: "We're still testing … which is why it's marked as Experimental"; on 2025-01-09 he said 404 errors came from a config error and it was "available on all instances now"). https://community.developer.atlassian.com/t/bulk-fetch-changelogs-experimental-api/87240. Verdict: limits **VERIFIED**; "experimental" **DISPUTED** (no longer flagged in the spec, and GA was not confirmed).

## C6. Jira Data Center. **VERIFIED**
- PATs: "Using Personal Access Tokens" lists Jira Core and Jira Software 8.14 and later. Tokens can be set to expire after a number of days or never expire. Default maximum is 10 tokens per user. Auth uses `Authorization: Bearer`. https://confluence.atlassian.com/display/ENTERPRISE/Using+Personal+Access+Tokens (Atlassian, via search summary)
- Search paging: KB "How to use the maxResults API parameter for Jira Issue Search REST API". The default is 50. `maxResults` is honored up to `jira.search.views.default.max`, which defaults to **1000**. The examples use `/rest/api/2/search` with startAt/maxResults/total. https://support.atlassian.com/jira/kb/how-to-use-the-maxresults-api-parameter-for-jira-issue-search-rest-api/ (Atlassian Support, via search summary)
- DC end of life: the Atlassian migration page (https://www.atlassian.com/migration, via search summary) gives three dates, which partner blogs (schneider.im, Seibert, Actonic) repeat:
  - 2026-03-30: end of new subscription sales to new customers.
  - 2028-03-30: end of sales and expansions to existing customers.
  - **2029-03-28**: end of life, when licenses go read-only.
  - A Medium post giving 2029-03-30 is the outlier.

## New findings
- There is an extra DC milestone: 2028-03-30 is the end of renewals and expansions for existing customers. Marketplace partners also mention 2025-12-16, when no new DC apps were accepted.
- The `changelog/bulkfetch` endpoint is closed to Connect apps (connect scope INACCESSIBLE), but API-token and OAuth access is fine.
- The `search/jql` maxResults description now says "max 5000 issues", for id/key-only requests.
- POST `/rest/api/3/issue/bulkfetch` with expand changelog is capped at 40 changelogs per issue and 100 issues per request.
- The new import wizard does not support importing into an existing project or updating existing issues (JRACLOUD-84385, 84516). The old experience is still needed.

## Looked for but not found
- An Atlassian statement on whether the CSV importer is available on the Free plan in 2026.
- Whether the new import wizard can map Date created and Date resolved.
- Any documented changelog cap of "20" for `search/jql` expand=changelog.
- The official CHANGE-2046 changelog text and removal date (the changelog page was not fetched).
- Whether a CSV Status column produces a changelog entry.
- An explicit official sentence that burst and per-issue limits apply to API-token scripts.
