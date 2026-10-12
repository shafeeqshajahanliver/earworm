# First insights from the 30-song pilot

First pass, 12 October 2026. 30 Billboard year-end number ones, split into three eras of 10 (1959–79, 1981–99, 2001–23). Ten songs per era is enough to spot leads and nowhere near enough to prove a trend. Each lead says how solid it is. Numbers come from `songs/*/` (see `reports/data-audit.md`); tempos use Deezer's figure where our reading was half-speed.

| # | Lead | 1959–79 | 1981–99 | 2001–23 | Strength |
|---|---|---|---|---|---|
| 1 | Weeks on the Hot 100 (median) | 22.5 | 24.5 | 48 | Strong: every post-2000 song ran 32+ weeks; no pre-1980 song passed 26 |
| 2 | Songs that are covers or remakes of an earlier song | 2 | 4 | 0 | Strong in this sample; check at scale |
| 3 | Words per song (median) | 242 | 297 | 417 | Strong: 5 of 10 modern songs exceed 400 words |
| 4 | Time before the first sung word (median, seconds) | 8 | 15 | 5 | Medium: 6 of 10 in 1981–99 wait 15 s+, none since 2000 |
| 5 | Songs with 3+ credited writers | 0 | 3 | 5 | Medium: Low has no writer data in MusicBrainz |
| 6 | Producer also credited as writer | 1 | 5 | 6 | Medium |
| 7 | "I" share of I/you/we pronouns | 59% | 47% | 58% | Medium: "you" peaks in 1981–99 |
| 8 | Album cover brightness (median, 0–1) | 0.44 | 0.42 | 0.29 | Medium: dark share of the cover rises 27% → 35% → 45% |
| 9 | Cover saturation (median, 0–1) | 0.28 | 0.43 | 0.20 | Weak to medium: early "covers" mix album sleeves and disc labels |
| 10 | Title sung (median times) | 6.5 | 9.5 | 11.5 | Weak: driven by Yeah! (80) and Low (65) |
| 11 | Tempo (median BPM) | 130 | 123 | 115 | Weak: wide spread, half-speed readings corrected by hand |
| 12 | Track length (median, seconds) | 204 | 245 | 228 | Weak |

Not used: loudness from previews (old songs on Deezer are often louder remasters), the chorus-timing proxy from lyrics (too crude), and preview keys (unreliable; see the audit).
