# citrushouse 季節メニュー 承認式の切替

紀州の食体験サイト(citrus house / 紀州蔵〜粋sui〜)の**季節限定メニューのStripe決済リンク**を、
クラウド(GitHub Actions)上で毎朝点検する仕組みです。PCやClaude Codeアプリの起動は不要です。

## 動きかた

- **開始(オンにする)＝承認式**
  日付では自動オンにしません。開始予定日の約1ヶ月前から、GitHubのIssueで
  「そろそろ○○を始める時期です」とお知らせ(担当者にメールが届く)。
  実際のオンは、依頼者が「○○を始めて」と言ったときに手動ワークフローで行います。
- **終了(オフにする)＝自動**
  終了予定日を過ぎたら自動でオフ(売り止めなので承認不要でも安全)。
- **エラー時**は実行が失敗し、GitHubからアカウントのメールに通知が届きます
  (お知らせ用Issueとは別の経路)。

## 開始のお知らせタイミング

開始予定日の **28日前・14日前・当日**、その後はオンにするまで **週1回**。
オンにすると自動で止まります。

## 対象と期間(日本時間)

| 商品 | 開始 | 終了 |
|---|---|---|
| 苺大福作り体験 | 2/1 | 5/31 |
| 流しそうめん | 6/1 | 10/30 |
| 梅仕事体験 | 5/21 | 6/20 |
| 焼き芋 | 12/15 | 2/15(年またぎ) |
| 串本産クエ鍋セット | 12/15 | 2/15(年またぎ) |

期間の変更は `toggle.py` の `PRODUCTS` を編集してください。

## 構成

- `toggle.py` … 判定と実行の本体
  - `python toggle.py` … 毎日の点検(自動オフ＋開始リマインド)
  - `python toggle.py --set "商品名" on|off` … 手動でオン/オフ(manual-switchが使う)
  - `python toggle.py --calendar-check YYYY-MM-DD` … 日付判定のみ表示(検査用)
- `.github/workflows/seasonal-toggle.yml` … 毎日 07:17 JST の自動点検
- `.github/workflows/manual-switch.yml` … 「Actions」から手動でオン/オフ
- `status.json` … 各商品の実オン/オフ状態。サイトがこれを読んでボタン表示を切り替える
  (販売中=オレンジ「申し込む」/ 停止中=黒「提供期間外」・押下不可)

## サイトとの連動

食体験サイト(wakayamasyokutaiken.netlify.app)の各ボタンは、公開URL
`https://raw.githubusercontent.com/kisyuugura-ui/citrushouse-seasonal-toggle/main/status.json`
を読み、季節商品のボタンを自動で切り替える。toggle.py が Stripe の実状態を
GitHub Contents API 経由で status.json に書き出す(毎日の点検時と手動切替時)。
反映はCDNの都合で最大5分程度。サイト側のスラッグは toggle.py の `PRODUCTS` と一致させること。

## 必要な設定(1回だけ)

- Stripeの制限付きAPIキー(支払いリンクの書き込み権限)を、リポジトリの
  **Settings → Secrets and variables → Actions** に `STRIPE_KEY` として登録。
- 両ワークフローの `permissions:` は `contents: write`(status.json更新のため)。
  seasonal-toggle はさらに `issues: write`(開始リマインドのため)。
