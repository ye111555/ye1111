import streamlit as st
import requests
from datetime import datetime, timedelta
import time

# ---------- 公共请求头 ----------
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://wx.icampus.ltd/",
    "Origin": "https://wx.icampus.ltd"
}

def step1_login(username, password, retries=2):
    url = "https://api.icampus.ltd/api/cloud/user/login"
    payload = {"phone": username, "password": password}
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=60)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(data.get("message"))
            return data["data"][0]["token"]
        except requests.exceptions.Timeout:
            if attempt == retries-1:
                raise Exception("登录超时，请稍后重试")
            time.sleep(1)
        except Exception as e:
            raise e

def step2_exchange_order_token(auth_token, retries=2):
    url = "https://api.icampus.ltd/api/hssdyzx/login/user_login"
    payload = {"token": auth_token}
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=60)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(data.get("message"))
            order_token = data.get("data", {}).get("token") or data.get("token")
            if not order_token:
                raise Exception("响应中没有订单token")
            return order_token
        except requests.exceptions.Timeout:
            if attempt == retries-1:
                raise Exception("换取订单token超时，请稍后重试")
            time.sleep(1)
        except Exception as e:
            raise e

def fetch_orders(order_token, retries=2):
    url = "https://api.icampus.ltd/api/hssdyzx/user/order_service/goods"
    params = {"payment": 2, "limit": 200, "index": 0}
    headers = {
        **COMMON_HEADERS,
        "Authorization": f"Bearer {order_token}"
    }
    cookies = {"token": order_token}
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=60)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(data.get("message"))
            return data.get("data", {}).get("list", [])
        except requests.exceptions.Timeout:
            if attempt == retries-1:
                raise Exception("订单接口超时，请稍后重试")
            time.sleep(1)
        except Exception as e:
            raise e

def get_week_dates():
    today = datetime.now().date()
    weekday = today.weekday()
    days_to_next_sunday = (6 - weekday) % 7
    if days_to_next_sunday == 0:
        next_sunday = today + timedelta(days=7)
    else:
        next_sunday = today + timedelta(days=days_to_next_sunday + 7)
    delta = (next_sunday - today).days + 1
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta)]

def generate_table(orders, date_list):
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

# ---------- Streamlit UI ----------
st.set_page_config(page_title="智慧校园订餐查询", page_icon="🍱")
st.title("🍱 未来一周订餐查询")

if "order_token" not in st.session_state:
    st.session_state.order_token = None

if st.session_state.order_token is None:
    with st.form("login_form"):
        username = st.text_input("账号（手机号）")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            if not username or not password:
                st.error("请填写完整")
            else:
                with st.spinner("登录中，请稍候..."):
                    try:
                        auth_token = step1_login(username, password)
                        order_token = step2_exchange_order_token(auth_token)
                        st.session_state.order_token = order_token
                        st.success("登录成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"登录失败：{str(e)}")
else:
    st.info("✅ 已登录")
    if st.button("退出"):
        st.session_state.order_token = None
        st.rerun()

    with st.spinner("获取订餐数据..."):
        try:
            orders = fetch_orders(st.session_state.order_token)
            if not orders:
                st.warning("未找到任何订餐记录")
            else:
                date_list = get_week_dates()
                table = generate_table(orders, date_list)
                st.write(f"📅 查询日期范围：{date_list[0]} 至 {date_list[-1]}")
                st.table({
                    "星期": [row[0] for row in table],
                    "午餐": [row[1] for row in table],
                    "晚餐": [row[2] for row in table]
                })
                txt_lines = []
                for row in table:
                    txt_lines.append(f"{row[0]}\t{row[1]}\t{row[2]}")
                txt_content = "\n".join(txt_lines).encode('utf-8')
                st.download_button(
                    label="📥 下载 TXT",
                    data=txt_content,
                    file_name="meal_plan.txt",
                    mime="application/octet-stream"
                )
        except Exception as e:
            st.error(f"查询失败：{str(e)}")
