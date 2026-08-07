# Stock B-roll (optional)

Drop short free / licensed clips here for long-form chapter pads.

Filenames (first match wins per section):

- `pros.mp4`, `cons.mp4`, `verdict.mp4`, `comparison.mp4`
- `pad.mp4` or `default.mp4` — generic fallback

Formats: `.mp4`, `.mov`, `.webm`, `.mkv`

Behavior:

- Auto-used when any clip is present
- Force on: `SHADOWCAST_BROLL=1`
- Force off: `SHADOWCAST_BROLL=0`

MP4 files are **gitignored** (large binaries). Re-download locally after clone.

## Current free pack (Mixkit License)

Source: [Mixkit Free Stock Video](https://mixkit.co/free-stock-video/)  
License: [Mixkit License](https://mixkit.co/license/#videoFree) — free for commercial use; attribution not required.

Clips trimmed to ~10s, audio stripped, H.264.

| File | Mixkit ID | CDN (source) |
|------|----------:|--------------|
| pad.mp4 | 46635 | https://assets.mixkit.co/videos/46635/46635-720.mp4 |
| default.mp4 | 99786 | https://assets.mixkit.co/videos/99786/99786-1080.mp4 |
| pros.mp4 | 4809 | https://assets.mixkit.co/videos/4809/4809-720.mp4 |
| cons.mp4 | 31771 | https://assets.mixkit.co/videos/31771/31771-720.mp4 |
| verdict.mp4 | 43527 | https://assets.mixkit.co/videos/43527/43527-1080.mp4 |
| comparison.mp4 | 9757 | https://assets.mixkit.co/videos/9757/9757-720.mp4 |

Trim example:

```bash
ffmpeg -y -i SOURCE.mp4 -t 10 -an -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p backend/assets/broll/{name}.mp4
```

Swap for niche-specific stock when you have it; keep the same filenames.
