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
