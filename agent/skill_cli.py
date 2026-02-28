"""
agent-skill  —  CLI for managing skills in the VS Code agent convention.

Skills live on disk under ``skills/<name>/SKILL.md`` (with optional
``references/`` subdirectories) following the convention established by
playwright-cli and other tools.  A Qdrant vectorstore provides fast
semantic search and is kept in sync with the filesystem.

Usage
-----
    # Import a single SKILL.md (and its references/) into skills/
    agent-skill import path/to/playwright-cli/SKILL.md

    # Bulk-import all SKILL.md files under a directory tree
    agent-skill install .claude/skills/

    # Rebuild the vectorstore from existing skills/ on disk
    agent-skill rebuild

    # List all stored skills
    agent-skill list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openai import OpenAI
from qdrant_client import QdrantClient

from .config import (
    EMBED_API_BASE_URL,
    EMBED_API_KEY,
    AGENT_QDRANT_PATH,
)
from .skills import SkillsStore


def _make_store() -> tuple[SkillsStore, QdrantClient]:
    """Initialise an embed client + QdrantClient and return a SkillsStore.

    The caller is responsible for closing the QdrantClient.
    """
    embed_client = OpenAI(base_url=EMBED_API_BASE_URL, api_key=EMBED_API_KEY)
    AGENT_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    qdrant = QdrantClient(path=str(AGENT_QDRANT_PATH))
    store = SkillsStore(client=embed_client, qdrant=qdrant)
    return store, qdrant


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.exists() or not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    store, qdrant = _make_store()
    try:
        name = store.import_from_file(path)
        print(f"Imported skill '{name}' from {path}")
    finally:
        qdrant.close()


def cmd_install(args: argparse.Namespace) -> None:
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    store, qdrant = _make_store()
    try:
        imported = store.install_from_dir(directory)
    finally:
        qdrant.close()

    if imported:
        print(f"Imported {len(imported)} skill(s): {', '.join(imported)}")
    else:
        print("No SKILL.md files found.")


def cmd_rebuild(args: argparse.Namespace) -> None:
    store, qdrant = _make_store()
    try:
        count = store.rebuild_vectorstore()
    finally:
        qdrant.close()

    print(f"Rebuilt vectorstore: {count} skill(s) indexed from skills/.")


def cmd_list(args: argparse.Namespace) -> None:
    store, qdrant = _make_store()
    try:
        names = store.list_skills()
    finally:
        qdrant.close()

    if names:
        for name in sorted(names):
            print(f"  {name}")
        print(f"\n{len(names)} skill(s) total.")
    else:
        print("No skills stored yet.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-skill",
        description="Manage skills in the VS Code agent convention (skills/<name>/SKILL.md).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # import
    p_import = sub.add_parser(
        "import",
        help="Import a single SKILL.md file (and its references/) into skills/.",
    )
    p_import.add_argument("file", help="Path to the SKILL.md file.")

    # install
    p_install = sub.add_parser(
        "install",
        help="Bulk-import all SKILL.md files found under a directory tree.",
    )
    p_install.add_argument(
        "directory",
        help="Root directory to scan recursively for SKILL.md files. "
             "Example: .claude/skills/",
    )

    # rebuild
    sub.add_parser(
        "rebuild",
        help="Rebuild the vectorstore from the on-disk skills/ directory.",
    )

    # list
    sub.add_parser("list", help="List all stored skill names.")

    args = parser.parse_args()
    {
        "import":  cmd_import,
        "install": cmd_install,
        "rebuild": cmd_rebuild,
        "list":    cmd_list,
    }[args.command](args)


if __name__ == "__main__":
    main()
