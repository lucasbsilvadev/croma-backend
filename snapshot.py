# snapshot.py
from pathlib import Path

IGNORE_DIRS = {
    ".venv", "venv", ".env", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".git", ".idea", ".vscode",
    "node_modules", "htmlcov",
}
IGNORE_FILES = {
    ".coverage", "coverage.xml", "snapshot.txt", "pytest-output.txt",
}
IGNORE_EXTS = {".pyc", ".pyo", ".pyd", ".log"}

def ignored(p: Path) -> bool:
    if p.name in IGNORE_DIRS or p.name in IGNORE_FILES:
        return True
    if p.suffix in IGNORE_EXTS:
        return True
    return False

def tree(root: Path, prefix: str = "") -> list[str]:
    lines = []
    items = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for item in items:
        if ignored(item):
            continue
        if item.is_dir():
            lines.append(f"{prefix}+---{item.name}")
            lines.extend(tree(item, prefix + "|   "))
        else:
            lines.append(f"{prefix}|   {item.name}")
    return lines

def dump(root: Path) -> str:
    parts = ["=== ESTRUTURA ===", "Listagem de caminhos de pasta", ""]
    parts.extend(tree(root))
    parts.append("")
    parts.append("")
    parts.append("=== CONTEUDO DOS ARQUIVOS ===")
    parts.append("")

    for path in sorted(root.rglob("*")):
        if path.is_dir() or ignored(path):
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root)
        parts.append("=" * 60)
        parts.append(f"FILE: {rel}")
        parts.append("=" * 60)
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            parts.append("[binário — ignorado]")
        parts.append("")

    return "\n".join(parts)

if __name__ == "__main__":
    out = dump(Path("."))
    Path("snapshot.txt").write_text(out, encoding="utf-8")
    print(f"snapshot.txt gerado ({out.count(chr(10))} linhas)")