---
name: homepage-collect
description: Collect or refresh the 2026 KNUE homepage project collaboration boards into Obsidian, including posts, comments, attachment originals, 14 site views and an aggregate dashboard. Triggers include 홈페이지 사업 진행 정보 수집, 홈페이지 협업게시판 수집, 사업 진행 정보 갱신. Use only for the hanshinit newknue project, not generic web scraping or scheduled notifications.
---

# Homepage project collection

Use the maintained collector, not newly generated one-off login code.
Resolve `<vault>` from the current vault root and `<skill>` as `<vault>/.claude/skills/homepage-collect/`.
Windows example: `C:/Dev/ObsidianVault`; macOS example: `/Users/kadragon/ObsidianVault`.
Default output: `12_Projects/2026/통합 홈페이지/10. 사업 진행 정보/`.

## Run

1. Resolve a real Python 3.11+ interpreter (`py -0p` on Windows). Use that same interpreter for dependencies and execution. On macOS, resolve `python3` and check its version. Do not reuse another machine's absolute interpreter path.
2. Install dependencies only when missing: `<python> -m pip install -r <skill>/scripts/requirements.txt`.
3. Delegate note-producing execution to `obsidian-operator`: run `<python> <skill>/scripts/sync.py --vault <vault>` there. The operator uses the maintained renderer; do not create notes manually.
4. Confirm exit 0, board totals, comment counts, attachment SHA-256 checks and note links. Open `_사업 진행 종합.md`; report new/updated/missing counts and unresolved site classification.

An offline integrity check is available with `collect.py --vault <vault> --verify`.
Offline rerender: `render_notes.py --output <output> --config <skill>/references/sites.json`.
When changing implementation, run both test files in `tests/` and independently check the live schema. New note generation, including script execution, is routed to `obsidian-operator`; the bulk renderer implements the verified project template and deterministic gates. Existing small in-scope note edits may be direct.

## Sources and behavior

- Authenticate at `https://cop.hanshinit.co.kr/newknue/login.do` with `.env` keys `HANSHIN_COP_ID`, `HANSHIN_COP_PW`. Load secrets in the collector process; never echo them. Cookies remain in memory.
- The observed login redirects are `index.do` → `sub.do` → `selectBbsNttList.do`. Read-only endpoints and login are explicitly allowlisted. Never call write, comment, delete or update endpoints.
- Collect all pages of boards 2695/key3774, 2696/key3775 and 2697/key3776. Read operations may change the website's read flag/view counter; no explicit business-data mutation is performed.
- Re-read existing posts/comments/attachment bytes on every refresh to detect silent edits and same-ID attachment replacement. Identical hash versions reuse existing files. This is an on-demand full check, not scheduled polling.
- Publish the current dataset only after all boards and attachment checks succeed. Retain prior content-addressed snapshots and attachment versions; a missing post is reported, never automatically deleted locally.
- Canonical 14-site list and aliases: `references/sites.json`, grounded in `_Sources/홈페이지/홈페이지-고도화-대상목록-2026.md`. Match title, body, comment and attachment filename; sender department is not target-site evidence. Multiple-site posts link to one source note. This detects mentions, not confirmed scope or completion.
- Site-less project-wide items appear in the common view; uncertain items remain unclassified. Facility reservation targets (총무과, 제4대학) remain outside the 14-site count. Classification overrides must cite source evidence; do not add unsupported aliases or infer a target from sender metadata.
- Attachment originals are saved and linked. Their internal content is not automatically summarized or used as site evidence. If the user wants attachment-content analysis, inspect the originals with the corresponding document skill and record exact evidence.
- Generated note body sections are marked; manual notes outside them survive refresh. Put user edits outside the managed markers. Do not replace an unmarked existing note. Do not modify the project hub or old monitoring note without authorization.

## Failure handling

Stop on failed authentication, unexpected redirects, schema/count mismatch or failed download. Report only the sanitized cause; never print credentials, cookies or login response bodies. Fix an observed schema/path with a regression test; do not broaden host or mutation permissions. Follow the vault's repeated-error stop rule. A leftover `.collection.lock` requires checking for a live collector process before removal.

No external reporting, scheduled jobs, or changes to credentials are implied by collection.

## Output

- `_사업 진행 종합.md`: source counts, processing statuses, recent discussions, site links and changes.
- `사이트별/<site>/_<site> 사업 진행.md`: all related records and discussion excerpts.
- `_공통 및 미분류 사업 진행.md`: common, additional facility scope and unresolved records.
- `원문노트/사업진행-<board>-<post>.md`: source body/comments and local attachment links.
- `원본데이터/dataset.json`: current verified machine-readable dataset.
- `원본데이터/게시글/<id>/`: content-only HTML and JSON snapshots; no authentication UI or cookies.
- `첨부파일/<id>/`: attachment originals, versioned by file ID and SHA-256.

Schema and verification details: [references/schema.md](references/schema.md).
