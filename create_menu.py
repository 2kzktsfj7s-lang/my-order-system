# ==========================================
# 分頁二：管理後台 (新增：戰情篩選模式)
# ==========================================
with tab2:
    st.subheader("📋 訂單管理後台")
    if st.text_input("🔑 密碼", type="password", key="admin_pwd") == "520":
        st.success("🔓 驗證成功")
        
        # 1. 系統營運開關
        status = get_system_status()
        if st.toggle("📢 開放接單中", value=status) != status:
            set_system_status(not status)
            st.rerun()

        st.write("---")
        
        # 2. 讀取資料
        conn = sqlite3.connect(DB_FILE)
        df_orders = pd.read_sql("SELECT * FROM orders", conn)
        conn.close()
        
        if not df_orders.empty:
            # ✨ 【新功能：戰情篩選面板】
            st.markdown("### 🔍 訂單過濾與搜尋")
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                search_name = st.text_input("👤 按姓名搜尋", placeholder="輸入關鍵字...")
            
            with col_filter2:
                # 從現有訂單中提取所有品項，用來反查系列（這需要讀取 menu.xlsx）
                df_all_menu = pd.read_excel(MENU_FILE)
                drink_series = ["全部"] + list(df_all_menu["分類"].unique())
                selected_filter_cat = st.selectbox("📂 按系列篩選", drink_series)

            # 執行篩選邏輯
            df_filtered = df_orders.copy()
            
            # 姓名關鍵字過濾
            if search_name:
                df_filtered = df_filtered[df_filtered['姓名'].str.contains(search_name, na=False)]
            
            # 系列過濾 (需比對 menu 中的分類)
            if selected_filter_cat != "全部":
                # 找出屬於該系列的品項名稱
                valid_drinks = df_all_menu[df_all_menu["分類"] == selected_filter_cat]["品項"].tolist()
                # 因為我們的飲品欄位可能被「淨化」過，所以用「包含」來比對最保險
                df_filtered = df_filtered[df_filtered['飲品'].apply(lambda x: any(d in x for d in valid_drinks))]

            # 3. 顯示統計數據
            st.write(f"📊 目前篩選結果：共 **{df_filtered['杯數'].sum()}** 杯 / 金額 **${df_filtered['金額'].sum()}**")
            
            # 4. 編輯與管理區
            st.write("---")
            select_all = st.checkbox("☑️ 全選目前顯示的訂單")
            df_filtered.insert(0, "選取", select_all)
            
            # 開放編輯 (僅顯示篩選後的結果)
            edited_df = st.data_editor(
                df_filtered, 
                hide_index=True, 
                use_container_width=True, 
                disabled=["id", "時間"]
            )
            
            col_save, col_del = st.columns([1, 1])
            with col_save:
                if st.button("💾 儲存修改內容", use_container_width=True):
                    try:
                        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                        for _, row in edited_df.iterrows():
                            c.execute("""UPDATE orders SET 姓名=?, 飲品=?, 茶底=?, 甜度=?, 冰量=?, 加料=?, 杯數=?, 備註=?, 金額=? 
                                      WHERE id=?""",
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
                    conn.commit(); conn.close()
                    st.rerun()
            
            # 5. LINE 清單 (也會跟著篩選結果變動)
            st.write("---")
            st.write("📋 **LINE 專用清單 (依篩選結果生成)**")
            summary = f"【上宇林 篩選統計】\n總計: {df_filtered['杯數'].sum()} 杯 / ${df_filtered['金額'].sum()} 元\n" + "-"*20 + "\n"
            for _, r in df_filtered.iterrows():
                summary += f"{r['姓名']}: {r['飲品']} ({r['甜度']}/{r['冰量']}) x{r['杯數']} - ${r['金額']}\n"
            st.code(summary)
            
        else:
            st.info("目前尚無訂單資料。")
    else:
        st.info("🔒 請輸入密碼解鎖後台管理系統")
