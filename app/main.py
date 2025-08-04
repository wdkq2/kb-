from __future__ import annotations

import logging
import os
from math import floor
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from .schemas import (
    OrderExecuteRequest,
    OrderExecuteResponse,
    OrderPreviewItem,
    OrderPreviewRequest,
    OrderPreviewResponse,
    TokenRequest,
    TokenResponse,
    WeightsRequest,
    WeightsResponse,
)
from .weights import calculate_weights
from .kis_client import kis_client

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health():
    return {"mode": kis_client.mode, "base_url": kis_client.base_url}


@app.post("/api/kis/token", response_model=TokenResponse)
async def api_token(req: TokenRequest):
    if req.mode:
        kis_client.mode = req.mode
    try:
        data = await kis_client.get_access_token(req.appkey, req.appsecret)
    except Exception as e:  # broad catch to return json
        raise HTTPException(status_code=500, detail=str(e))
    return TokenResponse(access_token=data["access_token"], expires_at=data["expires_at"])


@app.get("/api/quotes/daily", response_model=QuoteResponse)
async def quotes_daily(symbol: str, start: str, end: str):
    try:
        data = await kis_client.inquire_daily_price(symbol, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    prices = [
        {
            "date": item.get("stck_bsop_date"),
            "open": float(item.get("stck_oprc")),
            "high": float(item.get("stck_hgpr")),
            "low": float(item.get("stck_lwpr")),
            "close": float(item.get("stck_clpr")),
            "volume": float(item.get("acml_vol")),
        }
        for item in data.get("output2", [])
    ]
    return QuoteResponse(symbol=symbol, prices=prices)


@app.post("/api/portfolio/weights", response_model=WeightsResponse)
async def portfolio_weights(req: WeightsRequest):
    prices = {}
    for item in req.items:
        try:
            data = await kis_client.inquire_daily_price(item.symbol, "", "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        price = float(data.get("output2", [{}])[0].get("stck_clpr", 0))
        prices[item.symbol] = price
    result = calculate_weights(req, prices)
    return result


@app.post("/api/orders/preview", response_model=OrderPreviewResponse)
async def order_preview(req: OrderPreviewRequest):
    items: List[OrderPreviewItem] = []
    total_needed = 0.0
    for r in req.results:
        try:
            data = await kis_client.inquire_daily_price(r.symbol, "", "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        price = float(data.get("output2", [{}])[0].get("stck_clpr", 0))
        qty_market = floor(r.initial_buy_cash / price) if price else 0
        qty_limit = floor(r.dca_cash / r.limit_price_hint) if r.limit_price_hint else 0
        cash = qty_market * price + qty_limit * r.limit_price_hint
        total_needed += cash
        items.append(
            OrderPreviewItem(
                symbol=r.symbol,
                weight=r.weight,
                price=price,
                qty_market=qty_market,
                qty_limit=qty_limit,
                limit_price=r.limit_price_hint,
                cash_needed=round(cash, 2),
            )
        )
    return OrderPreviewResponse(items=items, total_cash_needed=round(total_needed, 2))


@app.post("/api/orders/execute", response_model=OrderExecuteResponse)
async def order_execute(req: OrderExecuteRequest):
    results = []
    for item in req.items:
        try:
            if item.qty_market > 0:
                resp_market = await kis_client.order_cash(
                    pdno=item.symbol, qty=item.qty_market, price="0", side="buy", ord_dvsn="01"
                )
                results.append(
                    {
                        "symbol": item.symbol,
                        "order_type": "market",
                        "qty": item.qty_market,
                        "price": 0,
                        "response": resp_market,
                    }
                )
            if item.qty_limit > 0:
                resp_limit = await kis_client.order_cash(
                    pdno=item.symbol,
                    qty=item.qty_limit,
                    price=str(item.limit_price),
                    side="buy",
                    ord_dvsn="00",
                )
                results.append(
                    {
                        "symbol": item.symbol,
                        "order_type": "limit",
                        "qty": item.qty_limit,
                        "price": item.limit_price,
                        "response": resp_limit,
                    }
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return OrderExecuteResponse(results=results)
