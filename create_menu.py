import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import datetime

# --- 1. 初始化設定 ---
MENU_FILE = "menu.xlsx"
DB_FILE = "orders_v221.db" # 延用您的資料庫

# 初始化暫存
if 'cart' not in st.session_state: st.session_state.cart = []
if 'show_receipt' not in st.session_state: st.session_state.show_receipt = False
if 'receipt_text' not in st.session_state: st.session_state.receipt_text = ""

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
    conn.commit(); conn.close()

if not os.path.exists(MENU_FILE):
    st.error(f"❌ 找不到 {MENU_FILE}！"); st.stop()
init_db()

# --- 2. 核心功能 ---
def get_system_status():
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT value FROM settings WHERE key='is_open'").fetchone()
    conn.close(); return res[0] == 'True'

def set_system_status(status):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE settings SET value=? WHERE key='is_open'", (str(status),))
    conn.commit(); conn.close()

def parse_drink_options(drink_name):
    if "香橙青綠" in drink_name: return ["青茶", "綠茶"], False, "🍵 茶底"
    if "柳橙/檸檬/蔓越莓" in drink_name: return ["柳橙", "檸檬", "蔓越莓"], False, "🍋 口味"
    if "/" not in drink_name: return ["固定"], True, "🍵 茶底"
    opts = []
    if "紅" in drink_name: opts.append("紅茶")
    if "綠" in drink_name: opts.append("綠茶")
    if "青" in drink_name: opts.append("青茶")
    if "烏" in drink_name: opts.append("烏龍茶")
    if "/冬瓜" in drink_name or "冬瓜/" in drink_name: opts.append("冬瓜茶")
    return (opts, False, "🍵 茶底") if opts else (["固定"], True, "🍵 茶底")

def get_clean_drink_name(drink_name, selection):
    if selection == "固定": return drink_name
    if "柳橙/檸檬/蔓越莓" in drink_name: return drink_name.replace("柳橙/檸檬/蔓越莓", selection)
    if "香橙青綠" in drink_name: return drink_name.replace("青綠", selection)
    slash_idx = drink_name.find('/')
    if slash_idx != -1: return drink_name[:slash_idx-1].strip() + selection
    return f"{drink_name}({selection})"

@st.dialog("🎉 訂單已成功送出！")
def show_receipt_modal(receipt_str):
    st.markdown(receipt_str)
    if st.button("✅ 關閉", use_container_width=True):
        st.session_state.show_receipt = False; st.rerun()

st.set_page_config(page_title="上宇林點餐系統", page_icon="🍵", layout="wide")
st.title("🍵 上宇林點餐系統 (V2.25)")

tab1, tab2 = st.tabs(["🛒 我要點餐", "📊 管理後台"])

# ==========================================
# 分頁一：前台 (內容同 V2.24，略)
# ==========================================
with tab1:
    is_open = get_system_status()
    if st.session_state.show_receipt:
        st.balloons(); show_receipt_modal(st.session_state.receipt_text)

    if not is_open:
        st.error("🚫 訂單已截止。")
    else:
        # [此處保留您原本的點餐表單與購物車邏輯...]
        user_input = st.text_input("輸入您的稱呼", placeholder="例如：USR/王小明")
        df_all = pd.read_excel(MENU_FILE)
        df_drinks = df_all[df_all["分類"] != "加料系列"]
        df_toppings = df_all[df_all["分類"] == "加料系列"]
        
        selected_cat = st.selectbox("📂 1. 選擇系列", ["全部"] + list(df_drinks["分類"].unique()))
        filtered_drinks = df_drinks if selected_cat == "全部" else df_drinks[df_drinks["分類"] == selected_cat]
        selected_drink_full = st.selectbox("🥤 2. 選擇品項", filtered_drinks.apply(lambda x: f"{x['品項']} (${x['價格']})", axis=1))
        drink_name_only = selected_drink_full.split(" ($")[0]

        with st.form("order_form"):
            current_tea_opts, tea_disabled, tea_label = parse_drink_options(drink_name_only)
            col1, col2, col3, col4 = st.columns(4)
            with col1: tea_base = st.selectbox(tea_label, current_tea_opts, disabled=tea_disabled)
            with col2: sweetness = st.selectbox("🍬 甜度", ["全糖", "少糖", "半糖", "微糖", "一分糖", "無糖"])
            with col3: ice_level = st.selectbox("🧊 冰量", ["正常", "少冰", "微冰", "去冰(小碎冰)", "完全去冰", "溫", "熱"])
            with col4: qty = st.number_input("🔢 杯數", min_value=1, value=1)
            toppings = st.multiselect("➕ 加料", df_toppings.apply(lambda x: f"{x['品項']} (+${x['價格']})", axis=1).tolist())
            note = st.text_input("📝 備註")
            
            if st.form_submit_button("➕ 加入待送清單", use_container_width=True):
                if user_input:
                    price = int(selected_drink_full.split("$")[1].replace(")", "")) + sum([int(t.split("+$")[1].replace(")", "")) for t in toppings])
                    st.session_state.cart.append({"姓名": user_input, "飲品": get_clean_drink_name(drink_name_only, tea_base), "甜度": sweetness, "冰量": ice_level, "加料": ', '.join([t.split(" (+")[0] for t in toppings]) if toppings else '無', "杯數": qty, "備註": note, "金額": price * qty})
                    st.success("✅ 已加入")
                else: st.error("❌ 填寫姓名")

        if st.session_state.cart:
            st.dataframe(pd.DataFrame(st.session_state.cart), use_container_width=True)
            if st.button("🚀 送出全部訂單", type="primary", use_container_width=True):
                conn = sqlite3.connect(DB_FILE); c = conn.cursor(); now = datetime.now().strftime("%m/%d %H:%M")
                receipt = "### 🧾 您的明細\n"
                for i in st.session_state.cart:
                    receipt += f"- {i['飲品']} ({i['甜度']}/{i['冰量']}) x{i['杯數']} — ${i['金額']}\n"
                    c.execute("INSERT INTO orders (姓名, 飲品, 茶底, 甜度, 冰量, 加料, 杯數, 備註, 金額, 時間) VALUES (?,?,?,?,?,?,?,?,?,?)", (i["姓名"], i["飲品"], i["茶底"], i["甜度"], i["冰量"], i["加料"], i["杯數"], i["備註"], i["金額"], now))
                conn.commit(); conn.close(); st.session_state.receipt_text = receipt; st.session_state.show_receipt = True; st.session_state.cart = []; st.rerun()

# ==========================================
# 分頁二：管理後台 (✨ 新增匯出列印功能)
# ==========================================
with tab2:
    if st.text_input("🔑 密碼", type="password") == "520":
        st.success("🔓 驗證成功")
        # 1. 狀態與數據
        conn = sqlite3.connect(DB_FILE); df_orders = pd.read_sql("SELECT * FROM orders", conn); conn.close()
        
        # 2. 營運開關與過濾 (略，同 V2.24)
        status = get_system_status()
        if st.toggle("📢 開放接單", value=status) != status: set_system_status(not status); st.rerun()

        if not df_orders.empty:
            st.write("---")
            st.subheader("🖨️ 列印與匯出專區")
            
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                # ✨ 功能 A：匯出 Excel
                # 我們使用 Excel 格式，並先進行簡單的排序
                df_export = df_orders.copy().sort_values(by="時間", ascending=False)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='訂單明細')
                
                st.download_button(
                    label="📥 下載 Excel 訂單檔案",
                    data=output.getvalue(),
                    file_name=f"上宇林訂單_{datetime.now().strftime('%m%d_%H%m')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col_ex2:
                # ✨ 功能 B：列印友善模式
                show_print_view = st.checkbox("🔍 開啟列印友善預覽 (關閉選單，方便 Ctrl+P)")

            if show_print_view:
                st.info("💡 提示：開啟後請直接按鍵盤 `Ctrl + P` (或手機列印功能)，即可印出下方純淨表格。")
                # 這裡顯示一個完全不帶按鈕、乾淨的表格供瀏覽器列印
                print_df = df_orders[["姓名", "飲品", "甜度", "冰量", "加料", "杯數", "備註", "金額"]].copy()
                st.table(print_df) # 使用 st.table 會比 st.dataframe 更適合直接列印
            else:
                # 原本的編輯器與管理功能
                st.write("---")
                select_all = st.checkbox("☑️ 全選")
                df_orders.insert(0, "選取", select_all)
                edited_df = st.data_editor(df_orders, hide_index=True, use_container_width=True, disabled=["id", "時間"])
                
                col_save, col_del = st.columns(2)
                with col_save:
                    if st.button("💾 儲存修改", use_container_width=True):
                        # (儲存邏輯同 V2.19...)
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, row in edited_df.iterrows():
                            c.execute("UPDATE orders SET 姓名=?, 飲品=?, 甜度=?, 冰量=?, 加料=?, 杯數=?, 備註=?, 金額=? WHERE id=?", (row['姓名'], row['飲品'], row['甜度'], row['冰量'], row['加料'], int(row['杯數']), row['備註'], int(row['金額']), int(row['id'])))
                        conn.commit(); conn.close(); st.success("已儲存！"); st.rerun()
                
                with col_del:
                    if st.button("🗑️ 刪除勾選", type="primary", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, row in edited_df[edited_df["選取"]].iterrows():
                            c.execute("DELETE FROM orders WHERE id=?", (int(row['id']),))
                        conn.commit(); conn.close(); st.rerun()

            st.write("---")
            st.write("📋 **LINE 專用清單**")
            summary = f"【上宇林 團購】\n總計: {df_orders['杯數'].sum()} 杯 / ${df_orders['金額'].sum()} 元\n" + "-"*20 + "\n"
            for _, r in df_orders.iterrows():
                summary += f"{r['姓名']}: {r['飲品']} ({r['甜度']}/{r['冰量']}) x{r['杯數']} - ${r['金額']}\n"
            st.code(summary)
