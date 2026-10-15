# Optional HD textures: development checkpoint

The PC port's primary goal remains accurate native play: graphics, audio,
controls, saving, widescreen and stability. Texture replacement is an optional
presentation layer. A complete remastered art pack is a separate project.

This checkpoint includes content-based replacement matching, aligned terrain
atlas windows, high-resolution sampling, capture/import tools, background
loading, settings controls and a Real-ESRGAN batch workflow. Extracted game
textures and local artwork samples are excluded from Git.

Validation at the checkpoint:

- `ac4` and `gsreplay` build successfully.
- Texture-loader tests pass with Python plus Pillow: identity including alpha,
  asynchronous loading, stable dumps, pack priority and malformed-file fallback.
- Texture-pool stress tests and GS sampling checks pass.
- An earlier synchronous version rendered a 2048x2048 F-4E replacement in the
  captured aircraft-selection scene. Original material alpha was preserved.
- A 512x512 terrain replacement matched a captured 64x64 tile, but the final
  flight screenshot had no visible pixel difference. Visible terrain improvement
  has therefore not been established by that test.

Remaining validation: exercise the current asynchronous version in live play,
test complete terrain mip families and seams, and verify the expanded mission
map. The Real-ESRGAN workflow needs an installed external upscaler and visual
review of its results. Generated artwork is a local experiment; its changed
colors and UV alignment need review before adoption. Model geometry and the
original low-detail aircraft meshes are unaffected by texture replacement.
