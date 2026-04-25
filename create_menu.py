import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import glob
from datetime import datetime

# --- 1. 初始化設定 ---
DB_FILE = "orders_v227.db" # 沿用您的歷史資料庫

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
                  金額 INTEGER, 時間 TEXT, session_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_open', 'True')")
    # ✨ 新增：記錄目前營業的店家菜單
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_menu', 'menu.xlsx')")
    conn.commit(); conn.close()

init_db()

# ✨ 自動掃描資料夾內所有的 Excel 檔
def get_available_menus():
    files = [f for f in glob.glob("*.xlsx") if not f.startswith("~")]
    return files if files else ["menu.xlsx"]

# --- 2. 核心狀態函數 ---
def get_system_status():
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT value FROM settings WHERE key='is_open'").fetchone()
    conn.close(); return res[0] == 'True'

def set_system_status(status):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE settings SET value=? WHERE key='is_open'", (str(status),))
    conn.commit(); conn.close()

# ✨ 獲取與設定目前的菜單
def get_active_menu():
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT value FROM settings WHERE key='active_menu'").fetchone()
    conn.close(); 
    # 如果資料庫存的檔案不見了，就抓資料夾裡的第一個
    active = res[0] if res else "menu.xlsx"
    if active not in get_available_menus() and len(get_available_menus()) > 0:
        return get_available_menus()[0]
    return active

def set_active_menu(menu_file):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE settings SET value=? WHERE key='active_menu'", (menu_file,))
    conn.commit(); conn.close()

# --- 智能解析器 (通用版) ---
def parse_drink_options(drink_name):
    if "香橙青綠" in drink_name: return ["青茶", "綠茶"], False, "🍵 茶底"
    if "柳橙/檸檬/蔓越莓" in drink_name: return ["柳橙", "檸檬", "蔓越莓"], False, "🍋 口味"
    if "/" not in drink_name: return ["固定"], True, "🍵 茶底"
    opts = []
    if "紅" in drink_name: opts.append("紅茶"); 
    if "綠" in drink_name: opts.append("綠茶"); 
    if "青" in drink_name: opts.append("青茶"); 
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
    if st.button("✅ 關閉視窗", use_container_width=True):
        st.session_state.show_receipt = False; st.rerun()

# ✨ 動態標題設定
current_menu_file = get_active_menu()
# 拿掉 .xlsx 當作店名
store_name = current_menu_file.replace(".xlsx", "")

st.set_page_config(page_title=f"{store_name} 點餐系統", page_icon="🥤", layout="wide")
st.title(f"🥤 {store_name} 點餐系統 (V2.29)")

tab1, tab2 = st.tabs(["🛒 我要點餐", "📊 管理後台"])

# ==========================================
# 分頁一：前台點餐區 (動態讀取店家)
# ==========================================
with tab1:
    is_open = get_system_status()
    if st.session_state.show_receipt:
        show_receipt_modal(st.session_state.receipt_text)

    if not os.path.exists(current_menu_file):
         st.error(f"❌ 找不到目前的菜單檔：{current_menu_file}，請去後台切換！")
    elif not is_open:
        st.error("🚫 訂單已截止，目前不開放點餐。")
    else:
        user_input = st.text_input("👤 訂購代表姓名", placeholder="例如：王小明")
        
        # ✨ 動態讀取當前設定的菜單檔
        try:
            df_all = pd.read_excel(current_menu_file)
            # 防呆：確認欄位是否正確
            if "分類" not in df_all.columns:
                st.error("❌ 菜單格式錯誤，必須包含『分類』欄位。")
                st.stop()
                
            df_drinks = df_all[df_all["分類"] != "加料系列"]
            df_toppings = df_all[df_all["分類"] == "加料系列"]
            
            selected_cat = st.selectbox("📂 選擇系列", ["全部"] + list(df_drinks["分類"].unique()))
            filtered_drinks = df_drinks if selected_cat == "全部" else df_drinks[df_drinks["分類"] == selected_cat]
            selected_drink_full = st.selectbox("🥤 選擇品項", filtered_drinks.apply(lambda x: f"{x['品項']} (${x['價格']})", axis=1))
            drink_name_only = selected_drink_full.split(" ($")[0]

            with st.form("order_form", clear_on_submit=False):
                current_tea_opts, tea_disabled, tea_label = parse_drink_options(drink_name_only)
                col1, col2, col3, col4 = st.columns(4)
                with col1: tea_base = st.selectbox(tea_label, current_tea_opts, disabled=tea_disabled)
                with col2: sweetness = st.selectbox("🍬 甜度", ["全糖", "少糖", "半糖", "微糖", "一分糖", "無糖"])
                with col3: ice_level = st.selectbox("🧊 冰量", ["正常", "少冰", "微冰", "去冰(小碎冰)", "完全去冰", "溫", "熱"])
                with col4: qty = st.number_input("🔢 杯數", min_value=1, value=1)
                
                # 如果這家店有加料才顯示加料區塊
                if not df_toppings.empty:
                    toppings = st.multiselect("➕ 加料", df_toppings.apply(lambda x: f"{x['品項']} (+${x['價格']})", axis=1).tolist())
                else:
                    toppings = []
                    
                note = st.text_input("📝 備註")
                
                if st.form_submit_button("➕ 加入待送清單", use_container_width=True):
                    if user_input:
                        price = int(selected_drink_full.split("$")[1].replace(")", "")) + sum([int(t.split("+$")[1].replace(")", "")) for t in toppings])
                        st.session_state.cart.append({
                            "姓名": user_input, "飲品": get_clean_drink_name(drink_name_only, tea_base), 
                            "茶底": tea_base, "甜度": sweetness, "冰量": ice_level, 
                            "加料": ', '.join([t.split(" (+")[0] for t in toppings]) if toppings else '無', 
                            "杯數": qty, "備註": note, "金額": price * qty
                        })
                        st.success("✅ 已加入")
                    else: st.error("❌ 請輸入姓名")

            if st.session_state.cart:
                st.write("---")
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[["飲品", "甜度", "冰量", "加料", "杯數", "金額"]], use_container_width=True)
                if st.button("🚀 送出全部訂單", type="primary", use_container_width=True):
                    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    receipt = f"### 🧾 {store_name} 點餐成功明細\n"
                    for i in st.session_state.cart:
                        receipt += f"- **{i['飲品']}** ({i['甜度']}/{i['冰量']}) x{i['杯數']} — `${i['金額']}`\n"
                        c.execute("INSERT INTO orders (姓名, 飲品, 茶底, 甜度, 冰量, 加料, 杯數, 備註, 金額, 時間, session_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                                  (i["姓名"], i["飲品"], i["茶底"], i["甜度"], i["冰量"], i["加料"], i["杯數"], i["備註"], i["金額"], now, '未收單'))
                    conn.commit(); conn.close()
                    st.session_state.receipt_text = receipt; st.session_state.show_receipt = True; st.session_state.cart = []; st.rerun()
        except Exception as e:
            st.error(f"❌ 讀取菜單失敗，請確認 {current_menu_file} 格式正確。錯誤碼：{e}")

# ==========================================
# 分頁二：管理後台 (✨ 新增：店家切換開關)
# ==========================================
with tab2:
    if st.text_input("🔑 管理密碼", type="password") == "520":
        st.success("🔓 進入管理模式")
        
        # ✨ 【重點新功能】：店家切換控制中心
        st.write("---")
        st.subheader("🏪 營運控制中心")
        col_ctrl1, col_ctrl2 = st.columns(2)
        
        with col_ctrl1:
            status = get_system_status()
            if st.toggle("📢 開放前台接單", value=status) != status: 
                set_system_status(not status); st.rerun()
                
        with col_ctrl2:
            all_menus = get_available_menus()
            if all_menus:
                current_idx = all_menus.index(current_menu_file) if current_menu_file in all_menus else 0
                new_menu = st.selectbox("🔄 切換營業店家 (讀取資料夾內 Excel)", all_menus, index=current_idx)
                if new_menu != current_menu_file:
                    set_active_menu(new_menu)
                    st.toast(f"✅ 店家已切換至：{new_menu.replace('.xlsx', '')}")
                    st.rerun()
            else:
                st.error("找不到任何 .xlsx 檔案，請將菜單丟入資料夾。")

        st.write("---")
        conn = sqlite3.connect(DB_FILE)
        all_sessions = pd.read_sql("SELECT DISTINCT session_id FROM orders ORDER BY id DESC", conn)['session_id'].tolist()
        conn.close()

        st.subheader("📜 歷史批次檢視")
        selected_session = st.selectbox("請選擇要查看的訂單批次：", all_sessions if all_sessions else ["尚無資料"])
        
        conn = sqlite3.connect(DB_FILE)
        df_view = pd.read_sql("SELECT * FROM orders WHERE session_id = ?", conn, params=(selected_session,))
        conn.close()

        if selected_session == '未收單' and not df_view.empty:
            st.warning(f"目前『未收單』區域共有 {df_view['杯數'].sum()} 杯飲料待處理。")
            if st.button("🚀 執行收單 (將目前訂單存入歷史紀錄)", type="primary", use_container_width=True):
                # 收單時把目前的店名也寫進去
                new_session_name = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} [{store_name}]"
                conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                c.execute("UPDATE orders SET session_id = ? WHERE session_id = '未收單'", (new_session_name,))
                conn.commit(); conn.close()
                st.success(f"✅ 收單成功！已存為：{new_session_name}")
                st.rerun()
        
        if not df_view.empty:
            st.write("---")
            st.metric(f"💰 {selected_session} 總額", f"${df_view['金額'].sum()}")
            
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_view.to_excel(writer, index=False, sheet_name='明細')
                    df_summary = df_view.groupby(["飲品", "甜度", "冰量", "加料"])["杯數"].sum().reset_index()
                    df_summary.to_excel(writer, index=False, sheet_name='統計')
                st.download_button(label="📥 下載此批次 Excel", data=output.getvalue(), file_name=f"{selected_session}.xlsx", use_container_width=True)
            
            with col_ex2:
                show_print = st.checkbox("🔍 開啟列印預覽")

            if show_print:
                st.table(df_view[["姓名", "飲品", "甜度", "冰量", "加料", "杯數", "金額"]])
            else:
                select_all = st.checkbox("☑️ 全選")
                df_view.insert(0, "選取", select_all)
                edited_df = st.data_editor(df_view, hide_index=True, use_container_width=True, disabled=["id", "時間", "session_id"])
                
                col_save, col_del = st.columns(2)
                with col_save:
                    if st.button("💾 儲存修改", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, r in edited_df.iterrows():
                            c.execute("UPDATE orders SET 姓名=?, 飲品=?, 甜度=?, 冰量=?, 加料=?, 杯數=?, 備註=?, 金額=? WHERE id=?", (r['姓名'], r['飲品'], r['甜度'], r['冰量'], r['加料'], int(r['杯數']), r['備註'], int(r['金額']), int(r['id'])))
                        conn.commit(); conn.close(); st.success("已更新！"); st.rerun()
                with col_del:
                    if st.button("🗑️ 刪除勾選", type="primary", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, r in edited_df[edited_df["選取"]].iterrows():
                            c.execute("DELETE FROM orders WHERE id=?", (int(r['id']),))
                        conn.commit(); conn.close(); st.rerun()

            st.write("---")
            st.write("📋 **LINE 專用清單**")
            summary = f"【{store_name} 團購 ({selected_session})】\n總計: {df_view['杯數'].sum()} 杯 / ${df_view['金額'].sum()} 元\n" + "-"*20 + "\n"
            for _, r in df_view.iterrows():
                topping = f" +{r['加料']}" if r['加料'] != "無" else ""
                note_str = f" (備註: {r['備註']})" if r['備註'] else ""
                summary += f"{r['姓名']}: {r['飲品']} ({r['甜度']}/{r['冰量']}){topping} x{r['杯數']}{note_str} - ${r['金額']}\n"
                
            st.code(summary, language="text")
