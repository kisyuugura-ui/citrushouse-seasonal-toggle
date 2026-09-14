# citrushouse 季節メニュー自動切替

紀州の食体験サイト(citrus house / 紀州蔵〜粋sui〜)の**季節限定メニューのStripe決済リンク**を、
今日の日付(日本時間)に応じて毎朝自動で有効化/無効化する仕組みです。

- クラウド(GitHub Actions)上で動くので、PCやClaude Codeアプリを起動しておく必要はありません。
- ブラウザ操作は使わず、Stripe APIを直接呼び出します。
- 実行が**失敗したときだけ**、GitHubからアカウントのメールに通知が届きます(正常時は無通知)。

## 対象と販売期間(日本時間)

| 商品 | 販売期間 |
|---|---|
| 苺大福作り体験 | 2/1 〜 5/31 |
| 流しそうめん | 6/1 〜 10/30 |
| 梅仕事体験 | 5/21 〜 6/20 |
| 焼き芋 | 12/15 〜 2/15(年をまたぐ) |
| 串本産クエ鍋セット | 12/15 〜 2/15(年をまたぐ) |

期間の変更は `toggle.py` の `PRODUCTS` を編集してください。

## 実行タイミング

`.github/workflows/seasonal-toggle.yml` で毎日 07:17 JST に自動実行。
「Actions」タブから手動実行(Run workflow)もできます。

## 必要な設定(1回だけ)

Stripeの制限付きAPIキー(Payment Links の書き込み権限)を、
リポジトリの **Settings → Secrets and variables → Actions** に
`STRIPE_KEY` という名前で登録してください。
