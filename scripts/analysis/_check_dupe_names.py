import re
from pathlib import Path

d = Path(__file__).parent
names = {}
for f in sorted(d.glob("build_pub_batch*_topics_data.py")):
    text = f.read_text(encoding="utf-8")
    new_names = re.findall(r'^\s{4}"((?:[^"\\]|\\.)*)":\s*\(\s*$', text, re.MULTILINE)
    reuse_names = re.findall(r'^\s*\(\s*\n\s*"((?:[^"\\]|\\.)*)",\s*\n', text, re.MULTILINE)
    for n in new_names + reuse_names:
        names.setdefault(n, []).append(f.name)

dupes = {n: files for n, files in names.items() if len(files) > 1}
print("total dupes:", len(dupes))
for n, files in dupes.items():
    print(" -", n, "->", files)
