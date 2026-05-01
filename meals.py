import requests
from datetime import datetime, timedelta

# ---------- 公共请求头 ----------
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://wx.icampus.ltd/",
    "Origin": "https://wx.icampus.ltd"
}

def step1_login(username, password):
    """第一步：账号密码登录，获取 auth_token"""
    url = "https://api.icampus.ltd/api/cloud/user/login"
    payload = {"phone": username, "password": password}
    resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"登录失败 HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("message"))
    auth_token = data["data"][0]["token"]
    print("✅ 第一步登录成功，获取到 auth_token")
    return auth_token

def step2_exchange_order_token(auth_token):
    """第二步：用 auth_token 换取真正的订单 token"""
    url = "https://api.icampus.ltd/api/hssdyzx/login/user_login"
    payload = {"token": auth_token}
    resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"换取订单 token 失败 HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("message"))
    # 返回的 data 中可能直接是 token 字符串，或者嵌套在 data.data.token 中
    order_token = data.get("data", {}).get("token") or data.get("token")
    if not order_token:
        raise Exception("响应中没有找到订单 token")
    print("✅ 第二步换取订单 token 成功")
    return order_token

def fetch_orders(order_token):
    """第三步：用订单 token 获取第三方支付订单"""
    url = "https://api.icampus.ltd/api/hssdyzx/user/order_service/goods"
    params = {"payment": 2, "limit": 200, "index": 0}
    headers = {
        **COMMON_HEADERS,
        "Authorization": f"Bearer {order_token}"
    }
    cookies = {"token": order_token}
    resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"订单接口 HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("message"))
    orders = data.get("data", {}).get("list", [])
    print(f"✅ 获取到 {len(orders)} 条订单")
    return orders

def get_week_dates():
    """从今天到下周日（包含）"""
    today = datetime.now().date()
    weekday = today.weekday()
    days_to_next_sunday = (6 - weekday) % 7
    if days_to_next_sunday == 0:
        next_sunday = today + timedelta(days=7)
    else:
        next_sunday = today + timedelta(days=days_to_next_sunday + 7)
    delta = (next_sunday - today).days + 1
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta)]

def generate_report(orders, date_list):
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    schedule = {date: {"lunch": [], "dinner": []} for date in date_list}
    for o in orders:
        if o.get("food_table_id") == 0:
            continue
        period = o.get("period_name", "")
        if "午餐" not in period and "晚餐" not in period:
            continue
        date_str = o.get("plan_date") or o.get("created_at", "")[:10]
        if date_str not in schedule:
            continue
        table_name = o.get("food_table_name", "").strip()
        option = o.get("food_option_name", "").strip()
        meal = table_name if option == "默认选项" else f"{table_name} {option}"
        meal = meal.strip()
        if "午餐" in period:
            schedule[date_str]["lunch"].append(meal)
        else:
            schedule[date_str]["dinner"].append(meal)
    rows = []
    for date in date_list:
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = weekday_names[dt.weekday()]
        lunch = "；".join(schedule[date]["lunch"]) if schedule[date]["lunch"] else "无"
        dinner = "；".join(schedule[date]["dinner"]) if schedule[date]["dinner"] else "无"
        rows.append([weekday, lunch, dinner])
    return rows

def main():
    print("=" * 50)
    print("智慧校园订餐查询（自动登录版）")
    print("=" * 50)
    username = input("请输入账号（手机号）: ").strip()
    password = input("请输入密码: ").strip()
    try:
        auth_token = step1_login(username, password)
        order_token = step2_exchange_order_token(auth_token)
        orders = fetch_orders(order_token)
        if not orders:
            print("未找到任何订餐记录")
            return
        date_list = get_week_dates()
        table = generate_report(orders, date_list)
        print(f"\n查询日期范围：{date_list[0]} 至 {date_list[-1]}\n")
        print(f"{'星期':<4} {'午餐':<20} {'晚餐':<20}")
        for row in table:
            print(f"{row[0]:<4} {row[1]:<20} {row[2]:<20}")
    except Exception as e:
        print(f"❌ 出错：{e}")

if __name__ == "__main__":
    main()