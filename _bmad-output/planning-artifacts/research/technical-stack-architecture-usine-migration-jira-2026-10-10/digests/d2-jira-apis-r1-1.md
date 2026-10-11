# d2 - Jira APIs (Cloud v3 / DC v2) - round 1, digest 1

Accessed 2026-10-10 for all items. Tool calls used: 12. Note: the developer.atlassian.com REST reference pages came back truncated via WebFetch, so no claim below is taken from the official endpoint reference itself.

## Findings

1. Claim: /rest/api/3/search/jql (enhanced search) replaces GET/POST /rest/api/3/search. Deprecation was announced 2024-10-31 with a removal date of 2025-05-01. The rollout was regional, and the old endpoint returns HTTP 410 Gone (observed in a report dated 2026-02-20).
   Source: https://github.com/atlassian/atlassian-mcp-server/issues/70 ; https://github.com/pycontribs/jira/issues/2379 ; https://experienceleague.adobe.com/en/docs/workfront-known-issues/issues/fusion/fusion-current/fusion-error-in-jira-search
   Publisher: GitHub issues / Adobe. Pub_date: 2026-02 / undated. Confidence: medium (secondary quotes of the CHANGE notice; I did not retrieve the CHANGE-xxxx page). Class: secondary.

2. Claim: Pagination on the new search uses nextPageToken instead of startAt. There is no random access and no parallel paging. Each token expires after 7 days. The returned count may be lower than maxResults. Staff said the typical page range is about 100-5000 with no exact limit stated. There is no total count; use POST /rest/api/3/search/approximate-count with a {jql} body, which returns {"count": n} (an estimate).
   Source: https://community.developer.atlassian.com/t/rfc-61-evolving-search-capabilities-addressing-scalability-with-a-new-enhanced-search-api/83027
   Publisher: Atlassian Developer Community (RFC-61, staff-authored). Pub_date: 2024-09 (older than 12 months; the design has since shipped). Confidence: medium-high. Class: primary (staff).

3. Claim: With expand=changelog on the new search APIs, at most 20 changelog entries per issue are returned inline. For more, call GET /rest/api/3/issue/{key}/changelog. The expands operations, transitions, editmeta and versionedRepresentations are not available on the new APIs.
   Source: same RFC-61 thread. Pub_date: 2024-09. Confidence: medium-high (the 20 limit is stated in the RFC; re-verify against the live reference). Class: primary (staff).

4. Claim: POST /rest/api/3/changelog/bulkfetch is marked Experimental. It was initially 404 on some instances (a config error on Atlassian's side, fixed 2025-01-09), and requires the read:jira-work scope. Third-party docs say up to 1000 issues per request and up to 10 fieldIds, with results paginated and sorted by changelog date then issue ID. The thread itself states no limits and no pagination. Known quirks: duplicates across pages with small page sizes (JRACLOUD-94906); entries with no fieldId (e.g. a key change) are missed by fieldIds filters (JRACLOUD-94912).
   Source: https://community.developer.atlassian.com/t/bulk-fetch-changelogs-experimental-api/87240 ; https://jira.atlassian.com/browse/JRACLOUD-94906 ; https://jira.atlassian.com/browse/JRACLOUD-94912 ; limits from https://www.withone.ai/knowledge/jira/conn_mod_def%3A%3AGJ4qeRk_S-k%3A%3Aec_Rl-izQAOY6XMR1oLMDQ
   Publisher: Atlassian Developer Community (staff); Atlassian Jira tracker; withone.ai (third party). Pub_date: 2025-01 for the thread. Confidence: low-medium for the numeric limits (third-party), medium for the Experimental status. Class: primary for status, secondary for limits.

5. Claim: Bulk fetch of issues via the new search is capped (staff: "can't offer larger batch sizes" at that time). One developer reported 100 per page.
   Source: RFC-61 thread (item 2). Confidence: low-medium. Class: primary (staff) / anecdotal.

6. Claim: Per-issue changelog is paginated GET /rest/api/3/issue/{key}/changelog (named as the route to full history). I did not retrieve its startAt/maxResults details this run.
   Source: RFC-61 thread. Confidence: low on pagination specifics. Class: primary (partial).

7. Claim: On Cloud, custom-field options must live inside a field context. The sequence is create the field, create the context (/field/{id}/context), then create options (POST /field/{id}/context/{contextId}/option). Third-party docs say up to 1000 options per request and 10000 per field. The Administer Jira global permission is required (third-party sources). Adding a field to a screen was NOT verified. Creating issue types, statuses and workflows by API was NOT researched.
   Source: https://community.developer.atlassian.com/t/receiving-400-bad-request-for-get-to-rest-api-3-customfield-fieldid-option/44472 ; https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issue-custom-field-options/ ; withone.ai connector docs.
   Publisher: Atlassian Developer Community / Atlassian / third party. Pub_date: undated. Confidence: medium for order and permission, low for the numeric limits. Class: mixed.

8. Claim: Atlassian changelog entries from October 2026 show the search/jql API is still evolving: 2026-10-08, direct JQL validation returns to /search/jql for queries using custom JQL functions, returning an immediate HTTP 400. 2026-10-07, user entity-property searches on voter/watcher/creator are deprecated, effective 2026-11-16.
   Source: https://developer.atlassian.com/changelog/ . Publisher: Atlassian. Pub_date: 2026-10. Confidence: high. Class: primary.

9. Claim: Data Center PATs are supported since Jira 8.14 (JSM 4.15, Confluence 7.9). The header is Authorization: Bearer <token>. Tokens can be created via the UI or POST /rest/pat/latest/tokens (Basic or an existing token is needed to call it). Attachment download via PAT was a reported limitation on Server (JRASERVER-72019; current status unknown).
   Source: https://confluence.atlassian.com/display/ENTERPRISE/Using+personal+access+tokens ; https://success.atlassian.com/solution-resources/agile-and-devops-ado/platform-administration/how-to-secure-jira-and-confluence-rest-api-calls-in-data-center
   Publisher: Atlassian. Pub_date: undated. Confidence: high. Class: primary.

10. Claim: DC /rest/api/2/search keeps startAt/maxResults pagination (default 50). maxResults is capped by jira.search.views.default.max (default 1000). The per-user ceiling is jira.search.views.max.limit. Paging past jira.search.platform.max.result.window (default 10,000) can fail, so narrow the JQL with date filters. Setting the property to unlimited is discouraged. The `total` field and expand=changelog behaviour were NOT confirmed this run.
    Source: https://support.atlassian.com/jira/kb/how-to-use-the-maxresults-api-parameter-for-jira-issue-search-rest-api/ ; https://support.atlassian.com/jira/kb/should-i-change-the-jirasearchviewsdefaultmax-parameter-to-unlimited-to-get-all-results-from-a-search-each-time/ ; https://support.atlassian.com/jira/kb/handling-jql-rest-api-searching-exceeding-max_result_window-in-jira/
    Publisher: Atlassian Support KB. Pub_date: undated. Confidence: high for the caps, unverified for the rest. Class: primary.

11. Claim: The Cloud search deprecation does not affect Data Center (community answer: "Nope").
    Source: https://community.developer.atlassian.com/t/effect-on-deprecation-of-jql-search-and-evaluate-expression-endpoints-on-jira-data-center/95510 . Publisher: Atlassian Developer Community. Pub_date: undated. Confidence: medium. Class: primary (community).

12. Claim: Atlassian Data Center end of life is 2029-03-28 (support ends; licences go read-only; extended maintenance by exception). It was announced on 2025-09-08. New-customer sales stop 2026-03-30 and the last renewal for existing customers is 2028-03-30 (secondary sources).
    Source: https://www.atlassian.com/software/jira/update (confirms only 2029-03-28) ; https://jimiwikman.se/writings/my-articles/atlassian/atlassian-data-center-is-officially-ending-on-march-28-2029-r258 ; https://saasjet.com/blog/atlassian-data-center-end-of-life/
    Publisher: Atlassian / blogs. Pub_date: 2025-09. Confidence: high for the 2029 date, medium for the intermediate dates. Class: primary / secondary.

## Bottom line (adapter design implications)
- Cloud adapter: use only /rest/api/3/search/jql. Loop on nextPageToken until isLast (I did not verify the isLast field name). Never parallelise pages. Do not rely on total; call approximate-count only for progress display. Keep the page size configurable and tolerate short pages.
- Treat inline expand=changelog as truncated (20 entries/issue). Whenever an issue shows 20 entries (or always, for correctness), fetch the rest with per-issue /changelog (startAt/maxResults). Alternatively use bulkfetch, but it is Experimental, so hide it behind a flag and add dedupe by changelog id.
- Incremental JQL `updated >= last_run`: store a watermark with overlap (e.g. minus a few minutes) and dedupe by issue key + changelog id, because eventual consistency was cited as the reason for the new search design.
- DC adapter: Bearer PAT (Jira >= 8.14), startAt/maxResults/total pagination. Use page size <= 1000, which is the server cap and may be lower. Slice JQL by date windows to stay under the 10,000 result window. Inline changelog on DC is unverified; test the fixtures against both inline and per-issue modes.
- Since DC is tested on fixtures only, pin the fixtures to documented shapes (startAt/total) and record that the caps are configurable server-side. DC EOL is 2029-03-28, so DC is low strategic risk for a demo but should be framed as legacy.
- Seeding a Cloud demo instance: field, then context, then options, with Administer Jira rights. Screen association is unverified.

## Leads not chased
- Official developer.atlassian.com v3 reference pages (truncated by the fetch tool) for exact search/jql parameters, isLast, the maxResults cap, bulkfetch limits and the field-creation type keys.
- The CHANGE-xxxx notices and the exact per-region removal dates.
- Rate limiting (Cloud and DC) and the DC rate-limiting docs.
- Creation of issue types, statuses and workflows via API; adding a field to a screen.
- DC expand=changelog and `total` semantics in the docs.atlassian.com REST reference.

## Looked for but not found
- The authoritative Atlassian text for the 2025-05-01 removal (only secondary quotes).
- Any evidence of a DC rate limit (the search results did not surface DC REST rate-limiting docs).
- A staff statement that bulkfetch has left Experimental status.
