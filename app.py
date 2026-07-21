import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# 페이지 기본 설정
st.set_page_config(page_title="폰테크 회선 및 페이백 종합 관리", page_icon="📱", layout="wide")

# 전화번호 하이픈 자동 포맷팅 함수
def format_phone_number(phone):
    clean_num = re.sub(r'[^0-9]', '', phone)
    if len(clean_num) == 11:
        return f"{clean_num[:3]}-{clean_num[3:7]}-{clean_num[7:]}"
    elif len(clean_num) == 10:
        return f"{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
    return phone

# DB 연결 및 컬럼 자동 업데이트(마이그레이션)
conn = sqlite3.connect('mobile_management.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT,
    phone_number TEXT,
    carrier TEXT,
    payment_card TEXT,
    monthly_fee REAL DEFAULT 0,
    opening_date DATE,
    plan_change_date DATE,
    cancellation_date DATE,
    actual_cancelled_date DATE,
    status TEXT DEFAULT '유지중'
)
''')

# 기존 DB 구조 자동 업데이트 (기존 테이블이 있어도 컬럼 추가)
existing_cols = [col[1] for col in cursor.execute("PRAGMA table_info(lines)").fetchall()]
new_cols = {
    'payment_card': 'TEXT',
    'monthly_fee': 'REAL DEFAULT 0',
    'opening_date': 'DATE',
    'plan_change_date': 'DATE',
    'cancellation_date': 'DATE',
    'actual_cancelled_date': 'DATE',
    'status': "TEXT DEFAULT '유지중'"
}
for col_name, col_type in new_cols.items():
    if col_name not in existing_cols:
        cursor.execute(f"ALTER TABLE lines ADD COLUMN {col_name} {col_type}")

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

st.title("📱 폰테크 회선 & 통합 정산/일정 관리 앱")

# Session State 초기화
if 'payback_item_list' not in st.session_state:
    st.session_state.payback_item_list = [
        {"type": "네이버페이", "amount": 30000},
        {"type": "네이버페이", "amount": 10000}
    ]
if 'edit_line_id' not in st.session_state:
    st.session_state.edit_line_id = None

# ---------------------------------------------------------
# 1. 사이드바: 신규 등록 및 수정 폼
# ---------------------------------------------------------
with st.sidebar:
    is_edit_mode = st.session_state.edit_line_id is not None
    
    if is_edit_mode:
        st.header("✏️ 회선 정보 수정")
        cursor.execute("SELECT * FROM lines WHERE id = ?", (st.session_state.edit_line_id,))
        line_data = cursor.fetchone()
        
        # 기존 데이터 변수 할당
        edit_name = line_data[1]
        edit_phone = line_data[2]
        edit_carrier = line_data[3]
        edit_card = line_data[4] or ""
        edit_fee = float(line_data[5] or 0)
        edit_op_date = datetime.strptime(line_data[6], "%Y-%m-%d").date() if line_data[6] else date.today()
        edit_pc_date = datetime.strptime(line_data[7], "%Y-%m-%d").date() if line_data[7] else date.today()
        edit_cc_date = datetime.strptime(line_data[8], "%Y-%m-%d").date() if line_data[8] else date.today()
        edit_status = line_data[10] or "유지중"
        
        if st.button("❌ 수정 취소하고 신규 등록으로"):
            st.session_state.edit_line_id = None
            st.rerun()
    else:
        st.header("➕ 신규 회선 및 캐시백 등록")
        edit_name = ""
        edit_phone = "010-0000-0000"
        edit_carrier = "알뜰폰(SKT망)"
        edit_card = ""
        edit_fee = 33000.0
        edit_op_date = date.today()
        edit_pc_date = date.today() + relativedelta(months=3)
        edit_cc_date = date.today() + relativedelta(months=6)
        edit_status = "유지중"

    name = st.text_input("명의자 이름", value=edit_name)
    phone_raw = st.text_input("전화번호", value=edit_phone)
    carrier = st.selectbox("통신사", ["SKT", "KT", "LGU+", "알뜰폰(SKT망)", "알뜰폰(KT망)", "알뜰폰(LGU+망)"], index=0)
    
    st.divider()
    st.subheader("💳 요금 및 결제 정보")
    monthly_fee = st.number_input("월 납부 요금 (원)", value=int(edit_fee), step=1000)
    payment_card = st.text_input("결제 카드 / 계좌", value=edit_card, placeholder="예: 신한 딥드림 / 우리 0123")
    
    st.divider()
    st.subheader("📅 주요 회선 일정")
    opening_date = st.date_input("개통일", value=edit_op_date)
    plan_change_date = st.date_input("요금제 변경가능일", value=edit_pc_date)
    cancellation_date = st.date_input("해지/번이 가능일", value=edit_cc_date)
    status = st.selectbox("현재 회선 상태", ["유지중", "요금제 변경 완료", "해지 완료", "번호이동 완료"], index=["유지중", "요금제 변경 완료", "해지 완료", "번호이동 완료"].index(edit_status))

    if not is_edit_mode:
        st.divider()
        st.subheader("💵 월별 지급 조건 (신규 전용)")
        start_date = st.date_input("캐시백 시작 월", datetime(2026, 9, 1))
        months_count = st.number_input("지급 개월 수", value=5, min_value=1, max_value=36)
        
        st.write("🎁 **회차당 들어올 혜택**")
        for idx, item in enumerate(st.session_state.payback_item_list):
            c1, c2 = st.columns([1.5, 1])
            item['type'] = c1.text_input(f"수단 #{idx+1}", value=item['type'], key=f"type_{idx}")
            item['amount'] = c2.number_input(f"금액 #{idx+1}", value=int(item['amount']), step=5000, key=f"amt_{idx}")

        col_add, col_del = st.columns(2)
        if col_add.button("➕ 혜택 추가"):
            st.session_state.payback_item_list.append({"type": "네이버페이", "amount": 10000})
            st.rerun()
        if col_del.button("➖ 삭제") and len(st.session_state.payback_item_list) > 1:
            st.session_state.payback_item_list.pop()
            st.rerun()

    st.divider()
    
    if is_edit_mode:
        if st.button("💾 회선 수정사항 저장하기", type="primary", use_container_width=True):
            formatted_phone = format_phone_number(phone_raw)
            cursor.execute('''
            UPDATE lines 
            SET person_name=?, phone_number=?, carrier=?, payment_card=?, monthly_fee=?, 
                opening_date=?, plan_change_date=?, cancellation_date=?, status=?
            WHERE id=?
            ''', (name, formatted_phone, carrier, payment_card, monthly_fee, 
                  opening_date.strftime("%Y-%m-%d"), plan_change_date.strftime("%Y-%m-%d"), 
                  cancellation_date.strftime("%Y-%m-%d"), status, st.session_state.edit_line_id))
            conn.commit()
            st.session_state.edit_line_id = None
            st.success("✅ 회선 정보가 수정되었습니다!")
            st.rerun()
    else:
        if st.button("🚀 신규 회선 및 일정 등록", type="primary", use_container_width=True):
            if name and phone_raw:
                formatted_phone = format_phone_number(phone_raw)
                cursor.execute('''
                INSERT INTO lines (person_name, phone_number, carrier, payment_card, monthly_fee, opening_date, plan_change_date, cancellation_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, formatted_phone, carrier, payment_card, monthly_fee, 
                      opening_date.strftime("%Y-%m-%d"), plan_change_date.strftime("%Y-%m-%d"), 
                      cancellation_date.strftime("%Y-%m-%d"), status))
                line_id = cursor.lastrowid
                
                base_date = datetime(start_date.year, start_date.month, 1)
                for i in range(int(months_count)):
                    target_date = base_date + relativedelta(months=i)
                    ym_str = target_date.strftime("%Y-%m")
                    
                    cursor.execute('INSERT INTO payback_schedules (line_id, installment_no, expected_year_month) VALUES (?, ?, ?)', 
                                   (line_id, i + 1, ym_str))
                    schedule_id = cursor.lastrowid
                    
                    for p_item in st.session_state.payback_item_list:
                        cursor.execute('INSERT INTO payback_items (schedule_id, item_type, amount) VALUES (?, ?, ?)', 
                                       (schedule_id, p_item['type'], p_item['amount']))
                    
                conn.commit()
                st.success(f"✅ {name}님 회선이 새로 등록되었습니다!")
                st.rerun()

# ---------------------------------------------------------
# 2. 메인 화면: 월별 캐시백 체크리스트 & 회선 관리
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🗓️ 월별 캐시백 입금 체크", "📱 전체 회선 및 일정 관리/수정"])

# TAB 1: 월별 캐시백 관리
with tab1:
    query = '''
    SELECT 
        pi.id AS item_id,
        l.person_name,
        l.phone_number,
        l.carrier,
        l.payment_card,
        l.monthly_fee,
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
        
        for (person, phone, carrier, card, fee, inst), group in month_df.groupby(['person_name', 'phone_number', 'carrier', 'payment_card', 'monthly_fee', 'installment_no']):
            card_info = f" | 💳 {card}" if card else ""
            fee_info = f" | 💸 월 {fee:,.0f}원" if fee else ""
            
            with st.expander(f"👤 **{person}** ({carrier} / {phone}){card_info}{fee_info} - {inst}회차", expanded=True):
                for _, row in group.iterrows():
                    col1, col2, col3 = st.columns([2, 2, 2])
                    col1.write(f"🎁 **{row['item_type']}**")
                    col2.write(f"**{row['amount']:,.0f} 원**")
                    
                    is_checked = bool(row['is_received'])
                    check_key = f"chk_item_{row['item_id']}"
                    new_status = col3.checkbox("입금/수령 완료", value=is_checked, key=check_key)
                    
                    if new_status != is_checked:
                        today_str = datetime.now().strftime("%Y-%m-%d") if new_status else None
                        cursor.execute('UPDATE payback_items SET is_received = ?, received_date = ? WHERE id = ?', 
                                       (1 if new_status else 0, today_str, row['item_id']))
                        conn.commit()
                        st.rerun()

        st.divider()
        total_expected = month_df['amount'].sum()
        total_received = month_df[month_df['is_received'] == 1]['amount'].sum()
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("해당 월 총 수령 예정액", f"{total_expected:,.0f} 원")
        col_m2.metric("현재 완료된 수령액", f"{total_received:,.0f} 원", delta=f"{total_received - total_expected:,.0f} 원")
    else:
        st.info("등록된 회선이 없습니다. 사이드바에서 첫 번째 회선을 등록해 보세요.")

# TAB 2: 전체 회선 목록 (수정 / 삭제 기능)
with tab2:
    st.subheader("📋 전체 회선 정보 및 D-Day 현황")
    lines_df = pd.read_sql_query("SELECT * FROM lines ORDER BY id DESC", conn)
    
    if not lines_df.empty:
        for _, line in lines_df.iterrows():
            line_id = line['id']
            with st.container():
                c_head, c_btn1, c_btn2 = st.columns([6, 1, 1])
                
                status_badge = f"[{line['status']}]" if line['status'] else ""
                c_head.markdown(f"#### 📱 {line['person_name']} | {line['phone_number']} ({line['carrier']}) `{status_badge}`")
                
                # 수정 버튼
                if c_btn1.button("✏️ 수정", key=f"edit_{line_id}"):
                    st.session_state.edit_line_id = line_id
                    st.rerun()
                
                # 삭제 버튼
                if c_btn2.button("🗑️ 삭제", key=f"del_{line_id}"):
                    cursor.execute("DELETE FROM lines WHERE id = ?", (line_id,))
                    conn.commit()
                    st.success(f"{line['person_name']}님의 회선이 삭제되었습니다.")
                    st.rerun()

                # 디테일 정보 표시
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.write(f"💳 **결제 수단:** {line['payment_card'] or '미입력'}")
                col_b.write(f"💸 **월 요금:** {line['monthly_fee']:,.0f}원")
                col_c.write(f"📅 **개통일:** {line['opening_date'] or '미입력'}")
                
                # D-Day 계산
                today = date.today()
                p_change_str = "미입력"
                if line['plan_change_date']:
                    p_date = datetime.strptime(line['plan_change_date'], "%Y-%m-%d").date()
                    d_day = (p_date - today).days
                    d_str = "D-Day!" if d_day == 0 else (f"D-{d_day}" if d_day > 0 else f"D+{-d_day}")
                    p_change_str = f"{line['plan_change_date']} ({d_str})"
                
                col_d.write(f"🔄 **요금제 변경가능:** {p_change_str}")
                
                st.caption(f"📌 해지/번이 가능일: {line['cancellation_date'] or '미입력'}")
                st.divider()
    else:
        st.info("등록된 회선이 없습니다.")
