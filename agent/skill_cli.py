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
import asyncio
import sys
from pathlib import Path

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from .config import Config
from .skills import SkillsStore


def _make_store(config: Config) -> tuple[SkillsStore, AsyncQdrantClient]:
    """Initialise an embed client + AsyncQdrantClient and return a SkillsStore.

    The caller is responsible for closing the AsyncQdrantClient.
    """
    embed_client = AsyncOpenAI(base_url=config.embed_api_base_url, api_key=config.embed_api_key)
    config.agent_qdrant_path.mkdir(parents=True, exist_ok=True)
    qdrant = AsyncQdrantClient(path=str(config.agent_qdrant_path))
    store = SkillsStore(config=config, client=embed_client, qdrant=qdrant)
    return store, qdrant


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_import(args: argparse.Namespace, config: Config) -> None:
    path = Path(args.file)
    if not path.exists() or not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    async def _run() -> None:
        store, qdrant = _make_store(config)
        try:
            name = await store.import_from_file(path)
            print(f"Imported skill '{name}' from {path}")
        finally:
            await qdrant.close()

    asyncio.run(_run())


def cmd_install(args: argparse.Namespace, config: Config) -> None:
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    async def _run() -> list[str]:
        store, qdrant = _make_store(config)
        try:
            return await store.install_from_dir(directory)
        finally:
            await qdrant.close()

    imported = asyncio.run(_run())

    if imported:
        print(f"Imported {len(imported)} skill(s): {', '.join(imported)}")
    else:
        print("No SKILL.md files found.")


def cmd_rebuild(args: argparse.Namespace, config: Config) -> None:
    async def _run() -> int:
        store, qdrant = _make_store(config)
        try:
            return await store.rebuild_vectorstore()
        finally:
            await qdrant.close()

    count = asyncio.run(_run())
    print(f"Rebuilt vectorstore: {count} skill(s) indexed from skills/.")


def cmd_list(args: argparse.Namespace, config: Config) -> None:
    async def _run() -> list[str]:
        store, qdrant = _make_store(config)
        try:
            return store.list_skills()
        finally:
            await qdrant.close()

    names = asyncio.run(_run())

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
    config = Config.from_yaml()

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
    }[args.command](args, config)


if __name__ == "__main__":
    main()
