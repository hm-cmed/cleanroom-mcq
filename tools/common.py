"""問題ファイルと事実票を読む共通の部品（build・監修ページ・監修の反映で使う）。"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY") or "hm-cmed/cleanroom-mcq"
DEFAULT_FACTS = os.environ.get("FACTS_DIR") or os.path.join(ROOT, "..", "cleanroom-gi-facts")
# 事実票に data/domains.yaml がないときに使う領域名
FALLBACK_DOMAINS = {
    "HP": "H. pylori関連疾患", "UG": "上部消化管出血", "ES": "食道", "GD": "胃・十二指腸",
    "IN": "小腸・大腸", "LV": "肝", "BP": "胆・膵", "AB": "腹膜・腹壁・急性腹症",
    "XS": "症候・検査・栄養", "NG": "神経消化器病",
}
NO_RESPONSE = "_No response_"


def load_facts(facts_repo: str) -> dict[str, dict]:
    facts: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(facts_repo, "data", "facts", "*.yaml"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            for card in yaml.safe_load(f) or []:
                facts[card["id"]] = card
    return facts


def load_domains(facts_repo: str) -> dict[str, dict]:
    path = os.path.join(facts_repo, "data", "domains.yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return {d["prefix"]: {"name": d["name"], "field": d.get("field", "")} for d in yaml.safe_load(f) or []}
    return {k: {"name": v, "field": "消化器"} for k, v in FALLBACK_DOMAINS.items()}


def item_files() -> list[str]:
    return sorted(glob.glob(os.path.join(ROOT, "items", "*.yaml")))


def load_items() -> list[dict]:
    items: list[dict] = []
    for path in item_files():
        with open(path, encoding="utf-8") as f:
            for it in yaml.safe_load(f) or []:
                it["_file"] = path
                items.append(it)
    return items


def item_hash(it: dict, facts: dict[str, dict]) -> str:
    """監修の対象（問題文・選択肢・正誤・根拠カードの主張文と出典）から作る版の印（10文字）。
    問題を直しても、根拠カードの主張文が変わっても、印が変わる＝再監修が必要になる。"""
    body = {"ask": it.get("ask"), "stem": it.get("stem"), "options": []}
    for o in it.get("options") or []:
        card = facts.get(o.get("fact")) or {}
        a = card.get("assertion") or {}
        p = card.get("provenance") or {}
        body["options"].append([o.get("text"), o.get("truth"), o.get("fact"),
                                a.get("plain_statement_ja"), p.get("source"), p.get("doi")])
    text = json.dumps(body, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def is_current_approval(it: dict, facts: dict[str, dict]) -> bool:
    return it.get("status") == "approved" and it.get("reviewed_hash") == item_hash(it, facts)


def parse_form(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    label = None
    buf: list[str] = []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if label is not None:
                out[label] = "\n".join(buf).strip()
            label, buf = m.group(1), []
        elif label is not None:
            buf.append(line)
    if label is not None:
        out[label] = "\n".join(buf).strip()
    return {k: ("" if v == NO_RESPONSE else v) for k, v in out.items()}


def set_item_fields(path: str, item_id: str, fields: dict[str, str]) -> bool:
    """items/*.yaml の該当問題の status などを、ほかの行の書式を崩さずに書き換える。"""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    start = next((i for i, l in enumerate(lines) if l.strip() == f"- id: {item_id}"), None)
    if start is None:
        return False
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("- id:")), len(lines))
    keys = tuple(fields)
    body = lines[start:end]
    pos = next((i for i, l in enumerate(body) if l.startswith("  status:")), None)
    kept = [l for l in body if not any(l.startswith(f"  {k}:") for k in keys)]
    if pos is None:
        pos = len(kept)
        while pos > 1 and kept[pos - 1].strip() == "":
            pos -= 1
    else:
        pos = sum(1 for l in body[:pos] if not any(l.startswith(f"  {k}:") for k in keys))
    new = [f"  {k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()]
    lines[start:end] = kept[:pos] + new + kept[pos:]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return True
