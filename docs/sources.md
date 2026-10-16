# Sources

Which source is trusted for what. Coverage figures are approximate and from Claude's knowledge; the pilot will measure real coverage for our songs. Licence terms are to be checked before bulk collection.

## Structure (sections, bridges, timings)

| Source | Gives | Coverage | Confidence | Access |
|---|---|---|---|---|
| McGill Billboard Project | Timed section labels and chords | ~700–900 Billboard Hot 100 songs, 1958–1991 | expert | Open download |
| Harmonix Set | Sections, beats, downbeats | ~900 Western pop songs | expert | Open download (annotations only) |
| Chordonomicon | Section labels attached to chords | ~660,000 songs | crowd | Open dataset (Hugging Face) |
| Genius | [Verse] [Chorus] [Bridge] labels in lyrics | Nearly all pop | crowd | API key; Shaf signs in. May block automated access |
| LRCLIB | Timestamped lyric lines | Very wide | crowd | Free, no login |

Bridge presence is recorded per source and compared; agreement across sources is the strongest evidence.

## Chords and theory

| Source | Gives | Coverage | Confidence | Access |
|---|---|---|---|---|
| Rolling Stone corpus (de Clercq & Temperley) | Roman-numeral harmony and melody, two independent analysts | ~200 songs | expert | Open download |
| McGill Billboard Project | Timed chords, key | as above | expert | Open download |
| Hooktheory TheoryTab | Key-relative chords and melody | Tens of thousands, strong on modern pop | crowd (curated) | Account; Shaf signs in |
| Chordonomicon | Chord sequences | ~660,000 songs | crowd | Open dataset |
| Wikipedia "Composition" | Key, tempo, vocal range, sometimes progression, often citing published sheet music | Most major hits | sourced | Open |
| Deezer / iTunes previews | Key, tempo, loudness (30 s clip) | Anything with a preview | computed | Free, no login |

Gaps (block automated access): Ultimate Guitar, Chordify, WhoSampled. Spotify audio features closed to new apps in late 2024; AcousticBrainz is a frozen archive with nothing after 2022.

## Covers

| Source | Gives | Confidence | Access |
|---|---|---|---|
| iTunes Search API | Artwork up to 3000px | sourced | Free, no login |
| Deezer API | Artwork 1000px | sourced | Free, no login |
| Cover Art Archive | Original scans, back covers, regional editions | sourced | Free, no login |
| Discogs | Designer, art director, photographer credits | sourced | Token; Shaf generates it |
| Wikidata / MusicBrainz | Some cover-art and photography credits | sourced | Open |
| Wikipedia | Story behind the artwork, where an article covers it | sourced | Open |

Default: the album cover of the album the song appeared on, plus the single sleeve where one exists.

## Facts and lineage

MusicBrainz (writers, producers, recordings, release dates, ISRCs), Wikidata (awards, IDs), SecondHandSongs (covers, samples, adaptations).

## What the 30-song pilot found (6 October 2026)

| Source | Result | Notes |
|---|---|---|
| Wikipedia, Wikidata, MusicBrainz | 30/30 | Charting recording found via the earliest single release group. Multi-version articles (e.g. I Will Always Love You) follow the artist's own version article |
| Billboard weekly Hot 100 (utdata/rwd-billboard-data) | 30/30 | Double A-sides chart as "A/B" |
| LRCLIB | 30/30 | Synced lyrics for every song |
| Deezer / iTunes previews | 30/30 | Tempo agrees with Deezer's own BPM apart from half/double-time cases. Key from a 30 s clip is rough (often the relative key) |
| Cover Art Archive | single 27, album 28 | Pre-1980 "single" images are often the disc label: no picture sleeve |
| iTunes artwork | 29 | Often a later reissue or re-recording; check before using |
| SecondHandSongs | 28 | Anonymous API throttles with 403 after ~25 quick calls; 6 s spacing works |
| McGill Billboard | 1 | DDMAL page 404; data via mirdata's Dropbox links / Zenodo. Its random sample barely overlaps year-end #1s |
| Harmonix Set | 3 | Structure only; often annotates shortened edits |
| Rolling Stone corpus | 4 | Two analysts per song; they often disagree on form, never on key |
| Isophonics | 0 | Beatles albums only |
| Chordonomicon | 2 | Matching needs Spotify track IDs. No key-free route found for 17 songs; 11 IDs found were different releases from the ones in the dataset. Odesli/song.link now needs a key (gap) |

## Lessons from scaling to 650 (October 2026)

- **Single releases carry other versions.** Matching "the first track with this title on the earliest single" picked 12-inch, dub and remix versions for 44 songs (Le Freak 5:30, Wannabe 6:21). `tools/facts.py` now takes the track closest to the Wikipedia single length and rejects dub/club/extended/percapella titles; 37 of the 44 are fixed, the rest are within normal edit differences or flagged.
- **Some titles are never sung as written** (Kill Bill, Tik Tok as "tick tock", SexyBack, 7 Rings). The lyrics title-word check now accepts these only when the lyric is time-synced and title, artist and a sourced length all agree. Plain-text entries for instrumentals can carry another song's words (Wheels had Chuck Berry), so they stay rejected.
- **Charting remixes** (Cold Heart (PNAU Remix), Despacito (Remix)) are allowed to match their own remix name.
- **SecondHandSongs** stops answering after a few hundred anonymous requests a day; `tools/lineage.py` stops at the first refusal and resumes on the next run.
- **Chordonomicon** contains rows that are whole albums under one Spotify ID (a Beatles row of ~2,000 chords holds Help! in the middle). Rows over 400 chords are rejected and recorded.
