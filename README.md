# Earworm

**The structure DNA of 1,000 pop songs.**

Pop keeps rebuilding the same song. Four chords loop under a verse, the chorus arrives sooner every decade, the bridge comes and goes, the key change lifts and then disappears. Earworm maps 1,000 pop songs to measure how the form has changed: sections, chord progressions, music theory, and the album covers that sold them.

It is a sister project to Bloodline (500 horror films) and follows the same rules: every fact carries a source, a retrieval date and a confidence level.

> **Status:** set-up. A 10-song pilot is listed in `songs.csv`; nothing has been collected yet. The pilot's year-end positions are from Claude's knowledge and need checking against the chart.

---

## Layers (planned)

| Layer | What it holds | Main sources |
|---|---|---|
| **The list** | 1,000 songs with artist, chart year, country, region and how each was selected | Curated (`songs.csv`) |
| **Facts** | Writers, producers, label, release dates, genres, awards, external IDs | MusicBrainz, Wikidata |
| **Article** | Background, composition (key, tempo, vocal range), reception, artwork notes | Wikipedia |
| **Structure** | Sections (intro, verse, pre-chorus, chorus, bridge, outro) with timings | McGill Billboard, Harmonix Set, Chordonomicon, Genius labels |
| **Timed lyrics** | Each sung line with its timestamp: time to first chorus, words, repetition | LRCLIB |
| **Chords and theory** | Progressions as positions in the key (I, IV, V, vi), borrowed chords, key changes | Rolling Stone corpus, McGill Billboard, Hooktheory, Chordonomicon |
| **Audio** | Key, tempo and loudness from 30-second previews (previews are never stored) | Deezer / iTunes previews, analysed locally |
| **Covers** | Album and single artwork, with colour, brightness, faces, text share; designer and photographer credits | iTunes, Deezer, Cover Art Archive, Discogs |
| **Lineage** | Covers, samples and interpolations | SecondHandSongs, MusicBrainz |

Source choices and their reliability are in [`docs/sources.md`](docs/sources.md). Every file is defined in [`docs/schema.md`](docs/schema.md).

## Privacy

Lyrics, chords transcribed by others and cover art are copyrighted. This repo stays private. Only derived measurements (timings, counts, tempos, colour values) could ever be published.
