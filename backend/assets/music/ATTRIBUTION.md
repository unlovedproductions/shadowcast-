# Music beds

Drop royalty-free loops here as `{mood}.wav` (also `.mp3` / `.flac`).

Moods: `chill`, `energetic`, `dramatic`, `minimal`.

WAV files are **gitignored** (large binaries). Re-download locally after clone.

## Current free pack (Mixkit License)

Source: [Mixkit Free Stock Music](https://mixkit.co/free-stock-music/)  
License: [Mixkit License](https://mixkit.co/license/#musicFree) — free for commercial use; attribution not required.

| Mood | Track | Mixkit ID | CDN |
|------|-------|----------:|-----|
| chill | Valley Sunset | 138 | https://assets.mixkit.co/music/138/138.mp3 |
| energetic | Sports Highlights | 80 | https://assets.mixkit.co/music/80/80.mp3 |
| dramatic | Silent Descent | 601 | https://assets.mixkit.co/music/601/601.mp3 |
| minimal | Relax Beat | 441 | https://assets.mixkit.co/music/441/441.mp3 |

Convert after download (mono 44.1 kHz WAV):

```bash
ffmpeg -y -i SOURCE.mp3 -ac 1 -ar 44100 -c:a pcm_s16le backend/assets/music/{mood}.wav
```

Replace with other Mixkit / CC0 / licensed beds anytime; filenames must stay `{mood}.wav`.
