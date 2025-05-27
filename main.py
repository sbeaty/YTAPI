from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import os
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import uvicorn

app = FastAPI(
    title="YouTube Search & Analysis API",
    description="API for searching YouTube videos and extracting comments and transcripts",
    version="1.0.0"
)

api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
youtube = build('youtube', 'v3', developerKey=api_key)

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
    """Get transcript from a specific video"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = ''
        for item in transcript_list:
            timestamp = item['start']
            text = item['text']
            transcript_text += f'[{timestamp}] {text}\n'
        return transcript_text
    except Exception as e:
        print(f'Error fetching transcript for video {video_id}: {str(e)}')
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
        
        # Build final video list maintaining chronological order
        videos = []
        for video_id in all_video_ids:  # Maintain original order
            if video_id in filtered_video_ids and len(videos) < max_results:
                videos.append(video_data_map[video_id])
        
        return videos
        
    except HttpError as e:
        print(f"An HTTP error occurred during search: {e}")
        return []

@app.get("/")
async def root():
    return {"message": "YouTube Search & Analysis API", "version": "1.0.0"}

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
            video_data["transcript"] = transcript
            video_data["has_transcript"] = transcript is not None
            if transcript:
                videos_with_transcripts += 1
        
        result["videos"][video['id']] = video_data
    
    result["total_comments"] = total_comments
    if include_transcripts:
        result["videos_with_transcripts"] = videos_with_transcripts
    
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)