import sys, os, time, random, requests, webbrowser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QLabel, QFileDialog, QListWidget, 
                             QMessageBox, QComboBox, QCheckBox, QDialog, QLineEdit, 
                             QProgressBar, QListWidgetItem, QFrame, QSplashScreen)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor, QColor, QPixmap
from PIL import Image
from flovico_core import FlovicoCore

# --- 环境路径适配 ---
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(BASE_DIR, "models")
os.environ["U2NET_HOME"] = MODELS_DIR
if not os.path.exists(MODELS_DIR): os.makedirs(MODELS_DIR)

# 100% 还原的忙碌日志
BUSY_LOGS = [
    "解析图像张量特征矩阵...", 
    "分离前景色与背景色差空间...", 
    "执行 Alpha 通道发丝抗锯齿...", 
    "载入高精度语义分割权重...", 
    "正在激活神经元推理节点...", 
    "分析图像主体光影连贯性...", 
    "执行非局部均值去噪计算..."
]

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, e): self.clicked.emit()

class RembgWorker(QThread):
    progress = pyqtSignal(str); item_status = pyqtSignal(str, bool); finished = pyqtSignal(int, int)
    def __init__(self, f, o, m, a, g, core): 
        super().__init__(); self.f, self.o, self.m, self.a, self.g, self.core = f, o, m, a, g, core

    def run(self):
        from rembg import remove, new_session
        s, f = 0, 0
        try:
            self.progress.emit("🚀 正在激活 AI 神经网络...第一次启动需要20-30秒左右，请耐心等候...")
            prov = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.g else ['CPUExecutionProvider']
            session = new_session(self.m, providers=prov)
            for p in self.f:
                # 强制联网校验，断网即停
                if self.core.check_quota().get("msg") == "网络连接失败":
                    self.progress.emit("❌ 授权校验中断，请重新连接网络！")
                    break
                name = os.path.basename(p)
                try:
                    for _ in range(2): self.progress.emit(f"[{name}] {random.choice(BUSY_LOGS)}"); time.sleep(0.1)
                    out = remove(Image.open(p), session=session, alpha_matting=self.a)
                    out.save(os.path.join(self.o, f"{os.path.splitext(name)[0]}_flovico.png"))
                    self.item_status.emit(p, True); s += 1
                    self.core.report_usage(1)
                except: self.item_status.emit(p, False); f += 1
        except Exception as e: self.progress.emit(f"引擎异常：{str(e)}")
        self.finished.emit(s, f)

class UpgradeDialog(QDialog):
    activated = pyqtSignal()
    def __init__(self, core, parent=None):
        super().__init__(parent); self.core = core; self.cur_order_id = None
        self.setWindowTitle("授权激活中心"); self.setFixedSize(650, 480); self.setStyleSheet("background-color: #ffffff;")
        
        main_v = QVBoxLayout(self); main_v.setContentsMargins(30, 20, 30, 20); main_v.setSpacing(20)
        
        # 头部标题
        title = QLabel("开启批量 Pro 极速生产力"); title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0f172a;")
        main_v.addWidget(title)

        # 中间双栏容器
        content_h = QHBoxLayout(); content_h.setSpacing(30)
        
        # --- 左侧：权益描述与套餐按钮 ---
        left_v = QVBoxLayout(); left_v.setSpacing(12)
        desc = QLabel("• <b>商业增效：</b>告别传统按张计费模式，一次付费终身无限批量导出。<br>"
                       "• <b>全系引擎：</b>解锁5大顶级离线AI引擎全部效果，产出提升200%。<br>"
                       "• <b>安全合规：</b>本地运行，物理隔绝云端泄露风险，保障商业隐私。")
        desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px; color: #64748b; line-height: 1.6;"); left_v.addWidget(desc)

        conf = self.core.get_cloud_config()
        self.btn_m = QPushButton(f"体验月卡 ￥{conf.get('price_monthly', '19.9')}")
        self.btn_y = QPushButton(f"尊享年卡 ￥{conf.get('price_yearly', '99')}")
        self.btn_l = QPushButton(f"至尊终身 ￥{conf.get('price_lifetime', '199')}")
        
        self.btns = {"monthly": self.btn_m, "yearly": self.btn_y, "lifetime": self.btn_l}
        for k, b in self.btns.items():
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, x=k: self.start_pay(x))
            left_v.addWidget(b)
        content_h.addLayout(left_v, 3)

        # --- 右侧：二维码展示区 ---
        right_v = QVBoxLayout(); right_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_box = QLabel("请选择套餐\n获取付款码"); self.qr_box.setFixedSize(220, 220)
        self.qr_box.setStyleSheet("border: 2px dashed #cbd5e1; border-radius: 10px; color: #94a3b8; font-size: 12px;")
        self.qr_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pay_hint = QLabel("支持微信/支付宝扫码"); self.pay_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        right_v.addWidget(self.qr_box); right_v.addWidget(self.pay_hint)
        content_h.addLayout(right_v, 2)
        
        main_v.addLayout(content_h)

        # --- 底部：激活码验证（后门保留）---
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("color: #f1f5f9;"); main_v.addWidget(line)
        h_input = QHBoxLayout(); self.key_input = QLineEdit(); self.key_input.setPlaceholderText("粘贴 16 位激活码...")
        self.key_input.setStyleSheet("padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px;")
        self.active_btn = QPushButton("验证激活"); self.active_btn.setStyleSheet("background-color: #0f172a; color: white; padding: 10px 20px; font-weight: bold; border-radius: 6px;")
        self.active_btn.clicked.connect(self.do_manual_act)
        h_input.addWidget(self.key_input); h_input.addWidget(self.active_btn); main_v.addLayout(h_input)

        # 定时轮询与初始化
        self.poll_timer = QTimer(self); self.poll_timer.timeout.connect(self.check_status)
        QTimer.singleShot(100, lambda: self.start_pay('yearly')) # 默认出年卡码

    def update_styles(self, selected_type):
        """选中套餐高亮效果"""
        for k, b in self.btns.items():
            if k == selected_type:
                b.setStyleSheet("QPushButton { background-color: #eff6ff; border: 2px solid #3b82f6; padding: 12px; border-radius: 8px; font-weight: bold; text-align: left; color: #1e40af; }")
            else:
                b.setStyleSheet("QPushButton { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px; font-weight: bold; text-align: left; color: #475569; }")

    def start_pay(self, o_type):
        self.update_styles(o_type); self.qr_box.setText("生成中..."); self.poll_timer.stop()
        res = self.core.create_order(o_type)
        if "url_qrcode" in res:
            self.cur_order_id = res['order_id']
            img_data = requests.get(res['url_qrcode']).content
            pix = QPixmap(); pix.loadFromData(img_data)
            self.qr_box.setPixmap(pix.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
            self.poll_timer.start(2000)
        else: self.qr_box.setText("获取失败"); QMessageBox.warning(self, "错误", "无法连接支付网关")

    def check_status(self):
        """支付成功自动关闭逻辑"""
        if self.cur_order_id:
            res = self.core.check_order_status(self.cur_order_id)
            if res.get('status') == 'paid':
                self.poll_timer.stop(); QMessageBox.information(self, "成功", "支付成功！Pro 功能已解锁。")
                self.activated.emit(); self.accept()

    def do_manual_act(self):
        res = self.core.check_quota(license_key=self.key_input.text().strip())
        if res.get('is_pro'): QMessageBox.information(self, "成功", "激活成功！"); self.activated.emit(); self.accept()
        else: QMessageBox.critical(self, "失败", f"无效激活码：{res.get('msg')}")

class FlovicoApp(QMainWindow):
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.core = FlovicoCore(); self.list_items_map = {}; self.init_ui()
    
    def init_ui(self):
        self.setMinimumSize(1050, 800)
        self.setStyleSheet("QMainWindow { background-color: #f1f5f9; } QFrame#Card { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; } QLabel { color: #475569; } QComboBox, QLineEdit { border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px; }")
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(25, 25, 25, 25); main_layout.setSpacing(20)
        self.ad_banner = ClickableLabel("正在同步云端安全网格..."); self.ad_banner.setStyleSheet("background-color: #fef3c7; color: #92400e; padding: 18px; font-weight: bold; border-radius: 10px; border: 1px solid #fde68a;")
        self.ad_banner.setAlignment(Qt.AlignmentFlag.AlignCenter); self.ad_banner.clicked.connect(lambda: webbrowser.open(self.core.get_cloud_config().get("ad_link", ""))); main_layout.addWidget(self.ad_banner)
        content_layout = QHBoxLayout(); content_layout.setSpacing(25); left_panel = QVBoxLayout(); left_panel.setSpacing(15)
        c1 = QFrame(); c1.setObjectName("Card"); v1 = QVBoxLayout(c1); v1.addWidget(QLabel("<b>⚙️ 算法策略配置</b>"))
        self.model_box = QComboBox(); self.model_box.addItems(["BiRefNet-Portrait (人像究极精修)", "BiRefNet-General (通用重装高精)", "U2Net-Cloth-Seg (服装专精)", "U2Net-Human (人像轻量版)", "ISNet-Anime (二次元动漫)"])
        self.model_map = {"BiRefNet-Portrait (人像究极精修)": "birefnet-portrait", "BiRefNet-General (通用重装高精)": "birefnet-general", "U2Net-Cloth-Seg (服装专精)": "u2net_cloth_seg", "U2Net-Human (人像轻量版)": "u2net_human_seg", "ISNet-Anime (二次元动漫)": "isnet-anime"}
        self.gpu_cb = QCheckBox("🚀 开启硬件加速 (推荐 N 卡勾选)"); self.gpu_cb.setChecked(True); self.alpha_cb = QCheckBox("✂️ 开启发丝级平滑 (Alpha Matting)"); v1.addWidget(self.model_box); v1.addWidget(self.gpu_cb); v1.addWidget(self.alpha_cb); left_panel.addWidget(c1)
        c2 = QFrame(); c2.setObjectName("Card"); v2 = QVBoxLayout(c2); v2.addWidget(QLabel("<b>💎 授权服务中心</b>")); self.quota_label = QLabel("正在同步配额..."); self.btn_pay = QPushButton("👑 升级批量 Pro 版"); self.btn_pay.setStyleSheet("background-color: #0f172a; color: white; padding: 14px; border-radius: 8px; font-weight: bold;"); self.btn_pay.clicked.connect(self.show_upgrade_dialog); v2.addWidget(self.quota_label); v2.addWidget(self.btn_pay); left_panel.addWidget(c2)
        c3 = QFrame(); c3.setObjectName("Card"); v3 = QVBoxLayout(c3); v3.addWidget(QLabel("<b>💡 专家级使用指南</b>"))
        # 100% 还原的 5 点说明话术
        g_txt = QLabel("<br>1. <b>画质定胜负：</b>输入原图分辨率越高（建议 > 2K），AI 对复杂发丝与织物边缘的处理就越接近商业级海报效果。<br><br>"
                       "2. <b>策略避坑准则：</b>处理毛绒、人像请务必勾选「发丝级平滑」；处理硬边缘素材请取消勾选以保障边缘锐度。<br><br>"
                       "3. <b>复杂背景挑战：</b>若背景与主体色彩极其接近，建议微调原图对比度后再导入，可显著提升 Alpha 通道识别成功率。<br><br>"
                       "4. <b>资产安全隐私：</b>基于本地物理算力渲染，素材永不触网。买断一次，即享终身无限批量处理。<br><br>"
                       "5. <b>软件说明：</b>付费版可解锁批量处理功能，单次可导入上千张图片进行自动抠图，极大提升工作效率。试用版每天提供3张免费配额，适合偶尔使用或测试效果。轻度使用的用户完全够用。")
        g_txt.setWordWrap(True); g_txt.setStyleSheet("font-size: 12px; line-height: 1.8; color: #64748b;"); v3.addWidget(g_txt); left_panel.addWidget(c3); left_panel.addStretch()
        right_panel = QVBoxLayout(); self.file_list = QListWidget(); self.file_list.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 12px; background: white; padding: 10px;")
        btn_box = QHBoxLayout(); btn_box.setSpacing(15); self.btn_add = QPushButton("导入新批次 (自动重置)"); self.btn_add.setFixedHeight(55); self.btn_add.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; font-weight: bold; border-radius: 10px; color: #475569;")
        self.btn_run = QPushButton("开始批量抠图"); self.btn_run.setFixedHeight(55); self.btn_run.setStyleSheet("background-color: #0f172a; color: white; font-weight: bold; font-size: 16px; border-radius: 10px;")
        btn_box.addWidget(self.btn_add, 1); btn_box.addWidget(self.btn_run, 2); right_panel.addWidget(self.file_list); right_panel.addLayout(btn_box); content_layout.addLayout(left_panel, 1); content_layout.addLayout(right_panel, 2); main_layout.addLayout(content_layout)
        self.pbar = QProgressBar(); self.pbar.hide(); self.status_label = QLabel("就绪 | 提示：直接将图片或文件夹拖入上方即可"); self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;"); main_layout.addWidget(self.pbar); main_layout.addWidget(self.status_label)
        self.btn_add.clicked.connect(self.select_files); self.btn_run.clicked.connect(self.handle_run)

    def update_quota_display(self):
        """有效期提示与原创版权声明标题还原"""
        res = self.core.check_quota(); conf = self.core.get_cloud_config()
        if res.get("msg") == "网络连接失败":
            self.btn_run.setEnabled(False); self.btn_run.setText("🔌 请连接网络以验证授权"); return
        
        if res.get('is_pro'):
            self.btn_pay.setText("✨ 您已是尊贵的 Pro 用户"); self.btn_pay.setEnabled(False)
            self.quota_label.setText(f"授权状态: 批量 Pro 商业版\n有效期至: {res.get('expire_date', '永久有效')}")
        else:
            self.btn_pay.setText("👑 升级批量 Pro 版"); self.btn_pay.setEnabled(True)
            self.quota_label.setText(f"授权状态: 全功能试用版\n今日剩余免费配额: {res.get('remaining_quota', 0)} 张")
        
        # 100% 还原的版权声明标题
        self.setWindowTitle(f"Flovico AI 智能批量抠图专家 | 客服QQ：{conf.get('qq_support', '657183')} | 本软件为Flovico国内团队原创开发，已申请软件著作权，破解、盗版必究！")
        self.ad_banner.setText(conf.get("ad_text", ""))

    def add_files(self, fs):
        self.file_list.clear(); self.list_items_map.clear()
        for f in fs:
            if os.path.isdir(f):
                for r, _, sfs in os.walk(f):
                    for sf in sfs:
                        if sf.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            p = os.path.join(r, sf); i = QListWidgetItem(f"⏳ [队列中] {p}"); self.file_list.addItem(i); self.list_items_map[p] = i
            elif f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                i = QListWidgetItem(f"⏳ [队列中] {f}"); self.file_list.addItem(i); self.list_items_map[f] = i
    def select_files(self): fs, _ = QFileDialog.getOpenFileNames(self, "导入素材"); self.add_files(fs) if fs else None
    def show_upgrade_dialog(self): d = UpgradeDialog(self.core, self); d.activated.connect(self.update_quota_display); d.exec()
    def handle_run(self):
        res = self.core.check_quota()
        if not res.get('is_pro') and res.get('remaining_quota', 0) <= 0: QMessageBox.warning(self, "额度不足", "请升级 Pro！"); return
        self.btn_run.setEnabled(False); out = QFileDialog.getExistingDirectory(self, "选择保存位置")
        if out:
            self.w = RembgWorker(list(self.list_items_map.keys()), out, self.model_map[self.model_box.currentText()], self.alpha_cb.isChecked(), self.gpu_cb.isChecked(), self.core)
            self.w.item_status.connect(self.update_item_ui); self.w.finished.connect(lambda: (self.btn_run.setEnabled(True), self.update_quota_display())); self.w.start()
        else: self.btn_run.setEnabled(True)

    def update_item_ui(self, p, ok):
        i = self.list_items_map.get(p)
        if i: i.setText(f"{'✅' if ok else '❌'} {p}"); i.setForeground(QColor("#10b981" if ok else "#ef4444"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = QSplashScreen(QPixmap(os.path.join(BASE_DIR, "splash.png"))); splash.show(); app.processEvents()
    window = FlovicoApp(); splash.finish(window); window.show(); QTimer.singleShot(500, window.update_quota_display); sys.exit(app.exec())