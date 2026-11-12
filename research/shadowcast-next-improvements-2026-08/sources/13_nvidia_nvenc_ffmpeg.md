# 13 — NVIDIA FFmpeg NVENC (primary)

- **URL:** https://docs.nvidia.com/video-technologies/video-codec-sdk/13.1/ffmpeg-with-nvidia-gpu/index.html
- **Type:** primary
- **Credibility:** 5 | **Recency:** 5 | **Bias:** low (vendor hardware docs)

## Verbatim quotes

> By leveraging NVENC and NVDEC with FFmpeg, you can significantly accelerate video decoding, encoding, and end-to-end transcoding workflows.

> Doing this ensures that the memory transfers (system memory to video memory and vice versa) are eliminated, and that transcoding is performed with the highest possible performance on the GPU hardware.

## Relevance

**H5/H8:** Speed gains come from ffmpeg encode path (NVENC), not Remotion rewrite. Keep MoviePy for composition; accelerate mux/encode.
