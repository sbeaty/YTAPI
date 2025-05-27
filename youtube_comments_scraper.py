import os
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

api_key = 'AIzaSyAlN-66eLljiexAKjZhbhKKh8B3_IGhf3c'
youtube = build('youtube', 'v3', developerKey=api_key)

def get_channel_id(handle):
    """Get channel ID from channel handle"""
    url = f'https://www.googleapis.com/youtube/v3/channels?part=id&forHandle={handle}&key={api_key}'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            return data['items'][0]['id']
        else:
            print(f"No channel found with the handle: {handle}")
            return None
    else:
        print(f"Error retrieving channel ID. Status code: {response.status_code}")
        return None

def get_recent_videos(channel_id, max_videos=2):
    """Get the most recent videos from a channel"""
    try:
        request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()

        if 'items' not in response or len(response['items']) == 0:
            print(f"No channel found with the ID: {channel_id}")
            return []

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        playlist_items_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=max_videos
        ).execute()

        videos = []
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

        return videos

    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def get_video_comments(video_id, max_comments=100):
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

def scrape_channel_comments(channel_handle, num_videos=2, max_comments_per_video=100):
    """Main function to scrape comments from recent videos of a channel"""
    print(f"Starting to scrape comments from channel: {channel_handle}")
    
    # Get channel ID
    channel_id = get_channel_id(channel_handle)
    if not channel_id:
        return None
    
    print(f"Channel ID: {channel_id}")
    
    # Get recent videos
    videos = get_recent_videos(channel_id, num_videos)
    if not videos:
        print("No videos found")
        return None
    
    print(f"Found {len(videos)} recent videos")
    
    # Scrape comments from each video
    all_comments = {}
    for video in videos:
        print(f"\nScraping comments from: {video['title']}")
        comments = get_video_comments(video['id'], max_comments_per_video)
        all_comments[video['id']] = {
            'video_info': video,
            'comments': comments,
            'comment_count': len(comments)
        }
        print(f"Found {len(comments)} comments")
    
    return all_comments

if __name__ == "__main__":
    # Example usage - Test with 2 most recent videos
    channel_handle = 'TheRandallCarlson'
    output_file = 'comments_data.json'

    # Scrape comments
    comments_data = scrape_channel_comments(channel_handle, num_videos=2, max_comments_per_video=50)

    if comments_data:
        # Save to JSON file
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(comments_data, file, indent=2, ensure_ascii=False)
        
        print(f"\nComments data saved to {output_file}")
        
        # Print summary
        total_comments = sum(data['comment_count'] for data in comments_data.values())
        print(f"Total videos processed: {len(comments_data)}")
        print(f"Total comments scraped: {total_comments}")
        
        # Show sample data
        for video_id, data in comments_data.items():
            print(f"\nVideo: {data['video_info']['title']}")
            print(f"Comments: {data['comment_count']}")
            if data['comments']:
                print(f"Sample comment: {data['comments'][0]['text'][:100]}...")
    else:
        print("Failed to scrape comments")