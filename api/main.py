"""FastAPI: превращает HTTP-запросы в транзакции CometBFT и читает документ через abci_query."""
import base64
import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# список RPC нод: если первая недоступна, пробуем следующую
NODES = os.getenv("COMET_RPCS", "http://node0:26657").split(",")

app = FastAPI(title="Совместный редактор на CometBFT")


class InsertReq(BaseModel):
    pos: int = Field(ge=0, examples=[0])
    text: str = Field(examples=["Привет"])


class DeleteReq(BaseModel):
    pos: int = Field(ge=0, examples=[0])
    length: int = Field(ge=0, examples=[1])


async def rpc(method: str, params: dict):
    last = None
    for node in NODES:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{node}/{method}", params=params)
            data = r.json()
            if "error" in data:
                raise HTTPException(502, data["error"])
            return node, data["result"]
        except httpx.HTTPError as e:
            last = e
    raise HTTPException(503, f"Ни одна нода не отвечает: {last}")


async def send_tx(op: dict):
    tx = json.dumps(op, ensure_ascii=False).encode("utf-8")
    # broadcast_tx_commit ждёт, пока tx попадёт в блок
    node, res = await rpc("broadcast_tx_commit", {"tx": "0x" + tx.hex()})
    if res["check_tx"]["code"] != 0 or res["deliver_tx"]["code"] != 0:
        raise HTTPException(400, res["check_tx"].get("log") or res["deliver_tx"].get("log"))
    return {"ok": True, "node": node, "height": int(res["height"]), "tx_hash": res["hash"]}


@app.post("/insert")
async def insert(req: InsertReq):
    return await send_tx({"op": "insert", "pos": req.pos, "text": req.text})


@app.post("/delete")
async def delete(req: DeleteReq):
    return await send_tx({"op": "delete", "pos": req.pos, "len": req.length})


@app.get("/document")
async def document(node: int | None = None):
    """node=0..3 — спросить конкретную ноду (для проверки, что у всех одинаково)."""
    global NODES
    saved = NODES
    if node is not None:
        NODES = [f"http://node{node}:26657"]
    try:
        n, res = await rpc("abci_query", {"path": '"/document"'})
    finally:
        NODES = saved
    r = res["response"]
    text = base64.b64decode(r.get("value") or "").decode("utf-8")
    return {"node": n, "info": r.get("log"), "text": text}


@app.get("/status")
async def status():
    out = []
    for i in range(4):
        url = f"http://node{i}:26657"
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                s = (await c.get(f"{url}/status")).json()["result"]
            out.append({"node": f"node{i}", "up": True,
                        "height": int(s["sync_info"]["latest_block_height"]),
                        "app_hash": s["sync_info"]["latest_app_hash"]})
        except Exception:
            out.append({"node": f"node{i}", "up": False})
    return out


@app.get("/health")
async def health():
    node, res = await rpc("health", {})
    return {"ok": True, "node": node}
