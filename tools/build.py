"""問題ファイル（items/*.yaml）を事実票と照合し、ブラウザ用の data/questions.js を作る。

    python tools/build.py                       # 事実票は ../cleanroom-gi-facts を使う
    python tools/build.py --facts <事実票のフォルダ>

照合で「エラー」があれば data/questions.js は作らず、終了コード 1 で止まる。
「注意」は人が確認すべき点（監修の参考）で、ビルドは続ける。結果は reports/check_report.md に出す。

このスクリプトは、問題文・選択肢・事実カードの文章を書き換えない（照合と書き出しだけを行う）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DEFAULT_FACTS, ROOT, is_current_approval, item_hash, load_domains, load_facts, load_items  # noqa: E402

ID_RE = re.compile(r"^Q-[A-Z]{2}-\d{3}$")
FACT_RE = re.compile(r"^[A-Z]{2}-\d{3}$")
ITEM_STATUS = {"draft", "approved", "retired"}
# 正答の根拠にしてよい事実カードの状態（draft のカードは出典の照合が済んでいない）
KEY_FACT_OK = {"verified_sources", "verified_expert"}
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def norm(s: str) -> str:
    """全角・半角のゆれと、数字の桁区切りをそろえる（照合のためだけに使う）。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"(?<=\d),(?=\d{3})", "", s)


def numbers(s: str) -> set[str]:
    return set(NUM_RE.findall(norm(s)))


def has_number(text: str, num: str) -> bool:
    return re.search(r"(?<![\d.])%s(?![\d])" % re.escape(num), text) is not None


def git_head(path: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip() or None
    except Exception:
        return None


def card_text(card: dict) -> str:
    a = card.get("assertion") or {}
    return norm(" ".join(str(a.get(k) or "") for k in ("plain_statement_ja", "condition", "differential")))


def check(items: list[dict], facts: dict[str, dict], domains: dict[str, dict]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    seen: set[str] = set()
    for n, it in enumerate(items, 1):
        where = it.get("id") or f"{n}番目の問題"
        iid = it.get("id", "")
        if not ID_RE.match(iid) or iid.split("-")[1] not in domains:
            errors.append(f"{where}: ID は Q-<領域>-<3桁> の形にし、領域は事実票の data/domains.yaml にある接頭辞にしてください（例 Q-LV-001）")
        if iid in seen:
            errors.append(f"{where}: ID が重複しています")
        seen.add(iid)
        status = it.get("status")
        if status not in ITEM_STATUS:
            errors.append(f"{where}: status は draft / approved / retired のいずれかです")
        if status == "retired":
            continue
        if status == "approved" and not (it.get("reviewer") and it.get("reviewed_at") and it.get("reviewed_hash")):
            errors.append(f"{where}: approved にするには reviewer（監修者）・reviewed_at（日付）・reviewed_hash（版）が必要です。GitHub の監修フォームから承認してください")
        if not isinstance(it.get("ask"), bool):
            errors.append(f"{where}: ask は true（正しいのは）か false（誤っているのは）です")
        stem = str(it.get("stem") or "")
        if not stem.endswith("どれか。"):
            warns.append(f"{where}: 問題文が「〜どれか。」で終わっていません")
        if it.get("ask") is False and "誤" not in stem:
            warns.append(f"{where}: ask: false ですが、問題文に「誤っている」の語がありません")
        if it.get("ask") is True and "誤" in stem:
            warns.append(f"{where}: ask: true ですが、問題文に「誤」の字があります")
        opts = it.get("options") or []
        if len(opts) != 5:
            errors.append(f"{where}: 選択肢は5つにしてください（今は{len(opts)}つ）")
            continue
        keys = [i for i, o in enumerate(opts) if o.get("truth") is it.get("ask")]
        if len(keys) != 1:
            errors.append(f"{where}: 正答（ask と truth が一致する選択肢）が1つではありません（{len(keys)}つ）")
        texts = [norm(o.get("text")) for o in opts]
        if len(set(texts)) != 5:
            errors.append(f"{where}: 同じ文の選択肢があります")
        opt_facts: list[dict] = []
        for j, o in enumerate(opts):
            label = f"{where} 選択肢{'abcde'[j]}"
            if not isinstance(o.get("truth"), bool):
                errors.append(f"{label}: truth は true か false です")
            fid = str(o.get("fact") or "")
            card = facts.get(fid)
            if not FACT_RE.match(fid) or card is None:
                errors.append(f"{label}: 事実カード {fid or '（空）'} が見つかりません")
                continue
            opt_facts.append(card)
            st = (card.get("publication_info") or {}).get("status")
            if st == "retired":
                errors.append(f"{label}: 事実カード {fid} は廃止（retired）されています")
            elif st not in KEY_FACT_OK:
                (errors if j in keys else warns).append(
                    f"{label}: 事実カード {fid} は出典の照合が済んでいません（status: {st}）")
            ctext = card_text(card)
            for num in numbers(o.get("text")):
                if not has_number(ctext, num):
                    msg = f"{label}: 数字「{num}」が事実カード {fid} の主張文にありません"
                    if o.get("truth"):
                        errors.append(msg + "（正しい選択肢の数字はカードと一致させてください）")
                    else:
                        warns.append(msg + "（誤りの選択肢として意図したものか確認してください）")
        all_text = " ".join(card_text(c) for c in opt_facts)
        for num in numbers(stem):
            if not has_number(all_text, num):
                warns.append(f"{where}: 問題文の数字「{num}」が、選択肢の事実カードのどれにもありません")
    return errors, warns


def export(items: list[dict], facts: dict[str, dict], facts_rev: str | None, domains: dict[str, dict]) -> dict:
    used: dict[str, dict] = {}
    out_items = []
    for it in items:
        if it.get("status") == "retired":
            continue
        key = next(i for i, o in enumerate(it["options"]) if o["truth"] is it["ask"])
        key_card = facts[it["options"][key]["fact"]]
        cur = key_card.get("curriculum") or {}
        out_items.append({
            "id": it["id"],
            "domain": it["id"].split("-")[1],
            "ask": it["ask"],
            "stem": it["stem"],
            "options": [{"text": o["text"], "truth": o["truth"], "fact": o["fact"]} for o in it["options"]],
            "key": key,
            "kokushi": cur.get("kokushi") or "",
            "core": cur.get("core_curriculum") or "",
            "subdomain": key_card.get("subdomain") or "",
            # 監修後に問題や根拠カードが変わったものは「監修前」として出す（再監修が必要）
            "status": "approved" if is_current_approval(it, facts) else "draft",
            "stale": it["status"] == "approved" and not is_current_approval(it, facts),
            "reviewer": it.get("reviewer") or "",
            "reviewed_at": str(it.get("reviewed_at") or ""),
        })
        for o in it["options"]:
            card = facts[o["fact"]]
            p = card.get("provenance") or {}
            a = card.get("assertion") or {}
            used[card["id"]] = {
                "statement": a.get("plain_statement_ja") or "",
                "source": p.get("source") or "",
                "doi": p.get("doi") or "",
                "pmid": p.get("pmid") or "",
                "url": p.get("url") or "",
                "source_class": p.get("source_class") or "",
                "status": (card.get("publication_info") or {}).get("status") or "",
            }
    return {
        "built_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
        "facts_revision": facts_rev or "",
        "domains": {k: v["name"] for k, v in domains.items()},
        "fields": {k: v["field"] for k, v in domains.items()},
        "items": out_items,
        "facts": dict(sorted(used.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="問題を事実票と照合し、data/questions.js を作る")
    ap.add_argument("--facts", default=DEFAULT_FACTS,
                    help="事実票レポジトリのフォルダ（既定: ../cleanroom-gi-facts。環境変数 FACTS_DIR でも指定できる）")
    args = ap.parse_args()
    facts_dir = os.path.join(args.facts, "data", "facts")
    if not os.path.isdir(facts_dir):
        print(f"事実票のフォルダが見つかりません: {facts_dir}", file=sys.stderr)
        return 2
    facts = load_facts(args.facts)
    domains = load_domains(args.facts)
    items = load_items()
    errors, warns = check(items, facts, domains)
    for it in items:
        if it.get("status") == "approved" and it.get("reviewed_hash") and not is_current_approval(it, facts):
            warns.append(f"{it['id']}: 監修のあとに問題文・選択肢・根拠カードが変わりました（版 {it['reviewed_hash']} → {item_hash(it, facts)}）。"
                         "再監修までは「監修前」として出題します")

    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    live = [i for i in items if i.get("status") != "retired"]
    lines = ["# 照合レポート", "",
             f"- 実行日時: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"- 事実票: {len(facts)} 件（コミット {git_head(args.facts) or '不明'}）",
             f"- 問題: {len(live)} 問（監修済み {sum(is_current_approval(i, facts) for i in live)} 問）",
             f"- エラー: {len(errors)} 件 / 注意: {len(warns)} 件", "",
             "## エラー（直すまで公開用データを作りません）", ""]
    lines += [f"- {e}" for e in errors] or ["- なし"]
    lines += ["", "## 注意（監修のときに確認してください）", ""]
    lines += [f"- {w}" for w in warns] or ["- なし"]
    with open(os.path.join(ROOT, "reports", "check_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"問題 {len(live)} 問 / エラー {len(errors)} 件 / 注意 {len(warns)} 件（reports/check_report.md）")
    if errors:
        for e in errors[:20]:
            print("  エラー:", e)
        return 1
    data = export(items, facts, git_head(args.facts), domains)
    body = json.dumps(data, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "data", "questions.js"), "w", encoding="utf-8") as f:
        f.write("// このファイルは tools/build.py が作ります。直接書き換えないでください。\n")
        f.write("window.MCQ_DATA = " + body + ";\n")
    print("data/questions.js を作りました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
