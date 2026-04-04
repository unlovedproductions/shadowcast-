"""
TTS (Text-to-Speech) Generator Module
Generates voiceover audio from script segments using Google TTS.
Can be optionally added to rendered videos.
"""

import json
import os
import tempfile

from gtts import gTTS
from moviepy import AudioFileClip, VideoFileClip, CompositeAudioClip, concatenate_audioclips


def generate_voiceover_for_segments(segments: list, output_path: str, lang: str = "en") -> str:
    """Generate a single voiceover audio file from script segments."""
    
    temp_files = []
    audio_clips = []
    
    try:
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue
            
            # Clean text of emoji for TTS
            clean_text = "".join(c for c in text if ord(c) < 0x1F600 or ord(c) > 0x1F9FF)
            clean_text = clean_text.strip()
            if not clean_text:
                continue
            
            # Generate TTS for this segment
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_files.append(tmp.name)
            
            tts = gTTS(text=clean_text, lang=lang, slow=False)
            tts.save(tmp.name)
            tmp.close()
            
            clip = AudioFileClip(tmp.name)
            audio_clips.append(clip)
        
        if audio_clips:
            final_audio = concatenate_audioclips(audio_clips)
            final_audio.write_audiofile(output_path, logger=None)
            final_audio.close()
        
        for clip in audio_clips:
            clip.close()
        
    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass
    
    return output_path


def add_voiceover_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """Combine a rendered video with a voiceover audio track."""
    
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    
    # Trim audio to match video duration
    if audio.duration > video.duration:
        audio = audio.subclipped(0, video.duration)
    
    video_with_audio = video.with_audio(audio)
    video_with_audio.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )
    
    video.close()
    audio.close()
    video_with_audio.close()
    
    return output_path


def generate_voiceover_for_script(script: dict, output_dir: str) -> str:
    """Generate voiceover for a complete script (short or long form)."""
    
    os.makedirs(output_dir, exist_ok=True)
    
    hook_type = script.get("hook_type", "unknown")
    fmt = script.get("format", "short_form")
    
    # Collect all segments
    if "chapters" in script:
        segments = []
        for chapter in script["chapters"]:
            segments.extend(chapter.get("segments", []))
    else:
        segments = script.get("segments", [])
    
    audio_path = os.path.join(output_dir, f"{hook_type}_{fmt}_voiceover.mp3")
    generate_voiceover_for_segments(segments, audio_path)
    
    return audio_path


if __name__ == "__main__":
    # Test with a simple script
    test_segments = [
        {"text": "This changes everything"},
        {"text": "The number one gadget of 2025"},
        {"text": "Check the link in description"},
    ]
    
    out = os.path.join(os.path.dirname(__file__), "output", "test_voiceover.mp3")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    generate_voiceover_for_segments(test_segments, out)
    print(f"✓ Test voiceover saved to {out}")
