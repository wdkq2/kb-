from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx
import hashlib
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class KISClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "KIS_BASE_URL", "https://openapivts.koreainvestment.com:29443"
        )
        self.appkey = os.getenv("KIS_APP_KEY", "")
        self.appsecret = os.getenv("KIS_APP_SECRET", "")
        self.cano = os.getenv("KIS_CANO", "")
        self.acnt_prdt_cd = os.getenv("KIS_ACNT_PRDT_CD", "")
        self.custtype = os.getenv("KIS_CUSTTYPE", "P")
        self.mode = os.getenv("KIS_MODE", "virtual")
        self.mock = os.getenv("KIS_MOCK", "0") == "1"
        self.token: Optional[str] = None
        self.expires: datetime = datetime.min
        self.token_strategy = os.getenv("TOKEN_TTL_STRATEGY", "short")

    async def get_access_token(self, appkey: Optional[str] = None, appsecret: Optional[str] = None) -> Dict[str, Any]:
        if appkey:
            self.appkey = appkey
        if appsecret:
            self.appsecret = appsecret
        now = datetime.utcnow()
        if self.token and now < self.expires:
            return {"access_token": self.token, "expires_at": self.expires}
        if self.mock:
            self.token = "MOCK_TOKEN"
            ttl = 24 if self.token_strategy == "short" else 24 * 90
            self.expires = now + timedelta(hours=ttl - 1)
            return {"access_token": self.token, "expires_at": self.expires}

        url = f"{self.base_url}/oauth2/tokenP"
        data = {"grant_type": "client_credentials", "appkey": self.appkey, "appsecret": self.appsecret}
        headers = {"content-type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=headers)
        if resp.status_code != 200:
            logger.error("token error %s %s", resp.status_code, resp.text)
            raise httpx.HTTPStatusError("token error", request=resp.request, response=resp)
        res = resp.json()
        self.token = res.get("access_token")
        ttl = 24 if self.token_strategy == "short" else 24 * 90
        self.expires = now + timedelta(hours=ttl - 1)
        return {"access_token": self.token, "expires_at": self.expires}

    def hashkey(self, body: Dict[str, Any]) -> str:
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def headers_for(self, tr_id: str, is_post: bool = False, body: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        token_info = await self.get_access_token()
        headers = {
            "authorization": f"Bearer {token_info['access_token']}",
            "appkey": self.appkey,
            "appsecret": self.appsecret,
            "tr_id": tr_id,
            "custtype": self.custtype,
            "content-type": "application/json; charset=UTF-8",
        }
        if is_post and body is not None:
            headers["hashkey"] = self.hashkey(body)
        return headers

    async def inquire_daily_price(self, symbol: str, start: str, end: str) -> Dict[str, Any]:
        if self.mock:
            price = 50000 + (int(symbol[-2:]) * 10)
            today = datetime.today().strftime("%Y%m%d")
            return {
                "output2": [
                    {
                        "stck_bsop_date": today,
                        "stck_oprc": price,
                        "stck_hgpr": price,
                        "stck_lwpr": price,
                        "stck_clpr": price,
                        "acml_vol": 0,
                    }
                ]
            }
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol, "fid_period_div_code": "D", "fid_org_adj_prc": "0"}
        headers = await self.headers_for("FHKST01010400")
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            logger.error("quote error %s %s", resp.status_code, resp.text)
            raise httpx.HTTPStatusError("quote error", request=resp.request, response=resp)
        return resp.json()

    async def order_cash(self, pdno: str, qty: int, price: str, side: str, ord_dvsn: str) -> Dict[str, Any]:
        tr_base = "TTTC" if self.mode == "real" else "VTTC"
        tr_id = f"{tr_base}0802U" if side == "buy" else f"{tr_base}0801U"
        body = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "PDNO": pdno,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(qty),
            "ORD_UNPR": price,
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N",
        }
        if self.mock:
            return {"mock": True, "tr_id": tr_id, "body": body}
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        headers = await self.headers_for(tr_id, is_post=True, body=body)
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            logger.error("order error %s %s", resp.status_code, resp.text)
            raise httpx.HTTPStatusError("order error", request=resp.request, response=resp)
        return resp.json()


kis_client = KISClient()
