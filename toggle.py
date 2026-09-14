#!/usr/bin/env python3
"""
季節限定メニューのStripe決済リンクを、今日の日付(日本時間)に応じて
自動で有効化/無効化するスクリプト。ブラウザ不要・Stripe APIを直接呼び出す。

- 期間内なのに無効 → 有効化
- 期間外なのに有効 → 無効化
- 一致していれば何もしない
- 何かエラーがあれば終了コード1で終わる(→ GitHub Actionsが失敗メールを送る)

APIキーは環境変数 STRIPE_KEY から読み込む(GitHub Secretsで設定)。
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

KEY = os.environ.get("STRIPE_KEY")
if not KEY:
    print("ERROR: 環境変数 STRIPE_KEY が設定されていません。", file=sys.stderr)
    sys.exit(1)

# (商品名, 決済リンクID, 販売期間(開始月, 開始日, 終了月, 終了日))
# 期間は日本時間で判定。12/15〜2/15 のように年をまたぐ場合も自動対応。
PRODUCTS = [
    ("苺大福作り体験",     "plink_1TwJQkBgho8oTryN1RKhQZIr", (2, 1, 5, 31)),
    ("流しそうめん",       "plink_1TwNdRBgho8oTryNRMClNBko", (6, 1, 10, 30)),
    ("梅仕事体験",         "plink_1TwNfvBgho8oTryNhvrTqBxr", (5, 21, 6, 20)),
    ("焼き芋",             "plink_1TwNlHBgho8oTryNSsfSe3Dk", (12, 15, 2, 15)),
    ("串本産クエ鍋セット", "plink_1TwgKyBgho8oTryNeyZ9xGPW", (12, 15, 2, 15)),
]


def in_window(month, day, win):
    sm, sd, em, ed = win
    cur = month * 100 + day
    start = sm * 100 + sd
    end = em * 100 + ed
    if start <= end:
        return start <= cur <= end
    # 年をまたぐ期間(例: 12/15〜2/15)
    return cur >= start or cur <= end


def stripe_api(method, path, data=None):
    url = "https://api.stripe.com" + path
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + KEY)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_jst = now_utc + datetime.timedelta(hours=9)
    month, day = now_jst.month, now_jst.day

    print(f"=== 季節メニュー自動切替 {now_jst:%Y-%m-%d %H:%M} JST ===")
    print(f"本日(JST): {month}/{day}")

    errors = []
    for name, plink, win in PRODUCTS:
        try:
            obj = stripe_api("GET", "/v1/payment_links/" + plink)
            current = bool(obj.get("active"))
            should = in_window(month, day, win)
            if current == should:
                state = "有効" if current else "無効"
                print(f"  {name}: 変更なし(すでに{state})")
            else:
                stripe_api("POST", "/v1/payment_links/" + plink,
                           {"active": "true" if should else "false"})
                action = "有効化" if should else "無効化"
                print(f"  {name}: {action}しました")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            print(f"  [エラー] {name}: {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)}件のエラーが発生しました。", file=sys.stderr)
        sys.exit(1)
    print("\n正常終了。")


if __name__ == "__main__":
    main()
