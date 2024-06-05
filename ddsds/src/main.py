import json
from apify import Actor
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

async def main() -> None:
    # Correct usage of the async context manager for the Actor instance
    async with Actor() as actor:
        actor_input = await actor.get_input() or {}
        
        # Get the YouTube link from the actor input
        youtube_link = actor_input.get('youtube_link')
        
        if youtube_link:
            # Assuming the YouTube link format is 'https://www.youtube.com/watch?v=dKfdRTAqX0c'
            video_id = youtube_link.split('v=')[-1]
            
            try:
                # Fetching the transcript using the video ID
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                
                # Concatenating all text items in the transcript into a single string
                transcript_text = " ".join([item['text'] for item in transcript_list])
                
                # Save the transcript text to the actor output
                await actor.push_data({"transcript": transcript_text})
                
                actor.log.info("Transcript extracted successfully.")
            except TranscriptsDisabled:
                actor.log.error("Transcripts are disabled for this video.")
            except NoTranscriptFound:
                actor.log.error("No transcript found for this video.")
            except Exception as e:
                actor.log.error(f"An error occurred: {e}")
        else:
            actor.log.error("YouTube link not provided in the actor input.")

# Remember to call the main function appropriately in your script
# For example, if you're using this in an Apify actor, you might use:
if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
