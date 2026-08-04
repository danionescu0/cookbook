# Todo

Deferred work — not being actively worked on, kept here so a future look doesn't have to redo the
same investigation from scratch.

## Instagram Reel imports: play button baked into the thumbnail image

**Problem**: recipes imported from Instagram Reels/video posts get a photo with a large play-button
icon in the middle. Verified live against real imported posts (`worker/app/instagram_client.py`
reads `meta[property="og:image"]`): for video posts, Instagram's server-generated thumbnail has the
play icon baked directly into the JPEG pixels — it's not a CSS/DOM overlay we could hide, and the
exact same asset (same CDN file ID) is used both as `og:image` and as the in-page poster before
playback, so there's no alternate "clean" URL sitting anywhere in the page to grab instead. Static
photo posts are unaffected — this only happens on video/Reel posts.

**Options investigated, and why each was set aside:**

1. **Read a different image source from the page** (e.g. the `<video poster>` attribute instead of
   `og:image`). Ruled out — confirmed live that Instagram serves the identical badge-baked asset
   everywhere on the page, so there's no clean alternative to switch to.
2. **Extract a real frame from the actual video.** The theoretically "correct" fix, but two blockers
   found by testing live:
   - Capturing a frame from the browser-decoded `<video>` element (canvas snapshot) doesn't work:
     Instagram's own front-end aborts programmatic `play()` calls in this headless session
     (`AbortError: The play() request was interrupted by a call to pause()`), so the video never
     reaches a decoded state to capture from.
   - The alternative — reconstructing the video from the fragmented-MP4 segments Instagram streams
     over `fetch()`, then extracting a frame with `ffmpeg` — is possible in principle but a real R&D
     effort: it depends on undocumented internals (opaque segment paths, and an embedded
     `video_url` JSON blob that was observed to appear only transiently/inconsistently), needs a new
     `ffmpeg`/video-decoding dependency in the worker image, and would silently break any time
     Instagram changes its streaming format.
3. **Classical image post-processing** (detect the button — fixed position or shape/circle
   detection — and blur or `cv2.inpaint` it out). Technically simple but a poor result: in the one
   live example inspected, the button sits almost exactly over the photo's subject (a hand/mouth
   mid-bite), which is typical since Instagram centers the badge and food/cooking Reels tend to
   frame the food or action centrally too. Classical inpainting just smears nearby pixels — on a
   detailed/textured region that reads as an obvious smudge, not a fix. Would also add a new heavy
   dependency (`opencv-python-headless`) just for this.
4. **Third-party AI object-removal service** (e.g. Clipdrop Cleanup, Stability AI's Erase endpoint,
   OpenAI `gpt-image-1` edit, Google Vertex AI Imagen edit). Best quality/effort tradeoff of
   everything considered — a generative model can plausibly reconstruct occluded detail instead of
   just smearing pixels, and only needs a rough/generous centered mask (no precise shape detection
   required, unlike option 3). Estimated cost ~$0.03–0.10 per image, which at this app's current
   volume (22 imports total, 30-per-user lifetime cap) works out to roughly **$3–15/year** — not the
   blocker. The real cost is standing up a brand-new vendor account/API key. Note: the project's
   existing Anthropic/Claude integration (`worker/app/claude_client.py`, used for recipe parsing)
   **cannot** be reused for this — Claude's API is vision-*in*/text-*out* only, with no
   image-generation or image-editing capability at any tier, so this would be a genuinely new
   vendor, not an extension of what's already integrated.

**Decision**: skipped for now — not worth the implementation/maintenance effort at current scale.
If revisited, start with option 4 (Clipdrop Cleanup or Stability's Erase endpoint), gated to posts
where `og:video` is present, using a fixed generous centered mask rather than trying to precisely
locate the icon.
