import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Lotte Homeshopping AX Simulator", layout="wide")
st.title("프로모션 시뮬레이터")
st.markdown("---")

# Codespace 내부 로컬 주소 바인딩
BACKEND_API_URL = "http://127.0.0"

st.sidebar.header("데이터")
category = st.sidebar.selectbox("1. 상품 카테고리", ["패션", "뷰티", "가전"])
time_grade = st.sidebar.selectbox("2. 방송 편성 시간대 등급", ["S_GRADE", "A_GRADE", "C_GRADE"])
base_price = st.sidebar.number_input("3. 상품 판매가 (부가세 포함, 원)", min_value=10000, value=120000, step=5000)
base_qty = st.sidebar.slider("4. 기준 방송 판매 수량", 100, 3000, 1500)
supply_cap = st.sidebar.slider("5. 협력사 재고 캡", 500, 5000, 2500)

st.sidebar.markdown("---")
initial_discount = st.sidebar.slider("카드 청구 할인율 (%)", 0.0, 15.0, 12.0, 0.5)
initial_share = st.sidebar.slider("판촉비 중 기업 분담률 (%)", 10.0, 90.0, 40.0, 5.0)

payload = {
    "category": category,
    "time_grade": time_grade,
    "base_price_with_vat": float(base_price),
    "base_quantity": float(base_qty),
    "vendor_supply_cap": float(supply_cap),
    "initial_card_discount_pct": float(initial_discount),
    "initial_lotte_share_pct": float(initial_share),
    "gift_cost_won": 5000.0,
    "points_amount_won": 3000.0,
    "coupon_value_won": 5000.0,
    "mobile_channel_ratio": 0.6
}

try:
    response = requests.post(BACKEND_API_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        status, message, prescription, metrics = data["status"], data["message"], data["prescription"], data["metrics"]
        
        if status == "APPROVED":
            st.success(f"**[승인]** {message}")
        elif status == "PRESCRIBED_ALTERNATIVE":
            st.warning(f"{message}")
            with st.container():
                st.markdown("### 최적화 제안")
                col_p1, col_p2 = st.columns(2)
                col_p1.metric(label="조정 권장 카드 할인율", value=f"{prescription['card_discount_pct']}%", delta=f"{round(prescription['card_discount_pct'] - initial_discount, 1)}%")
                col_p2.metric(label="기업 판촉 분담비 보정안", value=f"{prescription['lotte_share_pct']}%", delta=f"{round(prescription['lotte_share_pct'] - initial_share, 1)}%")
                st.info(f"**근거:** {prescription['reasoning']}")
        else:
            st.error(f"**[반려]** {message}")
            
        st.markdown("---")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("최종 예측 판매량", f"{metrics['actual_sold_qty']:,} 개")
        col_m2.metric("예측 반품량", f"{metrics['returned_qty']:,} 개", f"동적 반품률 {metrics['dynamic_return_rate_pct']}%", delta_color="inverse")
        col_m3.metric("기업 순이익", f"{int(metrics['lotte_net_profit']):,} 원", f"마진율 {metrics['lotte_net_margin_pct']}%")
        col_m4.metric("협력사 순이익", f"{int(metrics['vendor_net_profit']):,} 원", f"마진율 {metrics['vendor_net_margin_pct']}%")
        
        st.markdown("---")
        st.subheader("양사 정산 마진 및 재무 지표 시각화 대조")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.write("**양사 최종 정산 이익 비교액 (원)**")
            st.bar_chart(data=pd.DataFrame({"주체": ["기업", "협력사"], "순이익 (원)": [metrics["lotte_net_profit"], metrics["vendor_net_profit"]]}), x="주체", y="순이익 (원)", use_container_width=True)
        with col_c2:
            st.write("**양사 마진율 방어선 대조 (%)**")
            st.bar_chart(data=pd.DataFrame({"주체": ["기업 이익률", "협력사 이익률", "협력사 생존선"], "마진율 (%)": [metrics["lotte_net_margin_pct"], metrics["vendor_net_margin_pct"], 10.0]}), x="주체", y="마진율 (%)", use_container_width=True)
except Exception as e:
    st.error(f"🔌 백엔드 통신 실패. 백엔드가 구동 중인지 확인하세요. ({str(e)})")
