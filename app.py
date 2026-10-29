import streamlit as st
import pandas as pd
import math
from enum import Enum
from typing import Dict, Any
from scipy.optimize import minimize

class TimeGrade(str, Enum):
    S_GRADE = "S_GRADE"
    A_GRADE = "A_GRADE"
    C_GRADE = "C_GRADE"

class LotteHomeshoppingEngine:
    CATEGORY_POLICIES = {
        "패션": {"md_margin": 0.35, "base_return": 0.35, "markdown_ratio": 0.20, "delivery_cost": 6000.0},
        "뷰티": {"md_margin": 0.30, "base_return": 0.12, "markdown_ratio": 0.15, "delivery_cost": 5000.0},
        "가전": {"md_margin": 0.15, "base_return": 0.08, "markdown_ratio": 0.45, "delivery_cost": 30000.0}
    }

    @classmethod
    def run_simulation(cls, req: dict, card_discount: float, lotte_share: float) -> Dict[str, Any]:
        policy = cls.CATEGORY_POLICIES.get(req["category"], {"md_margin": 0.25, "base_return": 0.15, "markdown_ratio": 0.20, "delivery_cost": 6000.0})
        supply_price = req["base_price_with_vat"] / 1.1  # 부가세 분리 정산 원칙
        
        # Domain Protection
        card_discount = max(0.0, card_discount)
        lotte_share = max(0.0, min(100.0, lotte_share))
        
        # 8. 시간대별 가치 차등 (편성 효율 가중치)
        time_weight = {"S_GRADE": 2.2, "A_GRADE": 1.0, "C_GRADE": 0.25}.get(req["time_grade"], 1.0)
        allocated_qty = req["base_quantity"] * time_weight
        
        # 1, 4, 5. 비선형 수요 탄력성 (S-Curve) 및 마감 타임세일 효과
        promo_elasticity = math.log1p(card_discount) * 0.45 + (req["coupon_value_won"] / req["base_price_with_vat"]) * 0.20
        predicted_demand = allocated_qty * (1.0 + promo_elasticity)
        
        # 12. 방송 종료 후 유령 매출 (Tail Effect)
        total_attempted_qty = predicted_demand * 1.12
        
        # 11. 협력사 재고 및 생산 캡 병목 현상 반영
        actual_sold_qty = min(req["vendor_supply_cap"], total_attempted_qty)
        opportunity_loss = max(0.0, total_attempted_qty - req["vendor_supply_cap"]) * 5000.0
        
        # 10 ➔ 7. 주문 채널 믹스(ARS vs 앱)와 반품률의 종속적 인과 피드백 루프
        ars_ratio = 1.0 - req["mobile_channel_ratio"]
        dynamic_return_rate = policy["base_return"] + (ars_ratio * 0.10) - (req["mobile_channel_ratio"] * 0.05)
        dynamic_return_rate = max(0.05, min(0.60, dynamic_return_rate))
        
        # 7. 반품 수량 및 반품 가치 하락 감가상각 손실
        returned_qty = actual_sold_qty * dynamic_return_rate
        logistics_penalty = returned_qty * policy["delivery_cost"]
        inventory_markdown_loss = returned_qty * (supply_price * policy["markdown_ratio"])
        
        # 10. ARS 콜센터 인건비 마찰 비용
        ars_call_overhead = (actual_sold_qty * ars_ratio) * 1200.0
        
        # 1, 2, 3, 4, 9. 판촉 총액 산출 및 비용 부담 균형 매트릭스
        gross_gmv = req["base_price_with_vat"] * actual_sold_qty
        card_cost = gross_gmv * (card_discount / 100.0)
        gift_cost = req["gift_cost_won"] * actual_sold_qty
        points_cost = (req["points_amount_won"] * actual_sold_qty) * 0.65  # 적립금 낙각 효과 65%
        coupon_cost = (req["coupon_value_won"] * actual_sold_qty) * 0.45  # 쿠폰 사용률 45%
        
        total_promo_pool = card_cost + gift_cost + points_cost + coupon_cost
        lotte_promo_share = total_promo_pool * (lotte_share / 100.0)
        vendor_promo_share = total_promo_pool * (1.0 - (lotte_share / 100.0))
        
        # [최종 재무 정산 양방향 손익 산출]
        lotte_gross_revenue = (supply_price * actual_sold_qty) * policy["md_margin"]
        lotte_net_profit = lotte_gross_revenue - lotte_promo_share - logistics_penalty - inventory_markdown_loss - ars_call_overhead - opportunity_loss
        
        vendor_gross_revenue = (supply_price * actual_sold_qty) * (1.0 - policy["md_margin"])
        vendor_product_cost = (supply_price * actual_sold_qty) * 0.50  # 협력사 제조원가 기본 방어선 50%
        vendor_net_profit = vendor_gross_revenue - vendor_promo_share - vendor_product_cost
        
        lotte_margin_pct = (lotte_net_profit / (supply_price * actual_sold_qty)) * 100 if actual_sold_qty > 0 else 0.0
        vendor_margin_pct = (vendor_net_profit / vendor_gross_revenue) * 100 if vendor_gross_revenue > 0 else 0.0
        
        return {
            "actual_sold_qty": int(actual_sold_qty),
            "returned_qty": int(returned_qty),
            "dynamic_return_rate_pct": round(dynamic_return_rate * 100, 2),
            "lotte_net_profit": round(lotte_net_profit, 2),
            "lotte_net_margin_pct": round(lotte_margin_pct, 2),
            "vendor_net_profit": round(vendor_net_profit, 2),
            "vendor_net_margin_pct": round(vendor_margin_pct, 2),
            "is_feasible_win_win": vendor_margin_pct >= 10.0 and lotte_net_profit > 0
        }

# SciPy 기반 상생 균형 역산
class LotteWinWinOptimizer:
    @staticmethod
    def prescribe(req: dict) -> Dict[str, Any]:
        initial_res = LotteHomeshoppingEngine.run_simulation(req, req["initial_card_discount_pct"], req["initial_lotte_share_pct"])
        if initial_res["is_feasible_win_win"]:
            return {
                "status": "APPROVED",
                "message": "상생 마진 가이드라인을 통과했습니다.",
                "prescription": {"card_discount_pct": req["initial_card_discount_pct"], "lotte_share_pct": req["initial_lotte_share_pct"]},
                "metrics": initial_res
            }
            
        # SLSQP
        def objective(x):
            # x[0]: 카드할인율, x[1]: 기업 분담률 독립 벡터 탐색 보장
            res = LotteHomeshoppingEngine.run_simulation(req, float(x[0]), float(x[1]))
            return -res["lotte_net_profit"]
            
        def constraint_vendor_margin(x):
            res = LotteHomeshoppingEngine.run_simulation(req, float(x[0]), float(x[1]))
            return res["vendor_net_margin_pct"] - 10.0

        bounds = [(2.0, 15.0), (30.0, 80.0)]
        initial_guess = [req["initial_card_discount_pct"], req["initial_lotte_share_pct"]]
        constraints = [{"type": "ineq", "fun": constraint_vendor_margin}]
        
        opt_res = minimize(objective, initial_guess, method="SLSQP", bounds=bounds, constraints=constraints)
        
        if opt_res.success:
            opt_card = round(float(opt_res.x[0]), 1)
            opt_lotte = round(float(opt_res.x[1]), 1)
            final_metrics = LotteHomeshoppingEngine.run_simulation(req, opt_card, opt_lotte)
            return {
                "status": "PRESCRIBED_ALTERNATIVE",
                "message": "협력사 마진 보호 가이드라인",
                "prescription": {
                    "card_discount_pct": opt_card,
                    "lotte_share_pct": opt_lotte,
                    "reasoning": f"협력사 마진 10% 사수를 위해 카드할인을 {opt_card}%로 제어하고 기업 분담률을 {opt_lotte}%로 증액 보정했습니다."
                },
                "metrics": final_metrics
            }
        else:
            return {
                "status": "REJECTED_INFEASIBLE",
                "message": "현 원가 구조로는 양사 상생 마진을 확보할 수 없습니다.",
                "prescription": None,
                "metrics": initial_res
            }

#FE
st.set_page_config(page_title="Simulator", layout="wide")
st.title("프로모션 시뮬레이터")
st.markdown("---")

# 마케터 입력 제어 사이드바
st.sidebar.header("데이터 제어")
category = st.sidebar.selectbox("1. 상품 카테고리", ["패션", "뷰티", "가전"])
time_grade = st.sidebar.selectbox("2. 방송 편성 시간대 등급", [TimeGrade.S_GRADE.value, TimeGrade.A_GRADE.value, TimeGrade.C_GRADE.value])
base_price = st.sidebar.number_input("3. 상품 판매가 (부가세 포함, 원)", min_value=10000, value=120000, step=5000)
base_qty = st.sidebar.slider("4. 기준 방송 판매 수량", 100, 3000, 1500)
supply_cap = st.sidebar.slider("5. 협력사 재고 캡", 500, 5000, 2500)

st.sidebar.markdown("---")
initial_discount = st.sidebar.slider("카드 청구 할인율 (%)", 0.0, 15.0, 12.0, 0.5)
initial_share = st.sidebar.slider("판촉비 중 기업 분담률 (%)", 10.0, 90.0, 40.0, 5.0)

# 인메모리 연산을 위한 데이터 매핑 팩
req_payload = {
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

raw_result = LotteWinWinOptimizer.prescribe(req_payload)

status_res = raw_result["status"]
message = raw_result["message"]
prescription = raw_result["prescription"]
metrics = raw_result["metrics"]

# UI 결과 레이아웃
if status_res == "APPROVED":
    st.success(f"**[승인]** {message}")
elif status_res == "PRESCRIBED_ALTERNATIVE":
    st.warning(f"{message}")
    with st.container():
        st.markdown("### 최적화 ")
        col_p1, col_p2 = st.columns(2)
        col_p1.metric(label="조정 권장 카드 할인율", value=f"{prescription['card_discount_pct']}%", delta=f"{round(prescription['card_discount_pct'] - initial_discount, 1)}%")
        col_p2.metric(label="기업 판촉 분담비 보정안", value=f"{prescription['lotte_share_pct']}%", delta=f"{round(prescription['lotte_share_pct'] - initial_share, 1)}%")
        st.info(f"**근거:** {prescription['reasoning']}")
else:
    st.error(f"[반려] {message}")
    st.markdown("---")

# KPI 
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("최종 예측 판매량", f"{metrics['actual_sold_qty']:,} 개")
col_m2.metric("예측 반품량", f"{metrics['returned_qty']:,} 개", f"동적 반품률 {metrics['dynamic_return_rate_pct']}%", delta_color="inverse")
col_m3.metric("기업 순이익", f"{int(metrics['lotte_net_profit']):,} 원", f"마진율 {metrics['lotte_net_margin_pct']}%")
col_m4.metric("협력사 순이익", f"{int(metrics['vendor_net_profit']):,} 원", f"마진율 {metrics['vendor_net_margin_pct']}%")
st.markdown("---")

# 정산 시각화 대조 대시보드 차트
st.subheader("양사 정산 마진 및 재무 지표 시각화 대조")
col_c1, col_c2 = st.columns(2)
with col_c1:
st.write("양사 최종 정산 이익 비교액 (원)")
st.bar_chart(data=pd.DataFrame({"주체": ["기업", "협력사"], "순이익 (원)": [metrics["lotte_net_profit"], metrics["vendor_net_profit"]]}), x="주체", y="순이익 (원)", use_container_width=True)
with col_c2:
st.write("양사 마진율 방어선 대조 (%)")
st.bar_chart(data=pd.DataFrame({"주체": ["기업 이익률", "협력사 이익률", "협력사 생존선"], "마진율 (%)": [metrics["lotte_net_margin_pct"], metrics["vendor_net_margin_pct"], 10.0]}), x="주체", y="마진율 (%)", use_container_width=True)

