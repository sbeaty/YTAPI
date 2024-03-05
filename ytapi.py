from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re

app = Flask(__name__)

@app.route('/transcript', methods=['GET'])
def get_transcript():
    youtube_url = request.args.get('url')
    if not youtube_url:
        return jsonify({'error': 'No YouTube URL provided'}), 400
    
    # Extract the video ID from the URL
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
    if not video_id_match:
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    video_id = video_id_match.group(1)
    
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        # Concatenate all text entries into one block of text
        full_transcript = ' '.join([entry['text'] for entry in transcript_list])
        return jsonify({'transcript': full_transcript})
    except (TranscriptsDisabled, NoTranscriptFound):
        return jsonify({'error': 'Transcript not available for this video'}), 404

if __name__ == '__main__':
    app.run(debug=True)
