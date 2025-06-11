from fastapi import FastAPI, HTTPException, Query
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import uvicorn

app = FastAPI(
    title="YouTube Comments & Transcripts API",
    description="API for scraping YouTube comments and transcripts with working proxy support",
    version="2.0.0"
)

# Working API key and proper proxy configuration
API_KEY = 'AIzaSyBr-juudGbZtHf4xCTFtxF065SfO8b3YQU'
PROXY_URL = "https://f3138bb7d6946fd998eb:9a590d5c36b57e6f@gw.dataimpulse.com:823"
PROXIES = {"https": PROXY_URL, "http": PROXY_URL}

# Proper YouTube Transcript API proxy configuration
PROXY_CONFIG = GenericProxyConfig(
    http_url="http://f3138bb7d6946fd998eb:9a590d5c36b57e6f@gw.dataimpulse.com:823",
    https_url="https://f3138bb7d6946fd998eb:9a590d5c36b57e6f@gw.dataimpulse.com:823"
)

# Create YouTube Transcript API instance with proxy
ytt_api_proxy = YouTubeTranscriptApi(proxy_config=PROXY_CONFIG)
ytt_api_no_proxy = YouTubeTranscriptApi()

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
        "version": "2.0.1",
        "status": "working"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "proxy_configured": True}

@app.get("/debug-transcript/{video_id}")
async def debug_transcript(video_id: str):
    """Debug transcript availability for a specific video"""
    result = {
        "video_id": video_id,
        "available_transcripts": [],
        "proxy_test": None,
        "no_proxy_test": None,
        "errors": []
    }
    
    # List available transcripts
    try:
        transcript_list = ytt_api_no_proxy.list_transcripts(video_id)
        for transcript in transcript_list:
            result["available_transcripts"].append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable
            })
    except Exception as e:
        result["errors"].append(f"list_transcripts error: {str(e)}")
    
    # Test proper proxy method
    try:
        transcript = ytt_api_proxy.get_transcript(video_id)
        result["proxy_test"] = f"SUCCESS: Got {len(transcript)} transcript items"
    except Exception as e:
        result["proxy_test"] = f"FAILED: {str(e)}"
    
    # Test no proxy method
    try:
        transcript = ytt_api_no_proxy.get_transcript(video_id)
        result["no_proxy_test"] = f"SUCCESS: Got {len(transcript)} transcript items"
    except Exception as e:
        result["no_proxy_test"] = f"FAILED: {str(e)}"
    
    return result

@app.get("/transcript")
async def get_transcript(videoId: str = Query(..., description="YouTube video ID")):
    """Get transcript for a YouTube video with fallback method"""
    # First, try to list available transcripts for debugging
    try:
        transcript_list = ytt_api_no_proxy.list_transcripts(videoId)
        available_transcripts = []
        for transcript in transcript_list:
            available_transcripts.append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable
            })
        print(f"Available transcripts for {videoId}: {available_transcripts}")
    except Exception as e:
        print(f"Could not list transcripts for {videoId}: {e}")
    
    # Try with proper proxy configuration first
    try:
        transcript = ytt_api_proxy.get_transcript(videoId)
        text = " ".join([item['text'] for item in transcript])
        return {"transcript": text, "method": "proper_proxy"}
    except Exception as e:
        print(f"Proper proxy method failed for {videoId}: {e}")
        
    # Try with proxy and different languages
    try:
        transcript = ytt_api_proxy.get_transcript(videoId, languages=['en', 'en-US', 'en-GB'])
        text = " ".join([item['text'] for item in transcript])
        return {"transcript": text, "method": "proxy_multi_lang"}
    except Exception as e:
        print(f"Proxy multi-language method failed for {videoId}: {e}")
        
    # Fallback: try without proxy
    try:
        transcript = ytt_api_no_proxy.get_transcript(videoId)
        text = " ".join([item['text'] for item in transcript])
        return {"transcript": text, "method": "no_proxy"}
    except Exception as e:
        print(f"No proxy method failed for {videoId}: {e}")
        
    # Fallback: try without proxy with multiple languages
    try:
        transcript = ytt_api_no_proxy.get_transcript(videoId, languages=['en', 'en-US', 'en-GB'])
        text = " ".join([item['text'] for item in transcript])
        return {"transcript": text, "method": "no_proxy_multi_lang"}
    except Exception as e:
        print(f"No proxy multi-language method failed for {videoId}: {e}")
        raise HTTPException(status_code=500, detail=f"All transcript methods failed: {str(e)}")

@app.get("/transcript-with-timestamps")
async def get_transcript_with_timestamps(videoId: str = Query(..., description="YouTube video ID")):
    """Get transcript with timestamps and fallback method"""
    # Try with proxy first
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoId, proxies=PROXIES)
        formatted_transcript = ""
        for item in transcript:
            timestamp = item['start']
            text = item['text']
            formatted_transcript += f'[{timestamp}] {text}\n'
        return {"transcript": formatted_transcript}
    except Exception as e:
        print(f"Proxy method failed for {videoId}: {e}")
        
    # Fallback: try without proxy
    try:
        transcript = YouTubeTranscriptApi.get_transcript(videoId)
        formatted_transcript = ""
        for item in transcript:
            timestamp = item['start']
            text = item['text']
            formatted_transcript += f'[{timestamp}] {text}\n'
        return {"transcript": formatted_transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No transcript available: {str(e)}")

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
        
        # Get transcript with fallback
        transcript_text = None
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
            transcript_text = ""
            for item in transcript_list:
                timestamp = item['start']
                text = item['text']
                transcript_text += f'[{timestamp}] {text}\n'
        except Exception as e:
            print(f"Proxy transcript error for {video_id}: {e}")
            # Fallback: try without proxy
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
            except Exception as e2:
                transcript_text = None
                print(f"No proxy transcript error for {video_id}: {e2}")
        
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

@app.get("/channel-full-content")
async def get_channel_full_content(
    channel_handle: str = Query(..., description="YouTube channel handle"),
    include_comments: bool = Query(default=True, description="Include comments for each video"),
    max_comments_per_video: int = Query(default=50, ge=1, le=1000, description="Maximum comments per video")
):
    """Get ALL videos from channel with transcripts and optionally comments"""
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
        
        # Get channel uploads playlist
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        if 'items' not in channel_response or len(channel_response['items']) == 0:
            raise HTTPException(status_code=404, detail=f"No channel found with ID: {channel_id}")

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get ALL videos from uploads playlist
        all_videos = []
        next_page_token = None
        
        while True:
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            all_videos.extend(playlist_response['items'])
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break

        # Process each video for transcripts and optionally comments
        result_videos = []
        videos_with_transcripts = 0
        total_comments = 0
        
        for video in all_videos:
            video_id = video['snippet']['resourceId']['videoId']
            video_title = video['snippet']['title']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Get transcript with fallback method  
            transcript_text = None
            has_transcript = False
            try:
                # Try with proxy first
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                has_transcript = True
                videos_with_transcripts += 1
            except Exception as e:
                print(f"Proxy transcript error for {video_id}: {str(e)}")
                # Fallback: try without proxy
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    transcript_text = ""
                    for item in transcript_list:
                        timestamp = item['start']
                        text = item['text']
                        transcript_text += f'[{timestamp}] {text}\n'
                    has_transcript = True
                    videos_with_transcripts += 1
                except Exception as e2:
                    print(f"No proxy transcript error for {video_id}: {str(e2)}")
                    transcript_text = None
                    has_transcript = False
            
            # Get comments if requested
            comments = []
            if include_comments:
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
            
            video_data = {
                'video_info': {
                    'id': video_id,
                    'title': video_title,
                    'url': video_url,
                    'publishedAt': video['snippet']['publishedAt'],
                    'thumbnail': video['snippet']['thumbnails']['default']['url']
                },
                'transcript': transcript_text,
                'has_transcript': has_transcript
            }
            
            if include_comments:
                video_data['comments'] = comments
                video_data['comment_count'] = len(comments)
            
            result_videos.append(video_data)

        result = {
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "total_videos": len(result_videos),
            "videos_with_transcripts": videos_with_transcripts,
            "include_comments": include_comments,
            "videos": result_videos
        }
        
        if include_comments:
            result["total_comments"] = total_comments
            
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in channel-full-content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing channel: {str(e)}")

@app.get("/test-channel-transcript/{channel_handle}")
async def test_channel_transcript(channel_handle: str):
    """Test transcript extraction for first video in channel"""
    try:
        # Get channel ID
        import requests
        url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={channel_handle}&key={API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"Error retrieving channel ID. Status: {response.status_code}"}
        
        data = response.json()
        if 'items' not in data or len(data['items']) == 0:
            return {"error": f"No channel found with handle: {channel_handle}"}
        
        channel_id = data['items'][0]['id']
        
        # Get first video
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=1
        ).execute()
        
        if not playlist_response['items']:
            return {"error": "No videos found in channel"}
        
        video = playlist_response['items'][0]
        video_id = video['snippet']['resourceId']['videoId']
        video_title = video['snippet']['title']
        
        # Test transcript
        result = {
            "channel_handle": channel_handle,
            "channel_id": channel_id,
            "test_video_id": video_id,
            "test_video_title": video_title,
            "proxy_configured": True,
            "transcript": None,
            "has_transcript": False,
            "error": None
        }
        
        # Try with proxy first
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=PROXIES)
            transcript_text = ""
            for item in transcript_list:
                timestamp = item['start']
                text = item['text']
                transcript_text += f'[{timestamp}] {text}\n'
            
            result["transcript"] = transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text
            result["has_transcript"] = True
            result["transcript_length"] = len(transcript_text)
            result["method"] = "proxy"
            
        except Exception as e:
            print(f"Proxy method failed: {e}")
            # Fallback: try without proxy
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = ""
                for item in transcript_list:
                    timestamp = item['start']
                    text = item['text']
                    transcript_text += f'[{timestamp}] {text}\n'
                
                result["transcript"] = transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text
                result["has_transcript"] = True
                result["transcript_length"] = len(transcript_text)
                result["method"] = "no_proxy"
                
            except Exception as e2:
                result["error"] = f"Both methods failed. Proxy: {str(e)}, No proxy: {str(e2)}"
        
        return result
        
    except Exception as e:
        return {"error": f"Test failed: {str(e)}"}

@app.get("/docs-api")
async def get_api_docs():
    """API Documentation"""
    return {
        "title": "YouTube API Documentation",
        "version": "2.0.0",
        "base_url": "http://your-server:8001",
        "endpoints": [
            {
                "path": "/transcript?videoId={id}",
                "description": "Get video transcript (plain text)",
                "example": "/transcript?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/transcript-with-timestamps?videoId={id}",
                "description": "Get video transcript with timestamps",
                "example": "/transcript-with-timestamps?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/search?query={query}&maxResults={num}",
                "description": "Search YouTube videos",
                "example": "/search?query=python tutorial&maxResults=10"
            },
            {
                "path": "/video_details?videoId={id}",
                "description": "Get video details and statistics",
                "example": "/video_details?videoId=dQw4w9WgXcQ"
            },
            {
                "path": "/comments?videoId={id}&maxResults={num}",
                "description": "Get video comments",
                "example": "/comments?videoId=dQw4w9WgXcQ&maxResults=100"
            },
            {
                "path": "/video/{video_id}",
                "description": "Get complete video data (details + comments + transcript)",
                "example": "/video/dQw4w9WgXcQ"
            },
            {
                "path": "/channel-id?handle={handle}",
                "description": "Get channel ID from handle",
                "example": "/channel-id?handle=mkbhd"
            },
            {
                "path": "/channel-videos?channel_id={id}",
                "description": "Get all videos from channel",
                "example": "/channel-videos?channel_id=UCBJycsmduvYEL83R_U4JriQ"
            },
            {
                "path": "/channel-full-content?channel_handle={handle}&include_comments={bool}&max_comments_per_video={num}",
                "description": "Get ALL videos from channel with transcripts and optionally comments",
                "example": "/channel-full-content?channel_handle=mkbhd&include_comments=true&max_comments_per_video=30"
            }
        ],
        "notes": [
            "All endpoints return JSON",
            "Proxy configured for transcript access",
            "Rate limits apply per YouTube API quotas"
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)