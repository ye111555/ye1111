import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# ---------- 核心业务逻辑 ----------
def get_token_by_password(username, password):
    url = "https://api.icampus.ltd/api/cloud/user/login"
    payload = {"phone": username, "password": password}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"HTTP错误 {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("message"))
    token = data["data"][0]["token"]
    return token

def fetch_orders(token):
    order_url = "https://api.icampus.ltd/api/hssdyzx/user/order_service/goods"
    params = {"payment": 2, "limit": 200, "index": 0}
    cookies = {"token": token}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(order_url, headers=headers, cookies=cookies, params=params)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("message"))
    return data.get("data", {}).get("list", [])

def generate_report(orders, date_list):
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
        table = o.get("food_table_name", "").strip()
        option = o.get("food_option_name", "").strip()
        meal = table if option == "默认选项" else f"{table} {option}"
        if "午餐" in period:
            schedule[date_str]["lunch"].append(meal)
        else:
            schedule[date_str]["dinner"].append(meal)
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    lines = []
    for date in date_list:
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = weekday_cn[dt.weekday()]
        lunch = "；".join(schedule[date]["lunch"]) if schedule[date]["lunch"] else "无"
        dinner = "；".join(schedule[date]["dinner"]) if schedule[date]["dinner"] else "无"
        lines.append((weekday, lunch, dinner))
    return lines

def get_week_dates():
    today = datetime.now().date()
    weekday = today.weekday()
    days_until_next_sunday = (6 - weekday) % 7
    if days_until_next_sunday == 0:
        next_sunday = today + timedelta(days=7)
    else:
        next_sunday = today + timedelta(days=days_until_next_sunday + 7)
    delta = (next_sunday - today).days + 1
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta)]

# ---------- 网页模板 ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>订餐查询</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: system-ui, sans-serif; max-width: 600px; margin: 2rem auto; padding: 1rem; }
        input, button { padding: 0.5rem; font-size: 1rem; margin: 0.5rem 0; width: 100%; box-sizing: border-box; }
        table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
        th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
        th { background: #f0f0f0; }
        .error { color: red; }
        .success { color: green; }
        .info { font-size: 0.9rem; margin: 1rem 0; }
        .logout { margin-top: 1rem; text-align: right; }
        a { color: #666; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h2>📅 未来一周订餐查询</h2>
    {% if not session.get('token') %}
        <form method="post" action="/login">
            <input type="text" name="username" placeholder="账号（手机号）" required autofocus>
            <input type="password" name="password" placeholder="密码" required>
            <label style="display: flex; align-items: center; gap: 0.5rem;">
                <input type="checkbox" name="remember" value="yes"> 记住我（30天内自动登录）
            </label>
            <button type="submit">登录并查询</button>
        </form>
    {% else %}
        <div class="info">✅ 已登录：{{ session.get('username', '') }}</div>
        <div class="logout"><a href="/logout">退出 / 切换账号</a></div>
    {% endif %}

    {% if error %}
        <div class="error">❌ {{ error }}</div>
    {% endif %}
    {% if table %}
        <div class="success">✅ 查询时间：{{ start_date }} ~ {{ end_date }}</div>
        <table>
            <tr><th>星期</th><th>午餐</th><th>晚餐</th></tr>
            {% for row in table %}
            <tr>
                <td>{{ row[0] }}</td>
                <td>{{ row[1] }}</td>
                <td>{{ row[2] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    if not session.get('token'):
        return render_template_string(HTML_TEMPLATE, session={})
    try:
        orders = fetch_orders(session['token'])
        date_list = get_week_dates()
        lines = generate_report(orders, date_list)
        start_date = date_list[0]
        end_date = date_list[-1]
        return render_template_string(HTML_TEMPLATE, session=session, table=lines, start_date=start_date, end_date=end_date)
    except Exception as e:
        session.clear()
        return render_template_string(HTML_TEMPLATE, session={}, error=f"登录状态已失效，请重新登录 ({str(e)})")

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    remember = request.form.get('remember') == 'yes'
    if not username or not password:
        return render_template_string(HTML_TEMPLATE, session={}, error="请填写账号和密码")
    try:
        token = get_token_by_password(username, password)
        session['token'] = token
        session['username'] = username
        if remember:
            session.permanent = True
        else:
            session.permanent = False
        return redirect(url_for('index'))
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, session={}, error=str(e))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)