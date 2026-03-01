import asyncio
from typing import AsyncGenerator
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from app.core.config import settings
import io
import subprocess

class TranscriptCollector(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream):
        super().__init__(transcript_result_stream)
        self.transcribed_text = []

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcribed_text.append(alt.transcript)

class TranscribeService:
    @staticmethod
    async def convert_to_pcm(audio_bytes: bytes) -> bytes:
        """
        Uses ffmpeg to convert any audio source (MP3, M4A, etc.) to 
        raw 16-bit PCM mono at 16kHz.
        """
        command = [
            'ffmpeg',
            '-i', 'pipe:0',          # Input from stdin
            '-f', 's16le',           # Raw PCM 16-bit little-endian
            '-ac', '1',              # Mono
            '-ar', '16000',          # 16kHz sample rate
            'pipe:1'                 # Output to stdout
        ]
        
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = process.communicate(input=audio_bytes)
        
        if process.returncode != 0:
            print(f"[CONVERSION] FFmpeg Error: {stderr.decode()}")
            return audio_bytes # Fallback (will likely fail later)
            
        return stdout

    @staticmethod
    async def transcribe_audio_file(file_bytes: bytes, file_extension: str = "mp3") -> str:
        """
        Streams audio bytes directly to AWS Transcribe over HTTP/2.
        Converts non-native formats using ffmpeg.
        """
        print(f"[TRANSCRIPTION] Starting for extension: {file_extension}, size: {len(file_bytes)} bytes")
        
        # Determine format for the AWS Streaming API
        audio_format = "pcm"
        if file_extension in ["ogg", "webm"]:
            audio_format = "ogg-opus"
            processed_bytes = file_bytes
        elif file_extension == "flac":
            audio_format = "flac"
            processed_bytes = file_bytes
        else:
            # MP3, WAV, M4A, etc. - Normalize everything else to raw PCM via FFmpeg
            print(f"[TRANSCRIPTION] Normalizing {file_extension} to PCM 16k mono via FFmpeg...")
            processed_bytes = await TranscribeService.convert_to_pcm(file_bytes)
            audio_format = "pcm"

        try:
            # CRITICAL: On ARM/Linux (EC2 aarch64), the underlying CRT library requires these 
            # to be present in the OS environment to correctly resolve the streaming path.
            import os
            os.environ["AWS_ACCESS_KEY_ID"] = settings.AWS_ACCESS_KEY_ID
            os.environ["AWS_SECRET_ACCESS_KEY"] = settings.AWS_SECRET_ACCESS_KEY
            os.environ["AWS_DEFAULT_REGION"] = settings.AWS_REGION
            os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
            if hasattr(settings, "AWS_SESSION_TOKEN") and settings.AWS_SESSION_TOKEN:
                os.environ["AWS_SESSION_TOKEN"] = settings.AWS_SESSION_TOKEN

            client = TranscribeStreamingClient(region=settings.AWS_REGION)
            
            stream = await client.start_stream_transcription(
                language_code="en-US",
                media_sample_rate_hz=16000,
                media_encoding=audio_format
            )
            
            async def write_chunks():
                chunk_size = 1024 * 8
                buffer = io.BytesIO(processed_bytes)
                while True:
                    chunk = buffer.read(chunk_size)
                    if not chunk:
                        break
                    await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await stream.input_stream.end_stream()

            handler = TranscriptCollector(stream.output_stream)
            
            # Run both concurrently
            await asyncio.gather(write_chunks(), handler.handle_events())
            
            transcript = " ".join(handler.transcribed_text)
            print(f"[TRANSCRIPTION] Result: '{transcript}'")
            return transcript
            
        except Exception as e:
            print(f"[TRANSCRIPTION] ERROR: {str(e)}")
            raise e
