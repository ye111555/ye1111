import streamlit as st
import requests
from datetime import datetime, timedelta

# ---------- 核心 API 调用 ----------
def login(username, password):
    url = "https://api.icampus.ltd/api/cloud/user/login"
    payload = {"phone": username, "password": password}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        st.error(f"登录失败：HTTP {resp.status_code}")
        return None
    data = resp.json()
    if data.get("code") != 0:
        st.error(f"登录失败：{data.get('message')}")
        return None
    token = data["data"][0]["token"]
    return token

def fetch_orders(token):
    url = "https://api.icampus.ltd/api/hssdyzx/user/order_service/goods"
    params = {"payment": 2, "limit": 200, "index": 0}
    cookies = {"token": token}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10)
    if resp.status_code != 200:
        st.error(f"订单接口错误：HTTP {resp.status_code}")
        return []
    data = resp.json()
    if data.get("code") != 0:
        st.error(f"订单接口错误：{data.get('message')}")
        return []
    return data.get("data", {}).get("list", [])

def get_date_range():
    """从今天到下周日（包含）"""
    today = datetime.now().date()
    weekday = today.weekday()  # 周一=0, 周日=6
    days_to_next_sunday = (6 - weekday) % 7
    if days_to_next_sunday == 0:
        next_sunday = today + timedelta(days=7)
    else:
        next_sunday = today + timedelta(days=days_to_next_sunday + 7)
    delta = (next_sunday - today).days + 1
    date_list = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta)]
    return date_list

def generate_table(orders, date_list):
    """返回表格数据（星期，午餐，晚餐）"""
    # 初始化
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    schedule = {date: {"lunch": [], "dinner": []} for date in date_list}

    # 过滤正餐并填充
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

    # 构建表格行
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

# 初始化 session_state 存储 token
if "token" not in st.session_state:
    st.session_state.token = None

# 登录表单（只有未登录时显示）
if st.session_state.token is None:
    with st.form("login_form"):
        username = st.text_input("账号（手机号）")
        password = st.text_input("密码", type="password")
        col1, col2 = st.columns(2)
        with col1:
            remember = st.checkbox("记住我（本次会话有效）")
        with col2:
            submitted = st.form_submit_button("登录")
        if submitted:
            if not username or not password:
                st.error("请填写完整")
            else:
                token = login(username, password)
                if token:
                    st.session_state.token = token
                    st.success("登录成功！")
                    st.rerun()
else:
    # 已登录，显示查询结果和退出按钮
    st.info(f"当前账号已登录，如需切换请点击下方退出按钮")
    if st.button("🚪 退出登录"):
        st.session_state.token = None
        st.rerun()

    with st.spinner("正在获取订餐数据..."):
        try:
            orders = fetch_orders(st.session_state.token)
            if not orders:
                st.warning("未找到任何订餐记录")
            else:
                date_list = get_date_range()
                table_data = generate_table(orders, date_list)
                # 显示日期范围
                st.write(f"📅 查询范围：{date_list[0]} 至 {date_list[-1]}")
                # 显示表格
                st.table({
                    "星期": [row[0] for row in table_data],
                    "午餐": [row[1] for row in table_data],
                    "晚餐": [row[2] for row in table_data]
                })
                # 增加导出 CSV 按钮
                import pandas as pd
                df = pd.DataFrame(table_data, columns=["星期", "午餐", "晚餐"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 下载为 CSV", data=csv, file_name="meal_plan.csv", mime="text/csv")
        except Exception as e:
            st.error(f"查询失败：{str(e)}")