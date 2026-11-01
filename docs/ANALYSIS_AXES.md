# Core analysis axes

These eight axes are the product’s analysis order. Status describes the audited
DC site before the grain repair, not a promise that a source has been connected.
Ready means the required facts exist; partial means useful facts exist with a
stated limitation; needs setup means a source or configuration is missing.

| # | Axis and question | Source | Current status | Next action |
| --- | --- | --- | --- | --- |
| 1 | Impressions vs clicks: which pages and search terms have visibility but few clicks, and what may explain the gap? | GSC page totals and visible query detail | partial | Store query-free page and property totals; compare CTR and position. Treat causes as hypotheses, not proven explanations. |
| 2 | Break points: where does impression → click → visit → call click lose people? | GSC property totals; GA4 sessions and a configured call event | needs setup | Repair GSC totals; identify the existing GA4 call-click event. Ratios across sources are directional, not a matched-user funnel. |
| 3 | Mobile & iOS: how do device CTR/position and iOS/Android behavior differ? | GSC device totals; GA4 operating-system reports | partial | Store device totals and fetch site-level OS sessions/conversions. OS cannot be attributed to a GSC query or page. |
| 4 | Geography / zones: how visible are emergency locksmith searches for each city or neighborhood? | Visible GSC queries matched against configured zones | needs setup | Configure actual city/neighborhood names; this measures query wording, not searcher location. |
| 5 | Sitemaps: what was submitted, what is indexed, and which URLs are not? | GSC Sitemaps API and stored URL Inspection results | needs setup | Collect sitemap metadata and inspect a bounded URL sample, at most 200 URLs per run. Do not present the sample as complete coverage. |
| 6 | Internal links: which pages are orphaned, which links break, and how is the site connected? | Latest uploaded Ahrefs Site Audit CSV | needs setup | Supply a Site Audit export with URL, inbound links, and HTTP status information. |
| 7 | Links between our five sites: who links to whom? | Latest backlinks CSV for each portfolio site | needs setup | Supply backlinks exports and confirm the five real domains. Placeholder sites do not prove a missing link. |
| 8 | Search requests: which visible queries offer the largest opportunity? | GSC query detail; optional future keyword provider | partial | Rank positions 4–20 by impressions × (1 − CTR). Volume and difficulty remain null: needs keyword provider. |

## Audit baseline (22 October 2026)

For 22 September–19 October 2026, stored query detail has 0 clicks / 2,267
impressions. Read-only Google checks showed property totals of 4 / 2,519 and
page totals of 4 / 2,847. These are different aggregation grains and must never
be added together. The commercial-locksmith zero-click flag was false; the
panic-bar and fire-door repair pages still had zero clicks in page totals.
GA4 stored 7 sessions, 7 summed users and zero conversions, matching that
window. Its property time zone is America/Los_Angeles. The screenshot showing
10 sessions used a later date window. Call-event configuration, zones, URL
inspection history and Ahrefs CSVs were not available in the audit.
