# Shared Last Light assets

Both Godot presentations use the same PartyDeck artwork, fonts, and cues. The pack contains **47 runtime resources**, three font notice/credit files, and four editable card sources. Runtime asset and notice inputs occupy **1,047,559 bytes** before Godot import/export. The complete mapped source set is 1,054,942 bytes; its 47 import settings files add 43,569 bytes.

[manifest.json](manifest.json) records every asset's exact size and SHA-256, all contributing source paths and hashes, transformations, upstream font URLs, and import settings. It also pins the preparation script and generated `.import` files. No external artwork, texture photograph, icon library, model, or sound sample was added.

## Resource paths

| Resource | Contents | Source bytes |
| --- | --- | ---: |
| `res://assets/fonts/*.ttf` | Four unmodified Fraunces/Manrope faces | 538,500 |
| `res://assets/vectors/*.svg` | 24 byte-exact original PartyDeck SVGs | 15,542 |
| `res://assets/textures/cards/*.png` | Five RGBA card textures, 512 × 768 | 143,594 |
| `res://assets/textures/ranks/*.png` | Eight RGBA rank cutouts, 256 × 256 | 46,774 |
| `res://assets/audio/*.wav` | Six unmodified mono PCM16 cues | 285,150 |
| `res://assets/licenses/*.txt` | Two complete OFLs and a readable font-credit aggregate | 17,999 |

The palette is ink `#191526`, paper `#F4F0E8`, citron `#D6EF82`, and copper `#F16B48`. The source colors are unchanged from the existing PartyDeck design.

### Cards and rank symbols

The card textures are `face_crown.png`, `face_moon.png`, `face_star.png`, `face_wild.png`, and `back.png`. Every card uses the same 2:3 aspect ratio and transparent rounded corners. Faces combine the existing rank paths and card-border geometry on clean paper. The back is a direct rasterization of the original card-back SVG. Lighting, shadows, and selection highlights belong to each presentation.

Keep visible rank words and accessibility labels in the presentation's localized text. The textures and SVGs are wordless. Use a texture rectangle with the correct aspect ratio in 2D, and a matching card mesh with alpha-aware material or rounded geometry in 3D.

Rank textures use `crown.png`, `moon.png`, `star.png`, and `wild.png` for ink artwork on transparency. The corresponding `crown_mask.png`, `moon_mask.png`, `star_mask.png`, and `wild_mask.png` contain white artwork with the same alpha. Use the white masks when multiplying by a tint color; multiplying the ink variants cannot turn them into bright symbols.

All 24 original SVGs remain available, including `rank_*`, `card_back`, `partydeck_mark`, and the 18 `icon_*` symbols. Godot rasterizes them at **4× their declared source dimensions**: 24-unit icons become 96-pixel textures, 64-unit ranks become 256-pixel textures, and so on. Set display rectangles explicitly so imported pixel dimensions do not determine UI layout size.

PNG textures use lossless import with mipmaps and alpha-border correction. Automatic conversion to 3D VRAM compression is disabled so both presentations retain the same artwork; mipmaps are explicitly enabled. SVG textures use lossless import without mipmaps. Filtering is a CanvasItem/material setting in Godot 4, so each presentation chooses suitable linear filtering and mipmap sampling for its display size.

The 37 shared textures would occupy about **17.21 MiB as RGBA8 with the configured PNG mipmaps if all were resident simultaneously**. This is a texture-data estimate, not a measured GPU-memory profile; font caches, render targets, and other scene allocations are separate.

### Fonts

Use `fraunces_semibold.ttf` for short display headings. It is the original Fraunces 72pt SemiBold face, weight 600. Use `manrope_regular.ttf`, `manrope_medium.ttf`, and `manrope_semibold.ttf` for readable controls and body text at their actual weights 400, 500, and 600.

Godot imports these TTFs as `FontFile` resources. Existing dynamic-font defaults are retained, including grayscale antialiasing and ordinary rasterized glyphs. No font is subsetted, converted to an image atlas, or changed to MSDF. The import check verifies the retained TTF bytes, font metrics, and the English/accented-Latin glyph probe. It does not claim complete translated-script coverage.

### Audio

All six WAVs remain 44,100 Hz, mono, signed 16-bit little-endian PCM. The import settings explicitly select **PCM**, disable looping, and retain the original headroom, duration, and samples by disabling normalization, trimming, sample-rate changes, and 8-bit conversion. Godot 4.7.2 otherwise defaults WAV import to lossy Quite OK Audio compression.

| Cue | File | Duration |
| --- | --- | ---: |
| `CLICK` | `ui_tap.wav` | 70 ms |
| `CARD_PLAY` | `card_place.wav` | 240 ms |
| `CHALLENGE` | `challenge.wav` | 480 ms |
| `ROUND_END` | `safe.wav` | 640 ms |
| `LIGHT_OUT` | `light_out.wav` | 520 ms |
| `WIN` | `victory.wav` | 1,280 ms |

These are imported as `AudioStreamWAV` resources. Respect the shared sound setting and background lifecycle, and avoid replaying cues when an existing snapshot is rendered again. The sound named `safe` belongs to the neutral round result; use `light_out` when a light is eliminated.

## Licenses and packaging

The upstream evidence is preserved in [PartyDeck's font manifest](../../../assets/font_sources.json), [audio manifest](../../../assets/audio_manifest.json), and [original asset inventory](../../../docs/ASSETS.md). Geometry is derived from [generate_vectors.py](../../../assets/tools/generate_vectors.py); cue waveforms come from [generate_audio.py](../../../assets/tools/generate_audio.py).

Ship all three files in `assets/licenses/`: `fraunces_ofl.txt`, `manrope_ofl.txt`, and `font_notices.txt`. The first two match the upstream license bytes exactly; the readable aggregate includes both complete texts and font credits. Add **`assets/licenses/*.txt`** to the Godot export inclusion filter and independently inspect the resulting PCK. These raw text files need explicit packaging coverage.

This directory's credits cover the shared fonts and artwork. Godot's own `LICENSE.txt`, `COPYRIGHT.txt`, and any additional native/exported-library obligations are recorded by the engine packaging and release owners. The font aggregate is not a substitute for engine notices.

`sources/` contains editable, wordless card-face SVG compositions. `proofs/` contains review evidence. Both directories carry `.gdignore` and must be absent from runtime packs. The source manifest and this README are audit documentation; export tooling controls whether any audit metadata is included.

## Regeneration and checks

The preparation tool writes only this asset directory. It uses the existing development packages from [requirements.txt](../../../assets/tools/requirements.txt) and reads the audited local files. It performs no downloads and does not change the shipping Compose assets or credits.

```sh
# Generate the pack, preserve its import settings, and verify actual Godot imports.
/tmp/partydeck-asset-tools/bin/python godot/tools/prepare_assets.py \
  --godot /opt/partydeck-godot/godot

# Verify hashes without regenerating resource files.
/tmp/partydeck-asset-tools/bin/python godot/tools/prepare_assets.py --check

# Independently reimport/check the committed settings in an isolated temp project.
/tmp/partydeck-asset-tools/bin/python godot/tools/prepare_assets.py \
  --check --godot /opt/partydeck-godot/godot
```

`--godot` takes an existing verified Godot **4.7.2** executable. It creates an isolated Compatibility-renderer project, imports all resources, applies the documented settings, imports again, and loads each runtime resource through `ResourceLoader`. It does not modify the shared project configuration or download an engine. `--no-proof` leaves the existing card contact sheet untouched while preparing other files.

Actual Godot verification is recorded in [proofs/import_verification.json](proofs/import_verification.json). The run confirms 47 loaded resources and 47 import settings files, unmodified font and PCM data, font/glyph metrics, texture dimensions/mipmaps/corners, and 24 SVG raster comparisons against CairoSVG. The largest alpha difference is 1.408% of the reference silhouette coverage, within the checked 8% cross-rasterizer tolerance, with bounds agreeing within two pixels.

[proofs/cards.png](proofs/cards.png) shows the original card textures at 248, 88, and 136 pixels wide; independent design review found no blocking small-card defect. [proofs/godot_rank_imports.png](proofs/godot_rank_imports.png) shows the actual Godot-imported rank SVGs. These are asset proofs. Actual 2D/3D filtering, lighting, labels, device playback, and final PCK inclusion remain presentation/release checks.

## Authoritative Godot 4.7 sources

The versioned documentation website returned HTTP 403 in this environment, so API and format decisions were checked against the official documentation repository and the exact engine release sources:

- [Image formats, SVG rasterization, mipmaps, compression, and filtering](https://github.com/godotengine/godot-docs/blob/4.7/tutorials/assets_pipeline/importing_images.rst)
- [Audio sample import](https://github.com/godotengine/godot-docs/blob/4.7/tutorials/assets_pipeline/importing_audio_samples.rst)
- [TTF/OTF support and rasterized/MSDF font tradeoffs](https://github.com/godotengine/godot-docs/blob/4.7/tutorials/ui/gui_using_fonts.rst)
- [ResourceImporterTexture 4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ResourceImporterTexture.xml)
- [ResourceImporterDynamicFont 4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ResourceImporterDynamicFont.xml)
- [ResourceImporterWAV 4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ResourceImporterWAV.xml)
- [HashingContext 4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/HashingContext.xml)
