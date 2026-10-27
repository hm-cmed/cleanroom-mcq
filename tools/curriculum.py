"""カリキュラムの読み込みと、問題の分類（ブループリント・コアカリ）。

- ブループリント：事実票の data/curriculum/kokushi_r6_blueprint.yaml（大項目ごとの出題割合）と
  kokushi_r6_items.yaml（小項目の番号・名称・レベル）。
  大項目の下には公式の割合がないため、「大項目の割合 × 小項目のレベルの重み（a=3、b=2、c=1）」で
  中項目（例：Ⅵ-6 肝疾患）ごとの目安を作る。この重みは当サイトの仮定で、config.js から変えられない
  （変えるときは README に理由を書く）。
- コアカリ：事実票の data/curriculum/core-curriculum の別表1（疾患表、TBL0100）と別表2（臓器別の学修項目）。
  公式の割合はないため、「表の項目数（基本●の疾患は2、それ以外は1）」をカテゴリごとの目安にする。
"""
from __future__ import annotations

import csv
import os
import re

import yaml

LEVEL_W = {"a": 3, "b": 2, "c": 1}
# 出題基準の大項目 → コアカリ疾患表（別表1）のカテゴリ。カードに疾患表の番号がないときの分類に使う（当サイトの対応づけ）
KOKUSHI_TO_CORE = {
    "Ⅵ-1": ("消化器系", "食道疾患"), "Ⅵ-2": ("消化器系", "胃・十二指腸疾患"), "Ⅵ-3": ("消化器系", "小腸・大腸疾患"),
    "Ⅵ-4": ("消化器系", "小腸・大腸疾患"), "Ⅵ-5": ("消化器系", "消化管共通疾患"), "Ⅵ-6": ("消化器系", "肝疾患"),
    "Ⅵ-7": ("消化器系", "胆道疾患"), "Ⅵ-8": ("消化器系", "膵臓疾患"), "Ⅵ-9": ("消化器系", "腹膜・腹壁・横隔膜疾患"),
    "Ⅵ-10": ("消化器系", "腹膜・腹壁・横隔膜疾患"),
    "Ⅴ-1": ("循環器系", "不整脈"), "Ⅴ-2": ("循環器系", "心不全"), "Ⅴ-3": ("循環器系", "先天性心疾患"),
    "Ⅴ-4": ("循環器系", "弁膜症"), "Ⅴ-5": ("循環器系", "虚血性心疾患"), "Ⅴ-6": ("循環器系", "心筋・心膜疾患"),
    "Ⅴ-7": ("循環器系", "高血圧症"), "Ⅴ-8": ("循環器系", "動脈疾患"),
    "Ⅳ-1": ("呼吸器系", "呼吸器感染症"), "Ⅳ-2": ("呼吸器系", "閉塞性換気障害・拘束性換気障害"),
    "Ⅳ-3": ("呼吸器系", "免疫学的機序による肺疾患"), "Ⅳ-4": ("呼吸器系", "閉塞性換気障害・拘束性換気障害"),
    "Ⅳ-5": ("呼吸器系", "肺循環障害"), "Ⅳ-6": ("腫瘍", "呼吸器系"),
    "Ⅳ-7": ("呼吸器系", "胸膜・縦隔疾患・横隔膜"), "Ⅳ-8": ("呼吸器系", "異常呼吸"),
}
# 疾患表の「腫瘍」の行を、臓器のカテゴリに振り分ける（疾患名に含まれる語で判定。先に書いたものを優先）
TUMOR_TO_CORE = [("食道", "食道疾患"), ("胃", "胃・十二指腸疾患"), ("大腸", "小腸・大腸疾患"), ("胆", "胆道疾患"),
                 ("肝", "肝疾患"), ("膵", "膵臓疾患")]
CORE_W = {"●": 2, "": 1}
SECTION_SHORT = {"必修の基本的事項": "必修", "医学総論": "総論", "医学各論": "各論"}
KOKUSHI_RE = re.compile(r"(必修の基本的事項|医学総論|医学各論)\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+|\d+)(?:-(\d+))?(?:-([A-Z]))?(?:-([①-⑳㉑-㉟]))?")
CORE_RE = re.compile(r"\b(TBL-\d{2}-\d{2}-\d{3}|PS-\d{2}-\d{2}-\d{2}|[A-Z]{2}-\d{2}-\d{2}-\d{2})\b")


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(facts_repo: str) -> dict:
    base = os.path.join(facts_repo, "data", "curriculum")
    out: dict = {"blueprint": None, "items": {}, "groups": {}, "tbl": {}, "checked": {}}
    bp_path = os.path.join(base, "kokushi_r6_blueprint.yaml")
    it_path = os.path.join(base, "kokushi_r6_items.yaml")
    if os.path.exists(bp_path):
        with open(bp_path, encoding="utf-8") as f:
            out["blueprint"] = yaml.safe_load(f)
        out["checked"]["blueprint"] = bool(out["blueprint"].get("checked"))
    if os.path.exists(it_path):
        with open(it_path, encoding="utf-8") as f:
            items = yaml.safe_load(f)
        out["checked"]["items"] = bool(items.get("checked"))
        for ch in items.get("chapters") or []:
            for g in ch.get("groups") or []:
                gid = f"{ch['id']}-{g['id']}"
                out["groups"][gid] = {"chapter": ch["id"], "chapter_name": ch["name"], "name": g["name"]}
                for it in g.get("items") or []:
                    out["items"][it["code"]] = {"name": it["name"], "level": it["level"], "group": gid}
    cc = os.path.join(base, "core-curriculum", "2022", "ja")
    for row in _read_csv(os.path.join(cc, "tables", "TBL0100.csv")):
        system, category, item = row.get("system", ""), row.get("category", ""), row.get("item", "")
        if system == "腫瘍":   # 腫瘍の行は、疾患名から臓器のカテゴリに振り分ける
            organ = next((cat for kw, cat in TUMOR_TO_CORE if kw in item), None)
            if category == "消化器系" and organ:
                system, category = "消化器系", organ
        out["tbl"][row["index"]] = {"system": system, "category": category, "item": item,
                                    "core": (row.get("core") or "").strip()}
    index = {r["index"]: r for r in _read_csv(os.path.join(cc, "tables", "index.csv"))}
    for tid, meta in index.items():
        if not tid.startswith("TBL-02-"):
            continue
        for row in _read_csv(os.path.join(cc, "tables", meta.get("file", ""))):
            out["tbl"][row["index"]] = {"system": meta.get("item", ""), "category": row.get("category", ""),
                                        "item": row.get("item", ""), "core": ""}
    return out


def kokushi_codes(text: str) -> list[dict]:
    """「医学各論 Ⅵ-6-C-①（肝細胞癌、a）；…」から番号を取り出す。"""
    res = []
    for m in KOKUSHI_RE.finditer(text or ""):
        sec, ch, grp, mid, small = m.groups()
        code = "-".join(x for x in (ch, grp, mid, small) if x)
        res.append({"section": sec, "chapter": ch, "group": f"{ch}-{grp}" if grp else ch, "code": code})
    return res


def core_codes(text: str) -> list[str]:
    return CORE_RE.findall(text or "")


def blueprint_strata(cur: dict) -> dict[str, dict]:
    """医学各論の大項目（例：Ⅵ-6 肝疾患）ごとの目安の重み。"""
    bp = cur.get("blueprint") or {}
    pct = {s["id"]: s["pct"] for s in (bp.get("sections") or {}).get("医学各論", [])}
    by_group: dict[str, float] = {}
    by_chapter: dict[str, float] = {}
    for code, it in cur["items"].items():
        g = it["group"]
        w = LEVEL_W.get(it["level"], 1)
        by_group[g] = by_group.get(g, 0) + w
        ch = cur["groups"][g]["chapter"]
        by_chapter[ch] = by_chapter.get(ch, 0) + w
    out = {}
    for g, w in by_group.items():
        meta = cur["groups"][g]
        ch = meta["chapter"]
        out[f"bp:{g}"] = {"label": f"医学各論 {g} {meta['name']}", "chapter": f"{ch} {meta['chapter_name']}",
                          "weight": round(pct.get(ch, 0) * w / by_chapter[ch], 4)}
    return out


def core_strata(cur: dict) -> dict[str, dict]:
    """コアカリの別表（疾患表・臓器別の学修項目）のカテゴリごとの目安の重み。"""
    out: dict[str, dict] = {}
    for idx, row in cur["tbl"].items():
        key = f"core:{row['system']}:{row['category']}"
        label = f"{row['system']}：{row['category']}"
        d = out.setdefault(key, {"label": label, "system": row["system"], "weight": 0})
        d["weight"] += CORE_W.get(row["core"], 1)
    return out


def classify(card: dict, cur: dict) -> dict:
    """事実カード1枚の分類（ブループリントの中項目・コアカリのカテゴリ・レベル・基本疾患か）。"""
    c = card.get("curriculum") or {}
    bp, level, sections = None, "", set()
    for k in kokushi_codes(c.get("kokushi") or ""):
        sections.add(SECTION_SHORT.get(k["section"], k["section"]))
        if k["section"] == "医学各論" and bp is None and k["code"] in cur["items"]:
            bp = f"bp:{cur['items'][k['code']]['group']}"
            level = cur["items"][k["code"]]["level"]
    # 疾患表（別表1）の基本●の行 → 疾患表の行 → 臓器別の学修項目（別表2）の順に、最初に見つかったもので分類する
    rows = [(code, cur["tbl"][code]) for code in core_codes(c.get("core_curriculum") or "") if code in cur["tbl"]]
    # （疾患表の番号がないときは、出題基準の大項目から対応するカテゴリを使う）
    disease = [cr for cr in rows if cr[0].startswith("TBL-01-")]
    core, basic = None, False
    if disease:
        code, row = min(disease, key=lambda cr: 0 if cr[1]["core"] == "●" else 1)
        core, basic = f"core:{row['system']}:{row['category']}", row["core"] == "●"
    elif bp and bp[3:] in KOKUSHI_TO_CORE:
        system, category = KOKUSHI_TO_CORE[bp[3:]]
        core = f"core:{system}:{category}"
    elif rows:
        core = f"core:{rows[0][1]['system']}:{rows[0][1]['category']}"
    return {"bp": bp, "level": level, "core": core, "basic": basic, "sections": sorted(sections)}
