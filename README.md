# YouTube Comments & Transcripts Analysis API

A FastAPI-based service for extracting comments and transcripts from YouTube videos.

## Features

- Extract comments from specific YouTube videos
- Get transcripts from YouTube videos
- Analyze recent videos from specific channels
- Search for videos by query and analyze top N most recent results
- RESTful API with automatic documentation

## Endpoints

### 1. Root Endpoint
- **GET** `/` - API information

### 2. Channel Analysis
- **GET** `/comments/{channel_handle}` - Get comments from recent videos of a channel
- **GET** `/transcripts/{channel_handle}` - Get transcripts from recent videos of a channel

### 3. Single Video Analysis
- **GET** `/video/{video_id}` - Get both comments and transcript for a single video

### 4. Search and Analysis (NEW)
- **GET** `/search` - Search for videos by query and analyze top N most recent results

#### Search Parameters:
- `query` (required): Search query for YouTube videos
- `top_n` (default: 5, max: 20): Number of most recent videos to process
- `max_comments_per_video` (default: 100, max: 1000): Maximum comments per video
- `include_transcripts` (default: true): Whether to include video transcripts

#### Example Usage:
```
GET /search?query=python%20tutorial&top_n=3&max_comments_per_video=50&include_transcripts=true
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

3. Access the API documentation at: http://localhost:8000/docs

## API Response Format

### Search Endpoint Response:
```json
{
  "query": "search query",
  "videos_found": 3,
  "videos_processed": 3,
  "include_transcripts": true,
  "videos": {
    "video_id": {
      "video_info": {
        "id": "video_id",
        "url": "youtube_url",
        "title": "video title",
        "published": "2025-05-27T03:30:10Z",
        "channel_title": "Channel Name",
        "channel_id": "channel_id"
      },
      "comments": [...],
      "comment_count": 10,
      "transcript": "transcript text",
      "has_transcript": true
    }
  },
  "total_comments": 30,
  "videos_with_transcripts": 2
}
```

## Requirements

- Python 3.7+
- YouTube Data API v3 key
- Google API Python Client
- FastAPI
- youtube-transcript-api

## Note

Make sure to configure your YouTube API key in the `main.py` file before running the application.