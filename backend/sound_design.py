import os
import subprocess

import numpy as np
from scipy.io.wavfile import write as write_wav, read as read_wav
from scipy.signal import chirp

# Basic musical notes frequencies (Hz) for a C major scale, extended for multiple octaves
# Using A4 = 440 Hz as reference
NOTES = {
    'C3': 130.81,
    'C#3': 138.59,
    'D3': 146.83,
    'D#3': 155.56,
    'E3': 164.81,
    'F3': 174.61,
    'F#3': 184.99,
    'G3': 196.00,
    'G#3': 207.65,
    'A3': 220.00,
    'A#3': 233.08,
    'B3': 246.94,
    'C4': 261.63,
    'C#4': 277.18,
    'D4': 293.66,
    'D#4': 311.13,
    'E4': 329.63,
    'F4': 349.23,
    'F#4': 369.99,
    'G4': 392.00,
    'G#4': 415.30,
    'A4': 440.00,
    'A#4': 466.16,
    'B4': 493.88,
    'C5': 523.25,
    'C#5': 554.37,
    'D5': 587.33,
    'D#5': 622.25,
    'E5': 659.25,
    'F5': 698.46,
    'F#5': 739.99,
    'G5': 783.99,
    'G#5': 830.61,
    'A5': 880.00,
    'A#5': 932.33,
    'B5': 987.77,
}

# Common chord definitions (intervals from root)
CHORDS = {
    'major': [0, 4, 7],      # Root, Major Third, Perfect Fifth
    'minor': [0, 3, 7],      # Root, Minor Third, Perfect Fifth
    'major7': [0, 4, 7, 11], # Root, Major Third, Perfect Fifth, Major Seventh
    'minor7': [0, 3, 7, 10], # Root, Minor Third, Perfect Fifth, Minor Seventh
    'dim': [0, 3, 6],        # Root, Minor Third, Diminished Fifth
    'sus4': [0, 5, 7],       # Root, Perfect Fourth, Perfect Fifth
}

# Mapping mood to scale/key and common chord progressions
MOOD_SETTINGS = {
    "chill": {
        "scale": ['C3', 'D3', 'E3', 'G3', 'A3', 'C4', 'D4', 'E4', 'G4', 'A4'], # Pentatonic-like
        "progression_roots": ['C', 'G', 'A', 'F'], # I-V-vi-IV in C major
        "chord_types": ['major', 'minor7'],
        "base_octave": 3,
        "tempo_range": (60, 90),
        "note_duration_range": (0.5, 1.5),
        "amplitude_range": (0.1, 0.3),
    },
    "energetic": {
        "scale": ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5'], # C Major
        "progression_roots": ['C', 'F', 'G', 'C'], # I-IV-V-I in C major
        "chord_types": ['major', 'major7'],
        "base_octave": 4,
        "tempo_range": (120, 160),
        "note_duration_range": (0.2, 0.8),
        "amplitude_range": (0.4, 0.6),
    },
    "dramatic": {
        "scale": ['A3', 'B3', 'C4', 'D4', 'E4', 'F4', 'G4', 'A4'], # A Minor Harmonic
        "progression_roots": ['Am', 'G', 'C', 'F'], # vi-V-I-IV in C major (relative minor)
        "chord_types": ['minor', 'dim', 'major'],
        "base_octave": 3,
        "tempo_range": (70, 110),
        "note_duration_range": (0.8, 2.0),
        "amplitude_range": (0.3, 0.5),
    },
    "minimal": {
        "scale": ['C3', 'E3', 'G3', 'C4', 'E4', 'G4'], # C Major Triad
        "progression_roots": ['C', 'G'], # I-V
        "chord_types": ['major'],
        "base_octave": 3,
        "tempo_range": (40, 70),
        "note_duration_range": (1.0, 3.0),
        "amplitude_range": (0.05, 0.15),
    },
}



SAMPLE_RATE = 44100  # Hz

def generate_sine_wave(frequency, duration, amplitude=1.0):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * frequency * t)

def generate_chord(frequencies, duration, amplitude=1.0):
    chord_wave = np.zeros(int(SAMPLE_RATE * duration))
    for freq in frequencies:
        chord_wave += generate_sine_wave(freq, duration, amplitude)
    return chord_wave / len(frequencies) # Normalize amplitude

def get_note_frequency(note_name, octave_offset=0):
    """Returns the frequency of a given note name, with optional octave offset."""
    # Adjust octave based on offset
    base_note = note_name[:-1]
    base_octave = int(note_name[-1])
    adjusted_octave = base_octave + octave_offset
    adjusted_note_name = f"{base_note}{adjusted_octave}"

    if adjusted_note_name in NOTES:
        return NOTES[adjusted_note_name]
    else:
        # Fallback for notes outside defined range, try to transpose by octave
        # This is a simple transposition, might not be musically accurate for all cases
        print(f"Warning: Note {adjusted_note_name} not found. Attempting octave transposition.")
        # Find the closest octave for the base note
        for i in range(-2, 3): # Check a few octaves around
            transposed_note = f"{base_note}{base_octave + i}"
            if transposed_note in NOTES:
                return NOTES[transposed_note] * (2**(octave_offset))
        return 0 # Return 0 frequency if not found

def generate_background_music(duration_seconds, mood="chill", tempo=100):
    bed = _load_music_bed(mood, duration_seconds)
    if bed is not None:
        return bed
    return _synthesize_background_music(duration_seconds, mood, tempo)


def _music_beds_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "music")


def music_bed_moods() -> list[str]:
    """Return moods that have a drop-in bed under assets/music/."""
    base = _music_beds_dir()
    found: list[str] = []
    if not os.path.isdir(base):
        return found
    for name in sorted(os.listdir(base)):
        lower = name.lower()
        for ext in (".wav", ".mp3", ".flac"):
            if lower.endswith(ext):
                found.append(name[: -len(ext)])
                break
    return found


def music_beds_present() -> bool:
    return bool(music_bed_moods())


def _load_music_bed(mood: str, duration_seconds: float):
    """Prefer drop-in royalty-free beds: assets/music/{mood}.wav|.mp3."""
    base = _music_beds_dir()
    for ext in (".wav", ".mp3", ".flac"):
        path = os.path.join(base, f"{mood}{ext}")
        if not os.path.isfile(path):
            continue
        try:
            if path.endswith(".wav"):
                rate, data = read_wav(path)
                arr = data.astype(np.float32)
                if arr.ndim > 1:
                    arr = arr.mean(axis=1)
                max_abs = np.max(np.abs(arr)) or 1.0
                arr = arr / max_abs
                if rate != SAMPLE_RATE and len(arr) > 1:
                    # Naive resample for bed loops
                    x_old = np.linspace(0.0, 1.0, num=len(arr), endpoint=False)
                    n_new = int(len(arr) * SAMPLE_RATE / float(rate))
                    x_new = np.linspace(0.0, 1.0, num=max(1, n_new), endpoint=False)
                    arr = np.interp(x_new, x_old, arr).astype(np.float32)
            else:
                # ffmpeg decode to wav temp via scipy path not available — skip non-wav
                continue
            target = int(duration_seconds * SAMPLE_RATE)
            if len(arr) == 0:
                continue
            if len(arr) >= target:
                return arr[:target]
            reps = int(np.ceil(target / len(arr)))
            return np.tile(arr, reps)[:target]
        except Exception as exc:
            print(f"Warning: music bed load failed ({path}): {exc}")
    return None


def _synthesize_background_music(duration_seconds, mood="chill", tempo=100):
    settings = MOOD_SETTINGS.get(mood, MOOD_SETTINGS["chill"])
    
    all_music = np.array([])
    current_duration = 0

    # Calculate beat duration based on tempo (beats per minute)
    # Assuming 4 beats per measure, and each chord lasts for a measure or two
    beat_duration = 60 / tempo # Duration of a single beat in seconds

    while current_duration < duration_seconds:
        # Randomly pick a chord progression root from the mood settings
        root_note_str = np.random.choice(settings["progression_roots"])
        
        # Determine the actual root note frequency. For simplicity, we'll assume
        # root_note_str is like 'C', 'Am', etc. and map it to a base octave note.
        # This needs refinement for proper musical key handling.
        if root_note_str.endswith('m'): # Minor chord
            base_note_name = f"{root_note_str[:-1]}{settings['base_octave']}"
            chord_type = np.random.choice([ct for ct in settings["chord_types"] if ct.startswith('minor')])
        else: # Major chord
            base_note_name = f"{root_note_str}{settings['base_octave']}"
            chord_type = np.random.choice([ct for ct in settings["chord_types"] if ct.startswith('major')])

        root_freq = get_note_frequency(base_note_name)
        if root_freq == 0:
            continue # Skip if root frequency cannot be determined

        chord_intervals = CHORDS[chord_type]
        chord_frequencies = []
        for interval in chord_intervals:
            # Transpose the root frequency by the interval
            # A semitone is a multiplication by 2^(1/12)
            chord_frequencies.append(root_freq * (2**(interval/12)))
        
        # Random duration for the chord, within the mood's range, snapped to beat duration
        chord_duration = np.random.uniform(*settings["note_duration_range"])
        chord_duration = round(chord_duration / beat_duration) * beat_duration # Snap to beat
        if chord_duration == 0: chord_duration = beat_duration # Ensure minimum duration

        amplitude = np.random.uniform(*settings["amplitude_range"])
        chord_wave = generate_chord(chord_frequencies, chord_duration, amplitude)
        
        all_music = np.concatenate((all_music, chord_wave))
        current_duration += chord_duration

    # Trim or extend to exact duration_seconds
    target_samples = int(duration_seconds * SAMPLE_RATE)
    if len(all_music) > target_samples:
        all_music = all_music[:target_samples]
    elif len(all_music) < target_samples:
        # Loop the music if it's too short
        while len(all_music) < target_samples:
            all_music = np.concatenate((all_music, all_music))
        all_music = all_music[:target_samples]

    # Normalize to -1 to 1 range for WAV file output
    if len(all_music) > 0:
        max_val = np.max(np.abs(all_music))
        if max_val > 1e-6:
            all_music = all_music / max_val
    
    return all_music

def generate_sfx(effect_type, duration=0.5, amplitude=0.5):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    if effect_type == "whoosh":
        # A sweep from low to high frequency
        start_freq = np.random.uniform(200, 500)
        end_freq = np.random.uniform(1000, 2000)
        wave = chirp(t, f0=start_freq, f1=end_freq, t1=duration, method='linear')
        envelope = np.linspace(0, 1, len(t)) * np.linspace(1, 0, len(t)) # Fade in and out
        sfx = wave * envelope
    elif effect_type == "pop" or effect_type == "click":
        # A very short burst of high frequency noise or a quick decay
        sfx_duration = min(np.random.uniform(0.05, 0.15), duration) # Shorter duration, capped by main duration
        t_sfx = np.linspace(0, sfx_duration, int(SAMPLE_RATE * sfx_duration), endpoint=False)
        # A quick sine wave burst with a fast decay
        frequency = np.random.uniform(2000, 5000)
        sfx = np.sin(2 * np.pi * frequency * t_sfx) * np.exp(-50 * t_sfx) # Exponential decay
        sfx = np.pad(sfx, (0, len(t) - len(sfx)), mode='constant') # Pad with zeros
    elif effect_type == "ding":
        # A short, clear tone with a quick decay
        sfx_duration = min(np.random.uniform(0.3, 0.6), duration)
        t_sfx = np.linspace(0, sfx_duration, int(SAMPLE_RATE * sfx_duration), endpoint=False)
        frequency = np.random.uniform(800, 1200)
        sfx = np.sin(2 * np.pi * frequency * t_sfx) * np.exp(-8 * t_sfx) # Slower decay than pop
        sfx = np.pad(sfx, (0, len(t) - len(sfx)), mode='constant')
    elif effect_type == "swoosh":
        # Similar to whoosh but perhaps a bit faster and more pronounced
        start_freq = np.random.uniform(300, 700)
        end_freq = np.random.uniform(1500, 2500)
        wave = chirp(t, f0=start_freq, f1=end_freq, t1=duration, method='linear')
        envelope = np.sin(np.pi * t / duration) # Bell-shaped envelope
        sfx = wave * envelope
    elif effect_type == "bass_drop":
        # A low frequency sweep with a strong impact
        sfx_duration = min(np.random.uniform(0.8, 1.5), duration)
        t_sfx = np.linspace(0, sfx_duration, int(SAMPLE_RATE * sfx_duration), endpoint=False)
        start_freq = np.random.uniform(40, 80)
        end_freq = np.random.uniform(20, 30)
        wave = chirp(t_sfx, f0=start_freq, f1=end_freq, t1=sfx_duration, method='linear')
        envelope = np.exp(-2 * t_sfx) # Quick decay
        sfx = wave * envelope
        sfx = np.pad(sfx, (0, len(t) - len(sfx)), mode='constant')
    else:
        print(f"Unknown sound effect type: {effect_type}")
        return np.zeros(len(t))

    # Normalize and apply amplitude
    if len(sfx) > 0:
        sfx = sfx / np.max(np.abs(sfx)) * amplitude
    return sfx

def _cosine_duck_envelope(presence: np.ndarray, duck_factor: float, ramp_samples: int) -> np.ndarray:
    """Build a cosine-eased ducking envelope from a 0/1 presence mask."""
    duck_factor = float(np.clip(duck_factor, 0.05, 1.0))
    if ramp_samples <= 1:
        return np.where(presence > 0.1, duck_factor, 1.0)

    # Smooth binary presence, then map through a cosine ease between 1.0 and duck_factor.
    kernel = np.hanning(ramp_samples * 2 + 1)
    kernel = kernel / max(kernel.sum(), 1e-9)
    smoothed = np.convolve(presence.astype(np.float64), kernel, mode="same")
    smoothed = np.clip(smoothed, 0.0, 1.0)
    # Cosine ease: 1 at silence → duck_factor at full speech presence.
    ease = 0.5 - 0.5 * np.cos(np.pi * smoothed)
    return 1.0 - ease * (1.0 - duck_factor)


def apply_two_pass_loudnorm(
    wav_path: str,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
) -> str:
    """
    Two-pass ffmpeg loudnorm to YouTube-ish targets (−14 LUFS / −1 dBTP).

    Single-pass loudnorm can pump on speech; measure then apply linear=true.
    Falls back to the input file if ffmpeg/loudnorm is unavailable.
    """
    import json
    import re
    import tempfile

    measure_cmd = [
        "ffmpeg", "-y", "-i", wav_path,
        "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(measure_cmd, capture_output=True, check=False)
    except FileNotFoundError:
        print("Warning: ffmpeg not found; skipping loudnorm")
        return wav_path

    stderr = (proc.stderr or b"").decode(errors="replace")
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
    if not match:
        print("Warning: loudnorm measure parse failed; skipping loudnorm")
        return wav_path

    try:
        measured = json.loads(match.group(0))
    except json.JSONDecodeError:
        print("Warning: loudnorm JSON invalid; skipping loudnorm")
        return wav_path

    measured_i = measured.get("input_i")
    measured_lra = measured.get("input_lra")
    measured_tp = measured.get("input_tp")
    measured_thresh = measured.get("input_thresh")
    offset = measured.get("target_offset", 0)
    if None in (measured_i, measured_lra, measured_tp, measured_thresh):
        print("Warning: loudnorm missing measured fields; skipping")
        return wav_path

    fd, tmp_out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    filter_str = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={measured_i}:measured_LRA={measured_lra}"
        f":measured_TP={measured_tp}:measured_thresh={measured_thresh}"
        f":offset={offset}:linear=true:print_format=summary"
    )
    apply_cmd = [
        "ffmpeg", "-y", "-i", wav_path,
        "-af", filter_str,
        "-ar", str(SAMPLE_RATE),
        tmp_out,
    ]
    try:
        apply_proc = subprocess.run(apply_cmd, capture_output=True, check=False)
        if apply_proc.returncode != 0 or not os.path.exists(tmp_out) or os.path.getsize(tmp_out) <= 0:
            print("Warning: loudnorm apply failed; keeping pre-norm mix")
            try:
                os.unlink(tmp_out)
            except OSError:
                pass
            return wav_path
        os.replace(tmp_out, wav_path)
    except Exception as exc:
        print(f"Warning: loudnorm apply error ({exc}); keeping pre-norm mix")
        try:
            os.unlink(tmp_out)
        except OSError:
            pass
    return wav_path


def mix_audio(
    bg_music_array,
    sfx_list_with_timestamps,
    voiceover_array=None,
    output_path="output.wav",
    ducking_volume_factor=0.55,
    voiceover_start_seconds=0.0,
    apply_loudnorm: bool = True,
):
    # Determine the total duration of the mixed track
    voiceover_offset = max(0, int(float(voiceover_start_seconds or 0.0) * SAMPLE_RATE))
    total_duration_samples = len(bg_music_array)
    if voiceover_array is not None:
        total_duration_samples = max(
            total_duration_samples,
            voiceover_offset + len(voiceover_array),
        )

    mixed_audio = np.zeros(total_duration_samples)

    # Add background music
    mixed_audio[:len(bg_music_array)] += bg_music_array

    # Apply ducking if voiceover is present
    if voiceover_array is not None:
        vo_end = min(voiceover_offset + len(voiceover_array), total_duration_samples)
        vo_len = max(0, vo_end - voiceover_offset)
        # Create a ducking envelope. When voiceover is playing, reduce background music volume.
        voiceover_presence = np.zeros(total_duration_samples)
        if vo_len > 0:
            voiceover_presence[voiceover_offset:vo_end] = np.where(
                np.abs(voiceover_array[:vo_len]) > 0.01, 1, 0
            )

        # ~400ms cosine-ease ramps avoid clicky hard ducks (research default ~0.55 depth).
        ramp_samples = max(1, SAMPLE_RATE * 2 // 5)
        ducking_envelope = _cosine_duck_envelope(
            voiceover_presence, float(ducking_volume_factor), ramp_samples
        )

        # Apply ducking to background music
        mixed_audio[:len(bg_music_array)] = mixed_audio[:len(bg_music_array)] * ducking_envelope[:len(bg_music_array)]

        # Add voiceover after intro offset so narration aligns with on-screen content
        if vo_len > 0:
            mixed_audio[voiceover_offset:vo_end] += voiceover_array[:vo_len]

    # Add sound effects
    for sfx_data, start_time in sfx_list_with_timestamps:
        start_sample = int(start_time * SAMPLE_RATE)
        end_sample = start_sample + len(sfx_data)

        if end_sample > total_duration_samples:
            # Trim SFX if it goes beyond total duration
            sfx_data = sfx_data[:total_duration_samples - start_sample]
            end_sample = total_duration_samples
        
        if start_sample < total_duration_samples: # Ensure SFX starts within bounds
            mixed_audio[start_sample:end_sample] += sfx_data

    # Peak guard before loudnorm (loudnorm handles integrated LUFS).
    max_val = np.max(np.abs(mixed_audio))
    if max_val > 1e-6:
        mixed_audio = mixed_audio / max_val * 0.9  # Scale to avoid clipping
    audio_int = (mixed_audio * 32767).astype(np.int16)
    write_wav(output_path, SAMPLE_RATE, audio_int)
    if apply_loudnorm:
        apply_two_pass_loudnorm(output_path)

def add_audio_to_video(video_path, audio_path, output_path):
    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stdout = (e.stdout or b"").decode(errors="replace")
        stderr = (e.stderr or b"").decode(errors="replace")
        raise RuntimeError(
            f"ffmpeg mux failed for {output_path}: {stderr or stdout or e}"
        ) from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "ffmpeg not found. Please ensure ffmpeg is installed and in your PATH."
        ) from e
    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        raise RuntimeError(f"ffmpeg mux produced missing/empty output: {output_path}")
    print(f"Successfully added audio to video: {output_path}")

if __name__ == "__main__":
    print("Generating 30-second chill background music...")
    chill_music = generate_background_music(duration_seconds=30, mood="chill", tempo=80)
    write_wav("chill_music.wav", SAMPLE_RATE, (chill_music * 32767).astype(np.int16))
    print("Chill music generated: chill_music.wav")

    print("Generating sound effects...")
    whoosh_sfx = generate_sfx("whoosh", duration=0.7, amplitude=0.6)
    pop_sfx = generate_sfx("pop", duration=0.1, amplitude=0.8)
    ding_sfx = generate_sfx("ding", duration=0.5, amplitude=0.7)
    swoosh_sfx = generate_sfx("swoosh", duration=0.6, amplitude=0.5)
    bass_drop_sfx = generate_sfx("bass_drop", duration=1.0, amplitude=0.9)

    sfx_list = [
        (whoosh_sfx, 2.5),  # Whoosh at 2.5 seconds
        (pop_sfx, 5.0),     # Pop at 5.0 seconds
        (ding_sfx, 8.0),    # Ding at 8.0 seconds
        (swoosh_sfx, 12.0), # Swoosh at 12.0 seconds
        (bass_drop_sfx, 20.0) # Bass drop at 20.0 seconds
    ]

    # Generate a dummy voiceover for testing ducking
    print("Generating dummy voiceover...")
    voiceover_duration = 10 # seconds
    voiceover_freq = 200 # Hz
    voiceover_amplitude = 0.7
    voiceover_array = generate_sine_wave(voiceover_freq, voiceover_duration, voiceover_amplitude)
    # Make voiceover start at 10 seconds and last for 10 seconds
    full_voiceover_array = np.zeros(int(30 * SAMPLE_RATE)) # Total 30 seconds
    full_voiceover_array[int(10 * SAMPLE_RATE) : int(20 * SAMPLE_RATE)] = voiceover_array

    print("Mixing audio with sound effects and voiceover...")
    mix_audio(chill_music, sfx_list, voiceover_array=full_voiceover_array, output_path="mixed_audio_test.wav")
    print("Mixed audio generated: mixed_audio_test.wav")

    # For add_audio_to_video, we need a dummy video file. This is just a placeholder.
    # In a real scenario, you would have an actual video file.
    print("To test add_audio_to_video, please provide a dummy video file (e.g., dummy.mp4).")
    print("Skipping video integration for automated test.")

    # Example of how to use add_audio_to_video if a video file was present:
    # dummy_video_path = "dummy.mp4"
    # final_output_video_path = "final_video_with_audio.mp4"
    # add_audio_to_video(dummy_video_path, "mixed_audio_test.wav", final_output_video_path)
    # print(f"Final video with audio generated: {final_output_video_path}")
