from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import re
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import subprocess
import tempfile
import os

app = Flask(__name__)

API_KEY = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
youtube = build('youtube', 'v3', developerKey=API_KEY)

def get_transcript_alternative_1(video_id):
    """Alternative method 1: Direct timedtext API with user agent"""
    try:
        languages = ['en', 'en-US', 'en-GB']
        for lang in languages:
            url = f"http://video.google.com/timedtext?lang={lang}&v={video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            req = Request(url, headers=headers)
            try:
                response = urlopen(req, timeout=10)
                data = response.read().decode('utf-8')
                
                if data and '<transcript>' in data:
                    # Parse XML and extract text with timestamps
                    import xml.etree.ElementTree as ET
                    try:
                        root = ET.fromstring(data)
                        transcript_text = ''
                        for text_elem in root.findall('.//text'):
                            start = text_elem.get('start', '0')
                            text = text_elem.text or ''
                            if text.strip():
                                transcript_text += f'[{start}] {text.strip()}\n'
                        
                        if transcript_text.strip():
                            return transcript_text
                    except ET.ParseError:
                        continue
            except (HTTPError, URLError):
                continue
        
        return None
    except Exception as e:
        print(f"Alternative method 1 failed: {e}")
        return None

def get_transcript_alternative_2(video_id):
    """Alternative method 2: YouTube transcript API with enhanced error handling"""
    try:
        # Try multiple language codes
        language_codes = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
        
        for lang in language_codes:
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                transcript_text = ''
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                
                if transcript_text.strip():
                    return transcript_text
            except Exception:
                continue
        
        # Try without language specification
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = ''
            for item in transcript_list:
                timestamp = item['start']
                text = item['text']
                transcript_text += f'[{timestamp}] {text}\n'
            
            if transcript_text.strip():
                return transcript_text
        except Exception:
            pass
        
        return None
    except Exception as e:
        print(f"Alternative method 2 failed: {e}")
        return None

def get_transcript_alternative_3(video_id):
    """Alternative method 3: Using requests with session and headers"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        languages = ['en', 'en-US', 'en-GB']
        for lang in languages:
            url = f"https://video.google.com/timedtext?lang={lang}&v={video_id}"
            
            try:
                response = session.get(url, timeout=15)
                if response.status_code == 200 and response.text:
                    data = response.text
                    
                    if '<transcript>' in data:
                        import xml.etree.ElementTree as ET
                        try:
                            root = ET.fromstring(data)
                            transcript_text = ''
                            for text_elem in root.findall('.//text'):
                                start = text_elem.get('start', '0')
                                text = text_elem.text or ''
                                if text.strip():
                                    transcript_text += f'[{start}] {text.strip()}\n'
                            
                            if transcript_text.strip():
                                return transcript_text
                        except ET.ParseError:
                            continue
            except requests.RequestException:
                continue
        
        return None
    except Exception as e:
        print(f"Alternative method 3 failed: {e}")
        return None

def get_transcript_alternative_4(video_id):
    """Alternative method 4: Using yt-dlp for subtitle extraction"""
    try:
        # Check if yt-dlp is available
        result = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True)
        if result.returncode != 0:
            print("yt-dlp not available, skipping this method")
            return None
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Try to get auto-generated subtitles first, then manual ones
        for subtitle_type in ['--write-auto-sub', '--write-sub']:
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    cmd = [
                        'yt-dlp',
                        subtitle_type,
                        '--sub-lang', 'en',
                        '--sub-format', 'srv1',
                        '--skip-download',
                        '--output', f'{temp_dir}/%(title)s.%(ext)s',
                        video_url
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        # Look for subtitle files
                        for file in os.listdir(temp_dir):
                            if file.endswith('.srv1'):
                                subtitle_path = os.path.join(temp_dir, file)
                                with open(subtitle_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                # Parse srv1 format and extract text with timestamps
                                import xml.etree.ElementTree as ET
                                try:
                                    root = ET.fromstring(content)
                                    transcript_text = ''
                                    for p_elem in root.findall('.//p'):
                                        start = p_elem.get('t', '0')
                                        # Convert milliseconds to seconds
                                        start_seconds = float(start) / 1000 if start else 0
                                        text = p_elem.text or ''
                                        if text.strip():
                                            transcript_text += f'[{start_seconds}] {text.strip()}\n'
                                    
                                    if transcript_text.strip():
                                        return transcript_text
                                except ET.ParseError:
                                    continue
            except subprocess.TimeoutExpired:
                print("yt-dlp timeout")
                continue
            except Exception as e:
                print(f"yt-dlp error: {e}")
                continue
        
        return None
    except Exception as e:
        print(f"Alternative method 4 failed: {e}")
        return None

def get_transcript_robust(video_id):
    """Robust transcript fetching with multiple fallback methods"""
    methods = [
        ("YouTube Transcript API", get_transcript_alternative_2),
        ("Direct timedtext API", get_transcript_alternative_1),
        ("Requests with session", get_transcript_alternative_3),
        ("yt-dlp extraction", get_transcript_alternative_4)
    ]
    
    for method_name, method_func in methods:
        try:
            print(f"Trying {method_name} for video {video_id}")
            result = method_func(video_id)
            if result and result.strip():
                print(f"✅ {method_name} succeeded for video {video_id}")
                return result
            else:
                print(f"❌ {method_name} returned empty result for video {video_id}")
        except Exception as e:
            print(f"❌ {method_name} failed for video {video_id}: {e}")
    
    print(f"❌ All transcript methods failed for video {video_id}")
    return None

@app.route('/transcript', methods=['GET'])
def get_transcript():
    video_link = request.args.get('video_link')
    if not video_link:
        return jsonify({'error': 'Video link parameter is missing.'}), 400

    # Extract the video ID from the YouTube video link
    parsed_url = urlparse(video_link)
    if parsed_url.netloc != 'www.youtube.com':
        return jsonify({'error': 'Invalid YouTube video link.'}), 400

    query_params = parse_qs(parsed_url.query)
    video_id = query_params.get('v', [None])[0]
    if not video_id:
        return jsonify({'error': 'Invalid YouTube video link.'}), 400

    try:
        # Use robust transcript fetching with multiple fallback methods
        transcript_text = get_transcript_robust(video_id)
        if transcript_text:
            return jsonify({'transcript': transcript_text}), 200
        else:
            return jsonify({'error': 'No transcript available for this video. The video may not have captions enabled or may be restricted.'}), 404
    except Exception as e:
        return jsonify({'error': f'Error fetching transcript: {str(e)}'}), 500

@app.route('/search', methods=['GET'])
def search_videos():
    search_query = request.args.get('query')
    max_results = request.args.get('maxResults', default=5, type=int)
    if not search_query:
        return jsonify({'error': 'Query parameter is missing.'}), 400

    try:
        youtube_request = youtube.search().list(
            part="snippet",
            q=search_query,
            type="video",
            maxResults=max_results
        )
        response = youtube_request.execute()
        
        results = []
        for item in response.get('items', []):
            results.append({
                'title': item['snippet']['title'],
                'videoId': item['id']['videoId']
            })
        
        return jsonify({'results': results}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/video_details', methods=['GET'])
def video_details():
    video_id = request.args.get('videoId')
    if not video_id:
        return jsonify({'error': 'Video ID parameter is missing.'}), 400

    try:
        youtube_request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        )
        response = youtube_request.execute()
        
        if not response.get('items'):
            return jsonify({'error': 'No video details found for the given video ID.'}), 404
        
        video_info = response['items'][0]
        
        details = {
            'title': video_info['snippet']['title'],
            'description': video_info['snippet']['description'],
            'publishedAt': video_info['snippet']['publishedAt'],
            'viewCount': video_info['statistics'].get('viewCount'),
            'likeCount': video_info['statistics'].get('likeCount'),
            'dislikeCount': video_info['statistics'].get('dislikeCount'),
            'commentCount': video_info['statistics'].get('commentCount'),
            'duration': video_info['contentDetails'].get('duration')
        }
        
        return jsonify({'details': details}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/comments', methods=['GET'])
def get_comments():
    video_id = request.args.get('videoId')
    max_results = request.args.get('maxResults', default=5, type=int)
    if not video_id:
        return jsonify({'error': 'Video ID parameter is missing.'}), 400

    try:
        youtube_request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            textFormat="plainText"
        )
        response = youtube_request.execute()
        
        comments = []
        for item in response.get('items', []):
            comment = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'author': comment['authorDisplayName'],
                'text': comment['textDisplay'],
                'publishedAt': comment['publishedAt'],
                'likeCount': comment['likeCount']
            })
        
        return jsonify({'comments': comments}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/channel_id', methods=['GET'])
def get_channel_id():
    handle = request.args.get('handle')
    if not handle:
        return jsonify({'error': 'Handle parameter is missing.'}), 400
    
    try:
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={handle}&key={API_KEY}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data and len(data['items']) > 0:
                return jsonify({'channel_id': data['items'][0]['id']}), 200
            else:
                return jsonify({'error': f"No channel found with the handle: {handle}"}), 404
        else:
            return jsonify({'error': f"Error retrieving channel ID. Status code: {response.status_code}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/channel_videos', methods=['GET'])
def get_channel_videos():
    channel_id = request.args.get('channel_id')
    if not channel_id:
        return jsonify({'error': 'Channel ID parameter is missing.'}), 400

    try:
        request_obj = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request_obj.execute()

        if 'items' not in response or len(response['items']) == 0:
            return jsonify({'error': f"No channel found with the ID: {channel_id}"}), 404

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos = []
        next_page_token = None
        while True:
            playlist_items_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            videos += playlist_items_response['items']
            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                break

        video_urls = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_title = video['snippet']['title']
            video_urls.append({'URL': video_url, 'Title': video_title})

        return jsonify({'videos': video_urls}), 200

    except HttpError as e:
        return jsonify({'error': f"An HTTP error occurred: {e}"}), 500
    except KeyError as e:
        return jsonify({'error': f"Unexpected response structure: {e}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/channel_transcripts', methods=['GET'])
def get_channel_transcripts():
    channel_id = request.args.get('channel_id')
    if not channel_id:
        return jsonify({'error': 'Channel ID parameter is missing.'}), 400

    try:
        request_obj = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request_obj.execute()

        if 'items' not in response or len(response['items']) == 0:
            return jsonify({'error': f"No channel found with the ID: {channel_id}"}), 404

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos = []
        next_page_token = None
        while True:
            playlist_items_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            videos += playlist_items_response['items']
            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                break

        transcripts = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_title = video['snippet']['title']
            
            transcript_text = get_transcript_robust(video_id)
            if transcript_text:
                transcripts.append({
                    'URL': video_url,
                    'Title': video_title,
                    'transcript': transcript_text
                })
            else:
                transcripts.append({
                    'URL': video_url,
                    'Title': video_title,
                    'transcript': None,
                    'error': 'No transcript available for this video'
                })

        return jsonify({'transcripts': transcripts}), 200

    except HttpError as e:
        return jsonify({'error': f"An HTTP error occurred: {e}"}), 500
    except KeyError as e:
        return jsonify({'error': f"Unexpected response structure: {e}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/docs', methods=['GET'])
def get_docs():
    docs = {
        "title": "YouTube API Documentation",
        "version": "1.0",
        "endpoints": [
            {
                "path": "/transcript",
                "method": "GET",
                "description": "Get transcript for a YouTube video with timestamps",
                "parameters": [
                    {"name": "video_link", "type": "string", "required": True, "description": "YouTube video URL"}
                ],
                "example": "/transcript?video_link=https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "response": {"transcript": "[1.36] [♪♪♪]\\n[18.64] ♪ We're no strangers to love ♪\\n..."}
            },
            {
                "path": "/search",
                "method": "GET", 
                "description": "Search for YouTube videos",
                "parameters": [
                    {"name": "query", "type": "string", "required": True, "description": "Search query"},
                    {"name": "maxResults", "type": "integer", "required": False, "description": "Maximum number of results (default: 5)"}
                ],
                "example": "/search?query=python tutorial&maxResults=10",
                "response": {"results": [{"title": "Video Title", "videoId": "abc123"}]}
            },
            {
                "path": "/video_details",
                "method": "GET",
                "description": "Get detailed information about a YouTube video",
                "parameters": [
                    {"name": "videoId", "type": "string", "required": True, "description": "YouTube video ID"}
                ],
                "example": "/video_details?videoId=dQw4w9WgXcQ",
                "response": {"details": {"title": "Video Title", "description": "...", "viewCount": "123456"}}
            },
            {
                "path": "/comments",
                "method": "GET",
                "description": "Get comments for a YouTube video",
                "parameters": [
                    {"name": "videoId", "type": "string", "required": True, "description": "YouTube video ID"},
                    {"name": "maxResults", "type": "integer", "required": False, "description": "Maximum number of comments (default: 5)"}
                ],
                "example": "/comments?videoId=dQw4w9WgXcQ&maxResults=20",
                "response": {"comments": [{"author": "User", "text": "Great video!", "likeCount": 5}]}
            },
            {
                "path": "/channel_id",
                "method": "GET",
                "description": "Get channel ID from channel handle",
                "parameters": [
                    {"name": "handle", "type": "string", "required": True, "description": "YouTube channel handle (without @)"}
                ],
                "example": "/channel_id?handle=TheRandallCarlson",
                "response": {"channel_id": "UCAPciy143ZBXBrFpCVPnWDg"}
            },
            {
                "path": "/channel_videos",
                "method": "GET",
                "description": "Get all videos from a YouTube channel",
                "parameters": [
                    {"name": "channel_id", "type": "string", "required": True, "description": "YouTube channel ID"}
                ],
                "example": "/channel_videos?channel_id=UCAPciy143ZBXBrFpCVPnWDg",
                "response": {"videos": [{"URL": "https://www.youtube.com/watch?v=abc123", "Title": "Video Title"}]}
            },
            {
                "path": "/channel_transcripts",
                "method": "GET",
                "description": "Get transcripts for all videos in a YouTube channel",
                "parameters": [
                    {"name": "channel_id", "type": "string", "required": True, "description": "YouTube channel ID"}
                ],
                "example": "/channel_transcripts?channel_id=UCAPciy143ZBXBrFpCVPnWDg",
                "response": {"transcripts": [{"URL": "...", "Title": "...", "transcript": "[1.36] Hello world..."}]}
            },
            {
                "path": "/docs",
                "method": "GET",
                "description": "This documentation endpoint",
                "parameters": [],
                "example": "/docs",
                "response": {"title": "YouTube API Documentation", "endpoints": [...]}
            }
        ],
        "notes": [
            "All endpoints return JSON responses",
            "Error responses include an 'error' field with description",
            "Transcript endpoints may return null for videos without captions",
            "Rate limits apply based on YouTube API quotas"
        ]
    }
    return jsonify(docs), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
