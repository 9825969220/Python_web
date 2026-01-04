import urllib.parse  # <--- Add this
from flask import (
    Flask, render_template, request, send_file,
    jsonify, session, redirect, url_for
)
from flask_cors import CORS
import yt_dlp
import os
import threading
import time

app = Flask(__name__)
app.secret_key = "supersecretkey123"
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

progress_data = {"progress": "0%"}

# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get("username")
        pwd = request.form.get("password")

        # simple demo login
        if user == "admin" and pwd == "1234":
            session['user'] = user
            return redirect(url_for('index'))
        else:
            return "Invalid login"

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ================= HOME =================

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

# ================= PROGRESS =================

def progress_hook(d):
    if d['status'] == 'downloading':
        progress_data['progress'] = d.get('_percent_str', '0%').strip()

@app.route('/progress')
def progress():
    return jsonify(progress_data)

# ================= DOWNLOAD =================

import os
import yt_dlp
from flask import request, jsonify, send_file

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json(force=True)
        video_url = data.get('url')
        mode = data.get('mode')

        if not video_url:
            return jsonify({"error": "No URL provided"}), 400

        if not os.path.exists(DOWNLOAD_FOLDER):
            os.makedirs(DOWNLOAD_FOLDER)

        # BASE OPTIONS
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            # 'restrictfilenames': True, # Uncomment if you want to strip emojis/special chars
        }

        # 🔊 AUDIO
        if mode == 'audio':
            ydl_opts.update({
                'format': 'bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '256',
                }],
            })

        # 🎥 VIDEO
        else:
            ydl_opts.update({
                'format': 'bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4', 
                }],
                'postprocessor_args': {
                    'merger': ['-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart'],
                    'videoconvertor': ['-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart']
                }
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            temp_path = ydl.prepare_filename(info)
            
            # Determine final path
            if mode == 'audio':
                final_path = os.path.splitext(temp_path)[0] + '.mp3'
            else:
                final_path = os.path.splitext(temp_path)[0] + '.mp4'

            # --- FIX STARTS HERE ---
            
            # 1. Get the real filename (e.g., "Happy New Year.mp3")
            filename = os.path.basename(final_path)
            
            # 2. URL Encode it so special characters (emojis/spaces) don't break the header
            safe_filename = urllib.parse.quote(filename)

            # 3. Create the response object
            response = send_file(final_path, as_attachment=True, download_name=filename)

            # 4. Add Custom Header containing the filename
            response.headers["X-Filename"] = safe_filename
            
            # 5. ALLOW JavaScript to read this specific header (Crucial!)
            response.headers["Access-Control-Expose-Headers"] = "X-Filename"

            return response

    except Exception as e:
        print(f"Download Error: {e}") 
        return jsonify({"error": str(e)}), 500
    
def auto_delete(path):
    time.sleep(60)
    if os.path.exists(path):
        os.remove(path)

# ================= RUN =================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
