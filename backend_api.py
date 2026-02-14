"""
YouTube Downloader Backend API
Python Flask backend for downloading YouTube videos in MP4 and MP3 formats
Requires: Flask, yt-dlp, flask-cors
"""



from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import os
import requests

app = Flask(__name__)

# ✅ CORS (preflight/OPTIONS included)
CORS(
    app,
    resources={r"/api/*": {"origins": ["https://hang.hangoutspk.com"]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

@app.route("/", methods=["GET"])
def home():
    return "Backend is running ✅"

# ✅ Returns Title/Thumbnail/Channel using YouTube oEmbed (metadata only)
@app.route("/api/info", methods=["POST", "OPTIONS"])
def api_info():
    if request.method == "OPTIONS":
        return make_response("", 200)

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"status": "error", "error": "URL is required"}), 400

    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=15,
        )
        if r.status_code != 200:
            return jsonify({"status": "error", "error": "Invalid YouTube URL"}), 400

        j = r.json()
        return jsonify({
            "status": "working",
            "data": {
                "title": j.get("title"),
                "thumbnail": j.get("thumbnail_url"),
                "channel": j.get("author_name"),
                "url": url
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ✅ Keeps frontend from CORS failing (OPTIONS OK), but does NOT download content
@app.route("/api/download", methods=["POST", "OPTIONS"])
def api_download():
    if request.method == "OPTIONS":
        return make_response("", 200)

    return jsonify({
        "success": False,
        "error": "Download endpoint is disabled. Use metadata (/api/info) only."
    }), 501

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "Backend API"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# Configuration
DOWNLOAD_FOLDER = 'downloads'
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

# Clean up old files (older than 1 hour)
def cleanup_old_files():
    """Remove downloaded files older than 1 hour"""
    current_time = time.time()
    for filename in os.listdir(DOWNLOAD_FOLDER):
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > 3600:  # 1 hour
                try:
                    os.remove(filepath)
                except:
                    pass

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
        r'youtube\.com\/embed\/([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/api/info', methods=['POST'])
def get_video_info():
    """Get video information without downloading"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract available formats
            formats = {
                'mp4': [],
                'mp3': []
            }
            
            # Get video formats
            seen_qualities = set()
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height')
                    if height and height not in seen_qualities:
                        formats['mp4'].append({
                            'quality': f'{height}p',
                            'height': height,
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext', 'mp4'),
                            'filesize': f.get('filesize', 0)
                        })
                        seen_qualities.add(height)
            
            # Sort by quality
            formats['mp4'].sort(key=lambda x: x['height'], reverse=True)
            
            # Audio formats (MP3)
            formats['mp3'] = [
                {'quality': '320kbps', 'bitrate': 320},
                {'quality': '256kbps', 'bitrate': 256},
                {'quality': '192kbps', 'bitrate': 192},
                {'quality': '128kbps', 'bitrate': 128},
            ]
            
            return jsonify({
                'success': True,
                'data': {
                    'id': video_id,
                    'title': info.get('title'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration'),
                    'channel': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'formats': formats
                }
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Download video in specified format and quality"""
    try:
        cleanup_old_files()  # Clean old downloads
        
        data = request.json
        url = data.get('url')
        format_type = data.get('format', 'mp4')  # mp4 or mp3
        quality = data.get('quality', '720')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Generate unique filename
        filename_hash = hashlib.md5(f"{video_id}{format_type}{quality}".encode()).hexdigest()[:8]
        
        if format_type == 'mp3':
            output_template = os.path.join(DOWNLOAD_FOLDER, f'{filename_hash}.%(ext)s')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
                'quiet': True,
                'no_warnings': True,
            }
        else:  # mp4
            output_template = os.path.join(DOWNLOAD_FOLDER, f'{filename_hash}.%(ext)s')
            
            # Format selection based on quality
            if quality == '1080':
                format_selector = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
            elif quality == '720':
                format_selector = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
            elif quality == '480':
                format_selector = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
            else:  # 360
                format_selector = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best'
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            
            # Find the downloaded file
            downloaded_file = None
            for ext in ['mp3', 'mp4', 'm4a', 'webm']:
                potential_file = os.path.join(DOWNLOAD_FOLDER, f'{filename_hash}.{ext}')
                if os.path.exists(potential_file):
                    downloaded_file = potential_file
                    break
            
            if not downloaded_file:
                return jsonify({'error': 'Download failed'}), 500
            
            # Clean filename for download
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            download_name = f"{safe_title}.{format_type}"
            
            return send_file(
                downloaded_file,
                as_attachment=True,
                download_name=download_name,
                mimetype='audio/mpeg' if format_type == 'mp3' else 'video/mp4'
            )
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'YouTube Downloader API'})

@app.route('/')
def index():
    """API documentation"""
    return jsonify({
        'name': 'YouTube Downloader API',
        'version': '1.0',
        'endpoints': {
            '/api/info': {
                'method': 'POST',
                'description': 'Get video information',
                'body': {'url': 'YouTube video URL'}
            },
            '/api/download': {
                'method': 'POST',
                'description': 'Download video',
                'body': {
                    'url': 'YouTube video URL',
                    'format': 'mp4 or mp3',
                    'quality': 'quality value (e.g., 720, 1080 for mp4, 320, 256 for mp3)'
                }
            },
            '/api/health': {
                'method': 'GET',
                'description': 'Health check'
            }
        }
    })

if __name__ == '__main__':
    print("🚀 YouTube Downloader API Starting...")
    print("📦 Make sure you have installed:")
    print("   pip install flask flask-cors yt-dlp")
    print("\n🌐 API will run on: http://localhost:5000")
    print("📝 API Documentation: http://localhost:5000")
    print("\n⚠️  Note: You also need FFmpeg installed for audio conversion")
    app.run(debug=True, host='0.0.0.0', port=5000)
