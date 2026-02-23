import time, requests, datetime, secrets, hashlib
from fastapi import FastAPI, Query, Request
from fastapi.responses import PlainTextResponse
from urllib.parse import urlencode, unquote_plus
import uvicorn

app = FastAPI(title="Flovico Empire 支付与授权中枢 v6.4")

# ================= 核心配置区 =================
PB_URL = "http://127.0.0.1:8090" 
PB_ADMIN_EMAIL = "63378329@qq.com"
PB_ADMIN_PASSWORD = "d100200300" 

HUPI_APPID = "201906143841"      
HUPI_SECRET = "85ff4af4167252d0b0ab54d2b497a3e0" 
HUPI_URL = "https://api.xunhupay.com/payment/do.html"
NOTIFY_URL = "http://107.173.89.194:8000/hupi_notify" 
# ==============================================

class PBManager:
    def __init__(self): self.token = self._get_token()
    def _get_token(self):
        try:
            r = requests.post(f"{PB_URL}/api/admins/auth-with-password", json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASSWORD}, timeout=5)
            return r.json().get("token")
        except: return None
    def call(self, method, path, **kwargs):
        if not self.token: self.token = self._get_token()
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            r = requests.request(method, f"{PB_URL}/api/collections{path}", headers=headers, **kwargs)
            return r.json()
        except: return {"items": [], "totalItems": 0}

pb = PBManager()

def hupi_sign(data):
    """虎皮椒 MD5 签名 - 严格遵循空值不参与签名规则"""
    # 过滤掉 hash 且过滤掉 None 或空字符串
    clean_data = {k: str(v) for k, v in data.items() if k != 'hash' and v is not None and str(v).strip() != ""}
    sorted_data = sorted(clean_data.items(), key=lambda x: x[0])
    query_str = unquote_plus(urlencode(sorted_data))
    return hashlib.md5((query_str + HUPI_SECRET).encode('utf-8')).hexdigest()

@app.get("/config")
async def get_config(product_id: str = Query(...)):
    prod_res = pb.call("GET", "/products/records", params={"filter": f"product_id='{product_id}'"})
    default_res = {"ad_text": "正在同步...", "price_monthly": 19.9, "price_yearly": 99.0, "price_lifetime": 199.0}
    if prod_res.get('items'):
        p = prod_res['items'][0]
        default_res.update({
            "ad_text": p.get("ad_text"), "ad_link": p.get("ad_link"),
            "qq_support": p.get("qq_support"), "buy_link": p.get("buy_link"),
            "latest_version": p.get("latest_version"), "download_url": p.get("download_url"),
            "price_monthly": p.get("price_monthly"), "price_yearly": p.get("price_yearly"), "price_lifetime": p.get("price_lifetime")
        })
    return default_res

@app.post("/create_order")
async def create_order(data: dict):
    """创建订单：10分钟内未支付订单复用逻辑"""
    product_id_str = data.get("product_id")
    device_code = data.get("device_id")
    order_type = data.get("order_type")
    
    prod_res = pb.call("GET", "/products/records", params={"filter": f"product_id='{product_id_str}'"})
    if not prod_res.get('items'): return {"error": "Product Not Found"}
    product = prod_res['items'][0]
    
    dev_res = pb.call("GET", "/devices/records", params={"filter": f"machine_code='{device_code}'"})
    db_dev_id = dev_res['items'][0]['id'] if dev_res.get('items') else None
    
    # 查找10分钟内同类型未支付订单，防止数据库产生大量冗余
    ten_mins_ago = (datetime.datetime.now() - datetime.timedelta(minutes=10)).isoformat()
    old_order = pb.call("GET", "/orders/records", params={"filter": f"device_id='{db_dev_id}' && order_type='{order_type}' && status='unpaid' && created > '{ten_mins_ago}'"})
    
    trade_id = f"FL-{int(time.time())}-{secrets.token_hex(4).upper()}"
    price = product.get(f"price_{order_type}", 0.01)
    
    hupi_data = {
        "version": "1.1", "appid": HUPI_APPID, "trade_order_id": trade_id,
        "total_fee": str(price), "title": f"Flovico-{order_type}",
        "time": str(int(time.time())), "notify_url": NOTIFY_URL, "nonce_str": secrets.token_hex(8)
    }
    hupi_data["hash"] = hupi_sign(hupi_data)
    
    try:
        resp = requests.post(HUPI_URL, data=hupi_data, timeout=10).json()
        if resp.get("errcode") == 0:
            pb.call("POST", "/orders/records", json={
                "order_id": trade_id, "product_id": product['id'], "device_id": db_dev_id,
                "order_type": order_type, "amount": price, "status": "unpaid"
            })
            return {"order_id": trade_id, "url_qrcode": resp.get("url_qrcode")}
    except: pass
    return {"error": "支付网关异常"}

@app.post("/hupi_notify")
async def hupi_notify(request: Request):
    """修复回调：支持表单解析与严格验签"""
    try:
        form_data = await request.form()
        data = dict(form_data)
        if data.get("hash") != hupi_sign(data): return PlainTextResponse("fail")
        
        if data.get("status") == "OD":
            trade_id = data.get("trade_order_id")
            order_res = pb.call("GET", "/orders/records", params={"filter": f"order_id='{trade_id}'"})
            if order_res.get('items') and order_res['items'][0]['status'] == "unpaid":
                o = order_res['items'][0]
                pb.call("PATCH", f"/orders/records/{o['id']}", json={"status": "paid", "hupi_id": data.get("open_order_id"), "pay_time": datetime.datetime.now().isoformat()})
                l = pb.call("POST", "/licenses/records", json={"key": f"PAY-{trade_id}", "product_id": o['product_id'], "type": o['order_type'], "status": "active", "activated_at": datetime.datetime.now().isoformat()})
                pb.call("POST", "/license_bindings/records", json={"license_id": l['id'], "device_id": o['device_id']})
        return PlainTextResponse("success")
    except: return PlainTextResponse("fail")

@app.get("/check_order")
async def check_order(order_id: str):
    res = pb.call("GET", "/orders/records", params={"filter": f"order_id='{order_id}'"})
    return {"status": res['items'][0]['status']} if res.get('items') else {"status": "error"}

@app.post("/check_license")
async def check_license(data: dict):
    """解决“没网”报错：增加容错判断"""
    device_id = data.get("device_id"); today = datetime.date.today(); product_id_str = data.get("product_id")
    dev_res = pb.call("GET", "/devices/records", params={"filter": f"machine_code='{device_id}'"})
    
    if not dev_res.get('items'): 
        pb.call("POST", "/devices/records", json={"machine_code": device_id, "risk_level": "safe"})
        return {"is_pro": False, "remaining_quota": 3}
    
    db_dev = dev_res['items'][0]
    binds = pb.call("GET", "/license_bindings/records", params={"filter": f"device_id='{db_dev['id']}'", "expand": "license_id"})
    
    for b in binds.get('items', []):
        lic = b.get('expand', {}).get('license_id')
        if lic and lic['status'] == 'active':
            if lic['type'] == 'lifetime': return {"is_pro": True, "expire_date": "永久有效"}
            act_at = lic.get('activated_at')
            if act_at:
                act_date = datetime.datetime.strptime(act_at[:10], '%Y-%m-%d').date()
                expiry = act_date + datetime.timedelta(days=(365 if lic['type'] == 'yearly' else 30))
                if today <= expiry: return {"is_pro": True, "expire_date": expiry.isoformat()}
    
    # 配额核算
    usage_res = pb.call("GET", "/device_usage/records", params={"filter": f"device_id='{db_dev['id']}' && log_date='{today.isoformat()}'"})
    used = usage_res['items'][0].get('used_quota', 0) if usage_res.get('items') else 0
    return {"is_pro": False, "remaining_quota": max(0, 3 - used)}

@app.post("/report_usage")
async def report_usage(data: dict):
    """核心扣费网关：安全映射设备与产品ID，记录配额消耗"""
    machine_code = data.get("device_id")
    product_str_id = data.get("product_id")
    count = data.get("count", 1)
    today = datetime.date.today().isoformat()

    try:
        # 1. 查出产品 15位 ID
        prod_res = pb.call("GET", "/products/records", params={"filter": f"product_id='{product_str_id}'"})
        if not prod_res.get('items'): 
            return {"status": "error", "msg": "未找到产品"}
        db_product_id = prod_res['items'][0]['id']

        # 2. 查出设备 15位 ID
        dev_res = pb.call("GET", "/devices/records", params={"filter": f"machine_code='{machine_code}'"})
        if not dev_res.get('items'):
            new_dev = pb.call("POST", "/devices/records", json={"machine_code": machine_code, "risk_level": "safe"})
            db_device_id = new_dev.get('id')
        else:
            db_device_id = dev_res['items'][0]['id']

        # 3. 扣费更新或创建
        usage_res = pb.call("GET", "/device_usage/records", params={
            "filter": f"device_id='{db_device_id}' && product_id='{db_product_id}' && log_date='{today}'"
        })
        
        if usage_res.get('items'):
            record_id = usage_res['items'][0]['id']
            current_quota = usage_res['items'][0].get('used_quota', 0)
            pb.call("PATCH", f"/device_usage/records/{record_id}", json={"used_quota": current_quota + count})
        else:
            pb.call("POST", "/device_usage/records", json={
                "device_id": db_device_id, "product_id": db_product_id, "log_date": today, "used_quota": count
            })
            
        return {"status": "ok"}
    except Exception as e:
        print(f"扣费异常: {str(e)}")
        return {"status": "error"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
