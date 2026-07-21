import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 페이지 기본 설정
st.set_page_config(page_title="폰테크 회선 및 페이백 관리", page_icon="📱", layout="wide")

# 전화번호 하이픈 자동 포맷팅 함수 (01012345678 -> 010-1234-5678)
def format_phone_number(phone):
    clean_num = re.sub(r'[^0-9]', '', phone)
    if len(clean_num) == 11:
        return f"{clean_num[:3]}-{clean_num[3:7]}-{clean_num[7:]}"
    elif len(clean_num) == 10:
        return f"{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
    return phone

# DB 연결 및 초기화
conn = sqlite3.connect('mobile_management.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT,
    phone_number TEXT,
    carrier TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payback_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id INTEGER,
    installment_no INTEGER,
    expected_year_month TEXT,
    FOREIGN KEY (line_id) REFERENCES lines(id) ON DELETE CASCADE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payback_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER,
    item_type TEXT,
    amount REAL,
    is_received BOOLEAN DEFAULT 0,
    received_date DATE,
    FOREIGN KEY (schedule_id) REFERENCES payback_schedules(id) ON DELETE CASCADE
)
''')
conn.commit()

st.title("📱 폰테크 회선 & 월별 캐시백 관리 앱")

# Session State 초기화
if 'payback_item_list' not in st.session_state:
    st.session_state.payback_item_list = [
        {"type": "네이버페이", "amount": 30000},
        {"type": "네이버페이", "amount": 10000}
    ]

# ---------------------------------------------------------
# 사이드바: 회선 등록 및 다중 캐시백 설정
# ---------------------------------------------------------
with st.sidebar:
    st.header("➕ 회선 및 복수 캐시백 등록")
    name = st.text_input("명의자 이름", key="input_name")
    phone_raw = st.text_input("전화번호 (숫자만 입력해도 자동 변환)", value="010-0000-0000", key="input_phone")
    carrier = st.selectbox("통신사", ["SKT", "KT", "LGU+", "알뜰폰(SKT망)", "알뜰폰(KT망)", "알뜰폰(LGU+망)"])
    
    st.divider()
    st.subheader("💵 월별 지급 조건 설정")
    start_date = st.date_input("캐시백 시작 월 선택", datetime(2026, 9, 1))
    months_count = st.number_input("지급 개월 수 (개월)", value=5, min_value=1, max_value=36)
    
    st.write("---")
    st.write("**🎁 월별 들어올 혜택 항목들 (회차당 적용)**")
    
    for idx, item in enumerate(st.session_state.payback_item_list):
        c1, c2 = st.columns([1.5, 1])
        item['type'] = c1.text_input(f"수단 #{idx+1}", value=item['type'], key=f"type_{idx}")
        item['amount'] = c2.number_input(f"금액 #{idx+1}", value=int(item['amount']), step=5000, key=f"amt_{idx}")

    col_add, col_del = st.columns(2)
    if col_add.button("➕ 혜택 추가"):
        st.session_state.payback_item_list.append({"type": "네이버페이", "amount": 10000})
        st.rerun()
    if col_del.button("➖ 마지막 삭제") and len(st.session_state.payback_item_list) > 1:
        st.session_state.payback_item_list.pop()
        st.rerun()
        
    st.divider()
    # 상단/하단 어디서든 누르기 편하게 저장 버튼 강조
    save_btn = st.button("💾 이 회선 및 캐시백 일정 저장하기", type="primary", use_container_width=True)
    
    if save_btn:
        if name and phone_raw:
            formatted_phone = format_phone_number(phone_raw)
            
            cursor.execute("INSERT INTO lines (person_name, phone_number, carrier) VALUES (?, ?, ?)", 
                           (name, formatted_phone, carrier))
            line_id = cursor.lastrowid
            
            base_date = datetime(start_date.year, start_date.month, 1)
            for i in range(int(months_count)):
                target_date = base_date + relativedelta(months=i)
                ym_str = target_date.strftime("%Y-%m")
                
                cursor.execute('''
                INSERT INTO payback_schedules (line_id, installment_no, expected_year_month)
                VALUES (?, ?, ?)
                ''', (line_id, i + 1, ym_str))
                schedule_id = cursor.lastrowid
                
                for p_item in st.session_state.payback_item_list:
                    cursor.execute('''
                    INSERT INTO payback_items (schedule_id, item_type, amount)
                    VALUES (?, ?, ?)
                    ''', (schedule_id, p_item['type'], p_item['amount']))
                
            conn.commit()
            st.success(f"✅ {name}님 회선({formatted_phone}) 및 {months_count}개월간 캐시백 일정이 정상 저장되었습니다!")
            st.rerun()
        else:
            st.error("⚠️ 명의자 이름과 전화번호를 입력해 주세요.")

# ---------------------------------------------------------
# 메인 화면: 월별 입금 체크리스트
# ---------------------------------------------------------
st.subheader("🗓️ 월별 다중 캐시백 입금 체크리스트")

query = '''
SELECT 
    pi.id AS item_id,
    l.person_name,
    l.phone_number,
    l.carrier,
    ps.installment_no,
    ps.expected_year_month,
    pi.item_type,
    pi.amount,
    pi.is_received
FROM payback_items pi
JOIN payback_schedules ps ON pi.schedule_id = ps.id
JOIN lines l ON ps.line_id = l.id
ORDER BY ps.expected_year_month ASC, l.person_name ASC, pi.id ASC
'''
df = pd.read_sql_query(query, conn)

if not df.empty:
    all_months = sorted(df['expected_year_month'].unique())
    selected_month = st.selectbox("📅 조회할 입금 월 선택", all_months, index=0)
    
    month_df = df[df['expected_year_month'] == selected_month]
    
    st.write(f"### 📍 {selected_month} 입금 예정 목록")
    
    for (person, phone, carrier, inst), group in month_df.groupby(['person_name', 'phone_number', 'carrier', 'installment_no']):
        with st.expander(f"👤 **{person}** ({carrier} / {phone}) - {inst}회차", expanded=True):
            for _, row in group.iterrows():
                col1, col2, col3 = st.columns([2, 2, 2])
                col1.write(f"🎁 **{row['item_type']}**")
                col2.write(f"**{row['amount']:,.0f} 원**")
                
                is_checked = bool(row['is_received'])
                check_key = f"chk_item_{row['item_id']}"
                new_status = col3.checkbox("입금/수령 완료", value=is_checked, key=check_key)
                
                if new_status != is_checked:
                    today_str = datetime.now().strftime("%Y-%m-%d") if new_status else None
                    cursor.execute('''
                    UPDATE payback_items 
                    SET is_received = ?, received_date = ?
                    WHERE id = ?
                    ''', (1 if new_status else 0, today_str, row['item_id']))
                    conn.commit()
                    st.rerun()

    st.divider()
    total_expected = month_df['amount'].sum()
    total_received = month_df[month_df['is_received'] == 1]['amount'].sum()
    
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("해당 월 총 수령 예정액", f"{total_expected:,.0f} 원")
    col_m2.metric("현재 완료된 수령액", f"{total_received:,.0f} 원", delta=f"{total_received - total_expected:,.0f} 원")
else:
    st.info("등록된 회선이 없습니다. 왼쪽 사이드바에서 회선 정보 입력 후 아래의 [💾 저장하기] 버튼을 눌러보세요.")
