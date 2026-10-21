"""GitHub 上で問題を監修するためのページ（review/*.md）を作る。

    python tools/make_review_pages.py [--facts <事実票のフォルダ>]

問題ごとに「この問題を監修する」、10問ごとに「まとめて承認する」のリンクを付ける。
リンクを開くと、問題IDと版が入った Issue フォームが開く。問題やカードの文章は書き換えない。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DEFAULT_FACTS, REPO, ROOT, is_current_approval, item_hash, load_domains, load_facts, load_items  # noqa: E402

OUT = os.path.join(ROOT, "review")
BATCH = 10
LETTERS = "abcde"
CARD_STATUS = {"draft": "出典照合前", "verified_sources": "出典照合済み", "verified_expert": "監修済み", "retired": "廃止"}


def issue_url(template: str, **fields: str) -> str:
    q = "&".join(f"{k}={quote(v, safe='')}" for k, v in fields.items())
    return f"https://github.com/{REPO}/issues/new?template={template}&{q}"


def block(it: dict, facts: dict[str, dict]) -> list[str]:
    h = item_hash(it, facts)
    if is_current_approval(it, facts):
        state = f"監修済み（{it.get('reviewer', '')}、{it.get('reviewed_at', '')}）"
    elif it.get("status") == "approved":
        state = "**監修後に問題または根拠カードが変わったため、再監修が必要**"
    else:
        state = "監修待ち"
    key = next((i for i, o in enumerate(it["options"]) if o["truth"] is it["ask"]), None)
    L = [f"### {it['id']}　{state}", "", f"**{it['stem']}**", ""]
    for i, o in enumerate(it["options"]):
        card = facts.get(o["fact"]) or {}
        st = CARD_STATUS.get((card.get("publication_info") or {}).get("status"), "不明")
        mark = "**（正答）**" if i == key else ""
        L.append(f"- **{LETTERS[i]}.** {o['text']}　— {'正しい記述' if o['truth'] else '誤った記述'}{mark}")
        L.append(f"  - 根拠 {o['fact']}（カード：{st}）：{(card.get('assertion') or {}).get('plain_statement_ja', '（カードが見つかりません）')}")
    L.append("")
    if not is_current_approval(it, facts):
        L.append(f"- [この問題を監修する]({issue_url('question-review.yml', title=f'[監修] {it['id']}', question_id=it['id'], version=h)})　（版 `{h}`）")
        L.append("")
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=DEFAULT_FACTS)
    args = ap.parse_args()
    facts = load_facts(args.facts)
    domains = load_domains(args.facts)
    items = [it for it in load_items() if it.get("status") != "retired"]
    os.makedirs(OUT, exist_ok=True)
    today = dt.date.today().isoformat()
    by_domain: dict[str, list[dict]] = collections.OrderedDict()
    for d in domains:
        by_domain[d] = [it for it in items if it["id"].split("-")[1] == d]
    index = ["# 問題の監修（GitHub 版）", "",
             f"更新：{today}（`python tools/make_review_pages.py` で作り直す。手で編集しない）", "",
             "## 監修のしかた", "",
             "1. 下の表から領域を選び、ページを開く。",
             "2. 問題文・選択肢・正答と、各選択肢の根拠カードを読み、問題として成り立っているか確認する"
             "（正答が1つに決まるか、誤りの選択肢が確かに誤りか、紛らわしい表現がないか）。",
             "3. 問題がなければ「**まとめて承認する**」を開き、監修者名を書いて送信する。直すべき問題は一覧から行を消す。",
             "4. 直すべき問題は「**この問題を監修する**」から「修正が必要」を選び、修正案を書いて送信する。",
             "5. 数分で自動的に記録され、サイトでも「監修済み」として出題される。", "",
             "承認したあとに問題文や根拠カードが変わると、自動で「監修前」に戻り、再監修の対象になる。", "",
             "| 分野 | 領域 | 問題数 | 監修済み | 監修待ち |", "|---|---|---|---|---|"]
    for d, its in by_domain.items():
        if not its:
            continue
        done = sum(is_current_approval(it, facts) for it in its)
        index.append(f"| {domains[d]['field']} | [{domains[d]['name']}]({d}.md) | {len(its)} | {done} | {len(its) - done} |")
        L = [f"# {domains[d]['name']}の問題の監修", "", f"[← 一覧に戻る](README.md)　更新：{today}", ""]
        pending: list[tuple[dict, str]] = []
        for it in its:
            L += block(it, facts)
            if not is_current_approval(it, facts):
                pending.append((it, item_hash(it, facts)))
            if len(pending) == BATCH:
                L += batch(pending)
                pending = []
        if pending:
            L += batch(pending)
        with open(os.path.join(OUT, f"{d}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(L) + "\n")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(index) + "\n")
    print(f"review/ を更新しました（{len(items)} 問）")


def batch(pending: list[tuple[dict, str]]) -> list[str]:
    lines = "\n".join(f"{it['id']} {h}" for it, h in pending)
    ids = f"{pending[0][0]['id']}〜{pending[-1][0]['id']}" if len(pending) > 1 else pending[0][0]["id"]
    url = issue_url("question-batch-approve.yml", title=f"[監修] まとめて承認 {ids}", questions=lines)
    return [f"**[ここまでの {len(pending)} 問（{ids}）をまとめて承認する]({url})**", "", "---", ""]


if __name__ == "__main__":
    main()
