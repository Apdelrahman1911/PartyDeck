# iOS native hosts — CI 34488350932

Retained lifecycle and same-process reentry remain unqualified after the stale-first-ready failure. Five Authority Simulator fixture cases passed, including four reference full matches and secure launch/exit. Secure-default full match, production KMP factory, physical sensors, device Metal and real audio interruption remain unqualified. No clean-native-log or no-crash claim is made.

Exact source: `4f694296b08899176831e7c444c6f8082d40d64b`. Renderer pack SHA-256: `d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0`.

| Collection | Original PNGs | Staged text companions | Outcome |
| --- | ---: | ---: | --- |
| [Retained native host](retained/README.md) | 28 | 65 | Two cases passed; stale-first-ready/close-completion reentry failed. Three additional companions are indexed as source-only references. |
| [Authority native host](authority/README.md) | 45 | 361 | Five original Simulator fixture cases passed. |

[Frozen owner summary](provenance/collection-evidence-summary.json) · [Original owner mapping](provenance/source-map/mapping.json) · [Publication attachment index](provenance/published-attachment-index.json). Companions retain their recorded case/name/time associations; no one-to-one screenshot pairing is invented.
