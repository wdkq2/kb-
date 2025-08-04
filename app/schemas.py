from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class TokenRequest(BaseModel):
    appkey: Optional[str] = None
    appsecret: Optional[str] = None
    mode: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    expires_at: datetime


class QuoteRequest(BaseModel):
    symbol: str
    start: str
    end: str


class OHLCV(BaseModel):
    date: str = Field(..., description="YYYYMMDD")
    open: float
    high: float
    low: float
    close: float
    volume: float


class QuoteResponse(BaseModel):
    symbol: str
    prices: List[OHLCV]


class PortfolioItem(BaseModel):
    symbol: str
    reason: str


class WeightsRequest(BaseModel):
    total_cash: float = Field(..., gt=0)
    items: List[PortfolioItem]
    initial_buy_ratio: float = 0.5
    discount_rate: float = 0.03


class WeightResult(BaseModel):
    symbol: str
    weight: float
    initial_buy_cash: float
    dca_cash: float
    limit_price_hint: float


class WeightsResponse(BaseModel):
    results: List[WeightResult]


class OrderPreviewRequest(WeightsResponse):
    total_cash: float


class OrderPreviewItem(BaseModel):
    symbol: str
    weight: float
    price: float
    qty_market: int
    qty_limit: int
    limit_price: float
    cash_needed: float


class OrderPreviewResponse(BaseModel):
    items: List[OrderPreviewItem]
    total_cash_needed: float


class OrderExecuteRequest(OrderPreviewResponse):
    pass


class OrderResult(BaseModel):
    symbol: str
    order_type: str
    qty: int
    price: float
    response: dict


class OrderExecuteResponse(BaseModel):
    results: List[OrderResult]
