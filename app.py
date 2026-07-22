import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# 페이지 기본 설정
st.set_page_config(page_title="폰테크 회선 & 월별/연간 손익 관리 앱", page_icon="📱", layout="wide")

# 전화번호 하이픈 자동 포맷팅 함수
def format_phone_number(phone):
    clean_num = re.sub(r'[^0-9]', '', phone)
    if len(clean_num) == 11:
        return f"{clean_num[:3]}-{clean_num[3:7]}-{clean_num[7:]}"
    elif len(clean_num) == 10:
        return f"{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
    return phone

# DB 연결 및 테이블 생성
conn = sqlite3.connect('mobile_management.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT,
    phone_number TEXT,
    carrier TEXT,
    sub_carrier TEXT,
    device_model TEXT,
    payment_card TEXT,
    monthly_fee REAL DEFAULT 0,
    opening_payback REAL DEFAULT 0,
    device_sale_price REAL DEFAULT 0,
    opening_date DATE,
    plan_change_date DATE,
    cancellation_date DATE,
    actual_cancelled_date DATE,
    status TEXT DEFAULT '유지중',
    notes TEXT,
    event_image BLOB
)
''')

# 기존 DB 마이그레이션
existing_cols = [col[1] for col in cursor.execute("PRAGMA table_info(lines)").fetchall()]
new_cols = {
    'sub_carrier': 'TEXT',
    'device_model': 'TEXT',
    'opening_payback': 'REAL DEFAULT 0',
    'device_sale_price': 'REAL DEFAULT 0',
    'payment_card': 'TEXT',
    'monthly_fee': 'REAL DEFAULT 0',
    'opening_date': 'DATE',
    'plan_change_date': 'DATE',
    'cancellation_date': 'DATE',
    'actual_cancelled_date': 'DATE',
    'status': "TEXT DEFAULT '유지중'",
    'notes': 'TEXT',
    'event_image': 'BLOB'
}
for col_name, col_type in new_cols.items():
    if col_name not in existing_cols:
        cursor.execute(f"ALTER TABLE lines ADD COLUMN {col_name} {col_type}")

# 월별 스케줄 테이블 (항목명 group_title 컬럼 추가 반영)
cursor.execute('''
CREATE TABLE IF NOT EXISTS payback_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id INTEGER,
    group_title TEXT,
    installment_no INTEGER,
    expected_year_month TEXT,
    FOREIGN KEY (line_id) REFERENCES lines(id) ON DELETE CASCADE
)
''')

# 기존 payback_schedules 테이블 마이그레이션
ps_cols = [col[1] for col in cursor.execute("PRAGMA table_info(payback_schedules)").fetchall()]
if 'group_title' not in ps_cols:
    cursor.execute("ALTER TABLE payback_schedules ADD COLUMN group_title TEXT")

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

st.title("📱 폰테크 회선 & 월별/연간 손익 관리 앱")

# Session State 초기화 (복수 혜택 그룹 관리)
if 'benefit_groups' not in st.session_state:
    st.session_state.benefit_groups = [
        {
            "title": "기본 개통 혜택",
            "start_date": date.today() + relativedelta(months=1),
            "months_count": 5,
            "items": [{"type": "네이버페이", "amount": 30000}]
        },
        {
            "title": "친구추천 혜택",
            "start_date": date.today() + relativedelta(months=2),
            "months_count": 3,
            "items": [{"type": "네이버페이", "amount": 10000}]
        }
    ]

if 'edit_line_id' not in st.session_state:
    st.session_state.edit_line_id = None

# ---------------------------------------------------------
# 1. 사이드바: 회선 등록 및 수정 (항목별 개별 시기/기간 설정)
# ---------------------------------------------------------
with st.sidebar:
    is_edit_mode = st.session_state.edit_line_id is not None
    
    if is_edit_mode:
        st.header("✏️ 회선 정보 수정")
        cursor.execute("SELECT * FROM lines WHERE id = ?", (st.session_state.edit_line_id,))
        line_data = cursor.fetchone()
        
        cols_map = {col[1]: idx for idx, col in enumerate(cursor.execute("PRAGMA table_info(lines)").fetchall())}
        
        edit_name = line_data[cols_map['person_name']]
        edit_phone = line_data[cols_map['phone_number']]
        edit_carrier = line_data[cols_map['carrier']] or "SKT"
        edit_sub_carrier = line_data[cols_map['sub_carrier']] or ""
        edit_device = line_data[cols_map['device_model']] or ""
        edit_card = line_data[cols_map['payment_card']] or ""
        edit_fee = float(line_data[cols_map['monthly_fee']] or 0)
        edit_op_payback = float(line_data[cols_map['opening_payback']] or 0)
        edit_sale_price = float(line_data[cols_map['device_sale_price']] or 0)
        edit_notes = line_data[cols_map['notes']] or ""
        edit_img_bytes = line_data[cols_map['event_image']]
        
        edit_op_date = datetime.strptime(line_data[cols_map['opening_date']], "%Y-%m-%d").date() if line_data[cols_map['opening_date']] else date.today()
        edit_pc_date = datetime.strptime(line_data[cols_map['plan_change_date']], "%Y-%m-%d").date() if line_data[cols_map['plan_change_date']] else date.today()
        edit_cc_date = datetime.strptime(line_data[cols_map['cancellation_date']], "%Y-%m-%d").date() if line_data[cols_map['cancellation_date']] else date.today()
        edit_status = line_data[cols_map['status']] or "유지중"
        
        if st.button("❌ 수정 취소 및 신규 등록 전환"):
            st.session_state.edit_line_id = None
            st.rerun()
    else:
        st.header("➕ 신규 회선 및 세부 혜택 등록")
        edit_name = ""
        edit_phone = "010-0000-0000"
        edit_carrier = "알뜰폰(SKT망)"
        edit_sub_carrier = ""
        edit_device = ""
        edit_card = ""
        edit_fee = 33000.0
        edit_op_payback = 0.0
        edit_sale_price = 0.0
        edit_notes = ""
        edit_img_bytes = None
        edit_op_date = date.today()
        edit_pc_date = date.today() + relativedelta(months=3)
        edit_cc_date = date.today() + relativedelta(months=6)
        edit_status = "유지중"

    name = st.text_input("명의자 이름", value=edit_name)
    phone_raw = st.text_input("전화번호", value=edit_phone)
    
    carrier_list = ["SKT", "KT", "LGU+", "알뜰폰(SKT망)", "알뜰폰(KT망)", "알뜰폰(LGU+망)"]
    carrier_idx = carrier_list.index(edit_carrier) if edit_carrier in carrier_list else 0
    carrier = st.selectbox("통신사", carrier_list, index=carrier_idx)
    
    sub_carrier = ""
    if "알뜰폰" in carrier:
        sub_carrier = st.text_input("세부 별정통신사명 수기 입력", value=edit_sub_carrier, placeholder="예: 모비티, 프리티, 핀다이렉트 등")
    
    device_model = st.text_input("휴대폰 기종", value=edit_device, placeholder="예: 갤럭시 S24, 아이폰 15")
    
    opening_payback = 0.0
    device_sale_price = 0.0
    if carrier in ["SKT", "KT", "LGU+"]:
        st.divider()
        st.subheader("💵 개통 초기 정산 & 기기 판매")
        opening_payback = st.number_input("개통 시 즉시 페이백 (원)", value=int(edit_op_payback), step=10000)
        device_sale_price = st.number_input("📱 기기 판매 수익 (원)", value=int(edit_sale_price), step=10000)
    
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

    st.divider()
    st.subheader("🎁 항목별 캐시백/상품권 설정")
    st.caption("친구추천, 유지이벤트 등 항목마다 시작월과 기간을 각각 다르게 설정합니다.")
    
    # 세부 항목(그룹) 동적 관리
    for g_idx, group in enumerate(st.session_state.benefit_groups):
        with st.expander(f"📌 혜택 항목 #{g_idx+1}: {group['title']}", expanded=True):
            group['title'] = st.text_input(f"항목 명칭 (항목 #{g_idx+1})", value=group['title'], key=f"g_title_{g_idx}")
            c_s1, c_s2 = st.columns(2)
            group['start_date'] = c_s1.date_input(f"지급 시작월 #{g_idx+1}", value=group['start_date'], key=f"g_start_{g_idx}")
            group['months_count'] = c_s2.number_input(f"지급 기간(개월) #{g_idx+1}", value=group['months_count'], min_value=1, max_value=36, key=f"g_months_{g_idx}")
            
            st.write("월별/회차별 지급 금액")
            for item_idx, item in enumerate(group['items']):
                ci1, ci2 = st.columns([1.5, 1])
                item['type'] = ci1.text_input(f"혜택종류 #{g_idx+1}-{item_idx+1}", value=item['type'], key=f"itype_{g_idx}_{item_idx}")
                item['amount'] = ci2.number_input(f"금액 #{g_idx+1}-{item_idx+1}", value=int(item['amount']), step=5000, key=f"iamt_{g_idx}_{item_idx}")

            c_item_add, c_item_del = st.columns(2)
            if c_item_add.button(f"➕ 세부 혜택 추가 (항목 #{g_idx+1})", key=f"btn_add_item_{g_idx}"):
                group['items'].append({"type": "네이버페이", "amount": 10000})
                st.rerun()
            if c_item_del.button(f"➖ 세부 혜택 삭제", key=f"btn_del_item_{g_idx}") and len(group['items']) > 1:
                group['items'].pop()
                st.rerun()

    col_grp_add, col_grp_del = st.columns(2)
    if col_grp_add.button("➕ 새로운 혜택 항목 추가"):
        st.session_state.benefit_groups.append({
            "title": f"추가 혜택 {len(st.session_state.benefit_groups)+1}",
            "start_date": date.today() + relativedelta(months=1),
            "months_count": 1,
            "items": [{"type": "신세계상품권", "amount": 10000}]
        })
        st.rerun()
    if col_grp_del.button("🗑️ 마지막 혜택 항목 삭제") and len(st.session_state.benefit_groups) > 1:
        st.session_state.benefit_groups.pop()
        st.rerun()

    st.divider()
    st.subheader("📝 유의사항 및 이벤트 캡쳐")
    notes = st.text_area("기타 유의사항 / 메모", value=edit_notes, placeholder="예: 6개월 유지 필수, 데이터 사용 조건 등")
    
    uploaded_file = st.file_uploader("이벤트 안내 캡쳐 이미지 업로드", type=["png", "jpg", "jpeg"])
    
    img_blob = edit_img_bytes
    if uploaded_file is not None:
        img_blob = uploaded_file.read()
        st.image(img_blob, caption="업로드한 이벤트 이미지 미리보기", use_container_width=True)
    elif edit_img_bytes:
        st.image(edit_img_bytes, caption="기존 등록된 이벤트 이미지", use_container_width=True)

    st.divider()
    
    # DB 저장 로직 (항목별 스케줄 개별 생성)
    if is_edit_mode:
        if st.button("💾 수정사항 저장 및 혜택 일정 재설정", type="primary", use_container_width=True):
            formatted_phone = format_phone_number(phone_raw)
            line_id = st.session_state.edit_line_id
            
            cursor.execute('''
            UPDATE lines 
            SET person_name=?, phone_number=?, carrier=?, sub_carrier=?, device_model=?, payment_card=?, monthly_fee=?, 
                opening_payback=?, device_sale_price=?, opening_date=?, plan_change_date=?, cancellation_date=?, 
                status=?, notes=?, event_image=?
            WHERE id=?
            ''', (name, formatted_phone, carrier, sub_carrier, device_model, payment_card, monthly_fee, 
                  opening_payback, device_sale_price, opening_date.strftime("%Y-%m-%d"), 
                  plan_change_date.strftime("%Y-%m-%d"), cancellation_date.strftime("%Y-%m-%d"), 
                  status, notes, sqlite3.Binary(img_blob) if img_blob else None, line_id))
            
            # 기존 캐시백 일정 삭제 후 재생성
            cursor.execute("DELETE FROM payback_schedules WHERE line_id = ?", (line_id,))
            
            for grp in st.session_state.benefit_groups:
                base_date = datetime(grp['start_date'].year, grp['start_date'].month, 1)
                for i in range(int(grp['months_count'])):
                    target_date = base_date + relativedelta(months=i)
                    ym_str = target_date.strftime("%Y-%m")
                    
                    cursor.execute('INSERT INTO payback_schedules (line_id, group_title, installment_no, expected_year_month) VALUES (?, ?, ?, ?)', 
                                   (line_id, grp['title'], i + 1, ym_str))
                    schedule_id = cursor.lastrowid
                    
                    for p_item in grp['items']:
                        cursor.execute('INSERT INTO payback_items (schedule_id, item_type, amount) VALUES (?, ?, ?)', 
                                       (schedule_id, p_item['type'], p_item['amount']))

            conn.commit()
            st.session_state.edit_line_id = None
            st.success("✅ 회선 및 세부 항목별 혜택이 성공적으로 수정되었습니다!")
            st.rerun()
    else:
        if st.button("🚀 회선 등록 및 항목별 혜택 생성", type="primary", use_container_width=True):
            if name and phone_raw:
                formatted_phone = format_phone_number(phone_raw)
                cursor.execute('''
                INSERT INTO lines (person_name, phone_number, carrier, sub_carrier, device_model, payment_card, monthly_fee, opening_payback, device_sale_price, opening_date, plan_change_date, cancellation_date, status, notes, event_image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, formatted_phone, carrier, sub_carrier, device_model, payment_card, monthly_fee, 
                      opening_payback, device_sale_price, opening_date.strftime("%Y-%m-%d"), 
                      plan_change_date.strftime("%Y-%m-%d"), cancellation_date.strftime("%Y-%m-%d"), status, notes, sqlite3.Binary(img_blob) if img_blob else None))
                line_id = cursor.lastrowid
                
                for grp in st.session_state.benefit_groups:
                    base_date = datetime(grp['start_date'].year, grp['start_date'].month, 1)
                    for i in range(int(grp['months_count'])):
                        target_date = base_date + relativedelta(months=i)
                        ym_str = target_date.strftime("%Y-%m")
                        
                        cursor.execute('INSERT INTO payback_schedules (line_id, group_title, installment_no, expected_year_month) VALUES (?, ?, ?, ?)', 
                                       (line_id, grp['title'], i + 1, ym_str))
                        schedule_id = cursor.lastrowid
                        
                        for p_item in grp['items']:
                            cursor.execute('INSERT INTO payback_items (schedule_id, item_type, amount) VALUES (?, ?, ?)', 
                                           (schedule_id, p_item['type'], p_item['amount']))
                    
                conn.commit()
                st.success(f"✅ {name}님 회선이 새로 등록되었습니다!")
                st.rerun()

# ---------------------------------------------------------
# 2. 메인 화면
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🎁 월별 상품권/핀 수익 합산", "📱 전체 회선 관리", "📊 연간 폰 판매 & 총 수익 대시보드"])

# TAB 1: 월별 상품권/핀 수익 체크 (항목별 개별 조회)
with tab1:
    query = '''
    SELECT 
        pi.id AS item_id,
        l.person_name,
        l.phone_number,
        l.carrier,
        l.sub_carrier,
        l.device_model,
        l.payment_card,
        l.monthly_fee,
        l.notes,
        ps.group_title,
        ps.installment_no,
        ps.expected_year_month,
        pi.item_type,
        pi.amount,
        pi.is_received
    FROM payback_items pi
    JOIN payback_schedules ps ON pi.schedule_id = ps.id
    JOIN lines l ON ps.line_id = l.id
    ORDER BY ps.expected_year_month ASC, l.person_name ASC, ps.group_title ASC, pi.id ASC
    '''
    df = pd.read_sql_query(query, conn)

    if not df.empty:
        all_months = sorted(df['expected_year_month'].unique())
        selected_month = st.selectbox("📅 조회할 입금 월 선택", all_months, index=0)
        
        month_df = df[df['expected_year_month'] == selected_month]
        
        total_expected = month_df['amount'].sum()
        total_received = month_df[month_df['is_received'] == 1]['amount'].sum()
        active_lines_count = month_df['phone_number'].nunique()
        
        st.markdown(f"### 📍 {selected_month} 전체 회선 별정통신사 상품권 합산")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("📱 해당 월 혜택 해당 회선 수", f"{active_lines_count} 개 회선")
        col_m2.metric("🎁 해당 월 상품권 총 예정액", f"{total_expected:,.0f} 원")
        col_m3.metric("✅ 현재 수령 완료된 상품권액", f"{total_received:,.0f} 원", delta=f"{total_received - total_expected:,.0f} 원")
        
        st.divider()
        st.write("#### 회선 및 항목별 세부 지급 내역")
        
        for (person, phone, carrier, sub_carrier, device, card, fee, notes, g_title, inst), group in month_df.groupby(['person_name', 'phone_number', 'carrier', 'sub_carrier', 'device_model', 'payment_card', 'monthly_fee', 'notes', 'group_title', 'installment_no']):
            carrier_str = f"{carrier} ({sub_carrier})" if sub_carrier else carrier
            device_info = f" | 📲 {device}" if device else ""
            card_info = f" | 💳 {card}" if card else ""
            fee_info = f" | 💸 월 {fee:,.0f}원" if fee else ""
            g_title_str = f" [{g_title}]" if g_title else ""
            
            with st.expander(f"👤 **{person}** ({carrier_str} / {phone}){device_info}{card_info}{fee_info} -{g_title_str} `{inst}회차`", expanded=True):
                if notes:
                    st.info(f"📌 **유의사항/메모:** {notes}")
                for _, row in group.iterrows():
                    col1, col2, col3 = st.columns([2, 2, 2])
                    col1.write(f"🎁 **{row['item_type']}**")
                    col2.write(f"**{row['amount']:,.0f} 원**")
                    
                    is_checked = bool(row['is_received'])
                    check_key = f"chk_item_{row['item_id']}"
                    new_status = col3.checkbox("수령 완료", value=is_checked, key=check_key)
                    
                    if new_status != is_checked:
                        today_str = datetime.now().strftime("%Y-%m-%d") if new_status else None
                        cursor.execute('UPDATE payback_items SET is_received = ?, received_date = ? WHERE id = ?', 
                                       (1 if new_status else 0, today_str, row['item_id']))
                        conn.commit()
                        st.rerun()
    else:
        st.info("등록된 회선이 없습니다. 사이드바에서 첫 번째 회선을 등록해 보세요.")

# TAB 2: 전체 회선 관리
with tab2:
    st.subheader("📋 전체 회선 정보 및 D-Day 현황")
    lines_df = pd.read_sql_query("SELECT * FROM lines ORDER BY id DESC", conn)
    
    if not lines_df.empty:
        for _, line in lines_df.iterrows():
            line_id = line['id']
            with st.container():
                c_head, c_btn1, c_btn2 = st.columns([6, 1, 1])
                
                status_badge = f"[{line['status']}]" if line['status'] else ""
                device_str = f" ({line['device_model']})" if line['device_model'] else ""
                carrier_display = f"{line['carrier']} ({line['sub_carrier']})" if line['sub_carrier'] else line['carrier']
                
                c_head.markdown(f"#### 📱 {line['person_name']} | {line['phone_number']} ({carrier_display}){device_str} `{status_badge}`")
                
                if c_btn1.button("✏️ 수정", key=f"edit_{line_id}"):
                    st.session_state.edit_line_id = line_id
                    st.rerun()
                
                if c_btn2.button("🗑️ 삭제", key=f"del_{line_id}"):
                    cursor.execute("DELETE FROM lines WHERE id = ?", (line_id,))
                    conn.commit()
                    st.success(f"{line['person_name']}님의 회선이 삭제되었습니다.")
                    st.rerun()

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.write(f"💳 **결제 수단:** {line['payment_card'] or '미입력'}")
                col_b.write(f"💸 **월 요금:** {line['monthly_fee']:,.0f}원")
                col_c.write(f"🎁 **개통 페이백:** {line['opening_payback']:,.0f}원")
                col_d.write(f"📱 **기기 판매가:** {line['device_sale_price']:,.0f}원")
                
                today = date.today()
                p_change_str = "미입력"
                if line['plan_change_date']:
                    p_date = datetime.strptime(line['plan_change_date'], "%Y-%m-%d").date()
                    d_day = (p_date - today).days
                    d_str = "D-Day!" if d_day == 0 else (f"D-{d_day}" if d_day > 0 else f"D+{-d_day}")
                    p_change_str = f"{line['plan_change_date']} ({d_str})"
                
                st.caption(f"📅 개통일: {line['opening_date'] or '미입력'} | 🔄 요금제 변경: {p_change_str} | 📌 해지/번이 가능일: {line['cancellation_date'] or '미입력'}")
                
                if line['notes']:
                    st.warning(f"📝 **기타 유의사항:** {line['notes']}")
                
                if line['event_image']:
                    with st.expander("🖼️ 이벤트 안내 캡쳐 이미지 보기"):
                        st.image(line['event_image'], caption=f"{line['person_name']} - 이벤트 안내", use_container_width=True)
                
                st.divider()
    else:
        st.info("등록된 회선이 없습니다.")

# TAB 3: 연간 결산 대시보드
with tab3:
    st.subheader("📈 연간 폰 판매 수익 & 통합 결산 대시보드")
    
    years_df = pd.read_sql_query("SELECT DISTINCT strftime('%Y', opening_date) as year FROM lines WHERE opening_date IS NOT NULL ORDER BY year DESC", conn)
    
    if not years_df.empty:
        selected_year = st.selectbox("📅 결산 연도 선택", years_df['year'].tolist(), index=0)
        
        yearly_query = f'''
        SELECT 
            l.id AS line_id,
            l.person_name,
            l.phone_number,
            l.carrier,
            l.sub_carrier,
            l.device_model,
            l.opening_payback,
            l.device_sale_price,
            l.opening_date,
            l.notes,
            l.event_image,
            COALESCE(SUM(pi.amount), 0) AS total_monthly_giftcards
        FROM lines l
        LEFT JOIN payback_schedules ps ON l.id = ps.line_id
        LEFT JOIN payback_items pi ON ps.id = pi.schedule_id
        WHERE strftime('%Y', l.opening_date) = '{selected_year}'
        GROUP BY l.id
        '''
        y_df = pd.read_sql_query(yearly_query, conn)
        
        sum_device_sales = y_df['device_sale_price'].sum()
        sum_opening_payback = y_df['opening_payback'].sum()
        sum_giftcards = y_df['total_monthly_giftcards'].sum()
        total_yearly_revenue = sum_device_sales + sum_opening_payback + sum_giftcards
        
        st.markdown(f"### 🏆 {selected_year}년 총 폰테크 수익 결산")
        
        y_col1, y_col2, y_col3, y_col4 = st.columns(4)
        y_col1.metric("📱 연간 폰 판매 수익 총합", f"{sum_device_sales:,.0f} 원")
        y_col2.metric("🎁 연간 개통 즉시 페이백", f"{sum_opening_payback:,.0f} 원")
        y_col3.metric("💳 연간 알뜰폰 상품권 총합", f"{sum_giftcards:,.0f} 원")
        y_col4.metric("🔥 연간 총 합산 수익", f"{total_yearly_revenue:,.0f} 원")
        
        st.divider()
        st.write(f"#### 📋 {selected_year}년 개통 회선별 상세 내역")
        
        for _, row in y_df.iterrows():
            line_total = row['device_sale_price'] + row['opening_payback'] + row['total_monthly_giftcards']
            dev_str = f" ({row['device_model']})" if row['device_model'] else ""
            c_disp = f"{row['carrier']} ({row['sub_carrier']})" if row['sub_carrier'] else row['carrier']
            
            with st.expander(f"👤 **{row['person_name']}** - {row['phone_number']} [{c_disp}]{dev_str} | 💰 총 수익: {line_total:,.0f}원"):
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"📱 **폰 판매 수익:** {row['device_sale_price']:,.0f}원")
                c2.write(f"🎁 **개통 페이백:** {row['opening_payback']:,.0f}원")
                c3.write(f"💳 **상품권 총합:** {row['total_monthly_giftcards']:,.0f}원")
                c4.write(f"📅 **개통일:** {row['opening_date']}")
                
                if row['notes']:
                    st.info(f"📝 **유의사항:** {row['notes']}")
                if row['event_image']:
                    st.image(row['event_image'], caption="이벤트 안내 이미지", use_container_width=True)
    else:
        st.info("등록된 연도별 회선 데이터가 없습니다.")
