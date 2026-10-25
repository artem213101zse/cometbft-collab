"""ABCI-приложение: состояние = одна строка (документ).
CometBFT присылает транзакции в одинаковом порядке на все ноды,
мы применяем их детерминированно -> у всех одинаковый текст."""
import hashlib
import json

from abci.server import ABCIServer
from abci.application import BaseApplication, OkCode
from tendermint.abci.types_pb2 import (
    ResponseInfo, ResponseCheckTx, ResponseDeliverTx, ResponseQuery, ResponseCommit,
)

ERR = 1


def parse(tx: bytes):
    """Разобрать и проверить транзакцию (без учёта текущего текста)."""
    op = json.loads(tx.decode("utf-8"))
    if op.get("op") == "insert":
        if not isinstance(op.get("pos"), int) or not isinstance(op.get("text"), str) or op["pos"] < 0:
            raise ValueError("bad insert")
    elif op.get("op") == "delete":
        if not isinstance(op.get("pos"), int) or not isinstance(op.get("len"), int) or op["pos"] < 0 or op["len"] < 0:
            raise ValueError("bad delete")
    else:
        raise ValueError("unknown op")
    return op


class DocApp(BaseApplication):
    def __init__(self):
        self.doc = ""      # сам документ
        self.version = 0   # сколько операций применено

    def info(self, req):
        # Высота 0 => при старте CometBFT заново проиграет все блоки и восстановит документ
        return ResponseInfo(version="1.0", last_block_height=0, last_block_app_hash=b"")

    def check_tx(self, tx: bytes):
        try:
            parse(tx)
            return ResponseCheckTx(code=OkCode)
        except Exception as e:
            return ResponseCheckTx(code=ERR, log=str(e))

    def deliver_tx(self, tx: bytes):
        try:
            op = parse(tx)
        except Exception as e:
            return ResponseDeliverTx(code=ERR, log=str(e))
        # позиция за концом текста "прижимается" к концу — детерминированно на всех нодах
        pos = min(op["pos"], len(self.doc))
        if op["op"] == "insert":
            self.doc = self.doc[:pos] + op["text"] + self.doc[pos:]
        else:
            self.doc = self.doc[:pos] + self.doc[pos + op["len"]:]
        self.version += 1
        return ResponseDeliverTx(code=OkCode, log=f"applied v{self.version}")

    def query(self, req):
        if req.path == "/document":
            return ResponseQuery(code=OkCode, value=self.doc.encode("utf-8"),
                                 log=f"version={self.version}")
        return ResponseQuery(code=ERR, log="unknown path")

    def commit(self):
        # app_hash = хэш документа: ноды сверяют его, расхождение сразу заметно
        return ResponseCommit(data=hashlib.sha256(self.doc.encode("utf-8")).digest())


if __name__ == "__main__":
    ABCIServer(app=DocApp(), port=26658).run()
