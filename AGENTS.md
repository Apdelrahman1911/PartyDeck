# PartyDeck contributor instructions

Read `plan.md` and `docs/IMPLEMENTATION.md` before changing architecture. User requires delegated agents to use **gpt-6-astra with max reasoning**. Do not invent APIs, dependency versions or platform facts when authoritative documentation/source can be checked. Record material dependency decisions with sources.

The root coordinator owns shared Gradle configuration and Git integration. Agent file ownership is listed in `docs/IMPLEMENTATION.md`; coordinate cross-boundary edits. Preserve hidden information at the authority boundary. Never transmit authoritative GameState or admission/reconnect secrets in discovery/public views.

Use focused behavior tests and builds, then meaningful milestone/full qualification. Reviewers must independently verify. Do not call device/store signing or physical-network tests complete without execution evidence. Do not add a fake Godot renderer or launch entry.
