"""Build the Earworm app page: app/data.json (from tools/build_app_data.py) inlined into
app/template.html. Writes app/earworm.html (gitignored would be wise: it embeds derived data only)."""
import os, sys
from common import ROOT
t = open(os.path.join(ROOT, "app", "template.html")).read()
d = open(os.path.join(ROOT, "app", "data.json")).read().replace("</", "<\\/")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "app", "earworm.html")
open(out, "w").write(t.replace("__DATA__", d))
print(out, os.path.getsize(out))
