import math
import logging
from enum import Enum
from typing import Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from scipy.optimize import minimize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lotte-backend")

app = FastAPI(
    title="Lotte Homeshopping AX Promotion Simulator API",
    version="26.10.0",
    description="SciPy 기반 상생 최적화"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TimeGrade(str, Enum):
    S_GRADE = "S_GRADE"
    A_GRADE = "A_GRADE"
    C_GRADE = "C_GRADE"

class SimulationRequest(BaseModel):
    category: str = Field("패션", description="상품 카테고리")
    time_grade: TimeGrade = Field(TimeGrade.S_GRADE, description="8. 편성 시간대 등급")
    base_price_with_vat: float = Field(120000.0, description="소비자 판매가")
    base_quantity: float = Field(1500.0, description="기준 판매 수량")
    vendor_supply_cap: float = Field(2500.0, description="11. 협력사 재고 상한 캡")
    initial_card_discount_pct: float = Field(10.0, description="1. 초기 카드 할인율")
    initial_lotte_share_pct: float = Field(50.0, description="9. 초기 롯데 분담률")
    gift_cost_won: float = Field(5000.0, description="2. 사은품 조달 원가")
    points_amount_won: float = Field(3000.0, description="3. 적립금 인당 지급액")
    coupon_value_won: float = Field(5000.0, description="4. 앱 쿠폰 금액")
    mobile_channel_ratio: float = Field(0.6, description="10. 모바일 주문 비중")

class OptimizationPrescription(BaseModel):
    card_discount_pct: float = Field(..., description="처방된 최적 카드 할인율")
    lotte_share_pct: float = Field(..., description="처방된 최적 롯데 분담률")
    reasoning: str = Field(..., description="처방 논리 설명")

class FinancialMetrics(BaseModel):
    actual_sold_qty: int = Field(..., description="최종 예측 판매량")
    returned_qty: int = Field(..., description="예측 반품량")
    dynamic_return_rate_pct: float = Field(..., description="동적 반품률")
    lotte_net_profit: float = Field(..., description="기업 순이익")
    lotte_net_margin_pct: float = Field(..., description="기업 순이익률")
    vendor_net_profit: float = Field(..., description="협력사 순이익")
    vendor_net_margin_pct: float = Field(..., description="협력사 순이익률")
    is_feasible_win_win: bool = Field(..., description="상생 통과 여부")

class SimulationResponse(BaseModel):
    status: str = Field(..., description="결과 상태")
    message: str = Field(..., description="요약 메시지")
    prescription: OptimizationPrescription = Field(None, description="처방 수치")
    metrics: FinancialMetrics = Field(..., description="재무 매트릭스")

class LotteHomeshoppingEngine:
    CATEGORY_POLICIES = {
        "패션": {"md_margin": 0.35, "base_return": 0.35, "markdown_ratio": 0.20, "delivery_cost": 6000.0},
        "뷰티": {"md_margin": 0.30, "base_return": 0.12, "markdown_ratio": 0.15, "delivery_cost": 5000.0},
        "가전": {"md_margin": 0.15, "base_return": 0.08, "markdown_ratio": 0.45, "delivery_cost": 30000.0}
    }

    @classmethod
    def run_simulation(cls, req: SimulationRequest, card_discount: float, lotte_share: float) -> Dict[str, Any]:
        policy = cls.CATEGORY_POLICIES.get(req.category, {"md_margin": 0.25, "base_return": 0.15, "markdown_ratio": 0.20, "delivery_cost": 6000.0})
        supply_price = req.base_price_with_vat / 1.1
        
        card_discount = max(0.0, card_discount)
        lotte_share = max(0.0, min(100.0, lotte_share))
        
        time_weight = {"S_GRADE": 2.2, "A_GRADE": 1.0, "C_GRADE": 0.25}.get(req.time_grade, 1.0)
        allocated_qty = req.base_quantity * time_weight
        
        promo_elasticity = math.log1p(card_discount) * 0.45 + (req.coupon_value_won / req.base_price_with_vat) * 0.20
        predicted_demand = allocated_qty * (1.0 + promo_elasticity)
        
        total_attempted_qty = predicted_demand * 1.12
        actual_sold_qty = min(req.vendor_supply_cap, total_attempted_qty)
        opportunity_loss = max(0.0, total_attempted_qty - req.vendor_supply_cap) * 5000.0
        
        ars_ratio = 1.0 - req.mobile_channel_ratio
        dynamic_return_rate = policy["base_return"] + (ars_ratio * 0.10) - (req.mobile_channel_ratio * 0.05)
        dynamic_return_rate = max(0.05, min(0.60, dynamic_return_rate))
        
        returned_qty = actual_sold_qty * dynamic_return_rate
        logistics_penalty = returned_qty * policy["delivery_cost"]
        inventory_markdown_loss = returned_qty * (supply_price * policy["markdown_ratio"])
        
        ars_call_overhead = (actual_sold_qty * ars_ratio) * 1200.0
        
        gross_gmv = req.base_price_with_vat * actual_sold_qty
        card_cost = gross_gmv * (card_discount / 100.0)
        gift_cost = req.gift_cost_won * actual_sold_qty
        points_cost = (req.points_amount_won * actual_sold_qty) * 0.65
        coupon_cost = (req.coupon_value_won * actual_sold_qty) * 0.45
        
        total_promo_pool = card_cost + gift_cost + points_cost + coupon_cost
        lotte_promo_share = total_promo_pool * (lotte_share / 100.0)
        vendor_promo_share = total_promo_pool * (1.0 - (lotte_share / 100.0))
        
        lotte_gross_revenue = (supply_price * actual_sold_qty) * policy["md_margin"]
        lotte_net_profit = lotte_gross_revenue - lotte_promo_share - logistics_penalty - inventory_markdown_loss - ars_call_overhead - opportunity_loss
        
        vendor_gross_revenue = (supply_price * actual_sold_qty) * (1.0 - policy["md_margin"])
        vendor_product_cost = (supply_price * actual_sold_qty) * 0.50
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

class LotteWinWinOptimizer:
    @staticmethod
    def prescribe(req: SimulationRequest) -> Dict[str, Any]:
        initial_res = LotteHomeshoppingEngine.run_simulation(req, req.initial_card_discount_pct, req.initial_lotte_share_pct)
        if initial_res["is_feasible_win_win"]:
            return {
                "status": "APPROVED",
                "message": "초기 기획안이 가이드라인을 통과했습니다.",
                "prescription": {"card_discount_pct": req.initial_card_discount_pct, "lotte_share_pct": req.initial_lotte_share_pct},
                "metrics": initial_res
            }
            
        def objective(x):
            res = LotteHomeshoppingEngine.run_simulation(req, float(x[0]), float(x[1]))
            return -res["lotte_net_profit"]
            
        def constraint_vendor_margin(x):
            res = LotteHomeshoppingEngine.run_simulation(req, float(x[0]), float(x[1]))
            return res["vendor_net_margin_pct"] - 10.0

        bounds = [(2.0, 15.0), (30.0, 80.0)]
        initial_guess = [req.initial_card_discount_pct, req.initial_lotte_share_pct]
        constraints = [{"type": "ineq", "fun": constraint_vendor_margin}]
        
        opt_res = minimize(objective, initial_guess, method="SLSQP", bounds=bounds, constraints=constraints)
        
        if opt_res.success:
            opt_card = round(float(opt_res.x[0]), 1)
            opt_lotte = round(float(opt_res.x[1]), 1)
            final_metrics = LotteHomeshoppingEngine.run_simulation(req, opt_card, opt_lotte)
            return {
                "status": "PRESCRIBED_ALTERNATIVE",
                "message": "협력사 마진 보호 가이드라인에 의거하여 제안이 도출되었습니다.",
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
                "message": "현 원가 구조로는 양사 상생 마진을 확보할 없습니다.",
                "prescription": None,
                "metrics": initial_res
            }

@app.post("/api/v1/simulate", response_model=SimulationResponse, status_code=status.HTTP_200_OK)
async def simulate_endpoint(payload: SimulationRequest):
    try:
        raw_result = LotteWinWinOptimizer.prescribe(payload)
        prescription_data = None
        if raw_result.get("prescription") and raw_result["prescription"] is not None:
            prescription_data = OptimizationPrescription(
                card_discount_pct=raw_result["prescription"]["card_discount_pct"],
                lotte_share_pct=raw_result["prescription"]["lotte_share_pct"],
                reasoning=raw_result["prescription"].get("reasoning", "")
            )
        return SimulationResponse(
            status=raw_result["status"],
            message=raw_result["message"],
            prescription=prescription_data,
            metrics=FinancialMetrics(**raw_result["metrics"])
        )
    except Exception as e:
        logger.error(f"백엔드 내부 연산 에러: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Engine Math Error: {str(e)}")
