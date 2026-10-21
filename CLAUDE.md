# CLAUDE.md — クリーンルーム5択ドリル

事実カード（hm-cmed/cleanroom-facts）から作った5択問題を、ブラウザだけで解答・自動採点・解説するサイト。利用者も保守する人も、プログラミングの初心者を想定する。

## 構成

- ビルド不要の静的ファイル（`index.html`、`js/app.js`、`js/config.js`、`css/style.css`、`data/questions.js`）を GitHub Pages で公開する。
- 問題の原本は `items/*.yaml`。`python tools/build.py` で事実票と照合し、`data/questions.js` を作る。`data/questions.js` は手で書き換えない。

## 守ること

1. 問題文・選択肢・解説の根拠は事実カードだけ。教科書・ガイドライン・国試過去問の文章を写さない。
2. 事実カードの主張文と数値をこのレポジトリで書き換えない。直す必要があれば cleanroom-facts 側で直す。
3. 正しい選択肢の数字は、根拠カードの数字と一致させる。照合（`tools/build.py` の `check`）のルールを緩める変更は、理由を README に書く。
4. `status: approved`、`reviewer`、`reviewed_at`、`reviewed_hash` は人間（監修者）だけが付ける。GitHub の監修フォーム（`.github/ISSUE_TEMPLATE/`）から監修者が送った内容を、`tools/apply_github_review.py` が転記する。手で書かない。
5. 一度付けた問題IDは使い回さない。廃止は `status: retired`。
6. 解答の記録を外部に送る機能を足さない。CSP の `connect-src 'none'` を外さない。`innerHTML` を使わない。
7. 画面の文言は平易な日本語にする。
8. 学年別の配分の重み（`tools/curriculum.py` の LEVEL_W・CORE_W・KOKUSHI_TO_CORE）は当サイトの仮定。変えるときは理由を README に書く。ブループリントと出題基準の数値は事実票の `data/curriculum/` だけを使い、このレポジトリに写さない。
