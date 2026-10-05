"""Converte publicacoes.bib em publicacoes.yml para a listagem do Quarto.

Executado automaticamente via `pre-render` no _quarto.yml. Sem dependências
externas: o parser cobre o BibTeX exportado pelo Google Scholar, Zotero e ORCID.
"""

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "publicacoes.bib"
OUT = ROOT / "publicacoes.yml"

# Nome do autor do site, destacado em negrito na lista de autores
HIGHLIGHT = re.compile(r"\bFalco\b")

LATEX_ACCENTS = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303",
    '"': "\u0308", "c": "\u0327", "=": "\u0304",
}


def read_braced(text, i):
    """Lê um valor entre chaves a partir de text[i] == '{'; devolve (valor, fim)."""
    depth, start = 0, i
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError("chaves desbalanceadas no .bib")


def parse_bib(text):
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        kind = m.group(1).lower()
        if kind in ("comment", "string", "preamble"):
            continue
        body, _ = read_braced(text, text.index("{", m.start()))
        fields = {"type": kind, "key": m.group(2)}
        i = body.index(",") + 1
        while i < len(body):
            fm = re.compile(r"\s*(\w+)\s*=\s*").match(body, i)
            if not fm:
                break
            name, i = fm.group(1).lower(), fm.end()
            if body[i] == "{":
                value, i = read_braced(body, i)
            elif body[i] == '"':
                end = body.index('"', i + 1)
                value, i = body[i + 1:end], end + 1
            else:
                vm = re.compile(r"[^,\s}]+").match(body, i)
                value, i = vm.group(0), vm.end()
            fields[name] = value
            cm = re.compile(r"\s*,?").match(body, i)
            i = cm.end()
        entries.append(fields)
    return entries


def clean(value):
    value = re.sub(r"\\([`'^~\"=c])\s*\{?(\w)\}?",
                   lambda m: m.group(2) + LATEX_ACCENTS[m.group(1)], value)
    value = value.replace("\\&", "&").replace("--", "–").replace("~", " ")
    value = re.sub(r"\\\w+\s*", "", value)
    value = value.replace("{", "").replace("}", "")
    return unicodedata.normalize("NFC", " ".join(value.split()))


def format_authors(raw):
    names = []
    for author in re.split(r"\s+and\s+", clean(raw)):
        if "," in author:
            last, first = [p.strip() for p in author.split(",", 1)]
        else:
            parts = author.split()
            last, first = parts[-1], " ".join(parts[:-1])
        initials = " ".join(p[0] + "." for p in re.split(r"[\s.]+", first) if p)
        name = f"{last}, {initials}".strip(", ")
        names.append(name)
    return names


def main():
    items = []
    for e in parse_bib(BIB.read_text(encoding="utf-8")):
        venue = clean(e.get("journal") or e.get("booktitle") or e.get("publisher")
                      or e.get("school") or e.get("howpublished") or "")
        details = ", ".join(x for x in [
            e.get("volume") and f"v. {clean(e['volume'])}",
            e.get("number") and f"n. {clean(e['number'])}",
            e.get("pages") and clean(e["pages"]),
        ] if x)
        doi = clean(e.get("doi", ""))
        authors = format_authors(e.get("author", ""))
        items.append({
            "title": clean(e.get("title", "Sem título")),
            "authors": "; ".join(authors),
            # Autor(es) do site, destacados em negrito pelo template publicacoes.ejs
            "highlight": "; ".join(a for a in authors if HIGHLIGHT.search(a.split(",")[0])),
            "venue": venue,
            "details": details,
            "year": clean(e.get("year", "s.d.")),
            "date": f"{clean(e.get('year', '1900'))}-01-01",
            "doi": doi,
            "url": clean(e.get("url", "")) or (f"https://doi.org/{doi}" if doi else ""),
            "pdf": clean(e.get("pdf", "")),
            "note": clean(e.get("note", "")),
            "type": e["type"],
        })
    items.sort(key=lambda x: x["year"], reverse=True)
    # JSON é YAML válido: evita depender do PyYAML
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
