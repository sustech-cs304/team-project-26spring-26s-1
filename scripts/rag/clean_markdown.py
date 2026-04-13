from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path

from agent.config import config as app_config
from scripts.rag.paths import get_rag_paths

MARKDOWN_SUFFIXES = {".md", ".markdown", ".txt"}


@dataclass(slots=True)
class CleanStats:
    files_seen: int = 0
    files_written: int = 0
    lines_in: int = 0
    lines_out: int = 0
    removed_toc_lines: int = 0
    removed_noise_lines: int = 0
    removed_duplicate_lines: int = 0
    normalized_math_lines: int = 0
    table_blocks_seen: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清洗 Markdown 文档，使其更适合 RAG 切分与检索")
    parser.add_argument("--input-file", type=Path, default=None, help="单个 Markdown/TXT 文件")
    parser.add_argument("--input-dir", type=Path, default=None, help="输入目录")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录")
    parser.add_argument("--suffix", type=str, default=".cleaned.md", help="输出文件后缀，默认 .cleaned.md")
    parser.add_argument(
        "--heading-priority",
        type=str,
        default="1,2,3,4,5,6",
        help="标题优先级映射，逗号分隔（如 1,2,3,4,5,6）",
    )
    return parser.parse_args()


def parse_heading_priority(raw: str) -> list[int]:
    levels: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            level = int(part)
        except ValueError:
            continue
        if 1 <= level <= 6 and level not in levels:
            levels.append(level)
    return levels or [1, 2, 3, 4, 5, 6]


def resolve_paths(args: argparse.Namespace) -> tuple[list[Path], Path]:
    rag_paths = get_rag_paths(app_config)

    if args.input_file is not None:
        input_file = args.input_file
        output_dir = args.output_dir or rag_paths.cleaned_dir
        return [input_file], output_dir

    input_dir = args.input_dir or rag_paths.raw_dir

    output_dir = args.output_dir or rag_paths.cleaned_dir

    files = sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in MARKDOWN_SUFFIXES)
    return files, output_dir


def normalize_inline_math(text: str) -> tuple[str, bool]:
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        expr = match.group(1)
        compact = re.sub(r"(?<=\d)\s+(?=\d)", "", expr)
        compact = compact.replace(r"\geqslant", "≥").replace(r"\leqslant", "≤")
        if compact != expr:
            changed = True
        return compact

    normalized = re.sub(r"\$(.*?)\$", lambda m: f"${repl(m)}$", text)
    return normalized, changed


def should_drop_noise_line(stripped: str) -> bool:
    if not stripped:
        return False
    if re.fullmatch(r"#?\s*\d{1,4}\s*", stripped):
        return True
    if re.fullmatch(r"[·.•\-_=]{4,}", stripped):
        return True
    if stripped.lower() in {"page", "目录", "contents"}:
        return True
    if re.search(r"^page\s*\d+\s*(/|of)\s*\d+$", stripped.lower()):
        return True
    return False


def _parse_html_table_row(row_html: str) -> list[str]:
    cells = re.findall(r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", row_html, flags=re.IGNORECASE | re.DOTALL)
    parsed = []
    for cell in cells:
        text = re.sub(r"<[^>]+>", "", cell)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        parsed.append(text)
    return parsed


def html_table_to_markdown(table_html: str) -> str:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    parsed_rows = [_parse_html_table_row(row) for row in rows]
    parsed_rows = [row for row in parsed_rows if row]
    if not parsed_rows:
        return table_html

    max_cols = max(len(row) for row in parsed_rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in parsed_rows]

    header = normalized_rows[0]
    divider = ["---"] * max_cols
    body = normalized_rows[1:] if len(normalized_rows) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(divider) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def convert_html_tables(text: str, stats: CleanStats) -> str:
    table_pattern = re.compile(r"<table[^>]*>.*?</table>", flags=re.IGNORECASE | re.DOTALL)

    def _replace(match: re.Match[str]) -> str:
        stats.table_blocks_seen += 1
        html = match.group(0)
        md = html_table_to_markdown(html)
        if md == html:
            return f"\n<!-- table-convert-failed -->\n{html}\n"
        return f"\n{md}\n"

    return table_pattern.sub(_replace, text)


def normalize_heading_levels(lines: list[str], priority: list[int]) -> list[str]:
    normalized: list[str] = []
    prev_level = 0

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            normalized.append(line)
            continue

        match = re.match(r"^(#{1,6})\s*(.*)$", stripped)
        if not match:
            normalized.append(line)
            continue

        raw_level = len(match.group(1))
        title = match.group(2).strip()

        if raw_level in priority:
            target_level = priority.index(raw_level) + 1
        else:
            nearest = min(priority, key=lambda p: abs(p - raw_level))
            target_level = priority.index(nearest) + 1

        if prev_level and target_level > prev_level + 1:
            target_level = prev_level + 1
        prev_level = target_level
        normalized.append(f"{'#' * target_level} {title}")

    return normalized


def strip_toc_and_noise(lines: list[str], stats: CleanStats) -> list[str]:
    result: list[str] = []
    in_toc = False
    toc_line_pattern = re.compile(r"^[^#\n]{2,}([·.•\s]{2,}|\s{2,})\d+\s*$")

    for line in lines:
        stripped = line.strip()
        if stripped in {"# 目录", "# 目 录"}:
            in_toc = True
            stats.removed_toc_lines += 1
            continue

        if in_toc:
            if stripped.startswith("#") and "目录" not in stripped:
                in_toc = False
            elif not stripped or toc_line_pattern.match(stripped) or re.search(r"\d+\s*$", stripped):
                stats.removed_toc_lines += 1
                continue

        if should_drop_noise_line(stripped):
            stats.removed_noise_lines += 1
            continue

        if "\f" in line:
            line = line.replace("\f", "")
            stats.removed_noise_lines += 1

        line = re.sub(r"[ \t]+$", "", line)
        result.append(line)

    return result


def deduplicate_and_normalize(lines: list[str], stats: CleanStats) -> list[str]:
    result: list[str] = []
    prev_nonempty = ""
    blank_run = 0

    for raw_line in lines:
        line = raw_line.replace("\u3000", " ")
        normalized_math, changed = normalize_inline_math(line)
        if changed:
            stats.normalized_math_lines += 1
        line = normalized_math

        stripped = line.strip()
        if not stripped:
            blank_run += 1
            if blank_run > 1:
                continue
            result.append("")
            continue

        blank_run = 0
        dedup_key = re.sub(r"\s+", " ", stripped)
        if dedup_key == prev_nonempty and len(dedup_key) <= 120:
            stats.removed_duplicate_lines += 1
            continue

        result.append(line)
        prev_nonempty = dedup_key

    while result and not result[-1].strip():
        result.pop()
    return result


def insert_context_before_table(lines: list[str]) -> list[str]:
    result: list[str] = []
    recent_heading = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            recent_heading = stripped.lstrip("#").strip()

        if stripped.startswith("|") and "---" in stripped:
            previous = result[-1].strip() if result else ""
            marker = f"表格主题：{recent_heading}" if recent_heading else ""
            if marker and previous != marker:
                if previous:
                    result.append("")
                result.append(marker)

        result.append(line)
    return result


def clean_markdown_text(text: str, stats: CleanStats, heading_priority: list[int] | None = None) -> str:
    heading_priority = heading_priority or [1, 2, 3, 4, 5, 6]

    text = convert_html_tables(text, stats)
    lines = text.splitlines()
    stats.lines_in += len(lines)

    lines = strip_toc_and_noise(lines, stats)
    lines = deduplicate_and_normalize(lines, stats)
    lines = normalize_heading_levels(lines, heading_priority)
    lines = insert_context_before_table(lines)

    cleaned = "\n".join(lines).strip() + "\n"
    stats.lines_out += len(cleaned.splitlines())
    return cleaned


def build_output_path(source_path: Path, output_dir: Path, suffix: str) -> Path:
    if source_path.suffix.lower() in MARKDOWN_SUFFIXES:
        out_name = source_path.name[: -len(source_path.suffix)] + suffix
    else:
        out_name = source_path.name + suffix
    return output_dir / out_name


def process_file(
    source_path: Path,
    output_dir: Path,
    suffix: str,
    stats: CleanStats,
    heading_priority: list[int] | None = None,
) -> Path:
    stats.files_seen += 1
    text = source_path.read_text(encoding="utf-8")
    cleaned = clean_markdown_text(text, stats, heading_priority=heading_priority)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_output_path(source_path, output_dir, suffix)
    output_path.write_text(cleaned, encoding="utf-8")
    stats.files_written += 1
    print(f"[完成] {source_path.name} -> {output_path}")
    return output_path


def print_summary(stats: CleanStats, output_dir: Path) -> None:
    print("\n===== 清洗汇总 =====")
    print(f"输出目录: {output_dir}")
    print(f"处理文件数: {stats.files_seen}")
    print(f"成功写出数: {stats.files_written}")
    print(f"输入总行数: {stats.lines_in}")
    print(f"输出总行数: {stats.lines_out}")
    print(f"删除目录行数: {stats.removed_toc_lines}")
    print(f"删除噪声行数: {stats.removed_noise_lines}")
    print(f"删除重复行数: {stats.removed_duplicate_lines}")
    print(f"规范数学表达行数: {stats.normalized_math_lines}")
    print(f"识别表格块数: {stats.table_blocks_seen}")


def main() -> None:
    args = parse_args()
    files, output_dir = resolve_paths(args)
    if not files:
        print("[完成] 未找到可清洗的 Markdown/TXT 文件")
        return

    heading_priority = parse_heading_priority(args.heading_priority)
    stats = CleanStats()
    for source_path in files:
        process_file(
            source_path=source_path,
            output_dir=output_dir,
            suffix=args.suffix,
            stats=stats,
            heading_priority=heading_priority,
        )

    print_summary(stats, output_dir)


if __name__ == "__main__":
    main()
