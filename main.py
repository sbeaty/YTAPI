from fastapi import FastAPI, HTTPException, Query
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import uvicorn

app = FastAPI(
    title="YouTube Comments & Transcripts API",
    description="API for scraping YouTube comments and transcripts with working proxy support",
    version="2.0.0"
)

# Working API key and proxy configuration from working app.py
API_KEY = 'AIzaSyBr-juudGbZtHf4xCTFtxF065SfO8b3YQU'
PROXY_URL = "https://f3138bb7d6946fd998eb:9a590d5c36b57e6f@gw.dataimpulse.com:823"
PROXIES = {"https": PROXY_URL, "http": PROXY_URL}

youtube = build('youtube', 'v3', developerKey=API_KEY)

def extract_video_id(video_link: str) -> str:
    """Extract video ID from YouTube URL"""
    parsed_url = urlparse(video_link)
    if parsed_url.netloc == 'www.youtube.com':
        return parse_qs(parsed_url.query).get('v', [None])[0]
    return None

@app.get("/")
async def root():
    return {
        "message": "YouTube Comments & Transcripts API", 
        "version": "2.0.0",
        "status": "working"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "proxy_configured": True}

@app.get("/transcript")
async def get_transcript(videoId: str = Query(..., description="YouTube video ID")):
    """Get transcript for a YouTube video using working proxy method"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoId, proxies=PROXIES)
        text = " ".join([item['text'] for item in transcript])
        return {"transcript": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transcript-with-timestamps")
async def get_transcript_with_timestamps(videoId: str = Query(..., description="YouTube video ID")):
    """Get transcript with timestamps"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoId, proxies=PROXIES)
        formatted_transcript = ""
        for item in transcript:
            timestamp = item['start']
            text = item['text']
            formatted_transcript += f'[{timestamp}] {text}\n'
        return {"transcript": formatted_transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
async def search_videos(
    query: str = Query(..., description="Search query"),
    maxResults: int = Query(default=20, ge=1, le=50, description="Maximum results")
):
    """Search for YouTube videos"""
    try:
        response = youtube.search().list(
            part="snippet", 
            q=query, 
            type="video", 
            maxResults=maxResults
        ).execute()
        
        results = []
        for item in response.get('items', []):
            results.append({
                'title': item['snippet']['title'], 
                'videoId': item['id']['videoId'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'thumbnail': item['snippet']['thumbnails']['default']['url'],
                'channelTitle': item['snippet']['channelTitle'],
                'publishedAt': item['snippet']['publishedAt']
            })
        
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/video_details")
async def video_details(videoId: str = Query(..., description="YouTube video ID")):
    """Get detailed information about a YouTube video"""
    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics", 
            id=videoId
        ).execute()
        
        if not response.get('items'):
            raise HTTPException(status_code=404, detail="No video details found")
        
        info = response['items'][0]
        details = {
            'title': info['snippet']['title'],
            'description': info['snippet']['description'],
            'publishedAt': info['snippet']['publishedAt'],
            'viewCount': info['statistics'].get('viewCount'),
            'likeCount': info['statistics'].get('likeCount'),
            'commentCount': info['statistics'].get('commentCount'),
            'duration': info['contentDetails'].get('duration'),
            'channelTitle': info['snippet']['channelTitle'],
            'channelId': info['snippet']['channelId']
        }
        
        return {"details": details}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/comments")
async def get_comments(
    videoId: str = Query(..., description="YouTube video ID"),
    maxResults: int = Query(default=100, ge=1, le=5000, description="Maximum comments")
):
    """Get comments for a YouTube video"""
    try:
        response = youtube.commentThreads().list(
            part="snippet", 
            videoId=videoId, 
            maxResults=maxResults, 
            textFormat="plainText"
        ).execute()
        
        comments = []
        for item in response.get('items', []):
            comment_data = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'author': comment_data['authorDisplayName'],
                'text': comment_data['textDisplay'],
                'publishedAt': comment_data['publishedAt'],
                'likeCount': comment_data['likeCount']
            })
        
        return {"comments": comments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/video/{video_id}")
async def get_video_complete(
    video_id: str,
    max_comments: int = Query(default=50, ge=1, le=1000, description="Maximum comments")
):
    """Get complete video data: details, comments, and transcript"""
    try:
        # Get video details
        video_response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        ).execute()
        
        if not video_response.get('items'):
            raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found")
        
        video_info = video_response['items'][0]
        
        # Get comments
        try:
            comments_response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_comments,
                textFormat="plainText"
            ).execute()
            
            comments = []
            for item in comments_response.get('items', []):
                comment_data = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment_data['authorDisplayName'],
                    'text': comment_data['textDisplay'],
                    'publishedAt': comment_data['publishedAt'],
                    'likeCount': comment_data['likeCount']
                })
        except Exception as e:
            comments = []
            print(f"Comments error: {e}")
        
        # Get transcript
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
            transcript_text = ""
            for item in transcript_list:
                timestamp = item['start']
                text = item['text']
                transcript_text += f'[{timestamp}] {text}\n'
        except Exception as e:
            transcript_text = None
            print(f"Transcript error: {e}")
        
        result = {
            "video_info": {
                'id': video_id,
                'title': video_info['snippet']['title'],
                'description': video_info['snippet']['description'],
                'publishedAt': video_info['snippet']['publishedAt'],
                'channelTitle': video_info['snippet']['channelTitle'],
                'channelId': video_info['snippet']['channelId'],
                'viewCount': video_info['statistics'].get('viewCount'),
                'likeCount': video_info['statistics'].get('likeCount'),
                'commentCount': video_info['statistics'].get('commentCount'),
                'duration': video_info['contentDetails'].get('duration')
            },
            "comments": comments,
            "comment_count": len(comments),
            "transcript": transcript_text,
            "has_transcript": transcript_text is not None
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channel-id")
async def get_channel_id(handle: str = Query(..., description="YouTube channel handle")):
    """Get channel ID from channel handle"""
    try:
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={handle}&key={API_KEY}'
        import requests
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data and len(data['items']) > 0:
                return {"channel_id": data['items'][0]['id']}
            else:
                raise HTTPException(status_code=404, detail=f"No channel found with handle: {handle}")
        else:
            raise HTTPException(status_code=500, detail=f"Error retrieving channel ID. Status: {response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channel-videos")
async def get_channel_videos(channel_id: str = Query(..., description="YouTube channel ID")):
    """Get all videos from a YouTube channel"""
    try:
        # Get channel uploads playlist
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        if 'items' not in channel_response or len(channel_response['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with ID: {channel_id}")

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get all videos from uploads playlist
        videos = []
        next_page_token = None
        
        while True:
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            videos.extend(playlist_response['items'])
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break

        video_list = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_list.append({
                'videoId': video_id,
                'title': video['snippet']['title'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'publishedAt': video['snippet']['publishedAt'],
                'thumbnail': video['snippet']['thumbnails']['default']['url']
            })

        return {"videos": video_list, "total_count": len(video_list)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channel-transcripts")
async def get_channel_transcripts(channel_id: str = Query(..., description="YouTube channel ID")):
    """Get transcripts for all videos in a YouTube channel using working proxy method"""
    try:
        # Get channel uploads playlist
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        if 'items' not in channel_response or len(channel_response['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with ID: {channel_id}")

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get all videos from uploads playlist
        videos = []
        next_page_token = None
        
        while True:
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            videos.extend(playlist_response['items'])
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break

        # Get transcripts for each video using working proxy method
        transcripts = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_title = video['snippet']['title']
            
            try:
                # Use the working proxy method
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                
                transcripts.append({
                    'videoId': video_id,
                    'url': video_url,
                    'title': video_title,
                    'transcript': transcript_text,
                    'publishedAt': video['snippet']['publishedAt']
                })
            except Exception as e:
                transcripts.append({
                    'videoId': video_id,
                    'url': video_url,
                    'title': video_title,
                    'transcript': None,
                    'error': f'No transcript available: {str(e)}',
                    'publishedAt': video['snippet']['publishedAt']
                })

        return {"transcripts": transcripts, "total_count": len(transcripts)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transcripts/{channel_handle}")
async def get_channel_transcripts_by_handle(
    channel_handle: str,
    top_n: int = Query(default=5, ge=1, le=50, description="Number of most recent videos to process")
):
    """Get transcripts from the top N most recent videos of a channel by handle"""
    try:
        # First get channel ID from handle
        import requests
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={channel_handle}&key={API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error retrieving channel ID. Status: {response.status_code}")
        
        data = response.json()
        if 'items' not in data or len(data['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with handle: {channel_handle}")
        
        channel_id = data['items'][0]['id']
        
        # Get recent videos (limited to top_n)
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get only the most recent videos
        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=top_n
        ).execute()
        
        videos = playlist_response['items']

        # Get transcripts for each video
        transcripts = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_title = video['snippet']['title']
            
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                
                transcripts.append({
                    'videoId': video_id,
                    'url': video_url,
                    'title': video_title,
                    'transcript': transcript_text,
                    'has_transcript': True,
                    'publishedAt': video['snippet']['publishedAt']
                })
            except Exception as e:
                transcripts.append({
                    'videoId': video_id,
                    'url': video_url,
                    'title': video_title,
                    'transcript': None,
                    'has_transcript': False,
                    'error': f'No transcript available: {str(e)}',
                    'publishedAt': video['snippet']['publishedAt']
                })

        videos_with_transcripts = len([t for t in transcripts if t.get('has_transcript')])

        return {
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "videos_processed": len(transcripts),
            "videos_with_transcripts": videos_with_transcripts,
            "transcripts": transcripts
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/comments/{channel_handle}")
async def get_channel_comments_by_handle(
    channel_handle: str,
    top_n: int = Query(default=5, ge=1, le=50, description="Number of most recent videos to process"),
    max_comments_per_video: int = Query(default=100, ge=1, le=1000, description="Maximum comments per video")
):
    """Get comments from the top N most recent videos of a channel"""
    try:
        # Get channel ID from handle
        import requests
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={channel_handle}&key={API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error retrieving channel ID. Status: {response.status_code}")
        
        data = response.json()
        if 'items' not in data or len(data['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with handle: {channel_handle}")
        
        channel_id = data['items'][0]['id']
        
        # Get recent videos (limited to top_n)
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=top_n
        ).execute()
        
        videos = playlist_response['items']

        # Get comments for each video
        result = {
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "videos_processed": len(videos),
            "videos": {}
        }
        
        total_comments = 0
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_title = video['snippet']['title']
            
            try:
                comments_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=max_comments_per_video,
                    textFormat="plainText"
                ).execute()
                
                comments = []
                for item in comments_response.get('items', []):
                    comment_data = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'author': comment_data['authorDisplayName'],
                        'text': comment_data['textDisplay'],
                        'publishedAt': comment_data['publishedAt'],
                        'likeCount': comment_data['likeCount']
                    })
                
                result["videos"][video_id] = {
                    "video_info": {
                        'id': video_id,
                        'title': video_title,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'publishedAt': video['snippet']['publishedAt']
                    },
                    "comments": comments,
                    "comment_count": len(comments)
                }
                total_comments += len(comments)
                
            except Exception as e:
                result["videos"][video_id] = {
                    "video_info": {
                        'id': video_id,
                        'title': video_title,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'publishedAt': video['snippet']['publishedAt']
                    },
                    "comments": [],
                    "comment_count": 0,
                    "error": f"Error fetching comments: {str(e)}"
                }
        
        result["total_comments"] = total_comments
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-transcript/{video_id}")
async def test_transcript(video_id: str):
    """Test transcript functionality for debugging"""
    result = {
        "video_id": video_id,
        "proxy_configured": True,
        "transcript": None,
        "has_transcript": False,
        "error": None,
        "transcript_length": 0
    }
    
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
        transcript_text = ""
        for item in transcript_list:
            timestamp = item['start']
            text = item['text']
            transcript_text += f'[{timestamp}] {text}\n'
        
        result["transcript"] = transcript_text
        result["has_transcript"] = True
        result["transcript_length"] = len(transcript_text)
        
    except Exception as e:
        result["error"] = str(e)
    
    return result

@app.get("/transcript-from-url")
async def get_transcript_from_url(video_link: str = Query(..., description="Full YouTube video URL")):
    """Get transcript using video URL instead of just video ID"""
    try:
        video_id = extract_video_id(video_link)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube video URL")
        
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
        transcript_text = ""
        for item in transcript_list:
            timestamp = item['start']
            text = item['text']
            transcript_text += f'[{timestamp}] {text}\n'
        
        return {
            "video_url": video_link,
            "video_id": video_id,
            "transcript": transcript_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/docs-api")
async def get_api_docs():
    """Comprehensive API Documentation with all endpoints"""
    return {
        "title": "YouTube API Documentation",
        "version": "2.0.1", 
        "base_url": "http://45.33.70.141:8001",
        "endpoints": [
            {
                "path": "/",
                "method": "GET",
                "description": "API status and version info",
                "example": "/"
            },
            {
                "path": "/health",
                "method": "GET",
                "description": "Health check with proxy status",
                "example": "/health"
            },
            {
                "path": "/transcript?videoId={id}",
                "method": "GET",
                "description": "Get video transcript (plain text)",
                "example": "/transcript?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/transcript-with-timestamps?videoId={id}",
                "method": "GET",
                "description": "Get video transcript with timestamps",
                "example": "/transcript-with-timestamps?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/transcript-from-url?video_link={url}",
                "method": "GET",
                "description": "Get transcript using full YouTube URL",
                "example": "/transcript-from-url?video_link=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            },
            {
                "path": "/test-transcript/{video_id}",
                "method": "GET",
                "description": "Test transcript functionality for debugging",
                "example": "/test-transcript/dQw4w9WgXcQ"
            },
            {
                "path": "/search?query={query}&maxResults={num}",
                "method": "GET",
                "description": "Search YouTube videos",
                "example": "/search?query=python tutorial&maxResults=10"
            },
            {
                "path": "/video_details?videoId={id}",
                "method": "GET",
                "description": "Get video details and statistics",
                "example": "/video_details?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/comments?videoId={id}&maxResults={num}",
                "method": "GET",
                "description": "Get video comments",
                "example": "/comments?videoId=dQw4w9WgXcQ&maxResults=100"
            },
            {
                "path": "/video/{video_id}",
                "method": "GET",
                "description": "Get complete video data (details + comments + transcript)",
                "example": "/video/dQw4w9WgXcQ"
            },
            {
                "path": "/channel-id?handle={handle}",
                "method": "GET",
                "description": "Get channel ID from handle",
                "example": "/channel-id?handle=mkbhd"
            },
            {
                "path": "/channel-videos?channel_id={id}",
                "method": "GET",
                "description": "Get all videos from channel",
                "example": "/channel-videos?channel_id=UCBJycsmduvYEL83R_U4JriQ"
            },
            {
                "path": "/channel-transcripts?channel_id={id}",
                "method": "GET",
                "description": "Get transcripts for ALL videos in channel",
                "example": "/channel-transcripts?channel_id=UCBJycsmduvYEL83R_U4JriQ"
            },
            {
                "path": "/transcripts/{channel_handle}?top_n={num}",
                "method": "GET",
                "description": "Get transcripts from top N recent videos of channel",
                "example": "/transcripts/mkbhd?top_n=5"
            },
            {
                "path": "/comments/{channel_handle}?top_n={num}&max_comments_per_video={num}",
                "method": "GET",
                "description": "Get comments from top N recent videos of channel",
                "example": "/comments/mkbhd?top_n=5&max_comments_per_video=50"
            },
            {
                "path": "/channel-content/{channel_handle}?top_n={num}&max_comments_per_video={num}",
                "method": "GET", 
                "description": "Get N recent videos with transcripts+comments (no shorts, sorted recent first)",
                "example": "/channel-content/mkbhd?top_n=10&max_comments_per_video=30"
            },
            {
                "path": "/search-filtered?query={query}&top_n={num}&min_subscribers={num}",
                "method": "GET",
                "description": "Search videos: 1K+ subs, no shorts, has transcripts, sorted recent first",
                "example": "/search-filtered?query=AI tutorial&top_n=5&min_subscribers=5000"
            }
        ],
        "testing_examples": [
            "GET /transcript?videoId=dQw4w9WgXcQ",
            "GET /search?query=tutorial&maxResults=5", 
            "GET /search-filtered?query=AI tutorial&top_n=5&min_subscribers=1000",
            "GET /video_details?videoId=dQw4w9WgXcQ",
            "GET /video/dQw4w9WgXcQ",
            "GET /transcripts/mkbhd?top_n=3",
            "GET /comments/mkbhd?top_n=3&max_comments_per_video=10",
            "GET /channel-content/mkbhd?top_n=5&max_comments_per_video=20",
            "GET /test-transcript/dQw4w9WgXcQ"
        ],
        "notes": [
            "All endpoints return JSON responses",
            "Working proxy configured for transcript access", 
            "Rate limits apply per YouTube API quotas",
            "Use /test-transcript/{video_id} for debugging transcript issues",
            "Channel handles should not include @ symbol",
            "Transcript endpoints handle videos without captions gracefully"
        ]
    }

def filter_out_shorts(video_ids: list) -> list:
    """Filter out YouTube Shorts (videos <= 60 seconds) from a list of video IDs"""
    if not video_ids:
        return []
    
    try:
        filtered_ids = []
        # Process in batches of 50 (YouTube API limit)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            video_ids_str = ','.join(batch)
            
            response = youtube.videos().list(
                part='contentDetails',
                id=video_ids_str
            ).execute()
            
            for video in response['items']:
                duration = video['contentDetails']['duration']
                # Parse ISO 8601 duration (PT#M#S format)
                if 'PT' in duration:
                    duration_clean = duration.replace('PT', '')
                    total_seconds = 0
                    
                    if 'H' in duration_clean:
                        # Has hours, definitely not a short
                        filtered_ids.append(video['id'])
                        continue
                    
                    if 'M' in duration_clean:
                        minutes_part = duration_clean.split('M')[0]
                        try:
                            minutes = int(minutes_part)
                            total_seconds += minutes * 60
                            duration_clean = duration_clean.split('M')[1]
                        except ValueError:
                            continue
                    
                    if 'S' in duration_clean:
                        seconds_part = duration_clean.replace('S', '')
                        try:
                            if seconds_part:
                                seconds = int(seconds_part)
                                total_seconds += seconds
                        except ValueError:
                            continue
                    
                    # Only include videos longer than 60 seconds
                    if total_seconds > 60:
                        filtered_ids.append(video['id'])
        
        return filtered_ids
        
    except Exception as e:
        print(f"Error filtering shorts: {e}")
        return video_ids  # Return original list if filtering fails

def get_channel_subscriber_count(channel_id: str) -> int:
    """Get subscriber count for a channel"""
    try:
        response = youtube.channels().list(
            part='statistics',
            id=channel_id
        ).execute()
        
        if response['items']:
            subscriber_count = response['items'][0]['statistics'].get('subscriberCount', '0')
            return int(subscriber_count)
        return 0
        
    except Exception as e:
        print(f"Error getting subscriber count: {e}")
        return 0

@app.get("/channel-content/{channel_handle}")
async def get_channel_content_filtered(
    channel_handle: str,
    top_n: int = Query(default=10, ge=1, le=50, description="Number of recent videos to process"),
    max_comments_per_video: int = Query(default=50, ge=1, le=1000, description="Maximum comments per video")
):
    """Get N recent videos from channel with transcripts and comments (no shorts, sorted by recent)"""
    try:
        # Get channel ID from handle
        import requests
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={channel_handle}&key={API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error retrieving channel ID. Status: {response.status_code}")
        
        data = response.json()
        if 'items' not in data or len(data['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with handle: {channel_handle}")
        
        channel_id = data['items'][0]['id']
        
        # Get recent videos (more than needed to account for filtering)
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get more videos initially to account for filtering out shorts
        fetch_limit = top_n * 3  # Get 3x more to filter
        videos = []
        next_page_token = None
        
        while len(videos) < fetch_limit:
            items_to_fetch = min(50, fetch_limit - len(videos))
            
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=items_to_fetch,
                pageToken=next_page_token
            ).execute()
            
            videos.extend(playlist_response['items'])
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break

        # Filter out shorts
        all_video_ids = [video['snippet']['resourceId']['videoId'] for video in videos]
        filtered_video_ids = filter_out_shorts(all_video_ids)
        
        # Build final video list maintaining chronological order
        filtered_videos = []
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            if video_id in filtered_video_ids and len(filtered_videos) < top_n:
                filtered_videos.append(video)

        # Get content for each filtered video
        result_videos = []
        videos_with_transcripts = 0
        total_comments = 0
        
        for video in filtered_videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_title = video['snippet']['title']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Get transcript
            transcript_text = None
            has_transcript = False
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                has_transcript = True
                videos_with_transcripts += 1
            except Exception as e:
                transcript_error = str(e)
            
            # Get comments
            comments = []
            try:
                comments_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=max_comments_per_video,
                    textFormat="plainText"
                ).execute()
                
                for item in comments_response.get('items', []):
                    comment_data = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'author': comment_data['authorDisplayName'],
                        'text': comment_data['textDisplay'],
                        'publishedAt': comment_data['publishedAt'],
                        'likeCount': comment_data['likeCount']
                    })
                total_comments += len(comments)
                
            except Exception as e:
                print(f"Comments error for {video_id}: {e}")
            
            result_videos.append({
                'video_info': {
                    'id': video_id,
                    'title': video_title,
                    'url': video_url,
                    'publishedAt': video['snippet']['publishedAt'],
                    'thumbnail': video['snippet']['thumbnails']['default']['url']
                },
                'transcript': transcript_text,
                'has_transcript': has_transcript,
                'comments': comments,
                'comment_count': len(comments)
            })

        return {
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "videos_processed": len(result_videos),
            "videos_with_transcripts": videos_with_transcripts,
            "total_comments": total_comments,
            "videos": result_videos
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search-filtered")
async def search_videos_filtered(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(default=10, ge=1, le=20, description="Number of videos to return"),
    min_subscribers: int = Query(default=1000, ge=100, le=50000, description="Minimum subscriber count")
):
    """Search videos with filtering: 1K+ subs, no shorts, must have transcripts, sorted by recent"""
    try:
        # Search for more videos initially to account for filtering
        search_limit = min(top_n * 5, 50)  # Get 5x more to filter
        
        response = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="date",  # Sort by most recent
            maxResults=search_limit,
            publishedAfter="2020-01-01T00:00:00Z"  # Recent videos only
        ).execute()
        
        # Collect all video data
        all_video_data = []
        all_video_ids = []
        
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            all_video_ids.append(video_id)
            all_video_data.append({
                'id': video_id,
                'title': item['snippet']['title'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'publishedAt': item['snippet']['publishedAt'],
                'channelTitle': item['snippet']['channelTitle'],
                'channelId': item['snippet']['channelId'],
                'thumbnail': item['snippet']['thumbnails']['default']['url']
            })
        
        # Filter out shorts
        filtered_video_ids = filter_out_shorts(all_video_ids)
        
        # Filter by subscriber count and transcript availability
        result_videos = []
        
        for video_data in all_video_data:
            if video_data['id'] not in filtered_video_ids:
                continue  # Skip shorts
            
            # Check subscriber count
            subscriber_count = get_channel_subscriber_count(video_data['channelId'])
            if subscriber_count < min_subscribers:
                continue  # Skip channels with low subscriber count
            
            # Check for transcript availability
            has_transcript = False
            transcript_text = None
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_data['id'], proxies=PROXIES)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                has_transcript = True
            except Exception:
                continue  # Skip videos without transcripts
            
            video_data['subscriber_count'] = subscriber_count
            video_data['transcript'] = transcript_text
            video_data['has_transcript'] = has_transcript
            
            result_videos.append(video_data)
            
            # Stop when we have enough videos
            if len(result_videos) >= top_n:
                break
        
        return {
            "query": query,
            "videos_found": len(result_videos),
            "min_subscribers": min_subscribers,
            "filters_applied": ["no_shorts", "has_transcript", f"min_{min_subscribers}_subs"],
            "videos": result_videos
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)