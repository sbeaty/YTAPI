from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests

app = Flask(__name__)

API_KEY = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
youtube = build('youtube', 'v3', developerKey=API_KEY)

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
        # Format transcript with timestamps
        transcript_text = ''
        for item in transcript_list:
            timestamp = item['start']
            text = item['text']
            transcript_text += f'[{timestamp}] {text}\n'
        return jsonify({'transcript': transcript_text}), 200
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
            
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = ''
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                
                transcripts.append({
                    'URL': video_url,
                    'Title': video_title,
                    'transcript': transcript_text
                })
            except Exception as e:
                transcripts.append({
                    'URL': video_url,
                    'Title': video_title,
                    'transcript': None,
                    'error': f'Error fetching transcript: {str(e)}'
                })

        return jsonify({'transcripts': transcripts}), 200

    except HttpError as e:
        return jsonify({'error': f"An HTTP error occurred: {e}"}), 500
    except KeyError as e:
        return jsonify({'error': f"Unexpected response structure: {e}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
