"""
Simple web-based log viewer for jellyfin_debrid
Serves logs on http://localhost:7654
"""
from flask import Flask, jsonify, render_template_string
import time
import os

app = Flask(__name__)

LOG_FILE = "config/jellyfin_debrid.log"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Jellyfin Debrid Logs</title>
    <style>
        body {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Monaco', monospace;
            margin: 0;
            padding: 20px;
        }
        #logs {
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 13px;
            line-height: 1.4;
            background: #252526;
            padding: 15px;
            border-radius: 4px;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid #3e3e3e;
        }
        .header {
            margin-bottom: 20px;
        }
        .status {
            color: #4ec9b0;
            font-size: 12px;
        }
        h1 {
            margin: 0 0 10px 0;
            font-size: 18px;
            color: #4ec9b0;
        }
    </style>
    <script>
        let lastUpdate = 0;
        let autoScroll = true;
        
        function updateLogs() {
            console.log('Fetching logs...');
            const logsDiv = document.getElementById('logs');
            const statusDiv = document.getElementById('status');
            
            fetch('/api/logs?t=' + Date.now())
                .then(response => {
                    if (!response.ok) throw new Error('Network error');
                    return response.json();
                })
                .then(data => {
                    console.log('Got logs, length:', data.content.length);
                    
                    // Check if we're scrolled to the bottom
                    const isAtBottom = logsDiv.scrollHeight - logsDiv.scrollTop - logsDiv.clientHeight < 50;
                    
                    logsDiv.textContent = data.content;
                    
                    // Only auto-scroll if user is at bottom or auto-scroll is enabled
                    if (isAtBottom || autoScroll) {
                        logsDiv.scrollTop = logsDiv.scrollHeight;
                    }
                    
                    statusDiv.textContent = 'Connected - Last updated: ' + new Date().toLocaleTimeString() + (autoScroll ? ' [Auto-scroll ON]' : ' [Auto-scroll OFF - scroll to bottom to re-enable]');
                    statusDiv.style.color = '#4ec9b0';
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    statusDiv.textContent = 'Connection error - retrying...';
                    statusDiv.style.color = '#f48771';
                });
            
            // Update every 2 seconds
            setTimeout(updateLogs, 2000);
        }
        
        window.addEventListener('load', function() {
            const logsDiv = document.getElementById('logs');
            
            // Disable auto-scroll when user scrolls up
            logsDiv.addEventListener('scroll', function() {
                const isAtBottom = logsDiv.scrollHeight - logsDiv.scrollTop - logsDiv.clientHeight < 50;
                if (!isAtBottom) {
                    autoScroll = false;
                } else {
                    autoScroll = true;
                }
            });
            
            updateLogs();
        });
    </script>
</head>
<body>
    <div class="header">
        <h1>🎬 Jellyfin Debrid Logs</h1>
        <div class="status" id="status">Loading...</div>
    </div>
    <div id="logs">Loading logs...</div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/logs')
def get_logs():
    """Get logs as JSON"""
    if not os.path.exists(LOG_FILE):
        return jsonify({'content': 'Log file not found. Service may not be running yet.\n'})
    
    try:
        with open(LOG_FILE, 'rb') as f:
            content = f.read()
            text = content.decode('utf-8', errors='replace')
            all_lines = text.split('\n')
            # Return last 200 lines
            logs = '\n'.join(all_lines[-200:])
            return jsonify({'content': logs})
    except Exception as e:
        return jsonify({'content': f'Error reading log file: {str(e)}\n'})

if __name__ == '__main__':
    print("=" * 60)
    print("Jellyfin Debrid Log Viewer")
    print("=" * 60)
    print(f"Open your browser to: http://localhost:7654")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host='0.0.0.0', port=7654, debug=False, threaded=True)
