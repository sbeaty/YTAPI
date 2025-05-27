from fastapi import FastAPI, HTTPException, Query
from typing import Optional, Dict, Any
import os
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import uvicorn

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
    """Get the most recent videos from a channel"""
    try:
        request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()

        if 'items' not in response or len(response['items']) == 0:
            return []

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos = []
        next_page_token = None
        
        while len(videos) < max_videos:
            items_to_fetch = min(50, max_videos - len(videos))
            
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
                videos.append({
                    'id': video_id,
                    'url': video_url, 
                    'title': video_title,
                    'published': video_published
                })
                
            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                break

        return videos[:max_videos]

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

@app.get("/")
async def root():
    return {"message": "YouTube Comments & Transcripts API", "version": "1.0.0"}

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
        result["videos"][video['id']] = {
            "video_info": video,
            "transcript": transcript,
            "has_transcript": transcript is not None
        }
        if transcript:
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
    
    result = {
        "video_info": video_data,
        "comments": comments,
        "comment_count": len(comments),
        "transcript": transcript,
        "has_transcript": transcript is not None
    }
    
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)