"""Build site/index.html: the page template with the surface data, structures and fonts embedded.

The template is a page body (it was written for a host that adds the document skeleton), so the
standalone build wraps it in a full HTML document. The Google Fonts link is replaced by the font
files in fonts/ (Latin subset, WOFF2, SIL Open Font License; see fonts/OFL-*.txt) as data URIs,
so the page works fully offline. No dependencies beyond the standard library.

    python build.py
"""
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
</head>
<body>
"""
TAIL = "\n</body>\n</html>\n"


FONT_LINKS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n',
              '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600'
              '&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">\n')


def font_css():
    """@font-face rules for the Latin subset, one per weight (Plex Sans is one variable file)."""
    rules = []
    for line in (HERE / "fonts" / "latin.tsv").read_text(encoding="utf-8").splitlines():
        family, weight, fname, urange = line.split("\t")
        b64 = base64.b64encode((HERE / "fonts" / fname).read_bytes()).decode("ascii")
        rules.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};font-display:swap;"
                     f"src:url(data:font/woff2;base64,{b64}) format('woff2');unicode-range:{urange};}}")
    return "<style>\n" + "\n".join(rules) + "\n</style>\n"


def main():
    t = (HERE / "src" / "template.html").read_text(encoding="utf-8")
    for link in FONT_LINKS:
        assert link in t, "Google Fonts link not found in the template"
        t = t.replace(link, "")
    t = font_css() + t
    d = (HERE / "data" / "data.json").read_text(encoding="utf-8")
    g = (HERE / "data" / "geom.json").read_text(encoding="utf-8")
    assert "</script" not in d and "</script" not in g
    # the template carries its own charset/viewport metas for the hosted version; the head above replaces them
    t = t.replace('<meta charset="utf-8">\n', "").replace(
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n', "")
    out = HERE / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(HEAD + t.replace("__DATA__", d).replace("__GEOM__", g) + TAIL, encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(HERE)} ({out.stat().st_size // 1024} kB)")


if __name__ == "__main__":
    main()
