"""Resumable collection runner. Runs the per-song layers for every song that has facts.json and
lacks the layer's output (or its .none marker). With --follow it keeps polling while
tools/facts.py is still running, so audio and lyrics can trail behind facts.

Usage: PYTHONPATH=tools python3 tools/run_batch.py --only audio,lyrics [--follow]"""
import os, subprocess, sys, time
from common import SONGS, load_songs

import audio, lyrics

LAYERS = {  # name: (done-check paths, function)
    "audio": (["audio.json", "audio.none"], audio.process),
    "lyrics": (["lyrics/measures.json", "lyrics.none"], lyrics.process),
}


def done(sid, paths):
    return any(os.path.exists(os.path.join(SONGS, sid, p)) for p in paths)


def facts_running():
    return subprocess.run(["pgrep", "-f", "tools/facts.py"], capture_output=True).returncode == 0


def main():
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(LAYERS)
    follow = "--follow" in sys.argv
    while True:
        worked = 0
        for s in load_songs():
            sid = s["id"]
            if not os.path.exists(os.path.join(SONGS, sid, "facts.json")):
                continue
            for name in only:
                paths, fn = LAYERS[name]
                if done(sid, paths):
                    continue
                try:
                    fn(s)
                except Exception as e:
                    print(sid, name, "ERROR", repr(e)[:200], flush=True)
                worked += 1
        if not follow or (not worked and not facts_running()):
            break
        if not worked:
            time.sleep(60)


if __name__ == "__main__":
    main()
