# Analysis screenshots

Synthetic browser fixtures in a disposable `_smoke` database. These are UI test
artifacts, not real Google data or results for dcemergencylockanddoor.com.
Captured by `e2e/analysis.spec.ts` against FastAPI and PostgreSQL, with no Google calls.

| View | Screenshot |
| --- | --- |
| Desktop, light, 1440 × 1000 viewport | [Full page](desktop.png) · [First axis](impressions-desktop.png) |
| Phone, light, 390 × 844 viewport | [Full page](phone.png) · [First axis](impressions-phone.png) |
| Phone, dark, 390 × 844 viewport | [Full page](phone-dark.png) · [First axis](impressions-phone-dark.png) |

Fixtures intentionally leave call tracking and service zones unconfigured to show
setup states. Other panels exercise charts and the admin portfolio heatmap.
