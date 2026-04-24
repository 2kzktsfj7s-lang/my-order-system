import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- 1. 初始化設定 ---
MENU_FILE = "menu.xlsx"
DB_FILE = "orders_v223.db" 

if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'show_receipt' not in st.session_state:
    st.session_state.show_receipt = False
if 'receipt_text' not in st.session_state:
    st.session_state.receipt_text = ""

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  姓名 TEXT, 飲品 TEXT, 茶底 TEXT, 甜度 TEXT, 
                  冰量 TEXT, 加料 TEXT, 杯數 INTEGER, 備註 TEXT, 
                  金額 INTEGER, 時間 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_open', 'True')")
    conn.commit()
    conn.close()

if not os.path.exists(MENU_FILE):
    st.error(f"❌ 找不到 {MENU_FILE}！")
    st.stop()
init_db()

# --- 2. 核心功能函數 ---
def get_system_status():
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT value FROM settings WHERE key='is_open'").fetchone()
    conn.close()
    return res[0] == 'True'

def set_system_status(status):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE settings SET value=? WHERE key='is_open'", (str(status),))
    conn.commit()
    conn.close()

def parse_drink_options(drink_name):
    if "香橙青綠" in drink_name: return ["青茶", "綠茶"], False, "🍵 選擇茶底"
    if "柳橙/檸檬/蔓越莓" in drink_name: return ["柳橙", "檸檬", "蔓越莓"], False, "🍋 選擇口味"
    if "/" not in drink_name: return ["固定(不需選擇)"], True, "🍵 茶底"
    opts = []
    if "紅" in drink_name: opts.append("紅茶")
    if "綠" in drink_name: opts.append("綠茶")
    if "青" in drink_name: opts.append("青茶")
    if "烏" in drink_name: opts.append("烏龍茶")
    if "/冬瓜" in drink_name or "冬瓜/" in drink_name: opts.append("冬瓜茶")
    return (opts, False, "🍵 選擇茶底") if opts else (["固定(不需選擇)"], True, "🍵 茶底")

def get_clean_drink_name(drink_name, selection):
    if selection == "固定(不需選擇)": return drink_name
    if "柳橙/檸檬/蔓越莓" in drink_name: return drink_name.replace("柳橙/檸檬/蔓越莓", selection)
    if "香橙青綠" in drink_name: return drink_name.replace("青綠", selection)
    slash_idx = drink_name.find('/')
    if slash_idx != -1: return drink_name[:slash_idx-1].strip() + selection
    return f"{drink_name}({selection})"

# ✨ 彈跳視窗設定
@st.dialog("🎉 訂單已成功送出！")
def show_receipt_modal(receipt_str):
    st.markdown(receipt_str) # 使用 markdown 讓排版更漂亮
    if st.button("✅ 我確認好了，關閉視窗", use_container_width=True):
        st.session_state.show_receipt = False
        st.rerun()

st.set_page_config(page_title="上宇林點餐系統", page_icon="🍵", layout="wide")
st.title("🍵 上宇林點餐系統")

tab1, tab2 = st.tabs(["🛒 我要點餐", "📊 管理後台"])

# ==========================================
# 分頁一：前台點餐區
# ==========================================
with tab1:
    is_open = get_system_status()
    if st.session_state.show_receipt:
        st.balloons()
        show_receipt_modal(st.session_state.receipt_text)

    if not is_open:
        st.error("🚫 訂單已截止，目前不開放點餐。")
    else:
        st.subheader("👤 訂購人資訊")
        user_input = st.text_input("輸入您的稱呼 (單位/姓名)", placeholder="例如：USR/王小明")

        df_all = pd.read_excel(MENU_FILE)
        df_drinks = df_all[df_all["分類"] != "加料系列"]
        df_toppings = df_all[df_all["分類"] == "加料系列"]
        SWEET_OPTS = ["全糖", "少糖", "半糖", "微糖", "一分糖", "無糖"]
        ICE_OPTS = ["正常", "少冰", "微冰", "去冰(小碎冰)", "完全去冰", "溫", "熱"]

        categories = ["全部"] + list(df_drinks["分類"].unique())
        selected_cat = st.selectbox("📂 選擇系列", categories)
        if selected_cat == "養生熱飲系列":
            st.warning("🏮 提醒：此系列僅於 11月~隔年2月 供應。")
        
        filtered_drinks = df_drinks if selected_cat == "全部" else df_drinks[df_drinks["分類"] == selected_cat]
        drink_options = filtered_drinks.apply(lambda x: f"{x['品項']} (${x['價格']})", axis=1)
        selected_drink_full = st.selectbox("🥤 選擇品項", drink_options)
        drink_name_only = selected_drink_full.split(" ($")[0]

        with st.form("order_form", clear_on_submit=False):
            current_tea_opts, tea_disabled, tea_label = parse_drink_options(drink_name_only)
            col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1])
            with col1: tea_base = st.selectbox(tea_label, current_tea_opts, disabled=tea_disabled)
            with col2: sweetness = st.selectbox("🍬 甜度", SWEET_OPTS)
            with col3: ice_level = st.selectbox("🧊 冰量", ICE_OPTS)
            with col4: qty = st.number_input("🔢 杯數", min_value=1, value=1)
            
            topping_options = df_toppings.apply(lambda x: f"{x['品項']} (+${x['價格']})", axis=1).tolist()
            toppings = st.multiselect("➕ 加料", topping_options)
            note = st.text_input("📝 備註 (給主揪看)")
            
            if st.form_submit_button("➕ 加入待送清單", use_container_width=True):
                if not user_input: st.error("❌ 請填寫稱呼")
                else:
                    unit_price = int(selected_drink_full.split("$")[1].replace(")", "")) + sum([int(t.split("+$")[1].replace(")", "")) for t in toppings])
                    final_name = get_clean_drink_name(drink_name_only, tea_base)
                    st.session_state.cart.append({
                        "姓名": user_input, "飲品": final_name, "茶底": tea_base, 
                        "甜度": sweetness, "冰量": ice_level, 
                        "加料": ', '.join([t.split(" (+")[0] for t in toppings]) if toppings else '無', 
                        "杯數": qty, "備註": note, "金額": unit_price * qty
                    })
                    st.success("✅ 已加入清單")

        if st.session_state.cart:
            st.write("---")
            st.subheader("🛒 待送出清單")
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[["飲品", "甜度", "冰量", "加料", "杯數", "備註", "金額"]], use_container_width=True)
            
            if st.button("🚀 確認無誤，送出全部訂單", type="primary", use_container_width=True):
                try:
                    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    # ✨ ✨ 重點修復：在清空前組裝豪華明細 ✨ ✨
                    receipt_text = f"### 🧾 【{user_input}】的點餐清單\n"
                    receipt_text += f"訂單時間：{now}\n\n"
                    
                    for idx, item in enumerate(st.session_state.cart):
                        t_str = f" +{item['加料']}" if item['加料'] != "無" else ""
                        receipt_text += f"{idx+1}. **{item['飲品']}** ({item['甜度']}/{item['冰量']}){t_str} x{item['杯數']} — `${item['金額']}`\n"
                        # 寫入資料庫
                        c.execute("INSERT INTO orders (姓名, 飲品, 茶底, 甜度, 冰量, 加料, 杯數, 備註, 金額, 時間) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                                  (item["姓名"], item["飲品"], item["茶底"], item["甜度"], item["冰量"], item["加料"], item["杯數"], item["備註"], item["金額"], now))
                    
                    receipt_text += f"\n---\n### 💰 總計金額： **{cart_df['金額'].sum()}** 元\n"
                    receipt_text += "\n*(請截圖並準備零錢交給主揪！)*"
                    
                    conn.commit(); conn.close()
                    st.session_state.receipt_text = receipt_text
                    st.session_state.show_receipt = True
                    st.session_state.cart = []
                    st.rerun()
                except Exception as e: st.error(f"送出失敗: {e}")

# ==========================================
# 分頁二：管理後台 (編輯功能與一鍵全選)
# ==========================================
with tab2:
    st.subheader("📋 訂單管理後台")
    if st.text_input("🔑 密碼", type="password") == "520":
        st.success("🔓 驗證成功")
        status = get_system_status()
        if st.toggle("📢 開放接單中", value=status) != status:
            set_system_status(not status); st.rerun()

        st.write("---")
        conn = sqlite3.connect(DB_FILE)
        df_orders = pd.read_sql("SELECT * FROM orders", conn)
        conn.close()
        
        if not df_orders.empty:
            st.metric("💰 總金額", f"${df_orders['金額'].sum()}")
            st.write("💡 **直接修改下方表格內容並儲存。**")
            
            select_all = st.checkbox("☑️ 全選所有訂單")
            df_orders.insert(0, "選取", select_all)
            
            # 開放編輯
            edited_df = st.data_editor(df_orders, hide_index=True, use_container_width=True, disabled=["id", "時間"])
            
            col_save, col_del = st.columns([1, 1])
            with col_save:
                if st.button("💾 儲存修改內容", use_container_width=True):
                    try:
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, row in edited_df.iterrows():
                            c.execute("UPDATE orders SET 姓名=?, 飲品=?, 茶底=?, 甜度=?, 冰量=?, 加料=?, 杯數=?, 備註=?, 金額=? WHERE id=?",
                                      (row['姓名'], row['飲品'], row['茶底'], row['甜度'], row['冰量'], row['加料'], int(row['杯數']), row['備註'], int(row['金額']), int(row['id'])))
                        conn.commit(); conn.close()
                        st.success("✅ 修改已儲存！")
                        st.rerun()
                    except Exception as e: st.error(f"儲存失敗: {e}")
            
            with col_del:
                selected = edited_df[edited_df["選取"] == True]
                if st.button(f"🗑️ 刪除勾選 ({len(selected)})", type="primary", use_container_width=True):
                    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                    for _, row in selected.iterrows():
                        c.execute("DELETE FROM orders WHERE id=?", (int(row['id']),))
                    conn.commit(); conn.close(); st.rerun()
            
            st.write("---")
            st.write("📋 **LINE 清單**")
            summary = f"【上宇林 團購】\n總計: {df_orders['杯數'].sum()} 杯 / ${df_orders['金額'].sum()} 元\n" + "-"*20 + "\n"
            for _, r in df_orders.iterrows():
                summary += f"{r['姓名']}: {r['飲品']} ({r['甜度']}/{r['冰量']}) x{r['杯數']} - ${r['金額']}\n"
            st.code(summary)
    else: st.info("🔒 請輸入密碼解鎖")