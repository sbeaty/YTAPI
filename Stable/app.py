from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build

app = Flask(__name__)

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
        # Fetch the transcript using the video ID
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        # Concatenate all text items in the transcript into a single string
        transcript_text = " ".join([item['text'] for item in transcript_list])
        return jsonify({'transcript': transcript_text}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search_videos():
    search_query = request.args.get('query')
    max_results = request.args.get('maxResults', default=5, type=int)
    if not search_query:
        return jsonify({'error': 'Query parameter is missing.'}), 400

    try:
        api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
        youtube = build('youtube', 'v3', developerKey=api_key)
        
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
        api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
        youtube = build('youtube', 'v3', developerKey=api_key)
        
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
        api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
        youtube = build('youtube', 'v3', developerKey=api_key)
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
