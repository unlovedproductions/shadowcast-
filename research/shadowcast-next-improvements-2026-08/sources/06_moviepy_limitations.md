# 06 — MoviePy official limitations (primary library)

- **URL:** https://github.com/zulko/moviepy (README / docs via Context7 /zulko/moviepy)
- **Type:** primary
- **Credibility:** 5 | **Recency:** 5 | **Bias:** low (maintainer honesty)

## Verbatim quotes

> Users should be aware of MoviePy's limitations, such as being slower than ffmpeg for large-scale processing tasks.

> …memory usage tends to increase with the number of video clips processed simultaneously.

> …lowering optimization presets or increasing threads may not always improve rendering time if the bottleneck is MoviePy's frame computation rather than ffmpeg encoding.

## Relevance

**H5 opposition:** MoviePy is slower than raw ffmpeg — but for kinetic text overlays it remains the right abstraction. Performance pain ≠ Remotion rewrite justification unless scale triggers fire.
