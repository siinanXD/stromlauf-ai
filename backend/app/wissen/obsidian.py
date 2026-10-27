"""Obsidian-Export des gelernten Wissens (rein)."""

import re


def dateiname(name: str, fallback: str) -> str:
    """Dateiname nur aus erlaubten Zeichen; leer ergibt `fallback`."""
    sauber = re.sub(r"[^A-Za-z0-9äöüÄÖÜß ._-]", "_", name).strip()
    return sauber or fallback


def markdown(machine_id: str, name: str, stand: str, notizen: list[dict]) -> str:
    """Markdown-Notiz mit Frontmatter und je Satz einer Zeile samt Beleg-Links."""
    zeilen = ["---", f"machine_id: {machine_id}", f"stand: {stand}", "---", f"# {name}", ""]
    for notiz in notizen:
        links = " ".join(
            f"[[{b['filename']}|S. {b['page']}]]" if b.get("page") is not None
            else f"[[{b['filename']}]]"
            for b in notiz["belege"]
        )
        praefix = "- 🔒 " if notiz["gesperrt"] else "- "
        zeilen.append(f"{praefix}{notiz['text']} {links} ({notiz['quelle']})")
    return "\n".join(zeilen) + "\n"
