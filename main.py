import os
import threading
import time
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'tiktok-mirror-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), 'user_data')
os.makedirs(USER_DATA_DIR, exist_ok=True)

state = {
    'stop_flag': False,
    'is_running': False,
    'visit_count': 0,
    'connected': False,
    'browser': None,
    'context': None,
    'page': None,
    'loop_thread': None,
}
state_lock = threading.Lock()


def get_playwright_browser(headed=True):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        USER_DATA_DIR,
        headless=not headed,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
        ]
    )
    return pw, context


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/connect', methods=['POST'])
def connect_account():
    def open_login_browser():
        try:
            pw, context = get_playwright_browser(headed=False)
            page = context.new_page()
            page.goto('https://www.tiktok.com/login', wait_until='domcontentloaded', timeout=30000)
            socketio.emit('status_update', {'connected': False, 'message': 'Browser opened — please log in to TikTok, then click "Mark as Connected".'})

            with state_lock:
                state['browser'] = pw
                state['context'] = context
                state['page'] = page
        except Exception as e:
            socketio.emit('error', {'message': f'Failed to open browser: {str(e)}'})

    t = threading.Thread(target=open_login_browser, daemon=True)
    t.start()
    return jsonify({'success': True, 'message': 'Opening browser...'})


@app.route('/mark_connected', methods=['POST'])
def mark_connected():
    with state_lock:
        state['connected'] = True
    socketio.emit('status_update', {'connected': True, 'message': 'Status: Connected'})
    return jsonify({'success': True})


@app.route('/start', methods=['POST'])
def start_loop():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'success': False, 'message': 'Please provide a TikTok video URL.'})

    if not url.startswith('http'):
        return jsonify({'success': False, 'message': 'Invalid URL. Must start with http:// or https://'})

    with state_lock:
        if state['is_running']:
            return jsonify({'success': False, 'message': 'Loop is already running.'})
        if not state['connected']:
            return jsonify({'success': False, 'message': 'Please connect your TikTok account first.'})
        state['stop_flag'] = False
        state['is_running'] = True
        state['visit_count'] = 0

    def run_loop():
        try:
            with state_lock:
                context = state['context']
                page = state['page']

            if context is None:
                socketio.emit('error', {'message': 'No browser session found. Please connect first.'})
                with state_lock:
                    state['is_running'] = False
                return

            while True:
                with state_lock:
                    if state['stop_flag']:
                        break

                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                except Exception as nav_err:
                    socketio.emit('error', {'message': f'Navigation error: {str(nav_err)}'})
                    break

                time.sleep(5)

                with state_lock:
                    if state['stop_flag']:
                        break
                    state['visit_count'] += 1
                    count = state['visit_count']

                socketio.emit('visit_update', {'count': count})

        except Exception as e:
            socketio.emit('error', {'message': f'Loop error: {str(e)}'})
        finally:
            with state_lock:
                state['is_running'] = False
            socketio.emit('loop_stopped', {'message': 'Loop stopped.'})

    t = threading.Thread(target=run_loop, daemon=True)
    with state_lock:
        state['loop_thread'] = t
    t.start()
    return jsonify({'success': True, 'message': 'Loop started!'})


@app.route('/stop', methods=['POST'])
def stop_loop():
    with state_lock:
        state['stop_flag'] = True
    return jsonify({'success': True, 'message': 'Stop signal sent.'})


@app.route('/status', methods=['GET'])
def get_status():
    with state_lock:
        return jsonify({
            'connected': state['connected'],
            'is_running': state['is_running'],
            'visit_count': state['visit_count'],
        })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)


# Embedded HTML Template (original index.html)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TikTok Mirror Controller</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg-primary: #0a0a0a;
            --bg-card: #161616;
            --bg-input: #1e1e1e;
            --accent: #fe2c55;
            --accent-dark: #c0163c;
            --accent-2: #25f4ee;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
            --border: #2a2a2a;
            --success: #25f4ee;
            --error: #fe2c55;
            --warning: #ffcc00;
        }

        body {
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        header {
            width: 100%;
            padding: 20px 40px;
            display: flex;
            align-items: center;
            gap: 14px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-card);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: var(--accent);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }

        .logo h1 {
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .logo h1 span { color: var(--accent); }

        .header-badge {
            margin-left: auto;
            font-size: 0.75rem;
            color: var(--text-secondary);
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 20px;
        }

        main {
            width: 100%;
            max-width: 900px;
            padding: 36px 20px;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }

        @media (max-width: 680px) {
            .grid { grid-template-columns: 1fr; }
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
        }

        .card-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin-bottom: 20px;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-secondary);
            transition: background 0.3s;
            flex-shrink: 0;
        }

        .status-dot.connected { background: var(--success); box-shadow: 0 0 8px var(--success); }
        .status-dot.error { background: var(--error); }

        .status-text {
            font-size: 0.9rem;
            color: var(--text-secondary);
            transition: color 0.3s;
        }

        .status-text.connected { color: var(--success); }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 22px;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s;
            width: 100%;
        }

        .btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        .btn-primary {
            background: var(--accent);
            color: #fff;
        }

        .btn-primary:hover:not(:disabled) {
            background: var(--accent-dark);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: var(--bg-input);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover:not(:disabled) {
            border-color: var(--accent-2);
            color: var(--accent-2);
        }

        .btn-stop {
            background: transparent;
            color: var(--error);
            border: 1px solid var(--error);
        }

        .btn-stop:hover:not(:disabled) {
            background: var(--error);
            color: #fff;
        }

        .btn-mark {
            background: transparent;
            color: var(--accent-2);
            border: 1px solid var(--accent-2);
            margin-top: 10px;
        }

        .btn-mark:hover:not(:disabled) {
            background: var(--accent-2);
            color: #000;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }

        label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            letter-spacing: 0.5px;
        }

        input[type="text"] {
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 0.9rem;
            padding: 12px 16px;
            width: 100%;
            outline: none;
            transition: border-color 0.2s;
        }

        input[type="text"]:focus {
            border-color: var(--accent);
        }

        input[type="text"]::placeholder {
            color: #444;
        }

        .counter-display {
            text-align: center;
            padding: 24px 0;
        }

        .counter-number {
            font-size: 3.5rem;
            font-weight: 800;
            line-height: 1;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .counter-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 6px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .progress-bar-wrap {
            height: 4px;
            background: var(--bg-input);
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0 0;
        }

        .progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent), var(--accent-2));
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .progress-bar.active {
            animation: pulse-bar 2s ease-in-out infinite;
        }

        @keyframes pulse-bar {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .pulse-ring {
            display: none;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 0 0 rgba(254, 44, 85, 0.7);
            animation: pulse-ring 1.4s ease infinite;
        }

        .pulse-ring.active { display: inline-block; }

        @keyframes pulse-ring {
            0% { box-shadow: 0 0 0 0 rgba(254, 44, 85, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(254, 44, 85, 0); }
            100% { box-shadow: 0 0 0 0 rgba(254, 44, 85, 0); }
        }

        .loop-status {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        .btn-row {
            display: flex;
            gap: 10px;
        }

        .btn-row .btn { flex: 1; }

        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 9999;
        }

        .toast {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 20px;
            font-size: 0.85rem;
            max-width: 320px;
            animation: slide-in 0.3s ease;
            border-left: 3px solid var(--accent-2);
        }

        .toast.error { border-left-color: var(--error); }
        .toast.success { border-left-color: var(--success); }

        @keyframes slide-in {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .info-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px 28px;
        }

        .info-section h3 {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }

        .info-steps {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .info-steps li {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .step-num {
            flex-shrink: 0;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: var(--bg-input);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 700;
            color: var(--accent);
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-icon">♾️</div>
            <h1>TikTok <span>Mirror</span> Controller</h1>
        </div>
        <div class="header-badge">Auto-Loop Viewer</div>
    </header>

    <main>
        <div class="grid">
            <!-- Account Card -->
            <div class="card">
                <div class="card-title">Account Status</div>

                <div class="status-indicator">
                    <div class="status-dot" id="statusDot"></div>
                    <span class="status-text" id="statusText">Not connected</span>
                </div>

                <p style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:16px;line-height:1.5;">
                    Click <strong style="color:var(--text-primary)">Connect Account</strong> to open a TikTok login window. Log in manually, then click <strong style="color:var(--accent-2)">Mark as Connected</strong>.
                </p>

                <button class="btn btn-primary" id="btnConnect" onclick="connectAccount()">
                    🔗 Connect Account
                </button>
                <button class="btn btn-mark" id="btnMark" onclick="markConnected()" disabled>
                    ✓ Mark as Connected
                </button>
            </div>

            <!-- Counter Card -->
            <div class="card">
                <div class="card-title">Loop Statistics</div>
                <div class="counter-display">
                    <div class="counter-number" id="visitCount">0</div>
                    <div class="counter-label">Total Visits</div>
                </div>
                <div class="progress-bar-wrap">
                    <div class="progress-bar" id="progressBar"></div>
                </div>
            </div>
        </div>

        <!-- Automation Controls -->
        <div class="card">
            <div class="card-title">Automation Controls</div>

            <div class="loop-status">
                <span class="pulse-ring" id="pulseRing"></span>
                <span id="loopStatusText">Idle — waiting to start</span>
            </div>

            <div class="input-group">
                <label>TikTok Video URL</label>
                <input
                    type="text"
                    id="videoUrl"
                    placeholder="https://www.tiktok.com/@username/video/1234567890"
                />
            </div>

            <div class="btn-row">
                <button class="btn btn-secondary" id="btnStart" onclick="startLoop()">
                    ▶ Start Loop
                </button>
                <button class="btn btn-stop" id="btnStop" onclick="stopLoop()" disabled>
                    ■ Stop
                </button>
            </div>
        </div>

        <!-- How-to Section -->
        <div class="info-section">
            <h3>How to Use</h3>
            <ul class="info-steps">
                <li><span class="step-num">1</span> Click <strong>Connect Account</strong> — a browser window will open pointing to TikTok login.</li>
                <li><span class="step-num">2</span> Log in to TikTok in the browser window. Your session is saved persistently.</li>
                <li><span class="step-num">3</span> Return here and click <strong>Mark as Connected</strong>.</li>
                <li><span class="step-num">4</span> Paste a TikTok video URL and click <strong>Start Loop</strong>.</li>
                <li><span class="step-num">5</span> The counter updates in real-time. Click <strong>Stop</strong> to end the loop.</li>
            </ul>
        </div>
    </main>

    <div class="toast-container" id="toastContainer"></div>

    <script>
        const socket = io();
        let visitCount = 0;
        let isRunning = false;

        socket.on('connect', () => {
            fetchStatus();
        });

        socket.on('status_update', (data) => {
            if (data.connected) {
                setConnected(true);
            }
            if (data.message) showToast(data.message, data.connected ? 'success' : 'info');
        });

        socket.on('visit_update', (data) => {
            visitCount = data.count;
            document.getElementById('visitCount').textContent = visitCount;
            animateProgress();
        });

        socket.on('loop_stopped', (data) => {
            setRunning(false);
            showToast(data.message || 'Loop stopped.', 'info');
        });

        socket.on('error', (data) => {
            showToast(data.message, 'error');
            setRunning(false);
        });

        function fetchStatus() {
            fetch('/status')
                .then(r => r.json())
                .then(data => {
                    if (data.connected) setConnected(true);
                    visitCount = data.visit_count;
                    document.getElementById('visitCount').textContent = visitCount;
                    if (data.is_running) setRunning(true);
                });
        }

        function setConnected(val) {
            const dot = document.getElementById('statusDot');
            const txt = document.getElementById('statusText');
            const btnMark = document.getElementById('btnMark');
            if (val) {
                dot.className = 'status-dot connected';
                txt.textContent = 'Status: Connected';
                txt.className = 'status-text connected';
                btnMark.disabled = true;
                document.getElementById('btnConnect').textContent = '✓ Browser Open';
            } else {
                btnMark.disabled = false;
            }
        }

        function setRunning(val) {
            isRunning = val;
            const btnStart = document.getElementById('btnStart');
            const btnStop = document.getElementById('btnStop');
            const pulse = document.getElementById('pulseRing');
            const statusTxt = document.getElementById('loopStatusText');
            const bar = document.getElementById('progressBar');

            if (val) {
                btnStart.disabled = true;
                btnStop.disabled = false;
                pulse.classList.add('active');
                statusTxt.textContent = 'Running — visiting every 5 seconds';
                bar.classList.add('active');
                bar.style.width = '100%';
            } else {
                btnStart.disabled = false;
                btnStop.disabled = true;
                pulse.classList.remove('active');
                statusTxt.textContent = 'Idle — waiting to start';
                bar.classList.remove('active');
                bar.style.width = '0%';
            }
        }

        function animateProgress() {
            const bar = document.getElementById('progressBar');
            bar.style.width = '100%';
        }

        function connectAccount() {
            document.getElementById('btnConnect').disabled = true;
            document.getElementById('btnMark').disabled = false;
            fetch('/connect', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message || 'Browser opening...', 'info');
                })
                .catch(() => {
                    showToast('Failed to connect. Try again.', 'error');
                    document.getElementById('btnConnect').disabled = false;
                });
        }

        function markConnected() {
            fetch('/mark_connected', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    setConnected(true);
                    showToast('Account marked as connected!', 'success');
                });
        }

        function startLoop() {
            const url = document.getElementById('videoUrl').value.trim();
            if (!url) {
                showToast('Please enter a TikTok video URL.', 'error');
                return;
            }
            fetch('/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    visitCount = 0;
                    document.getElementById('visitCount').textContent = '0';
                    setRunning(true);
                    showToast(data.message, 'success');
                } else {
                    showToast(data.message, 'error');
                }
            });
        }

        function stopLoop() {
            fetch('/stop', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message, 'info');
                });
        }

        function showToast(message, type = 'info') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.4s';
                setTimeout(() => toast.remove(), 400);
            }, 4000);
        }
    </script>
</body>
</html>
"""
