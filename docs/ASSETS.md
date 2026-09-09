# PartyDeck assets

PartyDeck uses original vector artwork and sound synthesis, with unmodified, licensed Fraunces and Manrope fonts. All shipping assets are bundled for offline use. No external game artwork, icon font, texture, music recording, or audio sample is included.

The design uses ink `#191526`, paper `#F4F0E8`, citron `#D6EF82`, and restrained copper `#F16B48`. The interface owns semantic colors and contrast; decorative source art uses this fixed palette. Research and authoritative sources are recorded in [research/assets.md](research/assets.md).

## Shipping inventory

Shared resources live in `composeApp/src/commonMain/composeResources`. The generated resource package is `dev.partydeck.resources`. The fonts, vectors, cues, and license bundle below occupy **1,441,997 bytes before platform packaging**. This excludes screen strings and native launcher exports.

| Resources | Content | Size |
| --- | --- | ---: |
| `font/fraunces_semibold.ttf` | Upstream Fraunces 72pt SemiBold, weight 600 | 105,824 B |
| `font/manrope_regular.ttf` | Upstream Manrope Regular, weight 400 | 143,132 B |
| `font/manrope_medium.ttf` | Upstream Manrope Medium, weight 500 | 144,568 B |
| `font/manrope_semibold.ttf` | Upstream Manrope SemiBold, weight 600 | 144,976 B |
| `drawable/*.xml` | 24 original Android XML vectors | 27,361 B |
| `files/audio/*.wav` | Six original mono PCM cues | 285,150 B |
| `files/licenses/` including `runtime/` | 64 complete notices plus one readable aggregate | 590,986 B |

Use Fraunces for short display headings and large rank lettering. Use Manrope for instructions, actions, small labels, room information, and numeric text. Fonts are loaded through Compose's `Font(Res.font.name, FontWeight.… )`; the UI must request the corresponding weight explicitly. These are static font files, not generated or subsetted derivatives.

The exact pinned upstream URLs, SHA-256 digests, sizes, and licenses are in [font_sources.json](../assets/font_sources.json). All four files were independently downloaded and matched by the release reviewer.

### Vectors

The drawing recipes in [generate_vectors.py](../assets/tools/generate_vectors.py) are the canonical originals. [assets/vectors](../assets/vectors) contains editable SVG interchange exports; shared `drawable` files contain the equivalent Android XML vectors. Shared resources have no Android resource/theme references and use no external images, filters, or SVG-only runtime features.

| Resource | Canvas | Intended use |
| --- | --- | --- |
| `rank_crown`, `rank_moon`, `rank_star`, `rank_wild` | 64 × 64 | Tintable silhouettes for Last Light cards and rank labels |
| `card_back` | 160 × 240 | Original, rotationally symmetrical 2:3 deck back |
| `partydeck_mark` | 96 × 96 | Two paper cards and the four-point club light; authored color |
| `icon_*` | 24 × 24 | 18 tintable interface symbols, rounded 1.75-unit strokes |

The interface icon names are `arrow_back`, `arrow_forward`, `check`, `close`, `copy`, `exit`, `haptics`, `info`, `lock`, `motion`, `nearby`, `people`, `plus`, `qr_scan`, `settings`, `share`, `sound`, and `sound_off`, each prefixed with `icon_`.

Load vectors with `painterResource(Res.drawable.name)`. Rank and interface vectors use ink as their source color and should receive the appropriate UI tint. Do not tint `card_back` or `partydeck_mark`. Rank labels remain visible text: small internal details in Moon/Wild may merge at 20–24 dp, but their silhouettes remain distinct. Card-back hairlines are decorative and must not carry state. Use null content descriptions for decorative repeats; describe meaningful controls or card state at the enclosing semantic node.

The [asset proof sheet](../assets/previews/asset_sheet.png) shows actual bundled typography, monochrome ranks, card-back art, and all interface symbols. It is an asset review artifact, not an application screenshot or a substitute for screen testing.

### Launcher

[assets/launcher](../assets/launcher) contains the final original launcher:

- `partydeck_foreground.xml`, `partydeck_background.xml`, `partydeck_monochrome.xml`: 108 dp Android layers. The Android owner copies these into native resources and owns adaptive wrappers/manifest entries.
- Matching `.svg` layer exports: editable vector input for native icon tooling, including Apple's Icon Composer.
- `partydeck_1024.png`: opaque RGB, 1024 × 1024, embedded sRGB profile, full-bleed square background. No system corner mask is baked into it. The iOS owner integrates the asset catalog.
- `partydeck_launcher.svg` / `.xml`: composed reference/export source.

The foreground and monochrome alpha bounds fit the central Android 66 dp safe square. Measured bounds in the 108 dp canvas are `(30.0, 23.2)–(80.9, 83.5)` and `(28.4, 24.1)–(79.9, 85.1)`. The [mask proof](../assets/previews/launcher_masks.png) includes square, rounded, circular, and monochrome variants plus 32/48/64 px views. These mask shapes are illustrative checks; device launchers still require their own visual verification.

### Sound

[generate_audio.py](../assets/tools/generate_audio.py) creates the complete original cue set from oscillators and filtered, seeded noise. Smooth envelopes and quiet tails avoid hard waveform discontinuities. There is no downloaded or recorded audio. No looping music is included.

Every file is **44,100 Hz, mono, signed 16-bit little-endian linear PCM WAVE**. Exact paths and durations form the native playback contract:

| Feedback cue | `Res.readBytes` path | Duration | Peak |
| --- | --- | ---: | ---: |
| `CLICK` | `files/audio/ui_tap.wav` | 70 ms | −16 dBFS |
| `CARD_PLAY` | `files/audio/card_place.wav` | 240 ms | −13 dBFS |
| `CHALLENGE` | `files/audio/challenge.wav` | 480 ms | −10.5 dBFS |
| `ROUND_END` | `files/audio/safe.wav` | 640 ms | −13 dBFS |
| `LIGHT_OUT` | `files/audio/light_out.wav` | 520 ms | −13 dBFS |
| `WIN` | `files/audio/victory.wav` | 1,280 ms | −10.5 dBFS |

[audio_manifest.json](../assets/audio_manifest.json) records byte counts, sample frames, SHA-256, DC offset, RMS, peak, and descriptive intent. The full bundle is 285,150 bytes. No sample clips, all endpoints are zero, and each decoded cue is far below SoundPool's documented 1 MB limit. Asset checks do not establish physical playback latency or appropriate speaker loudness.

Android/iOS owners implement native preload, audio focus/session handling, sound preferences, and disposal. Every outcome also appears visually. Do not play cues while backgrounded, queue stale cues during reconnection, or use sound as the only indication of a turn or result. The cue named `safe` is for the safe/neutral round result; an eliminated light uses `LIGHT_OUT`.

## Licenses and attribution

The source [assets/licenses](../assets/licenses) files and their copies in `files/licenses` preserve the inspected upstream text without modification. The app reads **`files/licenses/third_party_notices.txt`** for a single offline Credits & licenses view.

- **Fraunces:** copyright The Fraunces Project Authors; design credited by Google Fonts to Undercase Type, Phaedra Charles, and Flavia Zimbardi. SIL Open Font License 1.1.
- **Manrope:** copyright The Manrope Project Authors; design credited to Mikhail Sharanda. SIL Open Font License 1.1.
- **QRose 1.2.0:** copyright 2023 Alexander Zhirkevich. Complete MIT license retained, along with the upstream MIT notices for Rafael Lins's qrcode-kotlin and Kazuhiko Arase's qrcode-generator identified by QRose's source headers.
- **AndroidX / CameraX:** Apache License 2.0; text matched against the actual CameraX 1.6.2 `camera-core` AAR's license entry.
- **ZXing 3.5.4:** tagged upstream `LICENSE` and `NOTICE` retained in full, including supplemental notices.
- **LibYuv:** the CameraX 1.6.2 published POM explicitly discloses BSD 3-Clause code. Upstream copyright/license and additional patent grant are retained.

Both font licenses allow software bundling with their copyright and license notices. Neither inspected font license declares a Reserved Font Name. Keep font files under OFL; attribution does not imply author endorsement. First-party PartyDeck geometry and synthesis contain no third-party asset material.

[software_notice_sources.json](../assets/software_notice_sources.json) records the original software notice sources and digests. The required [runtime manifest](../assets/licenses/runtime/software_notice_sources.json) adds 56 notice entries covering the inspected Kotlin, Compose, AndroidX, QR, cryptography, and Skiko/Skia sources. The source revisions, resolved artifact inventory, and license-specific evidence are documented in [dependency-licenses.md](dependency-licenses.md). Swift Crypto and Swift ASN.1 source candidates retain their audit qualifications; the actual native lock and linked iOS bundle still require comparison before claiming complete native coverage.

The offline aggregate is **258,084 bytes**, with **64 notice entries in 56 distinct text groups**. Identical text is printed once with every component/title attribution retained, and every individual resource preserves its source bytes. The required Independent JPEG Group, FreeType, and Adobe DNG acknowledgments appear at the beginning. Runtime notice filenames retain their original extensions or lack of an extension. Audit inventories, JSON manifests, and reporting helpers are not shipped as app resources.

## Localization and accessibility

All artwork is wordless. Screen text belongs in `composeResources/values` string files owned by the corresponding UI stream; localized rank names are separate from the symbols. The current product is English. Font inspection found 637 Unicode mappings in Fraunces and 678 in each Manrope file. Both pass the tested English/accented-Latin sample. Manrope also passed tested Greek/Cyrillic samples; Fraunces did not. Neither contains the tested Arabic or Japanese glyphs. These samples do not establish full script, shaping, or translation support.

Future translations need reviewed strings, plural rules, layout-direction checks, and script-appropriate fonts. Do not advertise a language merely because some of its characters are in a font. Keep invite tokens separate from surrounding prose, provide complete labels for icons and ranks, and keep card selection and remaining lights distinguishable without color or sound.

## Regeneration and verification

Application builds use checked-in resources and need no asset-generation dependencies or downloads. Geometry, audio, and notices can be regenerated with Python's standard library:

```sh
python3 assets/tools/generate_vectors.py
python3 assets/tools/generate_audio.py
python3 assets/tools/bundle_notices.py
```

Only if restoring a missing/corrupted font, run `python3 assets/tools/fetch_fonts.py`; it refuses content that differs from the pinned digest. Review tooling uses the verified development-only versions in [requirements.txt](../assets/tools/requirements.txt):

```sh
python3 -m venv /tmp/partydeck-asset-tools
/tmp/partydeck-asset-tools/bin/python -m pip install -r assets/tools/requirements.txt
/tmp/partydeck-asset-tools/bin/python assets/tools/render_assets.py
/tmp/partydeck-asset-tools/bin/python assets/tools/verify_assets.py
```

CairoSVG needs the platform Cairo library. No Python package is bundled into PartyDeck. Rendering previews and the native PNG are separate from the standard-library vector/audio exports.

Verification completed on Linux on 2026-09-09:

- All 68 pinned source font/notice files match their recorded SHA-256; all 64 notices appear unabridged in the app aggregate with their component/title attributions. Its SHA-256 is `1cbfc067e97159c272953f363f5b0729faa656a55b1bf76c0c9200c6dd90a455`.
- The 56 runtime notice resources match the manifest exactly, with no audit inventory or helper files included. Required native acknowledgments appear within the first 512 bytes of the aggregate.
- Four TTFs parse; expected weights and English/Latin probes pass.
- All 24 vectors parse, avoid platform resource references, and render through CairoSVG at small sizes. The original geometry, typography, and launcher mask sheets passed independent design review.
- Six WAVs parse with the agreed format/duration, safe headroom, zero endpoints, and bounded size. The release reviewer independently repeated font downloads and audio-format checks.
- Native launcher is opaque 1024 px sRGB; both foreground layers fit the adaptive-icon safe area.

Machine-readable results are in [verification.json](../assets/verification.json). Actual Compose Android/iOS rasterization, font scaling/screen-reader behavior, physical speaker listening, audio focus/mute/background behavior, native launcher masking, and final packaged-license inclusion remain integration/device checks recorded by the platform and release owners. The source/provenance checks above do not claim those device behaviors have been tested.
