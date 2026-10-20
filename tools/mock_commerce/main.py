"""模拟电商业务后端（供本地联调使用）。

生产环境对接真实电商服务；本地开发时用这个 FastAPI 服务提供
订单、物流、商品四类接口，方便零依赖跑通整条链路。

启动：
    uv run python tools/mock_commerce/main.py
    # 或 uv run uvicorn tools.mock_commerce.main:app --port 18081
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="模拟电商后端", version="0.1.0")

ORDERS: dict[str, dict] = {
    "A20240315001": {
        "order_number": "A20240315001",
        "user_id": "u1001",
        "amount": "299.00",
        "status": "SHIPPED",
        "status_desc": "已发货",
        "created_at": "2024-03-15 10:20:00",
        "items": [
            {"product_id": "P1001", "title": "轻薄连帽防晒衣", "quantity": 1}
        ],
    },
    "A20240315002": {
        "order_number": "A20240315002",
        "user_id": "u1001",
        "amount": "129.00",
        "status": "PAID",
        "status_desc": "待发货",
        "created_at": "2024-03-16 09:05:00",
        "items": [
            {"product_id": "P1002", "title": "速干运动短裤", "quantity": 2}
        ],
    },
}

LOGISTICS: dict[str, dict] = {
    "A20240315001": {
        "order_number": "A20240315001",
        "tracking_number": "SF1234567890",
        "logistics_company": "顺丰速运",
        "status": "IN_TRANSIT",
        "status_desc": "快件正在运输中",
        "traces": [
            {"time": "2024-03-16 08:00:00", "desc": "已揽收"},
            {"time": "2024-03-16 18:30:00", "desc": "到达杭州转运中心"},
        ],
    },
    "A20240315002": {
        "order_number": "A20240315002",
        "tracking_number": "",
        "logistics_company": "",
        "status": "NOT_SHIPPED",
        "status_desc": "商家尚未发货",
        "traces": [],
    },
}

PRODUCTS: dict[str, dict] = {
    "P1001": {
        "id": "P1001",
        "title": "轻薄连帽防晒衣",
        "price": "129.00",
        "stock": 120,
        "stock_status": "有货",
        "description": "UPF50+ 防晒，轻薄透气，适合春夏通勤与户外。",
        "attributes": {"材质": "锦纶 88% / 氨纶 12%", "季节": "春夏"},
    },
    "P1002": {
        "id": "P1002",
        "title": "速干运动短裤",
        "price": "89.00",
        "stock": 0,
        "stock_status": "缺货",
        "description": "速干面料，松紧腰头，适合跑步与健身。",
        "attributes": {"材质": "聚酯纤维", "季节": "夏季"},
    },
}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/users/{user_id}/orders")
async def list_orders(user_id: str) -> dict:
    orders = [
        order
        for order in ORDERS.values()
        if order["user_id"] == user_id
    ]
    return {"data": orders}


@app.get("/orders/{order_number}")
async def get_order(order_number: str) -> dict:
    order = ORDERS.get(order_number)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"data": order}


@app.get("/orders/{order_number}/logistics")
async def get_logistics(order_number: str) -> dict:
    logistics = LOGISTICS.get(order_number)
    if logistics is None:
        raise HTTPException(status_code=404, detail="物流信息不存在")
    return {"data": logistics}


@app.get("/products/{product_id}")
async def get_product(product_id: str) -> dict:
    product = PRODUCTS.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"data": product}


@app.get("/products")
async def list_products() -> dict:
    return {"data": list(PRODUCTS.values())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=18081)
