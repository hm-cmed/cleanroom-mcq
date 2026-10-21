"""GitHub の Issue フォームで送られた問題の監修結果を items/*.yaml に反映する（GitHub Actions から呼ぶ）。

    python tools/apply_github_review.py --event "$GITHUB_EVENT_PATH" --permission write --out result.md

- 承認：送られた「版」が今の問題の版（問題文・選択肢・根拠カードから計算）と一致するときだけ、
  status: approved、reviewer、reviewed_at、reviewed_hash を書く。問題文や選択肢は変えない。
- 修正が必要／廃止すべき：問題は変えず、proposals/ に修正案のファイルを作る。
- レポジトリへの書き込み権限（write 以上）がない人の送信は反映しない（公開レポジトリのため）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DEFAULT_FACTS, ROOT, is_current_approval, item_hash, load_facts, load_items, parse_form, set_item_fields  # noqa: E402

ALLOWED = {"admin", "maintain", "write"}
JST = dt.timezone(dt.timedelta(hours=9))
ID_RE = re.compile(r"^Q-[A-Z]{2}-\d{3}$")
VER_RE = re.compile(r"^[0-9a-f]{10}$")


def set_output(**kv: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(kv)
        return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--permission", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--facts", default=DEFAULT_FACTS)
    args = ap.parse_args()
    ev = json.loads(open(args.event, encoding="utf-8").read())
    issue = ev.get("issue") or {}
    number = issue.get("number")
    login = (ev.get("sender") or {}).get("login") or "unknown"
    form = parse_form(issue.get("body") or "")
    msg: list[str] = []

    def finish(changed: bool, close: bool, labels: str = "") -> int:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(msg) + "\n")
        set_output(changed="true" if changed else "false", close="true" if close else "false", labels=labels)
        return 0

    if args.permission not in ALLOWED:
        msg.append(f"ご報告ありがとうございます。@{login} さんは監修者として登録されていないため、この内容は自動では反映せず、"
                   "管理者が確認します。")
        return finish(False, False, "要確認")
    reviewer = re.sub(r"[\r\n\t]+", " ", form.get("監修者名", "")).strip()[:60]
    if not reviewer:
        msg.append("監修者名が空のため、反映していません。Issue を編集して監修者名を書いてください。")
        return finish(False, False)
    if "[x]" not in form.get("確認", "").lower():
        msg.append("「確認」のチェックが入っていないため、反映していません。")
        return finish(False, False)

    targets: list[tuple[str, str]] = []
    if "まとめて承認する問題" in form:
        judge = "承認"
        for line in form["まとめて承認する問題"].splitlines():
            parts = line.strip().split()
            if parts:
                targets.append((parts[0], parts[1] if len(parts) > 1 else ""))
    else:
        j = form.get("判定", "")
        judge = "承認" if j.startswith("承認") else "修正" if j.startswith("修正") else "廃止" if j.startswith("廃止") else ""
        targets.append((form.get("問題ID", "").strip(), form.get("確認した版", "").strip()))
    if not judge or not targets or len(targets) > 100:
        msg.append("判定または問題IDが読み取れませんでした（まとめて承認は100問まで）。フォームから送信してください。")
        return finish(False, False)

    facts = load_facts(args.facts)
    items = {it["id"]: it for it in load_items()}
    today = dt.datetime.now(JST).date().isoformat()
    who = f"{reviewer}（GitHub @{login}）"
    done, already, problems = [], [], []
    for qid, ver in targets:
        it = items.get(qid)
        if not ID_RE.match(qid) or it is None:
            problems.append(f"`{qid}`：このIDの問題はありません")
            continue
        h = item_hash(it, facts)
        if it.get("status") == "retired":
            problems.append(f"`{qid}`：廃止された問題です")
            continue
        if not VER_RE.match(ver) or ver != h:
            problems.append(f"`{qid}`：確認した版（`{ver or '空'}`）が今の問題（`{h}`）と違います。監修ページを開き直して確認してください")
            continue
        if judge == "承認":
            if is_current_approval(it, facts):
                already.append(qid)
                continue
            set_item_fields(it["_file"], qid, {"status": "approved", "reviewer": who, "reviewed_at": today, "reviewed_hash": h})
            done.append(qid)
        else:
            os.makedirs(os.path.join(ROOT, "proposals"), exist_ok=True)
            with open(os.path.join(ROOT, "proposals", f"github_review_{qid}_issue{number}.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join([
                    f"# 監修からの{'修正' if judge == '修正' else '廃止'}の提案：{qid}（Issue #{number}）", "",
                    f"- 監修者：{who}", f"- 日付：{today}", f"- 確認した版：`{h}`", "",
                    "## 修正案", "", form.get("修正案", "") or "（記入なし）", "",
                    "## コメント", "", form.get("コメント", "") or "（記入なし）", "",
                    "問題は書き換えていない。反映には担当者の判断が必要。", ""]))
            done.append(qid)

    if judge == "承認":
        if done:
            msg += [f"{reviewer} さんの監修を記録しました（{today}）。次の問題を「監修済み」にしました：", ""]
            msg += [f"- {x}" for x in done]
        if already:
            if msg:
                msg.append("")
            msg.append("すでに同じ内容で監修済みの問題：" + "、".join(already))
    elif done:
        msg.append(f"修正案として記録しました（`proposals/github_review_{done[0]}_issue{number}.md`）。問題の文章は変えていません。")
    if problems:
        msg += ["", "**反映できなかったもの**", ""] + [f"- {p}" for p in problems]
    if not msg:
        msg.append("反映するものがありませんでした。")
    close = judge == "承認" and not problems
    labels = "監修済み" if close else ("修正案" if judge != "承認" and done else "要確認")
    return finish(bool(done), close, labels)


if __name__ == "__main__":
    raise SystemExit(main())
