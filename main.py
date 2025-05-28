from fastapi import FastAPI, HTTPException, Query
from typing import Optional, Dict, Any
import os
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import uvicorn

# Import YouTube Transcript API with error handling
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_API_AVAILABLE = True
    print("✅ YouTube Transcript API loaded successfully")
except ImportError as e:
    print(f"❌ Failed to import YouTube Transcript API: {e}")
    TRANSCRIPT_API_AVAILABLE = False
    # Create a mock class to prevent errors
    class YouTubeTranscriptApi:
        @staticmethod
        def get_transcript(video_id, languages=None):
            raise Exception("YouTube Transcript API not available")
        
        @staticmethod
        def list_transcripts(video_id):
            raise Exception("YouTube Transcript API not available")

app = FastAPI(
    title="YouTube Comments & Transcripts API",
    description="API for scraping YouTube comments and transcripts",
    version="1.0.0"
)

api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
youtube = build('youtube', 'v3', developerKey=api_key)

def get_channel_id(handle: str) -> Optional[str]:
    """Get channel ID from channel handle"""
    url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={handle}&key={api_key}'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            return data['items'][0]['id']
    return None

def get_recent_videos(channel_id: str, max_videos: int = 10) -> list:
    """Get the most recent full-format videos from a channel (no shorts)"""
    try:
        request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()

        if 'items' not in response or len(response['items']) == 0:
            return []

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        all_videos = []
        next_page_token = None
        
        # Fetch more videos initially to account for filtering out shorts
        fetch_limit = max_videos * 3  # Get 3x more to filter
        
        while len(all_videos) < fetch_limit:
            items_to_fetch = min(50, fetch_limit - len(all_videos))
            
            playlist_items_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=items_to_fetch,
                pageToken=next_page_token
            ).execute()

            for video in playlist_items_response['items']:
                video_id = video['snippet']['resourceId']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                video_title = video['snippet']['title']
                video_published = video['snippet']['publishedAt']
                all_videos.append({
                    'id': video_id,
                    'url': video_url, 
                    'title': video_title,
                    'published': video_published
                })
                
            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                break

        # Filter out shorts
        all_video_ids = [video['id'] for video in all_videos]
        filtered_video_ids = filter_out_shorts(all_video_ids)
        
        # Build final video list maintaining chronological order
        filtered_videos = []
        for video in all_videos:
            if video['id'] in filtered_video_ids and len(filtered_videos) < max_videos:
                filtered_videos.append(video)
        
        return filtered_videos

    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def get_video_comments(video_id: str, max_comments: int = 100) -> list:
    """Get comments from a specific video"""
    comments = []
    try:
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=min(max_comments, 100),
            order='time'
        )
        response = request.execute()
        
        while response and len(comments) < max_comments:
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment['authorDisplayName'],
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'published': comment['publishedAt'],
                    'updated': comment['updatedAt']
                })
                
                if len(comments) >= max_comments:
                    break
            
            if 'nextPageToken' in response and len(comments) < max_comments:
                request = youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    maxResults=min(max_comments - len(comments), 100),
                    pageToken=response['nextPageToken'],
                    order='time'
                )
                response = request.execute()
            else:
                break
                
    except HttpError as e:
        print(f"Error fetching comments for video {video_id}: {e}")
        
    return comments

def get_video_transcript(video_id: str) -> Optional[str]:
    """Get transcript from a specific video - simplified working version"""
    if not TRANSCRIPT_API_AVAILABLE:
        print(f"❌ YouTube Transcript API not available for video {video_id}")
        return None
    
    print(f"🔍 Attempting to fetch transcript for video {video_id}")
    
    try:
        # Use the simple approach that works in the notebook
        print(f"📞 Calling YouTubeTranscriptApi.get_transcript({video_id})")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        print(f"✅ Got transcript with {len(transcript_list)} entries")
        
        transcript_text = ''
        for item in transcript_list:
            timestamp = item['start']
            text = item['text']
            transcript_text += f'[{timestamp}] {text}\n'
        
        print(f"📝 Built transcript text: {len(transcript_text)} characters")
        return transcript_text
    except Exception as e:
        print(f'❌ Error fetching transcript for video {video_id}: {str(e)}')
        print(f'❌ Exception type: {type(e).__name__}')
        return None

def filter_out_shorts(video_ids: list) -> list:
    """Filter out YouTube Shorts (videos <= 60 seconds) from a list of video IDs"""
    if not video_ids:
        return []
    
    try:
        # Get video details including duration for up to 50 videos at once
        filtered_ids = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            video_ids_str = ','.join(batch)
            
            request = youtube.videos().list(
                part='contentDetails',
                id=video_ids_str
            )
            response = request.execute()
            
            for video in response['items']:
                duration = video['contentDetails']['duration']
                # Parse ISO 8601 duration (PT#M#S format)
                # PT60S = 60 seconds, PT1M = 60 seconds, PT1M30S = 90 seconds
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
        
    except HttpError as e:
        print(f"An HTTP error occurred while filtering shorts: {e}")
        return video_ids  # Return original list if filtering fails

def get_channel_subscriber_count(channel_id: str) -> int:
    """Get subscriber count for a channel"""
    try:
        request = youtube.channels().list(
            part='statistics',
            id=channel_id
        )
        response = request.execute()
        
        if response['items']:
            subscriber_count = response['items'][0]['statistics'].get('subscriberCount', '0')
            return int(subscriber_count)
        return 0
        
    except HttpError as e:
        print(f"An HTTP error occurred while getting subscriber count: {e}")
        return 0

def filter_channels_by_subscribers(videos: list, min_subscribers: int = 5000) -> list:
    """Filter videos to only include channels with minimum subscriber count"""
    filtered_videos = []
    
    for video in videos:
        channel_id = video['channel_id']
        subscriber_count = get_channel_subscriber_count(channel_id)
        
        if subscriber_count >= min_subscribers:
            video['subscriber_count'] = subscriber_count
            filtered_videos.append(video)
            print(f"✅ Included: {video['channel_title']} ({subscriber_count:,} subscribers)")
        else:
            print(f"❌ Filtered out: {video['channel_title']} ({subscriber_count:,} subscribers)")
    
    return filtered_videos

def search_videos_by_query(query: str, max_results: int = 10) -> list:
    """Search for videos by query and return most recent full-format results (no shorts)"""
    try:
        # Request more videos initially to account for filtering out shorts
        search_limit = min(max_results * 3, 50)  # Get 3x more to filter
        
        request = youtube.search().list(
            part='snippet',
            q=query,
            type='video',
            order='date',
            maxResults=search_limit,
            publishedAfter='2020-01-01T00:00:00Z'
        )
        response = request.execute()
        
        # Collect all video IDs first
        all_video_ids = []
        video_data_map = {}
        
        for item in response['items']:
            video_id = item['id']['videoId']
            all_video_ids.append(video_id)
            video_data_map[video_id] = {
                'id': video_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'title': item['snippet']['title'],
                'published': item['snippet']['publishedAt'],
                'channel_title': item['snippet']['channelTitle'],
                'channel_id': item['snippet']['channelId']
            }
        
        # Filter out shorts
        filtered_video_ids = filter_out_shorts(all_video_ids)
        
        # Build video list maintaining chronological order
        videos = []
        for video_id in all_video_ids:  # Maintain original order
            if video_id in filtered_video_ids:
                videos.append(video_data_map[video_id])
        
        # Filter by subscriber count (5K+ subscribers)
        subscriber_filtered_videos = filter_channels_by_subscribers(videos, min_subscribers=5000)
        
        # Return only the requested number of results
        return subscriber_filtered_videos[:max_results]
        
    except HttpError as e:
        print(f"An HTTP error occurred during search: {e}")
        return []

@app.get("/")
async def root():
    return {
        "message": "YouTube Comments & Transcripts API", 
        "version": "1.0.0",
        "transcript_api_available": TRANSCRIPT_API_AVAILABLE
    }

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API status"""
    return {
        "status": "healthy",
        "transcript_api_available": TRANSCRIPT_API_AVAILABLE,
        "youtube_api_key_configured": bool(api_key),
        "timestamp": "2024-01-01"  # Will show current deployment
    }

@app.get("/test-transcript/{video_id}")
async def test_transcript(video_id: str):
    """Test transcript functionality for a specific video"""
    result = {
        "video_id": video_id,
        "transcript_api_available": TRANSCRIPT_API_AVAILABLE,
        "transcript": None,
        "has_transcript": False,
        "error": None
    }
    
    if not TRANSCRIPT_API_AVAILABLE:
        result["error"] = "YouTube Transcript API not available"
        return result
    
    try:
        transcript = get_video_transcript(video_id)
        result["transcript"] = transcript
        result["has_transcript"] = transcript is not None and transcript.strip() != ""
        result["transcript_length"] = len(transcript) if transcript else 0
    except Exception as e:
        result["error"] = str(e)
    
    return result

@app.get("/comments/{channel_handle}")
async def get_channel_comments(
    channel_handle: str,
    top_n: int = Query(default=5, ge=1, le=50, description="Number of most recent videos to process"),
    max_comments_per_video: int = Query(default=100, ge=1, le=1000, description="Maximum comments per video")
):
    """Get comments from the top N most recent videos of a channel"""
    
    # Get channel ID
    channel_id = get_channel_id(channel_handle)
    if not channel_id:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_handle}' not found")
    
    # Get recent videos
    videos = get_recent_videos(channel_id, top_n)
    if not videos:
        raise HTTPException(status_code=404, detail="No videos found for this channel")
    
    # Scrape comments from each video
    result = {
        "channel_handle": channel_handle,
        "channel_id": channel_id,
        "videos_processed": len(videos),
        "videos": {}
    }
    
    total_comments = 0
    for video in videos:
        comments = get_video_comments(video['id'], max_comments_per_video)
        result["videos"][video['id']] = {
            "video_info": video,
            "comments": comments,
            "comment_count": len(comments)
        }
        total_comments += len(comments)
    
    result["total_comments"] = total_comments
    return result

@app.get("/transcripts/{channel_handle}")
async def get_channel_transcripts(
    channel_handle: str,
    top_n: int = Query(default=5, ge=1, le=50, description="Number of most recent videos to process")
):
    """Get transcripts from the top N most recent videos of a channel"""
    
    # Get channel ID
    channel_id = get_channel_id(channel_handle)
    if not channel_id:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_handle}' not found")
    
    # Get recent videos
    videos = get_recent_videos(channel_id, top_n)
    if not videos:
        raise HTTPException(status_code=404, detail="No videos found for this channel")
    
    # Get transcripts from each video
    result = {
        "channel_handle": channel_handle,
        "channel_id": channel_id,
        "videos_processed": len(videos),
        "videos": {}
    }
    
    videos_with_transcripts = 0
    for video in videos:
        transcript = get_video_transcript(video['id'])
        # Check if transcript is not None, not empty, and not just whitespace
        is_valid_transcript = transcript is not None and transcript.strip() != ""
        result["videos"][video['id']] = {
            "video_info": video,
            "transcript": transcript if is_valid_transcript else None,
            "has_transcript": is_valid_transcript
        }
        if is_valid_transcript:
            videos_with_transcripts += 1
    
    result["videos_with_transcripts"] = videos_with_transcripts
    return result

@app.get("/video/{video_id}")
async def get_video_data(
    video_id: str,
    max_comments: int = Query(default=100, ge=1, le=1000, description="Maximum comments to fetch")
):
    """Get both comments and transcript for a single video"""
    
    # Get video info
    try:
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        if not video_response['items']:
            raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found")
            
        video_info = video_response['items'][0]['snippet']
        video_data = {
            'id': video_id,
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'title': video_info['title'],
            'published': video_info['publishedAt'],
            'channel_title': video_info['channelTitle'],
            'channel_id': video_info['channelId']
        }
        
    except HttpError:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found")
    
    # Get comments and transcript
    comments = get_video_comments(video_id, max_comments)
    transcript = get_video_transcript(video_id)
    
    # Check if transcript is not None, not empty, and not just whitespace
    is_valid_transcript = transcript is not None and transcript.strip() != ""
    
    result = {
        "video_info": video_data,
        "comments": comments,
        "comment_count": len(comments),
        "transcript": transcript if is_valid_transcript else None,
        "has_transcript": is_valid_transcript
    }
    
    return result

@app.get("/search")
async def search_and_analyze(
    query: str = Query(description="Search query for YouTube videos"),
    top_n: int = Query(default=5, ge=1, le=20, description="Number of most recent videos to process"),
    max_comments_per_video: int = Query(default=100, ge=1, le=1000, description="Maximum comments per video"),
    include_transcripts: bool = Query(default=True, description="Whether to include video transcripts")
):
    """Search for videos by query and get comments and transcripts from top N most recent results"""
    
    # Search for videos
    videos = search_videos_by_query(query, top_n)
    if not videos:
        raise HTTPException(status_code=404, detail=f"No videos found for query: '{query}'")
    
    # Process each video
    result = {
        "query": query,
        "videos_found": len(videos),
        "videos_processed": len(videos),
        "include_transcripts": include_transcripts,
        "videos": {}
    }
    
    total_comments = 0
    videos_with_transcripts = 0
    
    for video in videos:
        video_data = {
            "video_info": video,
            "comments": [],
            "comment_count": 0,
            "transcript": None,
            "has_transcript": False
        }
        
        # Get comments
        comments = get_video_comments(video['id'], max_comments_per_video)
        video_data["comments"] = comments
        video_data["comment_count"] = len(comments)
        total_comments += len(comments)
        
        # Get transcript if requested
        if include_transcripts:
            transcript = get_video_transcript(video['id'])
            # Check if transcript is not None, not empty, and not just whitespace
            is_valid_transcript = transcript is not None and transcript.strip() != ""
            video_data["transcript"] = transcript if is_valid_transcript else None
            video_data["has_transcript"] = is_valid_transcript
            if is_valid_transcript:
                videos_with_transcripts += 1
        
        result["videos"][video['id']] = video_data
    
    result["total_comments"] = total_comments
    if include_transcripts:
        result["videos_with_transcripts"] = videos_with_transcripts
    
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)