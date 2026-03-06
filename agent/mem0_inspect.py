#!/usr/bin/env python3
"""
Interactive CLI to inspect the agent's mem0 memory store.

Usage:
    agent-mem0-inspect          # interactive mode
    agent-mem0-inspect list     # dump all memories in every fraction
    agent-mem0-inspect search <query> [--fraction all|core_archive|episodic]
    agent-mem0-inspect count    # show entry counts per fraction
    agent-mem0-inspect get <id> # show a single memory by UUID
    agent-mem0-inspect delete <id>  # delete a single memory by UUID

Requires the same environment variables as the agent (AGENT_API_KEY etc.).
"""

from __future__ import annotations

import argparse
import sys
import json
from datetime import datetime

from .config import Config


# ── helpers ────────────────────────────────────────────────────────────
def _init_mem(config: Config):
    """Lazy-init mem0 so import-time errors surface clearly."""
    from mem0 import Memory
    return Memory.from_config(config.mem0_config)


def _fraction_ids(user_id: str) -> dict[str, str]:
    return {
        "core_archive": f"{user_id}_core_archive",
        "episodic":     f"{user_id}_episodic",
    }


def _fmt_memory(item: dict, *, verbose: bool = False) -> str:
    """Pretty-format a single memory item."""
    lines = []
    lines.append(f"  id:      {item.get('id', '?')}")
    lines.append(f"  memory:  {item.get('memory', '')}")
    if item.get("score") is not None:
        lines.append(f"  score:   {item['score']:.4f}")
    if item.get("created_at"):
        lines.append(f"  created: {item['created_at']}")
    if item.get("updated_at"):
        lines.append(f"  updated: {item['updated_at']}")
    if verbose:
        extra = {k: v for k, v in item.items()
                 if k not in ("id", "memory", "score", "created_at", "updated_at", "hash")}
        if extra:
            lines.append(f"  meta:    {json.dumps(extra, ensure_ascii=False)}")
    return "\n".join(lines)


# ── commands ───────────────────────────────────────────────────────────
def cmd_list(mem, fractions: dict[str, str], *, verbose: bool = False) -> None:
    for label, ns in fractions.items():
        result = mem.get_all(user_id=ns)
        entries = result.get("results", [])
        print(f"\n═══ {label} ({len(entries)} entries) ═══")
        if not entries:
            print("  (empty)")
        for i, item in enumerate(entries, 1):
            print(f"\n [{i}]")
            print(_fmt_memory(item, verbose=verbose))


def cmd_count(mem, fractions: dict[str, str]) -> None:
    print()
    for label, ns in fractions.items():
        result = mem.get_all(user_id=ns)
        n = len(result.get("results", []))
        print(f"  {label:20s}  {n} entries")
    print()


def cmd_search(mem, fractions: dict[str, str], query: str, fraction: str = "all",
               *, verbose: bool = False) -> None:
    if fraction == "all":
        namespaces = list(fractions.items())
    elif fraction in fractions:
        namespaces = [(fraction, fractions[fraction])]
    else:
        print(f"Unknown fraction '{fraction}'. Choose from: all, {', '.join(fractions)}")
        return

    for label, ns in namespaces:
        result = mem.search(query, user_id=ns)
        entries = result.get("results", [])
        print(f"\n═══ {label} — {len(entries)} results for '{query}' ═══")
        if not entries:
            print("  (no matches)")
        for i, item in enumerate(entries, 1):
            print(f"\n [{i}]")
            print(_fmt_memory(item, verbose=verbose))


def cmd_get(mem, mem_id: str) -> None:
    try:
        item = mem.get(mem_id)
        print()
        print(_fmt_memory(item, verbose=True))
    except Exception as exc:
        print(f"Error retrieving {mem_id}: {exc}")


def cmd_delete(mem, mem_id: str) -> None:
    confirm = input(f"Delete memory {mem_id}? [y/N] ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    try:
        mem.delete(mem_id)
        print(f"Deleted {mem_id}.")
    except Exception as exc:
        print(f"Error deleting {mem_id}: {exc}")


def cmd_interactive(mem, fractions: dict[str, str]) -> None:
    """Drop into an interactive REPL for exploring the store."""
    print("mem0 inspector — type 'help' for commands, 'quit' to exit.\n")
    while True:
        try:
            line = input("mem0> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break
        elif cmd == "help":
            print("""
Commands:
  list   [--verbose]                      List all memories
  count                                   Count entries per fraction
  search <query> [--fraction F] [--verbose]  Semantic search
  get    <id>                             Show single memory by UUID
  delete <id>                             Delete single memory by UUID
  raw    <fraction>                       Dump raw JSON for a fraction
  quit                                    Exit
""")
        elif cmd == "list":
            verbose = "--verbose" in line or "-v" in parts
            cmd_list(mem, fractions, verbose=verbose)
        elif cmd == "count":
            cmd_count(mem, fractions)
        elif cmd == "search":
            if len(parts) < 2:
                print("Usage: search <query> [--fraction all|core_archive|episodic]")
                continue
            fraction = "all"
            verbose = False
            # Parse flags from the rest of the line
            rest = line[len("search"):].strip()
            tokens = rest.split()
            query_parts = []
            i = 0
            while i < len(tokens):
                if tokens[i] == "--fraction" and i + 1 < len(tokens):
                    fraction = tokens[i + 1]
                    i += 2
                elif tokens[i] in ("--verbose", "-v"):
                    verbose = True
                    i += 1
                else:
                    query_parts.append(tokens[i])
                    i += 1
            query = " ".join(query_parts)
            if not query:
                print("Usage: search <query> [--fraction all|core_archive|episodic]")
                continue
            cmd_search(mem, fractions, query, fraction, verbose=verbose)
        elif cmd == "get":
            if len(parts) < 2:
                print("Usage: get <id>")
                continue
            cmd_get(mem, parts[1])
        elif cmd == "delete":
            if len(parts) < 2:
                print("Usage: delete <id>")
                continue
            cmd_delete(mem, parts[1])
        elif cmd == "raw":
            fraction = parts[1] if len(parts) > 1 else None
            if fraction not in fractions:
                print(f"Usage: raw <{'|'.join(fractions)}>")
                continue
            result = mem.get_all(user_id=fractions[fraction])
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"Unknown command: {cmd}. Type 'help' for usage.")


# ── main ───────────────────────────────────────────────────────────────
def main() -> None:
    config = Config.from_yaml()

    parser = argparse.ArgumentParser(
        description="Inspect the agent's mem0 long-term memory store.",
    )
    parser.add_argument("--user", default=config.user_id, help=f"User ID (default: {config.user_id})")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show extra metadata")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list",  help="Dump all memories")
    sub.add_parser("count", help="Show entry counts per fraction")

    p_search = sub.add_parser("search", help="Semantic search")
    p_search.add_argument("query", nargs="+")
    p_search.add_argument("--fraction", default="all",
                          choices=["all", "core_archive", "episodic"])

    p_get = sub.add_parser("get", help="Show one memory by UUID")
    p_get.add_argument("id")

    p_del = sub.add_parser("delete", help="Delete one memory by UUID")
    p_del.add_argument("id")

    args = parser.parse_args()
    fracs = _fraction_ids(args.user)

    print(f"Connecting to mem0 store (user={args.user})...")
    mem = _init_mem(config)

    if args.command is None:
        cmd_interactive(mem, fracs)
    elif args.command == "list":
        cmd_list(mem, fracs, verbose=args.verbose)
    elif args.command == "count":
        cmd_count(mem, fracs)
    elif args.command == "search":
        cmd_search(mem, fracs, " ".join(args.query), args.fraction, verbose=args.verbose)
    elif args.command == "get":
        cmd_get(mem, args.id)
    elif args.command == "delete":
        cmd_delete(mem, args.id)


if __name__ == "__main__":
    main()
