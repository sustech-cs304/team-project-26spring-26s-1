"""RAG 检索工具。

该模块负责：
1. 解析查询意图与专业名提示；
2. 执行标题召回、表格召回、词法召回与向量召回；
3. 对多路候选进行融合排序；
4. 返回适合 agent 阅读的带分数结果。
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain.tools import ToolRuntime, tool

from .embedding_store import NAMESPACE, build_indexed_store
from agent.config import load_config


@dataclass
class RankedResult:
    key: str
    value: dict[str, Any]
    score: float
    semantic_score: float
    lexical_score: float


@dataclass(slots=True)
class QueryAnalysis:
    normalized_query: str
    terms: list[str]
    intent_terms: list[str]
    program_hint: str
    document_hint: str


@dataclass(slots=True)
class RecallCandidate:
    key: str
    value: dict[str, Any]
    score: float
    channel: str


@dataclass(slots=True)
class CorpusChunk:
    key: str
    value: dict[str, Any]
    text: str
    retrieval_text: str
    title_path: str
    source_file: str
    chunk_index: Any


@dataclass(slots=True)
class CandidateFeatures:
    key: str
    value: dict[str, Any]
    semantic_score: float
    lexical_score: float
    title_score: float
    table_score: float
    text: str
    title_path: str
    retrieval_text: str
    source_file: str
    block_type: str
    document_type: str
    section_type: str
    metadata_term_hits: int
    program_hint_hit: bool
    exactness: float


_CORPUS_CACHE: dict[int, tuple[int, list[CorpusChunk]]] = {}
TITLE_BLOCK_TYPES = {"program_title", "faculty_title", "section_heading", "subsection_heading"}
TABLE_BLOCK_TYPES = {"curriculum_table", "teaching_plan_table", "table"}
HANDBOOK_KEYWORDS = {
    "学生手册",
    "学籍",
    "注册",
    "考试",
    "成绩",
    "补考",
    "重修",
    "请假",
    "休学",
    "复学",
    "退学",
    "毕业",
    "结业",
    "学位",
    "处分",
    "违纪",
    "作弊",
    "申诉",
    "宿舍",
    "公寓",
    "资助",
    "奖学金",
    "勤工助学",
    "社团",
    "党团",
    "入伍",
    "转专业",
    "转学",
}
PROGRAM_KEYWORDS = {
    "培养方案",
    "培养目标",
    "培养要求",
    "专业介绍",
    "课程结构图",
    "教学安排一览表",
    "专业课程",
    "专业本科",
    "学分结构",
}


def _get_metadata(value: dict[str, Any]) -> dict[str, Any]:
    metadata = value.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _dict_get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _build_embed_namespace(embed_dict: dict[str, Any] | None) -> Any:
    if not isinstance(embed_dict, dict) or not embed_dict:
        return None
    model = embed_dict.get("model")
    api_key = embed_dict.get("api_key")
    base_url = embed_dict.get("base_url")
    if not (model and api_key and base_url):
        return None
    return SimpleNamespace(
        model=model,
        api_key=api_key,
        base_url=base_url,
        dims=embed_dict.get("dims"),
    )


def _extract_embed_from_candidate(candidate: Any) -> Any:
    if candidate is None:
        return None

    # Object shape: config.api.embed
    api_obj = getattr(candidate, "api", None)
    if api_obj is not None:
        embed_obj = getattr(api_obj, "embed", None)
        if embed_obj is not None:
            return embed_obj

    # Dict-like shapes used by RunnableConfig and web runtimes
    if isinstance(candidate, dict):
        for path in (
            ("api", "embed"),
            ("configurable", "api", "embed"),
            ("configurable", "config", "api", "embed"),
            ("__agent_config", "api", "embed"),
            ("configurable", "__agent_config", "api", "embed"),
            ("configurable", "app_config", "api", "embed"),
        ):
            embed_ns = _build_embed_namespace(_dict_get_path(candidate, path))
            if embed_ns is not None:
                return embed_ns

    return None


def _resolve_embedding_config(runtime: ToolRuntime) -> Any:
    """Resolve embedding config from runtime or default config, supporting both object and dict shapes."""
    runtime_config = getattr(runtime, "config", None)
    embed = _extract_embed_from_candidate(runtime_config)
    if embed is not None:
        return embed

    runtime_context = getattr(runtime, "context", None)
    embed = _extract_embed_from_candidate(runtime_context)
    if embed is not None:
        return embed

    # Fallback 1: default loader (depends on process cwd)
    try:
        app_config = load_config()
        embed = _extract_embed_from_candidate(app_config)
        if embed is not None:
            return embed
    except Exception:
        pass

    # Fallback 2: repository-local config path
    repo_config_path = Path("config.yaml")
    try:
        app_config = load_config(str(repo_config_path))
        embed = _extract_embed_from_candidate(app_config)
        if embed is not None:
            return embed
    except Exception:
        pass

    raise ValueError(
        "Embedding config not found. Checked runtime.config/context and config.yaml in cwd/repository root."
    )


def _normalize_query_text(query: str) -> str:
    text = query.strip().lower()
    text = re.sub(r"[\s\u3000]+", "", text)
    text = re.sub(r"[，。！？、；：,.!?;:()（）【】\[\]<>《》\"'“”‘’]", "", text)
    stop_phrases = [
        "请教一下",
        "请问",
        "什么",
        "哪些",
        "如何",
        "怎么",
        "是否",
        "可能",
        "可以",
        "需要",
        "想要",
        "有关",
        "关于",
        "相关方面",
        "相关",
    ]
    stop_chars = ["的", "了", "和", "与", "及", "是", "吗", "呢", "吧", "啊", "呀", "哦", "嘛"]
    for phrase in stop_phrases:
        text = text.replace(phrase, "")
    for ch in stop_chars:
        text = text.replace(ch, "")
    return text


def _extract_terms_from_cjk_sequence(sequence: str) -> list[str]:
    if len(sequence) <= 2:
        return [sequence]

    max_n = min(5, len(sequence))
    terms: list[str] = []
    for n in range(max_n, 1, -1):
        for start in range(0, len(sequence) - n + 1):
            term = sequence[start : start + n]
            if term and term not in terms:
                terms.append(term)
    return terms


def _extract_program_hint(normalized_query: str) -> str:
    """从标准化后的查询中提取专业名提示。"""
    for suffix in (
        "本科人才培养方案",
        "培养方案",
        "专业课程结构图",
        "课程结构图",
        "专业教学安排一览表",
        "教学安排一览表",
        "专业培养目标",
        "培养目标",
        "专业培养要求",
        "培养要求",
        "专业介绍",
    ):
        if suffix in normalized_query:
            candidate = normalized_query.split(suffix, 1)[0]
            if candidate:
                return candidate

    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9]{2,20}?专业)", normalized_query)
    if match:
        candidate = match.group(1)
        if candidate not in {"转专业"}:
            return candidate
    return ""


def _detect_document_hint(normalized_query: str, program_hint: str) -> str:
    if not normalized_query:
        return ""

    program_hits = sum(1 for term in PROGRAM_KEYWORDS if term in normalized_query)
    handbook_hits = sum(1 for term in HANDBOOK_KEYWORDS if term in normalized_query)

    if program_hint:
        program_hits += 2

    if program_hits > 0 and handbook_hits > 0:
        return ""
    if program_hits > handbook_hits:
        return "培养方案"
    if handbook_hits > program_hits:
        return "学生手册"
    return ""


def _analyze_query(query: str, max_terms: int = 30) -> QueryAnalysis:
    normalized_query = _normalize_query_text(query)
    if not normalized_query:
        return QueryAnalysis(normalized_query="", terms=[], intent_terms=[], program_hint="", document_hint="")

    intent_terms = [
        term
        for term in ("流程", "步骤", "条件", "标准", "办法", "规定", "要求", "资格", "程序", "申请", "评选", "名单")
        if term in normalized_query
    ]

    terms: list[str] = []
    for token in re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]+", normalized_query):
        if re.fullmatch(r"[a-z0-9_]{2,}", token):
            if token not in terms:
                terms.append(token)
        else:
            for extracted in _extract_terms_from_cjk_sequence(token):
                if extracted not in terms:
                    terms.append(extracted)
                if len(terms) >= max_terms:
                    break
        if len(terms) >= max_terms:
            break

    for intent_term in intent_terms:
        if intent_term not in terms:
            terms.insert(0, intent_term)

    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
        if len(deduped) >= max_terms:
            break

    program_hint = _extract_program_hint(normalized_query)
    document_hint = _detect_document_hint(normalized_query, program_hint)

    return QueryAnalysis(
        normalized_query=normalized_query,
        terms=deduped,
        intent_terms=intent_terms,
        program_hint=program_hint,
        document_hint=document_hint,
    )


def _to_text(payload_value: Any) -> str:
    if isinstance(payload_value, bytes):
        try:
            return payload_value.decode("utf-8")
        except UnicodeDecodeError:
            return payload_value.decode("utf-8", errors="ignore")
    if isinstance(payload_value, str):
        return payload_value
    return ""


def _normalize_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    if not raw_scores:
        return {}
    values = list(raw_scores.values())
    score_min = min(values)
    score_max = max(values)
    if score_max == score_min:
        return {k: 1.0 for k in raw_scores}
    return {k: (v - score_min) / (score_max - score_min) for k, v in raw_scores.items()}


def _normalize_for_match(text: str) -> str:
    return _normalize_query_text(text)


def _infer_block_type_from_value(value: dict[str, Any]) -> str:
    metadata = _get_metadata(value)
    block_type = str(metadata.get("block_type") or "").strip()
    if block_type and block_type not in {"heading", "body_content"}:
        return block_type

    document_type = _infer_document_type_from_value(value)
    section_type = str(metadata.get("section_type") or value.get("title_path") or "").strip()
    title_path = str(metadata.get("title_path") or value.get("title_path") or "").strip()
    text = str(value.get("text") or "")
    is_table = bool(metadata.get("is_table")) or "<table" in text

    if document_type == "学生手册":
        if is_table:
            return "table"
        if re.fullmatch(r"第[一二三四五六七八九十百]+章.+", section_type):
            return "section_heading"
        if re.fullmatch(r"第[一二三四五六七八九十百]+节.+", section_type):
            return "subsection_heading"
        if re.fullmatch(r"第[一二三四五六七八九十百]+条.+", section_type):
            return "subsection_heading"
        if title_path and text.lstrip().startswith("#"):
            return "section_heading"
        return "body_content"

    if "课程结构图" in section_type or "课程结构图" in text:
        return "curriculum_table"
    if "教学安排一览表" in section_type or "教学安排一览表" in text:
        return "teaching_plan_table"

    if is_table:
        return "table"
    if re.fullmatch(r".+?(系|学院|医学院)$", section_type):
        return "faculty_title"
    if re.fullmatch(r".+?专业本科人才培养方案(?:（.*?）)?$", section_type) or section_type in {"2025级通识课程培养方案", "通识课程培养方案"}:
        return "program_title"
    if re.fullmatch(r"（\d{4}\s*级）", section_type):
        return "year_marker"
    if re.fullmatch(r"[一二三四五六七八九十]+、.+", section_type):
        return "section_heading"
    if re.fullmatch(r"（[一二三四五六七八九十]+）.+", section_type):
        return "subsection_heading"
    if section_type in {"注：", "注"}:
        return "note_heading"
    return "body_content"


def _collect_metadata_blob(value: dict[str, Any]) -> str:
    """聚合便于匹配的核心元数据文本。"""
    metadata = _get_metadata(value)
    return "\n".join(
        part
        for part in [
            str(metadata.get("faculty") or ""),
            str(metadata.get("major") or ""),
            str(metadata.get("document_type") or ""),
            str(metadata.get("title_path") or value.get("title_path") or ""),
            str(metadata.get("section_type") or ""),
            str(metadata.get("handbook_section") or ""),
        ]
        if part
    )


def _infer_document_type_from_value(value: dict[str, Any]) -> str:
    metadata = _get_metadata(value)
    document_type = str(metadata.get("document_type") or "").strip()
    if document_type:
        return document_type

    source_file = str(value.get("source_file") or "")
    title_path = str(metadata.get("title_path") or value.get("title_path") or "")
    text = str(value.get("text") or "")
    combined = f"{source_file}\n{title_path}\n{text}"
    if "学生手册" in combined:
        return "学生手册"
    return "培养方案"


def _document_hint_match(value: dict[str, Any], analysis: QueryAnalysis) -> bool:
    if not analysis.document_hint:
        return False
    return _infer_document_type_from_value(value) == analysis.document_hint


def _handbook_topic_hits(analysis: QueryAnalysis) -> set[str]:
    q = analysis.normalized_query
    topic_map = {
        "status": {"学籍", "注册", "入学", "复学", "休学", "退学", "转专业", "转学"},
        "exam": {"考试", "成绩", "补考", "重修", "旷考", "作弊"},
        "leave": {"请假", "缺课"},
        "degree": {"毕业", "结业", "学位", "证书"},
        "discipline": {"处分", "违纪", "开除", "警告", "记过", "留校察看"},
        "appeal": {"申诉", "复查", "投诉"},
        "aid": {"资助", "助学金", "勤工助学", "困难补助", "奖学金"},
        "dormitory": {"宿舍", "公寓"},
        "party": {"党团", "入党", "团员", "社团", "学生组织"},
    }
    hits: set[str] = set()
    for topic, terms in topic_map.items():
        if any(term in q for term in terms):
            hits.add(topic)
    return hits


def _query_specific_bonus(value: dict[str, Any], analysis: QueryAnalysis) -> float:
    normalized_blob = _normalize_for_match(
        "\n".join(
            [
                str(value.get("title_path") or ""),
                _collect_metadata_blob(value),
                str(value.get("retrieval_text") or value.get("text") or ""),
            ]
        )
    )
    bonus = 0.0

    strong_terms = [
        term
        for term in [
            analysis.program_hint,
            "补考" if "补考" in analysis.normalized_query else "",
            "重修" if "重修" in analysis.normalized_query else "",
            "作弊" if "作弊" in analysis.normalized_query else "",
            "退学" if "退学" in analysis.normalized_query else "",
            "未注册" if "未注册" in analysis.normalized_query else "",
            "复学申请" if "复学申请" in analysis.normalized_query else "",
            "学位证书" if "学位证书" in analysis.normalized_query else "",
            "毕业要求" if "毕业要求" in analysis.normalized_query else "",
            "成绩合格" if "成绩合格" in analysis.normalized_query else "",
            "学分要求" if "学分要求" in analysis.normalized_query else "",
        ]
        if term
    ]

    for term in strong_terms:
        if term in normalized_blob:
            bonus += 0.75
        elif len(term) >= 3:
            bonus -= 0.18

    if analysis.program_hint and _infer_document_type_from_value(value) == "培养方案":
        if analysis.program_hint in normalized_blob:
            bonus += 1.2
        else:
            bonus -= 0.45

    return bonus


def _program_hint_hit(value: dict[str, Any], analysis: QueryAnalysis, retrieval_text: str | None = None) -> bool:
    """判断候选是否显式命中查询中的专业名提示。"""
    if not analysis.program_hint:
        return False

    metadata_blob = _normalize_for_match(_collect_metadata_blob(value))
    if analysis.program_hint in metadata_blob:
        return True

    text = _normalize_for_match(str(value.get("text") or ""))
    if analysis.program_hint in text:
        return True

    if retrieval_text and analysis.program_hint in _normalize_for_match(retrieval_text):
        return True

    return False


def _block_type_priority(block_type: str) -> float:
    priorities = {
        "program_title": 1.0,
        "section_heading": 0.88,
        "subsection_heading": 0.86,
        "faculty_title": 0.8,
        "body_content": 0.72,
        "curriculum_table": 0.65,
        "teaching_plan_table": 0.65,
        "table": 0.58,
        "note_heading": 0.45,
        "year_marker": 0.3,
        "heading": 0.4,
    }
    return priorities.get(block_type, 0.5)


def _detect_query_intents(analysis: QueryAnalysis) -> set[str]:
    q = analysis.normalized_query
    intents: set[str] = set()
    if not q:
        return intents
    if "本科人才培养方案" in q or "培养方案" in q:
        intents.add("program_lookup")
    if "专业介绍" in q:
        intents.add("intro_lookup")
    if "培养目标" in q:
        intents.add("goal_lookup")
    if "培养要求" in q:
        intents.add("requirement_lookup")
    if "课程结构图" in q:
        intents.add("curriculum_table_lookup")
    if "教学安排一览表" in q or ("教学安排" in q and "一览表" in q):
        intents.add("teaching_plan_lookup")
    if "课程" in q and "表" in q:
        intents.add("table_lookup")
    handbook_topics = _handbook_topic_hits(analysis)
    if analysis.document_hint == "学生手册" or handbook_topics:
        intents.add("handbook_lookup")
    if "status" in handbook_topics:
        intents.add("status_lookup")
    if "exam" in handbook_topics:
        intents.add("exam_lookup")
    if "leave" in handbook_topics:
        intents.add("leave_lookup")
    if "degree" in handbook_topics:
        intents.add("degree_lookup")
    if "discipline" in handbook_topics:
        intents.add("discipline_lookup")
    if "appeal" in handbook_topics:
        intents.add("appeal_lookup")
    if "aid" in handbook_topics:
        intents.add("aid_lookup")
    if "dormitory" in handbook_topics:
        intents.add("dormitory_lookup")
    if "party" in handbook_topics:
        intents.add("party_lookup")
    return intents


def _important_query_terms(analysis: QueryAnalysis) -> list[str]:
    generic_terms = {
        "培养", "目标", "要求", "介绍", "专业", "本科", "方案", "课程", "结构图", "教学", "安排", "一览表"
    }
    terms: list[str] = []
    for term in analysis.terms:
        if len(term) < 3:
            continue
        if term in generic_terms:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _normalized_fields(value: dict[str, Any]) -> dict[str, str]:
    metadata = _get_metadata(value)
    return {
        "text": _normalize_for_match(str(value.get("text") or "")),
        "title_path": _normalize_for_match(str(metadata.get("title_path") or value.get("title_path") or "")),
        "section_type": _normalize_for_match(str(metadata.get("section_type") or "")),
        "major": _normalize_for_match(str(metadata.get("major") or "")),
        "faculty": _normalize_for_match(str(metadata.get("faculty") or "")),
        "document_type": _normalize_for_match(_infer_document_type_from_value(value)),
        "retrieval_text": _normalize_for_match(str(value.get("retrieval_text") or value.get("text") or "")),
    }


def _program_exactness(value: dict[str, Any], analysis: QueryAnalysis) -> float:
    q = analysis.normalized_query
    if not q:
        return 0.0
    fields = _normalized_fields(value)
    major = fields["major"]
    title_path = fields["title_path"]
    section_type = fields["section_type"]

    if q and q in {major, title_path, section_type}:
        return 1.0
    if q and major and (q in major or major in q):
        return 0.92
    if q and title_path and (q in title_path or title_path in q):
        return 0.88
    if q and section_type and (q in section_type or section_type in q):
        return 0.84
    return 0.0


def _field_match_score(value: dict[str, Any], analysis: QueryAnalysis) -> float:
    q = analysis.normalized_query
    if not q:
        return 0.0
    fields = _normalized_fields(value)
    score = 0.0
    if q and q in fields["major"]:
        score += 1.0
    if q and q in fields["section_type"]:
        score += 0.9
    if q and q in fields["title_path"]:
        score += 0.8
    if analysis.document_hint and _normalize_for_match(analysis.document_hint) == fields["document_type"]:
        score += 0.45
    if analysis.program_hint:
        if analysis.program_hint in fields["major"]:
            score += 1.2
        if analysis.program_hint in fields["title_path"]:
            score += 0.9
        if analysis.program_hint in fields["section_type"]:
            score += 0.75
        if analysis.program_hint in fields["retrieval_text"]:
            score += 0.35
    important_terms = _important_query_terms(analysis)
    score += sum(0.12 for term in important_terms if term in fields["major"])
    score += sum(0.1 for term in important_terms if term in fields["section_type"])
    score += sum(0.06 for term in important_terms if term in fields["text"])
    score += 0.2 * _query_specific_bonus(value, analysis)
    return score


def _handbook_section_bonus(value: dict[str, Any], intents: set[str]) -> float:
    if "handbook_lookup" not in intents:
        return 0.0

    section_blob = _normalize_for_match(_collect_metadata_blob(value) + "\n" + str(value.get("text") or ""))
    title_path = _normalize_for_match(str(_get_metadata(value).get("title_path") or value.get("title_path") or ""))
    bonus = 0.0
    mapping = {
        "status_lookup": ["学籍", "注册", "入学", "休学", "复学", "退学", "转专业", "转学"],
        "exam_lookup": ["考试", "成绩", "补考", "重修", "作弊", "旷考"],
        "leave_lookup": ["请假", "缺课"],
        "degree_lookup": ["毕业", "结业", "学位", "证书"],
        "discipline_lookup": ["处分", "违纪", "开除", "警告", "记过", "留校察看"],
        "appeal_lookup": ["申诉", "复查", "投诉"],
        "aid_lookup": ["资助", "助学金", "勤工助学", "困难补助", "奖学金"],
        "dormitory_lookup": ["宿舍", "公寓"],
        "party_lookup": ["党团", "入党", "团员", "社团"],
    }
    for intent, terms in mapping.items():
        if intent in intents:
            if any(term in title_path for term in terms):
                bonus += 0.9
            elif any(term in section_blob for term in terms):
                bonus += 0.55
    return bonus


async def _title_recall(runtime_store: Any, analysis: QueryAnalysis, limit: int) -> list[RecallCandidate]:
    corpus = await _load_corpus(runtime_store)
    if not corpus:
        return []

    candidates: list[RecallCandidate] = []
    intents = _detect_query_intents(analysis)

    for chunk in corpus:
        value = chunk.value
        block_type = _infer_block_type_from_value(value)
        if block_type not in TITLE_BLOCK_TYPES:
            continue
        document_type = _infer_document_type_from_value(value)

        score = _field_match_score(value, analysis)
        if block_type == "program_title":
            score += 0.35 + _program_exactness(value, analysis)
        elif block_type in {"section_heading", "subsection_heading"}:
            score += 0.2
        elif block_type == "faculty_title":
            score += 0.12

        if "program_lookup" in intents and block_type == "program_title":
            score += 0.55
        if "intro_lookup" in intents and block_type == "section_heading" and "专业介绍" in str(_get_metadata(value).get("section_type") or ""):
            score += 0.45
        if "goal_lookup" in intents and block_type in {"section_heading", "subsection_heading"} and "培养目标" in str(_get_metadata(value).get("section_type") or ""):
            score += 0.48
        if "requirement_lookup" in intents and block_type in {"section_heading", "subsection_heading"} and "培养要求" in str(_get_metadata(value).get("section_type") or ""):
            score += 0.48
        if analysis.program_hint and document_type == "培养方案":
            if _program_hint_hit(value, analysis, retrieval_text=str(value.get("retrieval_text") or "")):
                score += 1.0
                if block_type == "program_title":
                    score += 0.6
        if document_type == "学生手册":
            score += 0.18
            score += _handbook_section_bonus(value, intents)
        if analysis.document_hint == "培养方案" and document_type == "学生手册":
            score -= 0.35
        if analysis.document_hint == "学生手册" and document_type == "培养方案":
            score -= 0.35

        if score <= 0:
            continue
        candidates.append(RecallCandidate(key=chunk.key, value=value, score=float(score), channel="title"))

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:limit]


async def _table_recall(runtime_store: Any, analysis: QueryAnalysis, limit: int) -> list[RecallCandidate]:
    corpus = await _load_corpus(runtime_store)
    if not corpus:
        return []

    candidates: list[RecallCandidate] = []
    intents = _detect_query_intents(analysis)

    for chunk in corpus:
        value = chunk.value
        block_type = _infer_block_type_from_value(value)
        if block_type not in TABLE_BLOCK_TYPES:
            continue

        score = _field_match_score(value, analysis)
        if block_type == "curriculum_table":
            score += 0.2
        if block_type == "teaching_plan_table":
            score += 0.2

        if "curriculum_table_lookup" in intents and block_type == "curriculum_table":
            score += 0.55
        if "teaching_plan_lookup" in intents and block_type == "teaching_plan_table":
            score += 0.55
        if "table_lookup" in intents:
            score += 0.24
        if "program_lookup" in intents:
            score -= 0.38
        if "goal_lookup" in intents or "intro_lookup" in intents or "requirement_lookup" in intents:
            score -= 0.32
        if "handbook_lookup" in intents:
            score -= 0.45

        if score <= 0:
            continue
        candidates.append(RecallCandidate(key=chunk.key, value=value, score=float(score), channel="table"))

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:limit]


def _block_type_adjustment(value: dict[str, Any], analysis: QueryAnalysis) -> float:
    metadata = _get_metadata(value)
    block_type = _infer_block_type_from_value(value)
    document_type = _infer_document_type_from_value(value)
    section_type = str(metadata.get("section_type") or value.get("title_path") or "")
    text = str(value.get("text") or "")
    title_path = str(metadata.get("title_path") or value.get("title_path") or "")
    major = str(metadata.get("major") or "")
    faculty = str(metadata.get("faculty") or "")
    intents = _detect_query_intents(analysis)
    important_terms = _important_query_terms(analysis)
    metadata_text = _collect_metadata_blob(value)
    bonus = 0.0

    normalized_metadata_text = _normalize_for_match(metadata_text)
    normalized_text = _normalize_for_match(text)

    term_hits_in_metadata = sum(1 for term in important_terms if term in metadata_text)
    term_hits_in_text = sum(1 for term in important_terms if term in text)

    bonus += min(term_hits_in_metadata * 0.08, 0.24)
    bonus += min(term_hits_in_text * 0.04, 0.12)

    if "program_lookup" in intents:
        if block_type == "program_title":
            bonus += 0.7
            if analysis.normalized_query and analysis.normalized_query in _normalize_query_text(f"{metadata_text}\n{text}"):
                bonus += 0.2
        elif block_type in {"curriculum_table", "teaching_plan_table", "table"}:
            bonus -= 0.45

    if "intro_lookup" in intents:
        if block_type == "section_heading" and "专业介绍" in section_type:
            bonus += 0.38
        elif block_type == "body_content" and "专业介绍" in str(metadata.get("title_path") or value.get("title_path") or ""):
            bonus += 0.18
        elif block_type in {"curriculum_table", "teaching_plan_table", "table"}:
            bonus -= 0.2

    if "goal_lookup" in intents:
        if block_type in {"section_heading", "subsection_heading"} and "培养目标" in section_type:
            bonus += 0.4
        elif block_type == "body_content" and "培养目标" in str(metadata.get("title_path") or value.get("title_path") or ""):
            bonus += 0.24
        elif block_type in {"curriculum_table", "teaching_plan_table", "table"}:
            bonus -= 0.24

    if "requirement_lookup" in intents:
        if block_type in {"section_heading", "subsection_heading"} and "培养要求" in section_type:
            bonus += 0.4
        elif block_type == "body_content" and "培养要求" in str(metadata.get("title_path") or value.get("title_path") or ""):
            bonus += 0.24
        elif block_type in {"curriculum_table", "teaching_plan_table", "table"}:
            bonus -= 0.2

    if "curriculum_table_lookup" in intents and block_type == "curriculum_table":
        bonus += 0.42
    if "teaching_plan_lookup" in intents and block_type == "teaching_plan_table":
        bonus += 0.42
    if "table_lookup" in intents and block_type in {"curriculum_table", "teaching_plan_table", "table"}:
        bonus += 0.18

    if "curriculum_table_lookup" in intents:
        if block_type == "curriculum_table" and "课程结构图" in f"{section_type}\n{text}\n{title_path}":
            bonus += 0.6
        elif block_type in TABLE_BLOCK_TYPES - {"curriculum_table"}:
            bonus -= 0.25

        if analysis.program_hint:
            if analysis.program_hint in normalized_metadata_text or analysis.program_hint in normalized_text:
                bonus += 0.8
            else:
                bonus -= 0.5

    if "teaching_plan_lookup" in intents:
        if block_type == "teaching_plan_table" and "教学安排一览表" in f"{section_type}\n{text}\n{title_path}":
            bonus += 0.6
        elif block_type == "curriculum_table":
            bonus -= 0.2

        if analysis.program_hint:
            if analysis.program_hint in normalized_metadata_text or analysis.program_hint in normalized_text:
                bonus += 0.9
            else:
                bonus -= 0.6

    if block_type == "year_marker":
        bonus -= 0.08

    if document_type == "学生手册":
        bonus += _handbook_section_bonus(value, intents)
        if block_type in {"section_heading", "subsection_heading"}:
            bonus += 0.08
        if "handbook_lookup" in intents:
            bonus += 0.16
    elif "handbook_lookup" in intents:
        bonus -= 0.35

    if analysis.document_hint == "培养方案":
        bonus += 0.22 if document_type == "培养方案" else -0.3
    elif analysis.document_hint == "学生手册":
        bonus += 0.22 if document_type == "学生手册" else -0.3

    if text.strip().startswith("#") and len(text.strip()) <= 40 and block_type in {"faculty_title", "heading"}:
        bonus -= 0.04

    if important_terms and term_hits_in_metadata == 0 and block_type in {"program_title", "section_heading", "subsection_heading", "body_content"}:
        bonus -= 0.08

    return bonus


def _term_weight(term: str) -> float:
    if len(term) >= 5:
        return 2.0
    if len(term) == 4:
        return 1.6
    if len(term) == 3:
        return 1.3
    if term in {"流程", "条件", "标准", "办法", "规定", "申请", "评选", "程序", "资格", "步骤", "名单"}:
        return 1.1
    return 0.9


def _compute_base_fusion_score(
    intents: set[str],
    semantic_score: float,
    lexical_score: float,
    title_score: float,
    table_score: float,
) -> float:
    """按查询意图选择不同的多路召回融合权重。"""
    final = 0.0
    if "program_lookup" in intents:
        final += 0.8 * title_score + 0.35 * lexical_score + 0.15 * semantic_score - 0.15 * table_score
    elif "handbook_lookup" in intents:
        final += 0.55 * title_score + 0.5 * lexical_score + 0.2 * semantic_score - 0.1 * table_score
    elif {"goal_lookup", "intro_lookup", "requirement_lookup"} & intents:
        final += 0.5 * title_score + 0.45 * lexical_score + 0.15 * semantic_score - 0.12 * table_score
    elif {"curriculum_table_lookup", "teaching_plan_lookup", "table_lookup"} & intents:
        final += 0.65 * table_score + 0.25 * lexical_score + 0.15 * semantic_score + 0.05 * title_score
    else:
        if semantic_score > 0 and lexical_score > 0:
            final += 0.45 * semantic_score + 0.45 * lexical_score + 0.1 * title_score
        elif semantic_score > 0:
            final += 0.7 * semantic_score + 0.1 * title_score
        else:
            final += 0.65 * lexical_score + 0.1 * title_score
    return final


def _compute_priority_rank(
    value: dict[str, Any],
    block_type: str,
    exactness: float,
    intents: set[str],
    metadata_term_hits: int,
    program_hint_hit: bool,
) -> int:
    """基于查询意图给候选分配离散优先级，确保关键块排在前面。"""
    priority_rank = 0
    section_type = str(_get_metadata(value).get("section_type") or "")
    document_type = _infer_document_type_from_value(value)

    if "program_lookup" in intents:
        if block_type == "program_title" and exactness >= 0.9:
            return 3
        if block_type == "program_title" and exactness >= 0.75:
            return 2
        if block_type in TABLE_BLOCK_TYPES:
            return -1
        return 0

    if "goal_lookup" in intents:
        if block_type == "subsection_heading" and "培养目标" in section_type:
            return 3
        if block_type == "section_heading" and "培养目标" in section_type:
            return 2
        if block_type == "section_heading" and "专业培养目标及培养要求" in section_type:
            return 0
        return 0

    if "intro_lookup" in intents:
        if block_type == "section_heading" and "专业介绍" in section_type:
            return 3
        return 0

    if "requirement_lookup" in intents:
        if block_type == "subsection_heading" and "培养要求" in section_type:
            return 3
        if block_type == "section_heading" and "培养要求" in section_type:
            return 2
        if block_type == "section_heading" and "专业培养目标及培养要求" in section_type:
            return 0
        return 0

    if "curriculum_table_lookup" in intents:
        if block_type == "curriculum_table" and (program_hint_hit or metadata_term_hits > 0):
            return 3
        if block_type == "curriculum_table":
            return 2
        if block_type in TABLE_BLOCK_TYPES - {"curriculum_table"}:
            return -1
        return 0

    if "teaching_plan_lookup" in intents:
        if block_type == "teaching_plan_table" and (program_hint_hit or metadata_term_hits > 0):
            return 3
        if block_type == "teaching_plan_table":
            return 2
        if block_type == "curriculum_table":
            return -1
        return 0

    if "handbook_lookup" in intents:
        if document_type != "学生手册":
            return -1
        if metadata_term_hits >= 2:
            return 4
        if block_type == "section_heading":
            return 3
        if block_type == "subsection_heading":
            return 2
        if metadata_term_hits > 0:
            return 1

    return priority_rank


def _build_candidate_features(
    key: str,
    value: dict[str, Any],
    analysis: QueryAnalysis,
    semantic_norm: dict[str, float],
    lexical_norm: dict[str, float],
    title_norm: dict[str, float],
    table_norm: dict[str, float],
) -> CandidateFeatures:
    metadata = _get_metadata(value)
    text = str(value.get("text") or "")
    title_path = str(value.get("title_path") or "")
    retrieval_text = str(value.get("retrieval_text") or text)
    block_type = _infer_block_type_from_value(value)
    document_type = _infer_document_type_from_value(value)
    section_type = str(metadata.get("section_type") or "")
    metadata_blob = _collect_metadata_blob(value)
    normalized_metadata_blob = _normalize_for_match(metadata_blob)
    important_terms = _important_query_terms(analysis)
    metadata_term_hits = sum(1 for term in important_terms if term in normalized_metadata_blob)
    program_hint_hit = _program_hint_hit(value, analysis, retrieval_text=retrieval_text)
    exactness = _program_exactness(value, analysis)

    return CandidateFeatures(
        key=key,
        value=value,
        semantic_score=semantic_norm.get(key, 0.0),
        lexical_score=lexical_norm.get(key, 0.0),
        title_score=title_norm.get(key, 0.0),
        table_score=table_norm.get(key, 0.0),
        text=text,
        title_path=title_path,
        retrieval_text=retrieval_text,
        source_file=str(value.get("source_file") or ""),
        block_type=block_type,
        document_type=document_type,
        section_type=section_type,
        metadata_term_hits=metadata_term_hits,
        program_hint_hit=program_hint_hit,
        exactness=exactness,
    )


def _apply_document_routing_adjustments(final: float, features: CandidateFeatures, analysis: QueryAnalysis) -> float:
    if analysis.document_hint:
        if features.document_type == analysis.document_hint:
            return final + 0.75
        return final - 0.45

    if analysis.program_hint and features.document_type == "培养方案" and features.program_hint_hit:
        return final + 0.95

    return final


def _apply_program_adjustments(final: float, features: CandidateFeatures, analysis: QueryAnalysis, intents: set[str]) -> float:
    if "program_lookup" in intents and features.block_type == "program_title":
        final += 0.9 * features.exactness
    elif features.block_type in {"curriculum_table", "teaching_plan_table", "table"} and "program_lookup" in intents:
        final -= 0.35

    if "program_lookup" in intents:
        if features.block_type == "program_title" and features.exactness >= 0.9:
            final += 3.0
        elif features.block_type == "program_title" and features.exactness >= 0.75:
            final += 1.5

        if features.block_type in {"curriculum_table", "teaching_plan_table", "table"}:
            normalized_text = _normalize_for_match(features.text)
            if analysis.normalized_query and analysis.normalized_query in normalized_text:
                final -= 1.2
            else:
                final -= 0.6

    if analysis.program_hint and features.document_type == "培养方案":
        if features.program_hint_hit:
            final += 1.2
        elif "handbook_lookup" in intents:
            final -= 0.15
        else:
            final -= 0.55

    if analysis.program_hint and "handbook_lookup" in intents and features.document_type == "培养方案":
        if features.program_hint_hit:
            final += 2.4
            if features.block_type == "program_title":
                final += 1.0
        else:
            final -= 0.4

    if "curriculum_table_lookup" in intents:
        if features.block_type == "curriculum_table":
            final += 0.9
            if "课程结构图" in f"{features.section_type}\n{features.text}\n{features.title_path}":
                final += 0.5
        elif features.block_type in {"teaching_plan_table", "table"}:
            final -= 0.45

        if analysis.program_hint and not features.program_hint_hit:
            final -= 1.2

    if "teaching_plan_lookup" in intents:
        if features.block_type == "teaching_plan_table":
            final += 0.9
            if "教学安排一览表" in f"{features.section_type}\n{features.text}\n{features.title_path}":
                final += 0.5
        elif features.block_type == "curriculum_table":
            final -= 0.3

        if features.metadata_term_hits == 0 and _important_query_terms(analysis) and features.block_type in {"teaching_plan_table", "table"}:
            final -= 0.35
        if analysis.program_hint and not features.program_hint_hit:
            final -= 1.4

    return final


def _apply_handbook_adjustments(final: float, features: CandidateFeatures, analysis: QueryAnalysis, intents: set[str]) -> float:
    if "handbook_lookup" in intents:
        if features.document_type == "学生手册":
            final += 0.5
        else:
            final -= 0.35

    if "exam_lookup" in intents and features.document_type == "学生手册":
        handbook_bonus = _handbook_section_bonus(features.value, intents)
        if handbook_bonus > 0:
            final += 0.45

    if "degree_lookup" in intents and features.document_type == "学生手册":
        handbook_bonus = _handbook_section_bonus(features.value, intents)
        if handbook_bonus > 0:
            final += 0.35
        normalized_title = _normalize_for_match(features.title_path)
        if "毕业" in normalized_title and "学位" in normalized_title:
            final += 0.55
        elif "毕业" in normalized_title or "结业" in normalized_title:
            final += 0.35

    if "status_lookup" in intents and "退学" in _normalize_for_match(f"{features.title_path}\n{features.retrieval_text}"):
        final += 0.4

    return final


def _apply_common_score_adjustments(final: float, features: CandidateFeatures, analysis: QueryAnalysis) -> float:
    final += 0.08 * _block_type_priority(features.block_type)

    if features.title_path:
        final += min(len(features.title_path.split(" > ")) * 0.015, 0.06)

    if features.source_file:
        final += 0.02 if features.source_file.endswith(".md") else 0.0

    noise_factor = _chunk_noise_factor(features.text, features.title_path, features.value.get("chunk_index"))
    if _detect_query_intents(analysis) and features.block_type in {"section_heading", "subsection_heading"}:
        noise_factor = max(noise_factor, 0.9)
    if "program_lookup" in _detect_query_intents(analysis) and features.block_type == "program_title" and features.exactness >= 0.75:
        noise_factor = max(noise_factor, 0.95)

    final *= noise_factor
    final += _block_type_adjustment(features.value, analysis)

    if features.metadata_term_hits:
        final += min(features.metadata_term_hits * 0.18, 0.72)
    if features.program_hint_hit:
        final += 0.9
    final += _query_specific_bonus(features.value, analysis)

    if query_phrase := _normalize_query_text(" ".join(str(v) for v in [features.title_path, features.retrieval_text])):
        if query_phrase and query_phrase in features.retrieval_text:
            final += 0.05

    return final


def _ensure_cross_domain_coverage(
    selected: list[RankedResult],
    reranked: list[RankedResult],
    analysis: QueryAnalysis,
    intents: set[str],
    top_k: int,
    priority_keys: dict[str, tuple[int, float]],
) -> list[RankedResult]:
    if not (analysis.program_hint and "handbook_lookup" in intents):
        return selected[:top_k]

    has_program_result = any(_infer_document_type_from_value(item.value) == "培养方案" for item in selected)
    if has_program_result:
        return selected[:top_k]

    best_program_item = next(
        (
            item
            for item in reranked
            if _infer_document_type_from_value(item.value) == "培养方案"
            and _program_hint_hit(item.value, analysis, retrieval_text=str(item.value.get("retrieval_text") or ""))
        ),
        None,
    )
    if best_program_item is None:
        return selected[:top_k]

    if len(selected) >= top_k:
        selected = selected[:-1] + [best_program_item]
    else:
        selected.append(best_program_item)
    selected.sort(key=lambda x: priority_keys.get(x.key, (0, x.score)), reverse=True)
    return selected[:top_k]


def _looks_like_toc_chunk(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 12:
        return False
    page_num_like = 0
    for line in lines:
        if re.search(r"\d{1,4}$", line):
            page_num_like += 1
    return page_num_like >= 6


def _looks_like_cover_chunk(text: str, title_path: str, chunk_index: Any) -> bool:
    if title_path:
        return False

    stripped = text.strip()
    if not stripped:
        return True

    if str(chunk_index) == "0":
        return len(stripped) <= 80

    tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", stripped)
    if len(stripped) <= 60 and len(tokens) <= 4:
        return True

    if stripped.upper() == stripped and len(stripped) <= 80:
        return True

    return False


def _chunk_noise_factor(text: str, title_path: str, chunk_index: Any) -> float:
    factor = 1.0

    if _looks_like_toc_chunk(text):
        factor *= 0.35

    if _looks_like_cover_chunk(text, title_path, chunk_index):
        factor *= 0.1

    stripped = text.strip()
    if title_path and len(stripped) <= 24:
        factor *= 0.6

    if title_path and len(title_path.split(" > ")) == 1 and len(stripped) <= 80:
        factor *= 0.85

    return factor


def _parse_corpus_chunk(key: str, payload: dict[str, Any]) -> CorpusChunk | None:
    source_file = str(payload.get("source_file") or "")
    chunk_index = payload.get("chunk_index")
    text = str(payload.get("text") or "")
    retrieval_text = str(payload.get("retrieval_text") or text)
    title_path = str(payload.get("title_path") or "")
    if not source_file or not retrieval_text:
        return None
    return CorpusChunk(
        key=key,
        value=payload,
        text=text,
        retrieval_text=retrieval_text,
        title_path=title_path,
        source_file=source_file,
        chunk_index=chunk_index,
    )


async def _load_corpus(runtime_store: Any) -> list[CorpusChunk]:
    if not hasattr(runtime_store, "conn") or runtime_store.conn is None:
        return []

    conn = runtime_store.conn
    conn_id = id(conn)
    row_count_row = await conn.execute("SELECT COUNT(*) FROM store")
    row_count = (await row_count_row.fetchone())[0]
    await row_count_row.close()

    cached = _CORPUS_CACHE.get(conn_id)
    if cached and cached[0] == row_count:
        return cached[1]

    cursor = await conn.execute("SELECT key, value FROM store")
    rows = await cursor.fetchall()
    await cursor.close()

    corpus: list[CorpusChunk] = []
    for key, raw_value in rows:
        payload_text = _to_text(raw_value)
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        chunk = _parse_corpus_chunk(str(key), payload)
        if chunk is not None:
            corpus.append(chunk)

    _CORPUS_CACHE[conn_id] = (row_count, corpus)
    return corpus


async def _lexical_recall(runtime_store: Any, analysis: QueryAnalysis, limit: int) -> list[tuple[str, dict[str, Any], float]]:
    if not analysis.terms:
        return []
    corpus = await _load_corpus(runtime_store)
    if not corpus:
        return []

    term_weights = {term: _term_weight(term) for term in analysis.terms}
    total_weight = sum(term_weights.values()) or 1.0

    recalled: list[tuple[str, dict[str, Any], float]] = []
    for chunk in corpus:
        retrieval_text = chunk.retrieval_text
        title_path = chunk.title_path
        source_file = chunk.source_file
        metadata = _get_metadata(chunk.value)
        major = str(metadata.get("major") or "")
        section_type = str(metadata.get("section_type") or "")
        document_type = _infer_document_type_from_value(chunk.value)

        normalized_retrieval = _normalize_for_match(retrieval_text)
        normalized_title = _normalize_for_match(title_path)
        normalized_major = _normalize_for_match(major)
        normalized_section = _normalize_for_match(section_type)

        hit_weight = 0.0
        title_weight = 0.0
        source_weight = 0.0

        for term, weight in term_weights.items():
            if term in normalized_retrieval:
                hit_weight += weight
            if normalized_title and term in normalized_title:
                title_weight += weight
            if term in source_file:
                source_weight += weight * 0.25

        query_phrase = analysis.normalized_query
        phrase_boost = 0.8 if query_phrase and query_phrase in normalized_retrieval else 0.0
        title_boost = 0.5 if query_phrase and query_phrase in normalized_title else 0.0
        lexical_score = (hit_weight / total_weight) + 0.35 * (title_weight / total_weight) + source_weight + phrase_boost + title_boost

        if analysis.program_hint:
            if analysis.program_hint in normalized_major:
                lexical_score += 1.2
            elif analysis.program_hint in normalized_retrieval or analysis.program_hint in normalized_section:
                lexical_score += 0.7
            else:
                lexical_score -= 0.45

        if query_phrase:
            if query_phrase in normalized_title:
                lexical_score += 1.2
            elif query_phrase in normalized_major:
                lexical_score += 0.8

        if analysis.document_hint == document_type:
            lexical_score += 0.55
        elif analysis.document_hint:
            lexical_score -= 0.35

        intents = _detect_query_intents(analysis)
        block_type = _infer_block_type_from_value(chunk.value)
        if "curriculum_table_lookup" in intents:
            if block_type == "curriculum_table":
                lexical_score += 0.9
            elif block_type in {"teaching_plan_table", "table"}:
                lexical_score -= 0.35
        if "teaching_plan_lookup" in intents:
            if block_type == "teaching_plan_table":
                lexical_score += 0.9
            elif block_type == "curriculum_table":
                lexical_score -= 0.2
        if document_type == "学生手册":
            lexical_score += _handbook_section_bonus(chunk.value, intents)
        elif "handbook_lookup" in intents:
            lexical_score -= 0.2

        lexical_score += 0.25 * _query_specific_bonus(chunk.value, analysis)

        lexical_score *= _chunk_noise_factor(retrieval_text, title_path, chunk.chunk_index)

        if lexical_score <= 0:
            continue
        recalled.append((chunk.key, chunk.value, float(lexical_score)))

    recalled.sort(key=lambda x: x[2], reverse=True)
    return recalled[:limit]


def _hybrid_rerank(
    semantic_results,
    title_results: list[RecallCandidate],
    table_results: list[RecallCandidate],
    lexical_results: list[tuple[str, dict[str, Any], float]],
    analysis: QueryAnalysis,
    top_k: int,
) -> list[RankedResult]:
    semantic_raw = {
        str(item.key): float(item.score)
        for item in semantic_results
        if isinstance(item.score, (int, float))
    }
    lexical_raw = {key: score for key, _, score in lexical_results}
    title_raw = {item.key: item.score for item in title_results}
    table_raw = {item.key: item.score for item in table_results}

    semantic_norm = _normalize_scores(semantic_raw)
    lexical_norm = _normalize_scores(lexical_raw)
    title_norm = _normalize_scores(title_raw)
    table_norm = _normalize_scores(table_raw)

    value_by_key: dict[str, dict[str, Any]] = {}
    for item in semantic_results:
        value_by_key[str(item.key)] = item.value or {}
    for item in title_results:
        value_by_key.setdefault(item.key, item.value)
    for item in table_results:
        value_by_key.setdefault(item.key, item.value)
    for key, value, _ in lexical_results:
        value_by_key.setdefault(key, value)

    merged_keys = set(value_by_key.keys())
    intents = _detect_query_intents(analysis)
    reranked: list[RankedResult] = []
    priority_keys: dict[str, tuple[int, float]] = {}

    for key in merged_keys:
        value = value_by_key.get(key, {})
        features = _build_candidate_features(
            key=key,
            value=value,
            analysis=analysis,
            semantic_norm=semantic_norm,
            lexical_norm=lexical_norm,
            title_norm=title_norm,
            table_norm=table_norm,
        )

        final = _compute_base_fusion_score(
            intents,
            features.semantic_score,
            features.lexical_score,
            features.title_score,
            features.table_score,
        )
        final = _apply_document_routing_adjustments(final, features, analysis)
        final = _apply_program_adjustments(final, features, analysis, intents)
        final = _apply_handbook_adjustments(final, features, analysis, intents)
        final = _apply_common_score_adjustments(final, features, analysis)

        priority_rank = _compute_priority_rank(
            value=value,
            block_type=features.block_type,
            exactness=features.exactness,
            intents=intents,
            metadata_term_hits=features.metadata_term_hits,
            program_hint_hit=features.program_hint_hit,
        )

        priority_keys[key] = (priority_rank, float(final))

        reranked.append(
            RankedResult(
                key=key,
                value=value,
                score=float(final),
                semantic_score=float(features.semantic_score),
                lexical_score=float(max(features.lexical_score, features.title_score, features.table_score)),
            )
        )

    reranked.sort(key=lambda x: priority_keys.get(x.key, (0, x.score)), reverse=True)
    selected = reranked[:top_k]
    return _ensure_cross_domain_coverage(selected, reranked, analysis, intents, top_k, priority_keys)


def _format_retrieve_results(results) -> str:
    if not results:
        return "No matching chunks found."

    lines = []
    for idx, item in enumerate(results, start=1):
        value = item.value or {}
        score = item.score
        text = value.get("text", "")
        source_file = value.get("source_file", "unknown")
        chunk_index = value.get("chunk_index", "unknown")
        semantic_score = getattr(item, "semantic_score", None)
        lexical_score = getattr(item, "lexical_score", None)
        score_text = f"{score:.6f}" if isinstance(score, (int, float)) else "unknown"
        semantic_text = f"{semantic_score:.6f}" if isinstance(semantic_score, (int, float)) else "unknown"
        lexical_text = f"{lexical_score:.6f}" if isinstance(lexical_score, (int, float)) else "unknown"
        lines.append(
            (
                f"{idx}. score={score_text} semantic={semantic_text} lexical={lexical_text} "
                f"source={source_file} chunk={chunk_index} key={item.key}\n{text}"
            )
        )
    return "\n\n".join(lines)


@tool
async def retrieve_from_rag_db(runtime: ToolRuntime, query: str, top_k: int = 5) -> str:
    """Retrieve the most relevant chunks from the unified RAG database.

    This tool is designed for agent-facing retrieval across two document families:
    - program documents (`培养方案`): major introductions, objectives, requirements,
      curriculum maps, teaching plan tables, and major-specific credit/course rules
    - student handbook documents (`学生手册`): academic status, registration, exams,
      grades, makeup exams, leave, suspension, resumption, withdrawal, graduation,
      degrees, discipline, appeals, dormitories, aid, and student-affairs policies

    Recommended usage:
    - pass a full Chinese natural-language query sentence
    - include the major name for program questions when possible
    - include the policy target or procedure target for handbook questions
    - split cross-domain questions into multiple searches if needed

    Args:
        query: A Chinese natural-language search sentence.
        top_k: Number of ranked candidates to return. Default is 5.

    Returns:
        A formatted ranked result list for downstream reasoning, or an `Error:` message.
    """
    try:
        if not query or not query.strip():
            return "Error: Query must not be empty."
        if top_k <= 0:
            return "Error: top_k must be greater than 0."

        store = runtime.store
        if not store:
            return "Error: Store is not available from runtime."

        embedding_config = _resolve_embedding_config(runtime)
        indexed_store = build_indexed_store(store, embedding_config)
        await indexed_store.setup()

        semantic_limit = max(top_k * 8, 40)
        lexical_limit = max(top_k * 10, 80)

        analysis = _analyze_query(query)
        semantic_results = await indexed_store.asearch(
            (NAMESPACE,),
            query=query,
            limit=semantic_limit,
        )

        title_results = await _title_recall(store, analysis, limit=max(top_k * 6, 30))
        table_results = await _table_recall(store, analysis, limit=max(top_k * 4, 20))
        lexical_results = await _lexical_recall(store, analysis, limit=lexical_limit)
        reranked_results = _hybrid_rerank(
            semantic_results,
            title_results,
            table_results,
            lexical_results,
            analysis,
            top_k=top_k,
        )
        return _format_retrieve_results(reranked_results)
    except Exception as exc:
        return f"Error: Failed to retrieve query results: {exc}"