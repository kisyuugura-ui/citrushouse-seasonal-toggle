#!/usr/bin/env python3
"""
季節限定メニューのStripe決済リンクを管理するスクリプト。ブラウザ不要・Stripe APIを直接呼び出す。

【方針（2026-09-14 変更）】
- 開始(オンにする)は「承認式」。日付では自動オンにしない。
  開始予定日の約1ヶ月前から、GitHubのIssueで「そろそろ○○を始める時期です」と知らせる。
  実際のオンは、依頼者が「○○を始めて」と言ったときに manual-switch から行う。
- 終了(オフにする)は自動。終了予定日を過ぎたら自動でオフにする(売り止めなので安全)。
- 何かエラーがあれば終了コード1で終わる(→ GitHub Actionsが失敗メールを送る)。

【実行モード】
  python toggle.py                      … 毎日の点検(自動オフ＋開始リマインド)
  python toggle.py --set "名前" on|off   … 指定商品を手動でオン/オフ(manual-switchから使う)
  python toggle.py --calendar-check DATE … 日付判定のみを表示(検査用。Stripe/GitHub不要)

APIキーは環境変数 STRIPE_KEY から、GitHubトークンは GITHUB_TOKEN から読み込む。
"""
import os
import sys
import json
import base64
import datetime
import urllib.request
import urllib.parse
import urllib.error

# (商品名, スラッグ, 決済リンクID, 開始(月,日), 終了(月,日))
# スラッグはサイトのボタン(data-product)と status.json のキーに使う。変更しないこと。
# 期間は日本時間で判定。12/15〜2/15 のように年をまたぐ場合も自動対応。
PRODUCTS = [
    ("苺大福作り体験",     "ichigo-daifuku", "plink_1TwJQkBgho8oTryN1RKhQZIr", (2, 1),   (5, 31)),
    ("流しそうめん",       "nagashi-somen",  "plink_1TwNdRBgho8oTryNRMClNBko", (6, 1),   (10, 30)),
    ("梅仕事体験",         "umeshigoto",     "plink_1TwNfvBgho8oTryNhvrTqBxr", (5, 21),  (6, 20)),
    ("焼き芋",             "yakiimo",        "plink_1TwNlHBgho8oTryNSsfSe3Dk", (12, 15), (2, 15)),
    ("串本産クエ鍋セット", "kue-nabe",       "plink_1TwgKyBgho8oTryNeyZ9xGPW", (12, 15), (2, 15)),
]

# 開始リマインドを出す「開始日までの残り日数」(1ヶ月前と2週間前)
PRE_START_REMIND_DAYS = (28, 14)


# ---------- 日付ヘルパー ----------

def in_window(today, start_md, end_md):
    """today(date)が販売期間[start, end]内か。年をまたぐ期間にも対応。"""
    cur = today.month * 100 + today.day
    s = start_md[0] * 100 + start_md[1]
    e = end_md[0] * 100 + end_md[1]
    if s <= e:
        return s <= cur <= e
    return cur >= s or cur <= e  # 例: 12/15〜2/15


def _occurrences(md, today):
    cands = []
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            cands.append(datetime.date(y, md[0], md[1]))
        except ValueError:
            pass
    return cands


def days_to_next(md, today):
    """今日から次に md(月,日) が来るまでの日数(今日ならば0)。"""
    future = [c for c in _occurrences(md, today) if c >= today]
    return (min(future) - today).days


def days_since_prev(md, today):
    """直近に過ぎた md(月,日) から今日までの日数(今日ならば0)。"""
    past = [c for c in _occurrences(md, today) if c <= today]
    return (today - max(past)).days


def season_year(today, start_md, end_md):
    """このシーズンを識別する年(開始日の年)。Issueの重複防止に使う。"""
    if in_window(today, start_md, end_md):
        past = [c for c in _occurrences(start_md, today) if c <= today]
        return max(past).year
    future = [c for c in _occurrences(start_md, today) if c >= today]
    return min(future).year


def decide(today, current_active, start_md, end_md):
    """
    今日の状態から取るべき行動を返す。
    戻り値: ("auto_off" | "remind_start" | "none", 説明文)
    current_active: 現在Stripeで有効かどうか(True/False)。judge用にNoneも可。
    """
    inwin = in_window(today, start_md, end_md)
    dtns = days_to_next(start_md, today)
    if current_active:
        # 期間外で、かつ開始1ヶ月前より前 → 自動オフ(終了処理／季節外れの消し忘れ対策)
        if (not inwin) and dtns > max(PRE_START_REMIND_DAYS):
            return ("auto_off", "販売期間を過ぎたため無効化")
        return ("none", "販売中(または開始準備中)のため変更なし")
    else:
        # オフのとき: 開始が近い/来ているなら開始リマインド
        dsps = days_since_prev(start_md, today)
        pre = dtns in PRE_START_REMIND_DAYS
        on_or_after = inwin and (dsps % 7 == 0)  # 開始日と、その後オンにするまで週1
        if pre or on_or_after:
            return ("remind_start", "開始時期のお知らせ対象")
        return ("none", "販売期間外のため変更なし")


# ---------- Stripe API ----------

def stripe_api(method, path, data=None):
    key = os.environ.get("STRIPE_KEY")
    if not key:
        raise RuntimeError("環境変数 STRIPE_KEY が設定されていません。")
    url = "https://api.stripe.com" + path
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ---------- GitHub Issue(開始リマインドの通知) ----------

def _github(method, path, data=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN / GITHUB_REPOSITORY が設定されていません。")
    url = "https://api.github.com" + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "citrushouse-seasonal-toggle")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def notify_start(name, today, start_md):
    """開始リマインドのIssueを作成、既にあればコメントを追加。owner宛にメール通知が届く。"""
    repo = os.environ["GITHUB_REPOSITORY"]
    owner = repo.split("/")[0]
    yr = season_year(today, start_md, start_md)  # 開始日基準の年
    title = f"【開始のお知らせ】{name}（{yr}年シーズン）"

    # 既存の未クローズIssueを探す(タイトル完全一致)
    issues = _github("GET", f"/repos/{repo}/issues?state=open&per_page=100")
    existing = next((i for i in issues if i.get("title") == title and "pull_request" not in i), None)

    msg = (f"@{owner} **{name}** の販売開始が近づいています（予定日 {start_md[0]}/{start_md[1]}）。\n\n"
           f"食材の手配ができ次第、Claude Codeに「**{name}を始めて**」とお伝えください。\n"
           f"準備中は毎回このお知らせが届きます。オンにすると自動で止まります。\n\n"
           f"（本日 {today:%Y-%m-%d} 時点の自動お知らせ）")

    if existing:
        _github("POST", f"/repos/{repo}/issues/{existing['number']}/comments", {"body": msg})
        return f"Issue #{existing['number']} にコメント追加"
    created = _github("POST", f"/repos/{repo}/issues",
                      {"title": title, "body": msg, "assignees": [owner]})
    return f"Issue #{created['number']} を新規作成"


# ---------- サイト用の販売状態ファイル(status.json) ----------

def write_status(states):
    """status.json を更新(既存とマージ)。サイトがボタン表示を切り替えるために読む公開ファイル。"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("  (GITHUB_TOKEN未設定のため status.json 更新はスキップ)")
        return
    path = f"/repos/{repo}/contents/status.json"
    sha = None
    products = {}
    try:
        cur = _github("GET", path)
        sha = cur.get("sha")
        products = json.loads(base64.b64decode(cur["content"]).decode()).get("products", {})
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    products.update(states)
    body = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "products": products,
    }
    content_b64 = base64.b64encode(
        json.dumps(body, ensure_ascii=False, indent=2).encode()).decode()
    payload = {"message": "update status.json", "content": content_b64}
    if sha:
        payload["sha"] = sha
    _github("PUT", path, payload)
    print("  status.json を更新しました")


# ---------- 各モード ----------

def now_jst():
    forced = os.environ.get("FORCE_DATE")
    if forced:
        return datetime.datetime.strptime(forced, "%Y-%m-%d")
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)


def run_daily():
    today = now_jst().date()
    # SKIP_STRIPE=1 のときはStripeに一切触れず、全商品オフとみなして通知だけ検証する(テスト用・安全)
    skip_stripe = os.environ.get("SKIP_STRIPE") == "1"
    print(f"=== 季節メニュー点検 {today:%Y-%m-%d}(JST){' [テスト:Stripe未接続]' if skip_stripe else ''} ===")
    errors = []
    states = {}
    for name, slug, plink, s_md, e_md in PRODUCTS:
        try:
            if skip_stripe:
                current = False
            else:
                obj = stripe_api("GET", "/v1/payment_links/" + plink)
                current = bool(obj.get("active"))
            action, why = decide(today, current, s_md, e_md)
            if action == "auto_off":
                stripe_api("POST", "/v1/payment_links/" + plink, {"active": "false"})
                current = False
                print(f"  {name}: 無効化しました（終了）")
            elif action == "remind_start":
                result = notify_start(name, today, s_md)
                print(f"  {name}: 開始リマインド送信（{result}）")
            else:
                state = "有効" if current else "無効"
                print(f"  {name}: 変更なし（現在{state}・{why}）")
            if not skip_stripe:
                states[slug] = current
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            print(f"  [エラー] {name}: {e}", file=sys.stderr)
    # サイト用の販売状態を実状態で書き出す
    if not skip_stripe and states:
        try:
            write_status(states)
        except Exception as e:  # noqa: BLE001
            errors.append(f"status.json: {e}")
            print(f"  [エラー] status.json: {e}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)}件のエラーが発生しました。", file=sys.stderr)
        sys.exit(1)
    print("\n正常終了。")


def run_set(name_arg, onoff):
    if onoff not in ("on", "off"):
        print("使い方: --set \"商品名\" on|off", file=sys.stderr)
        sys.exit(1)
    match = next((p for p in PRODUCTS if p[0] == name_arg), None)
    if not match:
        print(f"該当商品がありません: {name_arg}", file=sys.stderr)
        print("有効な商品名: " + " / ".join(p[0] for p in PRODUCTS), file=sys.stderr)
        sys.exit(1)
    name, slug, plink = match[0], match[1], match[2]
    active = "true" if onoff == "on" else "false"
    stripe_api("POST", "/v1/payment_links/" + plink, {"active": active})
    obj = stripe_api("GET", "/v1/payment_links/" + plink)
    now = "有効" if obj.get("active") else "無効"
    print(f"{name} を {'有効化' if onoff=='on' else '無効化'} しました。現在の状態: {now}")
    if (obj.get("active") is True) != (onoff == "on"):
        print("反映が確認できませんでした。", file=sys.stderr)
        sys.exit(1)
    # サイト用の販売状態も更新
    write_status({slug: bool(obj.get("active"))})


def run_calendar_check(date_str):
    today = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    print(f"=== 日付判定チェック {today:%Y-%m-%d} ===")
    print(f"{'商品':<18}{'期間内':<7}{'開始まで':<9}{'ONの時':<14}{'OFFの時'}")
    for name, _slug, _plink, s_md, e_md in PRODUCTS:
        inwin = "はい" if in_window(today, s_md, e_md) else "いいえ"
        dtns = days_to_next(s_md, today)
        if_on, _ = decide(today, True, s_md, e_md)
        if_off, _ = decide(today, False, s_md, e_md)
        label = {"auto_off": "自動オフ", "remind_start": "開始通知", "none": "変更なし"}
        print(f"{name:<18}{inwin:<7}{str(dtns)+'日':<9}{label[if_on]:<14}{label[if_off]}")


def main():
    args = sys.argv[1:]
    if not args:
        run_daily()
    elif args[0] == "--set" and len(args) == 3:
        run_set(args[1], args[2])
    elif args[0] == "--calendar-check" and len(args) == 2:
        run_calendar_check(args[1])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
