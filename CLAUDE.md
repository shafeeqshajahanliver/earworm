# Earworm

Private research corpus of 1,000 pop songs, owned by Shafeeq Shajahan (Shaf). Sister project to Bloodline (`shafeeqshajahanliver/bloodline`), built the same way. Focus: song structure (sections, bridges), chord progressions, music theory, and album covers. `docs/schema.md` defines every file; `docs/sources.md` says which source is trusted for what.

## Working rules

- Shaf is non-technical. Explain in plain English, lead with what the data shows, and keep code out of the conversation unless he asks.
- Never sign in with Shaf's credentials or use his API keys. If a step needs a login (Genius, Hooktheory, Discogs), he runs it himself. Never read `.env`.
- Never work around a site that blocks automated access (e.g. Ultimate Guitar, Chordify, WhoSampled). Record it as a gap.
- Keep the repo private. Never commit audio (previews included) or video; analyse previews in `_cache/` and keep only the measurements. Use Git LFS for images.
- Never edit source files to fix data. Use `songs/<id>/corrections.json`.
- Every new fact carries a source, retrieval date and confidence level: `expert` (hand-annotated research datasets: McGill Billboard, Rolling Stone corpus, Harmonix Set), `sourced` (cited in a published source, e.g. Wikipedia citing sheet music), `crowd` (Chordonomicon, Genius, LRCLIB), `computed` (our own audio or image analysis), `claude-knowledge`, `first pass` (interpretive tags, until Shaf reviews them).
- Where expert and crowd sources disagree, keep both and record the disagreement; the expert value wins in reports.
- Store chords both as written and as positions in the key (Roman numerals). Crowd chord sheets often sit in the wrong key because of capo use; the Roman numerals survive that.
- Check artist, year and version when matching. Re-recordings, remixes, live versions, radio edits and same-name songs are common. Match to the charting recording.
- `chart_year` in `songs.csv` is the chart year used for selection; release dates come from MusicBrainz and live in `facts.json`.
- Keep requests slow (Wikipedia 1 per 3 s, MusicBrainz 1 per second) with an identifying User-Agent.
