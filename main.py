#!/usr/bin/env python3
"""
TikTok Mirror Controller v3.0
সম্পূর্ণ ফাংশনাল ভার্সন - Render-এর জন্য আপডেটেড
"""

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import threading
import time
import os
import json
import re
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tiktok-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# ============ কনফিগারেশন ============
USER_DATA_DIR = os.path.join(os.getcwd(), "tiktok_session")
os.makedirs(USER_DATA_DIR, exist_ok=True)

# ============ গ্লোবাল ভেরিয়েবল ============
class TikTokBot:
    def __init__(self):
        self.driver = None
        self.is_connected = False
        self.is_running = False
        self.stop_flag = False
        self.visit_count = 0
        self.username = None
        self.current_url = None
        self.wait = None
        self.lock = threading.Lock()

bot = TikTokBot()

# ============ HTML টেমপ্লেট ============
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTok Mirror Controller</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            max-width: 600px;
            width: 100%;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #ff0050, #00f2fe);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 14px;
            opacity: 0.9;
        }

        .content {
            padding: 30px;
        }

        .status-card {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-left: 5px solid #ff0050;
        }

        .status-info h3 {
            font-size: 16px;
            color: #666;
            margin-bottom: 5px;
        }

        .status-info p {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }

        .status-badge {
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 600;
        }

        .badge-connected {
            background: #d4edda;
            color: #155724;
        }

        .badge-disconnected {
            background: #f8d7da;
            color: #721c24;
        }

        .badge-running {
            background: #cce5ff;
            color: #004085;
        }

        .badge-stopped {
            background: #fff3cd;
            color: #856404;
        }

        .url-input {
            margin-bottom: 20px;
        }

        .url-input label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
        }

        .url-input input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }

        .url-input input:focus {
            outline: none;
            border-color: #ff0050;
        }

        .url-input input:disabled {
            background: #f5f5f5;
            cursor: not-allowed;
        }

        .button-group {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
        }

        .btn {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            transition: all 0.3s;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-primary {
            background: linear-gradient(135deg, #ff0050, #ff4d7d);
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255,0,80,0.3);
        }

        .btn-success {
            background: linear-gradient(135deg, #00f2fe, #4facfe);
            color: white;
        }

        .btn-success:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,242,254,0.3);
        }

        .btn-danger {
            background: linear-gradient(135deg, #ff4444, #ff6b6b);
            color: white;
        }

        .btn-danger:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255,68,68,0.3);
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .counter-box {
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
        }

        .counter-label {
            font-size: 18px;
            margin-bottom: 10px;
            opacity: 0.9;
        }

        .counter-number {
            font-size: 72px;
            font-weight: bold;
            line-height: 1;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
            display: none;
        }

        .progress-bar.active {
            display: block;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #ff0050, #00f2fe);
            animation: progress 1.5s ease-in-out infinite;
            width: 100%;
        }

        @keyframes progress {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }

        .stat-item {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #ff0050;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #666;
            font-size: 14px;
        }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            border-radius: 10px;
            padding: 15px 25px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 10px;
            transform: translateX(400px);
            transition: transform 0.3s;
            z-index: 1000;
        }

        .toast.show {
            transform: translateX(0);
        }

        .toast.success { border-left: 4px solid #28a745; }
        .toast.error { border-left: 4px solid #dc3545; }
        .toast.warning { border-left: 4px solid #ffc107; }
        .toast.info { border-left: 4px solid #17a2b8; }

        .username {
            background: #e8f5e9;
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            display: none;
        }

        .username.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fab fa-tiktok"></i> TikTok Mirror Controller</h1>
            <p>প্রোফেশনাল অটোমেশন টুল | রিয়েল-টাইম কাউন্টার</p>
        </div>

        <div class="content">
            <!-- স্ট্যাটাস কার্ড -->
            <div class="status-card">
                <div class="status-info">
                    <h3>অ্যাকাউন্ট স্ট্যাটাস</h3>
                    <p id="accountStatusText">ডিসকানেক্টেড</p>
                </div>
                <div class="status-badge" id="accountStatusBadge">● ডিসকানেক্টেড</div>
            </div>

            <!-- ইউজারনেম ডিসপ্লে -->
            <div class="username" id="usernameDisplay">
                <i class="fas fa-user-circle"></i> <span id="username">-</span>
            </div>

            <!-- কানেক্ট বাটন -->
            <button class="btn btn-primary" id="connectBtn" onclick="connectAccount()" style="width: 100%; margin-bottom: 20px;">
                <i class="fas fa-plug"></i> অ্যাকাউন্ট কানেক্ট
            </button>

            <!-- URL ইনপুট -->
            <div class="url-input">
                <label><i class="fas fa-link"></i> TikTok ভিডিও URL</label>
                <input type="url" id="urlInput" placeholder="https://www.tiktok.com/@username/video/123456789" disabled>
            </div>

            <!-- কন্ট্রোল বাটন -->
            <div class="button-group">
                <button class="btn btn-success" id="startBtn" onclick="startAutomation()" disabled>
                    <i class="fas fa-play"></i> শুরু
                </button>
                <button class="btn btn-danger" id="stopBtn" onclick="stopAutomation()" disabled>
                    <i class="fas fa-stop"></i> বন্ধ
                </button>
            </div>

            <!-- কাউন্টার -->
            <div class="counter-box">
                <div class="counter-label">মোট ভিজিট</div>
                <div class="counter-number" id="counter">0</div>
            </div>

            <!-- প্রোগ্রেস বার -->
            <div class="progress-bar" id="progressBar">
                <div class="progress-fill"></div>
            </div>

            <!-- পরিসংখ্যান -->
            <div class="stats-grid" id="statsGrid" style="display: none;">
                <div class="stat-item">
                    <div class="stat-value" id="successCount">0</div>
                    <div class="stat-label">সফল</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="failedCount">0</div>
                    <div class="stat-label">ব্যর্থ</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="successRate">0%</div>
                    <div class="stat-label">সাফল্য</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="sessionTime">00:00</div>
                    <div class="stat-label">সময়</div>
                </div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast">
        <i class="fas" id="toastIcon"></i>
        <span id="toastMessage"></span>
    </div>

    <script>
        const socket = io();
        let isConnected = false;
        let isRunning = false;
        let sessionTimer = null;
        let sessionSeconds = 0;

        // এলিমেন্ট রেফারেন্স
        const elements = {
            connectBtn: document.getElementById('connectBtn'),
            startBtn: document.getElementById('startBtn'),
            stopBtn: document.getElementById('stopBtn'),
            urlInput: document.getElementById('urlInput'),
            counter: document.getElementById('counter'),
            accountStatusText: document.getElementById('accountStatusText'),
            accountStatusBadge: document.getElementById('accountStatusBadge'),
            usernameDisplay: document.getElementById('usernameDisplay'),
            username: document.getElementById('username'),
            progressBar: document.getElementById('progressBar'),
            statsGrid: document.getElementById('statsGrid'),
            successCount: document.getElementById('successCount'),
            failedCount: document.getElementById('failedCount'),
            successRate: document.getElementById('successRate'),
            sessionTime: document.getElementById('sessionTime')
        };

        // সকেট ইভেন্ট
        socket.on('connect', () => {
            showToast('সার্ভারের সাথে সংযুক্ত', 'success');
        });

        socket.on('status_update', (data) => {
            updateUI(data);
        });

        socket.on('connection_status', (data) => {
            isConnected = data.connected;
            if (data.username) {
                elements.username.textContent = data.username;
                elements.usernameDisplay.classList.add('show');
            }
            
            if (isConnected) {
                elements.accountStatusText.textContent = 'কানেক্টেড';
                elements.accountStatusText.style.color = '#28a745';
                elements.accountStatusBadge.textContent = '● কানেক্টেড';
                elements.accountStatusBadge.className = 'status-badge badge-connected';
                elements.connectBtn.disabled = true;
                elements.connectBtn.innerHTML = '<i class="fas fa-check"></i> কানেক্টেড';
                elements.urlInput.disabled = false;
                
                if (!isRunning) {
                    elements.startBtn.disabled = false;
                }
                
                showToast('✅ অ্যাকাউন্ট কানেক্টেড!', 'success');
            } else {
                elements.accountStatusText.textContent = 'ডিসকানেক্টেড';
                elements.accountStatusText.style.color = '#dc3545';
                elements.accountStatusBadge.textContent = '● ডিসকানেক্টেড';
                elements.accountStatusBadge.className = 'status-badge badge-disconnected';
                elements.connectBtn.disabled = false;
                elements.connectBtn.innerHTML = '<i class="fas fa-plug"></i> অ্যাকাউন্ট কানেক্ট';
                elements.urlInput.disabled = true;
                elements.startBtn.disabled = true;
                elements.stopBtn.disabled = true;
                elements.usernameDisplay.classList.remove('show');
            }
        });

        socket.on('automation_started', () => {
            isRunning = true;
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = false;
            elements.progressBar.classList.add('active');
            elements.statsGrid.style.display = 'grid';
            elements.urlInput.disabled = true;
            
            startSessionTimer();
            showToast('▶️ অটোমেশন শুরু হয়েছে', 'success');
        });

        socket.on('automation_stopped', (data) => {
            isRunning = false;
            elements.startBtn.disabled = !isConnected;
            elements.stopBtn.disabled = true;
            elements.progressBar.classList.remove('active');
            elements.urlInput.disabled = !isConnected;
            
            if (data.final_count) {
                showToast(`⏹️ অটোমেশন বন্ধ | মোট ভিজিট: ${data.final_count}`, 'info');
            }
            
            stopSessionTimer();
        });

        socket.on('visit_update', (data) => {
            elements.counter.textContent = data.count;
        });

        socket.on('stats_update', (data) => {
            elements.successCount.textContent = data.successful || 0;
            elements.failedCount.textContent = data.failed || 0;
            
            const total = (data.successful || 0) + (data.failed || 0);
            const rate = total > 0 ? Math.round((data.successful / total) * 100) : 0;
            elements.successRate.textContent = rate + '%';
        });

        socket.on('error', (data) => {
            showToast('❌ ' + data.message, 'error');
        });

        // ফাংশন
        function connectAccount() {
            socket.emit('connect_account');
        }

        function startAutomation() {
            const url = elements.urlInput.value.trim();
            if (!url) {
                showToast('URL দিন!', 'warning');
                return;
            }
            socket.emit('start_automation', { url: url });
        }

        function stopAutomation() {
            socket.emit('stop_automation');
        }

        function updateUI(data) {
            if (data.count !== undefined) elements.counter.textContent = data.count;
            if (data.username) elements.username.textContent = data.username;
        }

        function startSessionTimer() {
            sessionSeconds = 0;
            if (sessionTimer) clearInterval(sessionTimer);
            
            sessionTimer = setInterval(() => {
                sessionSeconds++;
                const mins = Math.floor(sessionSeconds / 60);
                const secs = sessionSeconds % 60;
                elements.sessionTime.textContent = 
                    `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }, 1000);
        }

        function stopSessionTimer() {
            if (sessionTimer) {
                clearInterval(sessionTimer);
                sessionTimer = null;
            }
        }

        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            const icon = document.getElementById('toastIcon');
            const msg = document.getElementById('toastMessage');
            
            icon.className = 'fas';
            
            if (type === 'success') {
                icon.className += ' fa-check-circle';
                toast.className = 'toast show success';
            } else if (type === 'error') {
                icon.className += ' fa-exclamation-circle';
                toast.className = 'toast show error';
            } else if (type === 'warning') {
                icon.className += ' fa-exclamation-triangle';
                toast.className = 'toast show warning';
            } else {
                icon.className += ' fa-info-circle';
                toast.className = 'toast show info';
            }
            
            msg.textContent = message;
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // এন্টার কী
        elements.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !elements.startBtn.disabled) {
                startAutomation();
            }
        });
    </script>
</body>
</html>
'''

# ============ ব্রাউজার ফাংশন ============
def init_browser():
    """ব্রাউজার ইনিশিয়ালাইজ"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280,720')
        chrome_options.add_argument(f'user-data-dir={USER_DATA_DIR}')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36')
        
        # Render-এর জন্য হেডলেস মোড
        chrome_options.add_argument('--headless=new')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        bot.driver = driver
        bot.wait = WebDriverWait(driver, 10)
        
        # TikTok লোড
        driver.get("https://www.tiktok.com")
        time.sleep(3)
        
        # কুকি চেক
        check_login_status()
        
        return True
    except Exception as e:
        print(f"Browser init error: {e}")
        return False

def check_login_status():
    """লগইন স্ট্যাটাস চেক"""
    try:
        # কুকি থেকে লগইন স্ট্যাটাস চেক
        cookies = bot.driver.get_cookies()
        for cookie in cookies:
            if 'session' in cookie.get('name', '').lower() or 'sid' in cookie.get('name', '').lower():
                bot.is_connected = True
                
                # ইউজারনেম বের করার চেষ্টা
                try:
                    bot.driver.get("https://www.tiktok.com")
                    time.sleep(2)
                    elements = bot.driver.find_elements(By.CSS_SELECTOR, '[data-e2e="user-avatar"]')
                    if elements:
                        bot.username = "TikTok User"
                except:
                    pass
                
                return True
        
        bot.is_connected = False
        return False
    except:
        bot.is_connected = False
        return False

# ============ অটোমেশন লুপ ============
def automation_loop(url):
    """মেইন অটোমেশন লুপ"""
    bot.is_running = True
    bot.stop_flag = False
    bot.current_url = url
    
    success_count = 0
    fail_count = 0
    
    socketio.emit('automation_started')
    
    while bot.is_running and not bot.stop_flag:
        try:
            # ভিডিও পেজে যাওয়া
            bot.driver.get(url)
            time.sleep(2)
            
            # স্ক্রল
            bot.driver.execute_script("window.scrollBy(0, 300)")
            time.sleep(5)  # ৫ সেকেন্ড ভিউ
            
            if not bot.stop_flag:
                with bot.lock:
                    bot.visit_count += 1
                    success_count += 1
                    
                socketio.emit('visit_update', {'count': bot.visit_count})
                socketio.emit('stats_update', {
                    'successful': success_count,
                    'failed': fail_count
                })
                
        except Exception as e:
            fail_count += 1
            socketio.emit('stats_update', {
                'successful': success_count,
                'failed': fail_count
            })
            time.sleep(2)
    
    bot.is_running = False
    socketio.emit('automation_stopped', {'final_count': bot.visit_count})

# ============ ফ্লাস্ক রুট ============
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    return jsonify({
        'connected': bot.is_connected,
        'running': bot.is_running,
        'count': bot.visit_count,
        'username': bot.username
    })

# ============ সকেট ইভেন্ট ============
@socketio.on('connect_account')
def handle_connect():
    try:
        if not bot.driver:
            if not init_browser():
                socketio.emit('error', {'message': 'ব্রাউজার শুরু হয়নি'})
                return
        
        # লগইন পেজ
        bot.driver.get("https://www.tiktok.com/login")
        time.sleep(2)
        
        # QR কোড বা ফোন নম্বর অপশন
        try:
            # ফোন/ইমেইল অপশন ক্লিক
            phone_option = bot.driver.find_element(By.XPATH, "//div[contains(text(), 'ফোন/ইমেইল')]")
            phone_option.click()
        except:
            pass
        
        socketio.emit('connection_status', {
            'connected': True,
            'username': 'Logging in...'
        })
        
        # লগইন মনিটর
        def monitor_login():
            for i in range(60):  # ৬০ সেকেন্ড
                time.sleep(1)
                if check_login_status():
                    socketio.emit('connection_status', {
                        'connected': True,
                        'username': bot.username or 'TikTok User'
                    })
                    break
        
        thread = threading.Thread(target=monitor_login)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        socketio.emit('error', {'message': f'কানেক্ট এরর: {str(e)}'})

@socketio.on('start_automation')
def handle_start(data):
    url = data.get('url', '').strip()
    
    if not url:
        socketio.emit('error', {'message': 'URL দিন'})
        return
    
    if not bot.driver or not bot.is_connected:
        socketio.emit('error', {'message': 'প্রথমে অ্যাকাউন্ট কানেক্ট করুন'})
        return
    
    if bot.is_running:
        socketio.emit('error', {'message': 'অটোমেশন চলছে'})
        return
    
    # ইউআরএল ভ্যালিডেশন
    if not re.match(r'https?://(www\.)?tiktok\.com/@[\w.-]+/video/\d+', url):
        socketio.emit('error', {'message': 'ভুল TikTok URL ফরম্যাট'})
        return
    
    bot.visit_count = 0
    thread = threading.Thread(target=automation_loop, args=(url,))
    thread.daemon = True
    thread.start()

@socketio.on('stop_automation')
def handle_stop():
    if bot.is_running:
        bot.stop_flag = True
        socketio.emit('status_update', {'message': 'স্টপ হচ্ছে...'})
    else:
        socketio.emit('error', {'message': 'কোন অটোমেশন চলছে না'})

# ============ ক্লিনআপ ============
def cleanup():
    if bot.driver:
        try:
            bot.driver.quit()
        except:
            pass

# ============ মেইন ============
if __name__ == '__main__':
    import atexit
    atexit.register(cleanup)
    
    print("\n" + "="*60)
    print("🎵 TikTok Mirror Controller v3.0 (Render-এর জন্য)")
    print("="*60)
    print("\n📱 সার্ভার চালু হচ্ছে...")
    
    # Render-এর পোর্ট এনভায়রনমেন্ট ভেরিয়েবল থেকে নেওয়া
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 পোর্ট: {port}")
    print("\n📱 নেটওয়ার্ক অ্যাড্রেস:")
    print(f"   http://0.0.0.0:{port}")
    print("\n⚠️  মনে রাখবেন:")
    print("   1. প্রথমে 'অ্যাকাউন্ট কানেক্ট' এ ক্লিক করুন")
    print("   2. TikTok এ লগইন করুন (হেডলেস ব্রাউজারে)")
    print("   3. তারপর URL দিয়ে Start দিন")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
