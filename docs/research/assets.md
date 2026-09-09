# PartyDeck asset research

Verified 2026-09-09. This records source facts separately from PartyDeck design decisions. Assets are original except for the explicitly licensed fonts below.

## Typeface decision

Use **Fraunces 72pt SemiBold** for short display headings and large rank letters, paired with **Manrope Regular / Medium / SemiBold** for body copy, navigation, buttons, numeric room codes, and accessibility labels. The display face gives the card club an editorial identity; the sans keeps instructions and small controls calm and legible. Do not use the display face for dense rules or tiny metadata.

Both are SIL Open Font License 1.1 fonts. The actual license files permit bundling and embedding with software, require inclusion of the copyright notice and license, and prohibit selling the font by itself. Neither inspected license declares a Reserved Font Name. Download unmodified static TTFs from the upstream authors, preserve their licenses in both source attribution and distributable resources, and record SHA-256 digests. Static files avoid needing any variable-axis behavior in the app.

| Source | Verified evidence | Selected source files |
| --- | --- | --- |
| [Fraunces upstream](https://github.com/undercasetype/Fraunces), commit `7ccdec31c6028118dce3e47fe864e3744460371d` | [Google Fonts metadata](https://github.com/google/fonts/blob/334b789e33413f3aba4264d9aa6c97f7b94c5a2f/ofl/fraunces/METADATA.pb) names Undercase Type/Phaedra Charles/Flavia Zimbardi and links this upstream. [OFL](https://github.com/google/fonts/blob/334b789e33413f3aba4264d9aa6c97f7b94c5a2f/ofl/fraunces/OFL.txt) inspected. | `fonts/ttf/Fraunces72pt-SemiBold.ttf` |
| [Manrope upstream](https://github.com/aaronbell/manrope), commit `6f81ebecdf65e4463b798cc07b16a4f8d5216917` | [Google Fonts metadata](https://github.com/google/fonts/blob/334b789e33413f3aba4264d9aa6c97f7b94c5a2f/ofl/manrope/METADATA.pb) names Mikhail Sharanda and this source repository/commit. [OFL](https://github.com/aaronbell/manrope/blob/6f81ebecdf65e4463b798cc07b16a4f8d5216917/OFL.txt) inspected. The older `sharanda/manrope` repository linked in the copyright notice returns 404; the source above is accessible. | `fonts/ttf/manrope-regular.ttf`, `manrope-medium.ttf`, `manrope-semibold.ttf` |

Planned Compose names: `Res.font.fraunces_semibold`, `Res.font.manrope_regular`, `Res.font.manrope_medium`, `Res.font.manrope_semibold`. Glyph coverage must be checked from the exact bundled font binaries before making language-support claims; Google Fonts subset lists alone do not prove coverage of a different upstream static file.

## Original vector direction

Use an ink background (`#191526`), paper (`#F4F0E8`), citron (`#D6EF82`), copper (`#F16B48`), and restrained muted lilac (`#A99CB8`). These are design proposals coordinated with the shell and design reviewer, not platform constants. Color contrast is measured at integration. Dark ink labels belong on the bright accents.

Produce an original, compact vector set rather than borrowing casino artwork or using bitmap generation:

- A small fan of paper cards with a four-point club light: PartyDeck's app mark and launcher identity.
- Crown, crescent moon, five-point star, and interlaced wild shapes for the proposed Last Light ranks. Each silhouette must work in one color and appear with a text rank label.
- A symmetrical paper-deck back, built from borders, short ticks, orbital geometry, and the club light. No text, embedded images, gradients, filters, or texture behind readable copy.
- A restrained family of geometric interface symbols with a consistent optical size and stroke. No emoji or per-platform font glyph substitutions for icons.

Author sources as SVG and generate Android XML VectorDrawable equivalents for common resources. Card-back canvas is 2:3; rank symbols are square and separated from localized rank text. Keep the stateful six-light penalty indicator in Compose, where accessibility semantics can describe remaining lights.

## Compose packaging evidence

The [JetBrains resource setup guide](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-resources-setup.html) specifies `composeResources/drawable`, `font`, `values`, and `files`. It supports Android XML vectors without references to Android resources.

The [resource access guide](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-resources-usage.html) documents `painterResource(Res.drawable.name)`, `Font(Res.font.name, FontWeight.SemiBold)`, and suspending `Res.readBytes("files/path")`. It explicitly excludes Android from SVG support; therefore shipping SVG files as shared drawable resources is insufficient. SVGs stay in the editable source asset directory; Android XML vectors ship in common drawable resources.

## Sound strategy

Create six short, original PCM cues: a dry selection tick, soft paper placement, restrained challenge knock, warm safe chime, low extinguish cue, and brief resolved victory chord. Synthesize them in a deterministic script using oscillators, filtered seeded noise, and click-free attack/release envelopes. These contain no samples, recorded performances, speech, gunshots, or copyrighted music. Do not include looping background music in this first implementation; a local social game should leave room for conversation.

Common delivery format: **44,100 Hz, mono, signed 16-bit little-endian PCM in WAVE**. Target less than 1 MB total and less than 2 seconds per cue; most should be under 0.6 seconds. Leave signal headroom and do not normalize every cue to full scale. Asset quality checks cover duration, peak, DC offset, silence at boundaries, and non-clipping. Real-device listening remains a release check.

The [Android supported-format table](https://developer.android.com/media/platform/supported-formats) explicitly supports 8/16-bit linear PCM in `.wav` and documents 44,100 Hz recording. Apple's [audio guide](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/MultimediaPG/UsingAudio/UsingAudio.html) documents linear PCM and short `.wav` sound files. This Apple guide is archived; use it only as evidence for file-format support, not to choose current platform playback APIs. Android/iOS implementation agents own API research, audio-session behavior, preload/disposal, and respecting mute/lifecycle preferences.

Planned paths: `files/audio/ui_tap.wav`, `card_place.wav`, `challenge.wav`, `safe.wav`, `light_out.wav`, and `victory.wav`. Audio is supplementary: every event needs visible text/state, cues are muteable, and no outcome is conveyed only by sound. Never replay a backlog of cues after reconnect or foregrounding.

## Launcher delivery

The [Android adaptive-icon guide](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive) requires 108×108 dp foreground/background layers and identifies the central 66×66 dp safe zone. Provide original foreground/background/monochrome VectorDrawable layers with the important mark inside that zone; platform packaging owns the manifest and adaptive icon wrapper.

The current [Apple app-icon HIG](https://developer.apple.com/design/human-interface-guidelines/app-icons), also verified through its [documentation data](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/app-icons.json), describes 1024×1024 px layout for iOS/iPadOS/macOS, unmasked square layers, and system rounding. It permits a flattened image but prefers editable vector foreground layers for Icon Composer. Deliver a full-bleed opaque sRGB 1024×1024 PNG plus SVG source layers with no pre-rounded outer icon mask. The iOS agent owns catalog/Xcode integration and macOS visual qualification.

## Localization and accessibility readiness

Bundle fonts for offline use. Keep all user-facing sentences and pluralized quantities in common string resources; avoid concatenating translated fragments. Use `values` as the complete English fallback and add language-qualified resource directories only when actual translations are reviewed. JetBrains documents language/region/script qualifiers and warns that a script-specific language also needs a script-less fallback to avoid ambiguous resolution on Android/desktop.

Keep rank names, room labels, instructions, content descriptions, and error text outside SVGs. Icons indicate shape, never language. Treat room codes as isolated left-to-right tokens; prose follows the ambient layout direction. Verify large text and screen-reader labels in the application, including selected-card count, remaining lights, local-turn status, and results. No claim of translated language support is made by merely bundling a font with additional glyphs.

## Acceptance before shipping

Verify pinned source hashes and bundled notices; inspect exact glyph coverage; render and inspect a contact sheet at small sizes; parse every XML vector and use shared-resource generation/compilation; generate sound metrics and listen on mobile hardware; review launcher masking; and independently review the real composed screens for legibility and scaling. Platform device/store checks must remain explicitly documented when they cannot be completed on Linux.
