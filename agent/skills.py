"""
Self-learning skills store — VS Code agent convention.

The agent can persist reusable multi-step workflows discovered during
conversations and retrieve them in future sessions before attempting
similar tasks.  This implements a form of procedural long-term memory,
distinct from the factual long-term memory in mem0.

Storage design — on-disk + vectorstore
---------------------------------------
Skills are stored on disk following the VS Code / GitHub Copilot skill
convention (see https://github.com/microsoft/playwright-cli):

    <workspace>/skills/
      <skill-name>/
        SKILL.md          # Main skill file with YAML frontmatter
        references/       # Optional additional reference documents
          topic-1.md
          topic-2.md

The SKILL.md format uses YAML frontmatter followed by a markdown body::

    ---
    name: my-skill
    description: When to apply this skill
    allowed-tools: Bash(tool:*)   # optional
    ---

    # Title
    Markdown body used as steps.

The on-disk directory is the **source of truth**.  A Qdrant-backed vector
store provides fast semantic search and is kept in sync on every save().
When the vectorstore drifts (e.g. after manual edits to skill files on
disk), the user can rebuild it via ``agent-skill rebuild`` or the
``skills_rebuild`` tool.

Retrieval
---------
A two-stage hybrid lookup is used:

1. Semantic  — embed the query and search trigger-only vectors (top-k+2).
   Catches paraphrases and semantically similar task descriptions.

2. Keyword   — token-set intersection of query words against name+trigger
   from an in-memory index populated at startup and kept in sync on save.
   Catches exact tool/library names and abbreviations that embeddings miss.

Results from both stages are unioned, deduplicated by name, and returned
with semantic hits ranked first.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from .config import Config
from .vectorstore import VectorStore

if TYPE_CHECKING:
    from .tools import ToolEntry


class SkillsStore:
    """Persistent store for agent-learned procedural workflows.

    On-disk ``skills/`` directory is the source of truth.  Qdrant vectorstore
    provides fast semantic search and is kept in sync by :meth:`save`.
    """

    def __init__(self, config: Config, client: AsyncOpenAI, qdrant: AsyncQdrantClient) -> None:
        self._config = config
        self._store = VectorStore(
            client=client,
            qdrant=qdrant,
            collection=config.skills_collection_name,
            embed_model=config.embed_model,
            embed_dims=config.embed_dims,
        )
        self._skills_dir: Path = config.skills_dir
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index for BM25 keyword fallback.
        # Loaded from disk at startup; kept in sync by save().
        self._index: list[dict] = self._load_index_from_disk()

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    def _skill_dir(self, name: str) -> Path:
        """Return the directory for a skill: ``skills/<name>/``."""
        return self._skills_dir / name

    def _skill_file(self, name: str) -> Path:
        """Return the SKILL.md path for a skill."""
        return self._skill_dir(name) / "SKILL.md"

    def _load_index_from_disk(self) -> list[dict]:
        """Scan the ``skills/`` directory tree and build the in-memory index."""
        index: list[dict] = []
        if not self._skills_dir.exists():
            return index
        for skill_md in sorted(self._skills_dir.rglob("SKILL.md")):
            try:
                skill = self.parse_skill_md(skill_md)
                index.append(skill)
            except Exception as exc:
                print(f"[skills] Warning: could not parse {skill_md}: {exc}")
        return index

    @staticmethod
    def _skill_id(name: str) -> str:
        """Deterministic UUID from a skill name so same-name saves overwrite."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

    @staticmethod
    def _format(skills: list[dict]) -> str:
        if not skills:
            return "No matching skill found."
        parts: list[str] = []
        for s in skills:
            block = f"### {s['name']}\n**trigger**: {s['trigger']}\n**steps**:\n{s['steps']}"
            if s.get("notes"):
                block += f"\n**notes**: {s['notes']}"
            refs = s.get("references", [])
            if refs:
                block += "\n**references**: " + ", ".join(refs)
            parts.append(block)
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # SKILL.md parsing / serialization
    # ------------------------------------------------------------------

    @staticmethod
    def parse_skill_md(path: Path) -> dict:
        """Parse a SKILL.md file into a skill dict.

        Supports the YAML-frontmatter markdown convention used by
        playwright-cli and other tools that install skills for coding agents.

        Expected format::

            ---
            name: my-skill
            description: When to apply this skill
            allowed-tools: Bash(tool:*)   # optional
            ---

            # Title
            Markdown body used as steps.

        Returns a dict with keys: name, trigger, steps, notes, references.
        ``references`` is a list of relative paths to reference files
        found in the skill directory.
        """
        text = path.read_text(encoding="utf-8")

        # Strip leading/trailing whitespace and split off frontmatter
        text = text.strip()
        fm: dict[str, str] = {}
        body = text

        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                fm_block = text[3:end].strip()
                body = text[end + 4:].strip()
                for line in fm_block.splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fm[k.strip().lower()] = v.strip()

        name    = fm.get("name", path.parent.name or path.stem)
        trigger = fm.get("description", "")
        notes   = fm.get("allowed-tools", "")

        # Discover reference files under references/ sibling directory
        refs_dir = path.parent / "references"
        references: list[str] = []
        if refs_dir.is_dir():
            references = sorted(
                str(f.relative_to(path.parent))
                for f in refs_dir.rglob("*.md")
            )

        return {
            "name": name,
            "trigger": trigger,
            "steps": body,
            "notes": notes,
            "references": references,
        }

    @staticmethod
    def serialize_skill_md(name: str, trigger: str, steps: str, notes: str = "") -> str:
        """Serialize a skill into the SKILL.md frontmatter format.

        The output is compatible with the convention used by playwright-cli
        and recognised by Claude Code / GitHub Copilot when placed under
        ``skills/<name>/SKILL.md`` or similar paths.
        """
        lines = ["---", f"name: {name}", f"description: {trigger}"]
        if notes:
            lines.append(f"allowed-tools: {notes}")
        lines += ["---", "", steps]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save(self, name: str, trigger: str, steps: str, notes: str = "") -> None:
        """Persist a skill to both disk and vectorstore simultaneously.

        Creates/updates ``skills/<name>/SKILL.md`` on disk and upserts
        the corresponding vector into the Qdrant collection.
        """
        # 1. Write SKILL.md to disk
        skill_dir = self._skill_dir(name)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            self.serialize_skill_md(name, trigger, steps, notes),
            encoding="utf-8",
        )

        # 2. Discover references already present on disk
        refs_dir = skill_dir / "references"
        references: list[str] = []
        if refs_dir.is_dir():
            references = sorted(
                str(f.relative_to(skill_dir))
                for f in refs_dir.rglob("*.md")
            )

        payload = {
            "name": name,
            "trigger": trigger,
            "steps": steps,
            "notes": notes,
            "references": references,
        }

        # 3. Delete old entry (if any) then insert fresh vector
        skill_id = self._skill_id(name)
        await self._store.delete_by_id(skill_id)
        vector = (await self._store.embed([f"{name}: {trigger}"]))[0]
        await self._store.upsert_records(
            [{"id": skill_id, "vector": vector, "payload": payload}],
            batch_size=1,
        )

        # 4. Keep in-memory index in sync
        for entry in self._index:
            if entry["name"] == name:
                entry.update(payload)
                return
        self._index.append(dict(payload))

    async def rebuild_vectorstore(self) -> int:
        """Rebuild the vectorstore from the ``skills/`` directory on disk.

        Clears the existing vectorstore collection and re-indexes all
        SKILL.md files found under the skills directory.  Also refreshes the
        in-memory keyword index.

        Returns the number of skills indexed.
        """
        # Reload from disk
        self._index = self._load_index_from_disk()

        # Clear and rebuild
        await self._store.clear_collection()

        if not self._index:
            return 0

        # Embed all skills and upsert in one batch
        texts = [f"{s['name']}: {s['trigger']}" for s in self._index]
        vectors = await self._store.embed_batched(texts, batch_size=32, progress=True)

        records = [
            {
                "id": self._skill_id(skill["name"]),
                "vector": vec,
                "payload": skill,
            }
            for skill, vec in zip(self._index, vectors)
        ]
        await self._store.upsert_records(records, batch_size=64)
        return len(records)

    async def lookup(self, query: str, top_k: int | None = None) -> list[dict]:
        """Hybrid lookup: semantic union keyword, semantic hits ranked first."""
        if top_k is None:
            top_k = self._config.skills_search_top_k
        results: list[dict] = []
        seen: set[str] = set()

        # Stage 1 — semantic search over trigger-space vectors
        for hit in await self._store.search(query, top_k=top_k + 2):
            name = hit["payload"].get("name", "")
            if name and name not in seen:
                seen.add(name)
                results.append(hit["payload"])

        # Stage 2 — keyword: token-set intersection on name + trigger
        query_tokens = set(query.lower().split())
        for entry in self._index:
            if entry["name"] in seen:
                continue
            candidate_tokens = set(
                (entry["name"] + " " + entry["trigger"]).lower().split()
            )
            if query_tokens & candidate_tokens:
                seen.add(entry["name"])
                results.append(entry)

        return results[:top_k]

    def read_reference(self, skill_name: str, ref_path: str) -> str:
        """Read the content of a reference file for a skill.

        Args:
            skill_name: The skill name (directory name under ``skills/``).
            ref_path: Relative path to the reference file within the skill dir.

        Returns:
            The content of the reference file, or an error message.
        """
        target = (self._skill_dir(skill_name) / ref_path).resolve()
        skill_root = self._skill_dir(skill_name).resolve()

        # Security: ensure the resolved path stays inside the skill directory
        if not str(target).startswith(str(skill_root)):
            return f"Error: path '{ref_path}' escapes the skill directory."

        if not target.is_file():
            return f"Error: reference file not found: {ref_path}"

        try:
            return target.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error reading {ref_path}: {exc}"

    async def import_from_file(self, path: Path) -> str:
        """Import a single SKILL.md (and its sibling ``references/``) into
        the skills store.

        The skill directory structure is copied to ``skills/<name>/``.
        Returns the name of the imported skill.
        """
        skill = self.parse_skill_md(path)
        name = skill["name"]

        src_dir = path.parent
        dst_dir = self._skill_dir(name)
        dst_dir.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        shutil.copy2(path, dst_dir / "SKILL.md")

        # Copy references/ if present
        src_refs = src_dir / "references"
        if src_refs.is_dir():
            dst_refs = dst_dir / "references"
            if dst_refs.exists():
                shutil.rmtree(dst_refs)
            shutil.copytree(src_refs, dst_refs)

        # Write vectorstore + refresh in-memory index
        await self.save(skill["name"], skill["trigger"], skill["steps"], skill["notes"])
        return name

    async def install_from_dir(self, directory: Path) -> list[str]:
        """Recursively import every SKILL.md found under *directory*.

        Copies each skill's directory into the ``skills/`` folder and
        indexes it into the vectorstore.

        Returns the list of skill names that were imported.
        """
        imported: list[str] = []
        for skill_file in sorted(directory.rglob("SKILL.md")):
            try:
                name = await self.import_from_file(skill_file)
                imported.append(name)
            except Exception as exc:
                print(f"[skills] Warning: could not import {skill_file}: {exc}")
        return imported

    def list_skills(self) -> list[str]:
        """Return the names of all skills found on disk."""
        return [e["name"] for e in self._index]

    # ------------------------------------------------------------------
    # Tool entries
    # ------------------------------------------------------------------

    def get_tools(self) -> list[ToolEntry]:
        """Return skill tool entries for registration with the Tools registry."""

        async def _lookup_tool(p: dict) -> str:
            return self._format(await self.lookup(p["query"]))

        async def _save_tool(p: dict) -> str:
            await self.save(p["name"], p["trigger"], p["steps"], p.get("notes", ""))
            return f"Skill '{p['name']}' saved to skills/{p['name']}/SKILL.md and vectorstore."

        return [
            (
                {
                    "name": "skills_lookup",
                    "description": (
                        "Search your skills notebook for a learned workflow that matches the current task. "
                        "Call this BEFORE attempting any multi-step task — if a matching skill exists, "
                        "follow its steps rather than re-deriving the procedure from scratch. "
                        "Uses both semantic similarity and keyword matching on skill names and trigger descriptions. "
                        "Returns up to 3 matching skills with their step-by-step procedures and notes. "
                        "If a returned skill lists references, you can read them with skills_read_reference."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "A natural-language description of the task you are about to perform. "
                                    "Be specific about what you want to accomplish. "
                                    "Examples: 'summarize a webpage from a URL', "
                                    "'debug a Python import error', "
                                    "'fetch JSON from a REST API and parse the result'."
                                ),
                            }
                        },
                        "required": ["query"],
                    },
                },
                _lookup_tool,
            ),
            (
                {
                    "name": "skills_save",
                    "description": (
                        "Save a reusable workflow to your skills notebook after successfully completing "
                        "a non-trivial multi-step task that required tool usage, trial-and-error, or "
                        "non-obvious sequencing. Write it clearly enough that your future self can follow "
                        "it without rediscovering the steps. "
                        "The skill is written to skills/<name>/SKILL.md on disk AND indexed into the "
                        "vectorstore simultaneously. "
                        "Saving a skill with an existing name overwrites the previous entry — use this "
                        "to refine a skill after discovering a better approach."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": (
                                    "Short, unique snake_case identifier for this skill. "
                                    "Examples: 'scrape_and_summarize', 'debug_python_traceback', "
                                    "'fetch_json_api', 'patch_file_safely'."
                                ),
                            },
                            "trigger": {
                                "type": "string",
                                "description": (
                                    "A concise description of WHEN to apply this skill — "
                                    "the task type or user request that should activate it. "
                                    "Examples: 'user asks to summarize a webpage by URL', "
                                    "'user reports a Python error with a traceback', "
                                    "'need to call a REST API and parse the JSON response'."
                                ),
                            },
                            "steps": {
                                "type": "string",
                                "description": (
                                    "Numbered step-by-step procedure. Include the specific tool calls "
                                    "used at each step, key parameters, and any intermediate checks. "
                                    "Example:\n"
                                    "1. run_shell('curl -s <url>') to fetch raw HTML\n"
                                    "2. run_python to strip tags with BeautifulSoup\n"
                                    "3. Summarize the cleaned text in ≤200 words"
                                ),
                            },
                            "notes": {
                                "type": "string",
                                "description": (
                                    "Optional. Edge cases, known failure modes, and workarounds discovered "
                                    "during execution. Examples: 'If curl returns 403, retry with -A Mozilla/5.0', "
                                    "'BeautifulSoup may need html.parser if lxml is not installed'."
                                ),
                            },
                        },
                        "required": ["name", "trigger", "steps"],
                    },
                },
                _save_tool,
            ),
            (
                {
                    "name": "skills_read_reference",
                    "description": (
                        "Read the contents of a reference file belonging to a skill. "
                        "Use this after skills_lookup returns a skill that lists reference files. "
                        "References contain detailed documentation on specific sub-topics."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "The skill name (directory name under skills/).",
                            },
                            "ref_path": {
                                "type": "string",
                                "description": (
                                    "Relative path to the reference file within the skill directory. "
                                    "Example: 'references/request-mocking.md'."
                                ),
                            },
                        },
                        "required": ["skill_name", "ref_path"],
                    },
                },
                lambda p: self.read_reference(p["skill_name"], p["ref_path"]),
            ),
        ]
