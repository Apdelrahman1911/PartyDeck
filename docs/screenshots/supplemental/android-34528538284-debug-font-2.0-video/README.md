# Android debug font 2.0 — complete decoded recordings

These **233 PNG derivatives** come from three original recordings in Android API 36 run **34528538284**, exact head `8030efe1c56e7885ed1fd3bd5140bb8ff82fcc57` and old PCK `557b2297bed133a433acc25efa4837462465dd4e06da659ae5a4cbd792f77fe0` (**1,549,560 bytes**). They are supplemental decoded frames and add zero original CI PNG captures.

Every decoded identity is covered by **122 direct full-size views and 111 verified identical-byte matches**. No private card faces were visible in those frames. Every frame filename, SHA-256, exact media presentation timestamp and original 1600 × 720 canvas is retained. Root decoded the recordings with no autorotation, cropping, resampling or temporal frame dropping; the publication reviewer reused that frozen decode.

| Original recording | Decoded identities | Direct views | Reviewed byte matches |
| --- | ---: | ---: | ---: |
| [3D landscape rotation](decode/3d-landscape-rotation/README.md) | 88 | 44 | 44 |
| [2D split entry](decode/2d-split-entry/README.md) | 80 | 43 | 37 |
| [2D split exit](decode/2d-split-exit/README.md) | 65 | 35 | 30 |

At font 2.0, several native and Standard hand/action regions are below the landscape or split viewport. The 3D rotation retains an intermediate sideways image, then portrait closing/privacy cover and a concealed Standard portrait return; its lower Reveal/action area is clipped. Both 2D split transitions show closing and privacy covers before Standard public headers; the hand is offscreen in the resulting narrow/landscape views.

The held target was **Standard table**, independently identified by its XML and input log. The visible lighter button is not evidence of a Show hand hold or card drag. Media PTS is not bounded against InputDispatcher CLOCK_MONOTONIC; host UTC and Winscope elapsed time cannot establish a per-frame before-UP deadline. Covering all decoded frames does not prove every rendered device frame was captured or establish continuous privacy. The two lower-priority 2D rotation recordings were not decoded or reviewed here. These old-PCK findings do not qualify current main or the separate JVM correction.

[Frozen review](provenance/visual-review/review.json), [held-target binding](provenance/visual-review/target-binding.json), [root decode freeze](decode/decode-freeze.json) and [original recording/observation companions](companions.md) preserve the complete bounded provenance. Identical bytes share findings while every frame identity stays separate.
