# Collection contract

This reference documents source-specific parsing and offline verification.

## Observed HTML

- List: `.bbsCount` contains total records and page count; `table.list tbody tr td.subject a` links include `bbsNo` and `nttNo`; `.bbs_comment` contains the displayed reply count.
- Post: `table.view` rows use labels `제목`, `내용`, `작성자`, `부서`, `처리구분`; `.bbsInfo .bbsCount` carries Korean date/time.
- Comments: `#bbsNttComment .bbsReplyCount`, `ul > li .name`, `.date`, `.bbsReplyText`. Dates may use `YYYY.MM.DD`; normalize comparison, preserve source display.
- Files: `table.view ul.attach a` links use `/newknue/downloadBbsFile.do?atchmnflNo=<id>`.

## Dataset v1

Top-level keys: `schema_version`, `collected_at` (Asia/Seoul ISO), `boards`, `posts`, `changes`, `errors`.
Boards contain `id`, `key`, `name`, `total`, `collected`.
Post identity is `<bbs_no>-<ntt_no>`, stable across title changes. Fields include source URL, title, sender, department, created timestamp, source processing status, plain/HTML body, comments, attachments, sites, classification evidence/category, source HTML path and semantic content hash.
Comments retain author/date/text. Attachments retain file ID/name/source URL/local relative path/size/SHA-256. Paths resolve inside the destination.
`changes` compares current source-content hashes with the previous verified dataset: `new`, `updated`, `missing`. Snapshots and old notes remain available for missing records.

Board-edit detection hashes source fields and attachment identities/content only; local site classifications and storage paths do not mark a post as edited. Full snapshot hashes also include classification metadata. Archived metadata retains the source timestamp, excluding volatile view counters. Overrides use the same evidence rules for stored records and rendered views.

## Checks

1. Exactly 14 distinct configured canonical sites.
2. Unique board/post IDs; every board's collected count equals the source total.
3. Every post's parsed comment count equals source reply count and list count.
4. Every download is nonempty; declared Content-Length matches when present; login/error HTML is rejected.
5. Local attachment sizes and SHA-256 values match the dataset; HTML archives exist.
6. Rendered links resolve; one source note per post; no source duplication across site views.
7. Same inputs leave generated notes and immutable versions unchanged; manual text outside markers survives.

Managed notes adapt `99_Template/_프로젝트.md` with `type: project`, `status: active`, the existing `#업무/홈페이지` tag, project summary and source-specific sections. Empty template sections are omitted. Source quotations remain verbatim, including original wording and dates.
