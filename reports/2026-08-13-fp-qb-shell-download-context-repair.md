# Fantasy Points QB shell download context repair

Date: 2026-08-13. This is an acquisition-only repair made before any offense
window artifact or QB shell-fit result existed.

The first invocation of the frozen 56-export Offense Coverage Matrix plan set
and rendered the exact 2022 Weeks 1--4 Offense table, but timed out waiting for
the values-response event and wrote no CSV. The preserved screenshot and a
read-only response trace showed the cause: the downloader navigates to the
catalog's Defense route and then switches through the visible Offense control,
while its response listener still expected the original Defense URL. The site
correctly sent the scoped response at the active Offense URL.

The repair derives the expected `/values` endpoint from the authenticated
Fantasy Points report URL actually on screen after context selection. It still
requires the exact POST method, HTTP success, submitted season/week JSON,
response content, rendered game-count scope, downloaded Season/G scope, and
artifact hash/shape. It changes no plan, season, week, feature, support rule,
model, outcome or gate. The failed run remains immutable at
`fantasy-points/automated/20260813T140405Z__same-season-qb-shell-fit-last-four-v1`
with zero accepted artifacts.
