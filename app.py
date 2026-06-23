from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import threading

app = Flask(__name__)
CORS(app)

def get_format_opts(fmt):
    if fmt == "mp3":
        return {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(title)s.%(ext)s',
        }
    heights = {'720p': 720, '480p': 480, '360p': 360}
    h = heights.get(fmt, 480)
    return {
        'format': f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best[height<={h}]',
        'merge_output_format': 'mp4',
        'outtmpl': '%(title)s.%(ext)s',
    }

@app.route('/info', methods=['GET'])
def get_info():
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', ''),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['GET'])
def download():
    url = request.args.get('url', '')
    fmt = request.args.get('format', '480p')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    tmpdir = tempfile.mkdtemp()
    opts = get_format_opts(fmt)
    opts['outtmpl'] = os.path.join(tmpdir, '%(title)s.%(ext)s')
    opts['quiet'] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')

        files = os.listdir(tmpdir)
        if not files:
            return jsonify({'error': 'Download failed'}), 500

        filepath = os.path.join(tmpdir, files[0])
        filename = files[0]
        ext = filename.rsplit('.', 1)[-1]
        mime = 'audio/mpeg' if ext == 'mp3' else 'video/mp4'

        def generate():
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    yield chunk
            # cleanup
            try:
                os.remove(filepath)
                os.rmdir(tmpdir)
            except:
                pass

        safe_name = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        return Response(
            generate(),
            mimetype=mime,
            headers={
                'Content-Disposition': f'attachment; filename="{safe_name}.{ext}"',
                'X-Accel-Buffering': 'no',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
