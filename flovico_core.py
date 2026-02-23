import os, sys, requests, threading, json, uuid

class FlovicoCore:
    def __init__(self):
        # 核心：您的通用网关 IP 地址
        self.api_base = "http://107.173.89.194:8000" 
        # 核心：软件身份标识与当前版本号
        self.product_id = "rembg_pro_001"
        self.version = "1.0.0.0" 
        self.machine_code = str(uuid.getnode())
        
        # 处理授权文件存储路径
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.license_path = os.path.join(base_dir, ".license_key")
        
        self.license_key = self.load_license()
        self.cloud_config = {
            "ad_text": "正在同步云端安全网格...", 
            "ad_link": "https://flovico.com", 
            "buy_link": "https://flovico.com/pay", 
            "qq_support": "657183",
            "download_url": "https://flovico.com",
            "latest_version": "1.0.0.0"
        }

    def load_license(self):
        """加载本地激活码文件"""
        try:
            if os.path.exists(self.license_path):
                with open(self.license_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except: pass
        return None

    def get_cloud_config(self):
        """同步云端配置、版本与价格参数"""
        try:
            r = requests.get(f"{self.api_base}/config", params={"product_id": self.product_id}, timeout=5)
            if r.status_code == 200:
                self.cloud_config.update(r.json())
        except: pass
        return self.cloud_config

    def create_order(self, order_type):
        """向服务端请求创建支付订单并获取二维码"""
        try:
            res = requests.post(f"{self.api_base}/create_order", json={
                "product_id": self.product_id,
                "device_id": self.machine_code,
                "order_type": order_type
            }, timeout=10)
            return res.json()
        except Exception as e:
            return {"error": f"订单创建失败: {str(e)}"}

    def check_order_status(self, order_id):
        """轮询查询订单支付状态"""
        try:
            r = requests.get(f"{self.api_base}/check_order", params={"order_id": order_id}, timeout=5)
            return r.json()
        except:
            return {"status": "error"}

    def check_quota(self, license_key=None):
        """核心授权校验：确保联网并获取到期时间"""
        target_key = license_key or self.license_key or "Trial_User"
        try:
            res = requests.post(f"{self.api_base}/check_license", json={
                "device_id": self.machine_code, 
                "license_key": target_key, 
                "product_id": self.product_id
            }, timeout=5).json()
            
            # 若手动输入激活码成功，则持久化保存
            if res.get('is_pro') and license_key:
                try:
                    with open(self.license_path, "w", encoding="utf-8") as f:
                        f.write(license_key)
                    self.license_key = license_key
                except: pass
            return res
        except: 
            # 网络异常视为未授权
            return {"is_pro": False, "remaining_quota": 0, "msg": "网络连接失败"}

    def report_usage(self, count=1):
        """上报图片处理量"""
        try:
            requests.post(f"{self.api_base}/report_usage", json={
                "device_id": self.machine_code, 
                "product_id": self.product_id, 
                "count": count
            }, timeout=5)
        except: pass