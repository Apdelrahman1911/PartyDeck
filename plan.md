You are taking ownership of a new project called **PartyDeck**.

Repository:

`https://github.com/Apdelrahman1911/PartyDeck.git`

The repository may currently be empty or nearly empty. You are responsible for planning, bootstrapping, implementing, reviewing, testing, and bringing the project as close to production quality as reasonably possible.

# 1. Environment and platform constraints

You are working primarily on a **Linux environment**.

Do not block the project because something requires macOS or Windows.

For anything that genuinely requires another operating system:

* Use **GitHub Actions macOS runners** for macOS/iOS/Xcode-specific work.
* Use **GitHub Actions Windows runners** for Windows-specific work.
* Keep native-device-only or genuinely unavailable verification clearly documented, but do not stop unrelated work because of it.
* Prefer Linux-compatible development and validation wherever possible.

The primary shipping targets are:

1. **Android — highest priority**
2. **iOS — highest priority**
3. **JVM Desktop — optional**

Implement JVM/Desktop only if it can share most of the code and does not create significant additional work, complexity, architectural compromises, or delays.

Android and iOS must never be compromised in order to support Desktop.

# 2. Product concept

PartyDeck is a **Kotlin Multiplatform party-game application**.

It will eventually be able to contain multiple party/local-multiplayer games, so do not architect the entire application around only one game.

The first main game is inspired by the bluffing card-game concept commonly seen in games such as Liar's Deck.

Core gameplay concept:

* Several players join a local multiplayer game.
* Each player has a hidden hand of cards.
* Each round has a required card rank/type.
* A player places one or more cards face-down and claims they match the required rank.
* The player may be telling the truth or bluffing.
* The next player can either continue playing or challenge the previous player by calling them a liar.
* If the challenged player lied, they receive the penalty.
* If they were truthful, the challenger receives the penalty.
* The penalty is a fictional game mechanic inspired by Russian roulette.
* Players are progressively eliminated until there is a winner.

The exact rules, deck composition, round flow, balancing, animations, and presentation must be designed carefully rather than blindly copying another product.

Do not copy copyrighted assets, branding, UI, sounds, or proprietary implementation from another game.

Research existing bluffing/card/party games to understand what makes the interaction satisfying, then create an original PartyDeck implementation and presentation.

# 3. Technical direction

Build this primarily as a **Kotlin Multiplatform application**.

Use modern, stable, actively supported technologies and versions.

Before choosing libraries, frameworks, patterns, Gradle plugins, Godot integration mechanisms, networking approaches, serialization solutions, or other dependencies:

**Research them first.**

Do not guess library APIs or versions from memory when authoritative documentation can be checked.

Prefer:

* Current stable releases.
* Official documentation.
* Official repositories.
* Well-supported maintained libraries.
* Platform-native recommended practices.

Avoid unnecessary experimental dependencies unless they provide a clear advantage.

The architecture should allow some games to be implemented with standard KMP/Compose UI while games requiring a game engine can use **Godot**.

Godot must not unnecessarily control the entire application lifecycle.

The KMP application should remain the application shell.

A possible high-level model is:

KMP application
→ Navigation / settings / lobby / networking / application lifecycle
→ Game engine abstraction
→ Platform-specific Godot bridge
→ Godot game

Use KMP `expect/actual` only where platform-specific behavior is genuinely required.

Prefer a common interface plus a small platform-specific factory/implementation instead of spreading `expect/actual` everywhere.

Keep the Godot bridge event-based and coarse-grained. Do not create unnecessary frame-by-frame chatter between KMP and Godot.

# 4. Local multiplayer

The first game is intended to support **local multiplayer between multiple devices**.

Research and choose the cleanest architecture.

P2pKit may be evaluated:

`https://github.com/p2pKit/P2pKit`

Do not automatically use it simply because it was mentioned.

Review:

* Current project status.
* Android support.
* iOS support.
* Discovery behavior.
* Connection lifecycle.
* Authentication.
* Encryption.
* Reconnection.
* Performance.
* Maintenance quality.
* Production readiness.
* Godot/KMP integration cost.

If P2pKit is genuinely the best fit, use it.

If another solution is materially better, document why and use the better solution.

The multiplayer architecture should preferably be:

* Host-authoritative.
* One player/device acts as the game authority.
* Clients send actions/intents.
* Host validates actions.
* Hidden cards remain hidden from other clients.
* Random game outcomes are generated authoritatively rather than independently on every device.
* Reconnection should be considered.
* Duplicate/replayed actions should not corrupt the state.
* Disconnects must fail gracefully.
* Game networking must be isolated from the actual game-rule domain layer.

Do not over-engineer networking for FPS-level traffic. This is primarily a turn-based party/card game.

# 5. First phase — environment bootstrap

Before implementing the actual application, inspect the repository and determine everything required to build the project.

Install/configure all reasonable Linux-side requirements.

For example, as applicable:

* JDK.
* Kotlin.
* Gradle.
* Android SDK.
* Android command-line tools.
* Android platform/build tools.
* NDK if genuinely required.
* Godot.
* Required export templates.
* Git.
* CI tooling.
* Any other development/runtime dependencies.

Then create the smallest possible smoke-test project or bootstrap configuration necessary to prove that the environment actually works.

Validate at least the important paths such as:

* Kotlin compilation.
* KMP project configuration.
* Android build.
* Compose Multiplatform.
* Godot CLI/headless execution if Godot will be used.
* KMP ↔ platform bridge feasibility.
* Any chosen networking library integration.
* GitHub Actions availability for macOS/iOS validation.

Do not spend hours proving every possible edge case during bootstrap.

We need sufficient evidence that the toolchain is usable.

# 6. Independent environment verification

After you prepare the environment, delegate an independent agent to inspect the setup.

That agent should independently attempt the important smoke tests rather than merely reading your output.

It should report:

* What was tested.
* What worked.
* What failed.
* Exact blockers.
* Anything suspicious or incorrectly configured.

Resolve important setup defects before major implementation begins.

# 7. Planning phase

Before major implementation, create a **detailed implementation plan** covering the project end-to-end.

Use all available agents intelligently during planning.

Do not create a superficial checklist.

The plan should cover at least:

* Product architecture.
* Module structure.
* Platform strategy.
* Android.
* iOS.
* Optional JVM.
* Godot integration.
* Multiplayer architecture.
* Lobby/discovery.
* Game rules.
* State machine.
* Card/deck model.
* Hidden-information handling.
* Bluff/challenge resolution.
* Penalty mechanic.
* Player elimination.
* Round progression.
* Win conditions.
* Disconnect/reconnect.
* Host loss strategy.
* App navigation.
* Main menu.
* Lobby UI.
* Gameplay UI.
* Results screens.
* Settings.
* Audio.
* Animation.
* VFX.
* Asset strategy.
* Accessibility.
* Localization readiness.
* Performance.
* Error handling.
* Persistence where needed.
* Testing.
* CI.
* Packaging.
* Android release-readiness.
* iOS release-readiness.
* Security/privacy implications.
* Final review and qualification.

While producing the plan, use agents to independently investigate specific areas and challenge assumptions.

The plan must identify dependencies between tasks so the implementation can be parallelized safely.

# 8. Agent organization

After planning, organize the work across **15 agents**.

Use approximately:

* **10 implementation agents**
* **5 review/verification agents**

You are the coordinator.

Do not simply create 15 agents and let them modify overlapping parts of the repository randomly.

You must:

* Define clear ownership.
* Minimize conflicting writes.
* Define module/file boundaries.
* Define expected deliverables.
* Define acceptance criteria.
* Track dependencies.
* Integrate changes carefully.
* Make sure reviewers are actually reviewing rather than rubber-stamping.

Implementation agents should handle parallelizable work.

Review agents should independently inspect their assigned implementation streams.

Whenever practical, pair implementation streams with reviewers.

# 9. Continuous review

Do **not** wait until the entire project is finished before reviewing it.

Review continuously.

After meaningful milestones:

1. Inspect implementation.
2. Run relevant validation.
3. Have an independent reviewer inspect it.
4. Fix important defects.
5. Continue.

The goal is to avoid completing 70% of the project and then discovering that the architecture or implementation is fundamentally wrong.

Important architectural and UI decisions should receive early review.

# 10. Research requirement for every agent

Whenever you delegate work, explicitly tell the agent:

**Do not invent APIs, versions, platform behavior, or technical facts from memory when they can be verified. Research authoritative sources first.**

Agents should research:

* Library versions.
* Framework APIs.
* Platform constraints.
* Android requirements.
* iOS requirements.
* Godot integration.
* Networking.
* performance-sensitive patterns.
* UX conventions where applicable.

Use authoritative documentation wherever possible.

# 11. UI / UX priority

One of the highest priorities of the entire project is:

**UI quality, UX quality, and performance.**

I do not want a generic developer-looking game interface.

The final result should feel like a polished commercial product.

Pay particular attention to:

* Visual hierarchy.
* Typography.
* Spacing.
* Motion.
* Animation timing.
* Card presentation.
* Touch feedback.
* Transitions.
* Lobby experience.
* Loading experience.
* Error states.
* Empty states.
* Responsive layouts.
* Android/iOS safe areas.
* Different screen sizes.
* Accessibility.
* Landscape/portrait decision.
* Haptics where appropriate.
* Audio feedback.
* Game tension.
* Bluff/challenge presentation.
* Penalty presentation.
* Winner/round-end presentation.

Keep UX simple.

A new user should not need to study documentation just to create or join a game.

# 12. Dedicated design review

Assign at least one agent specifically to evaluate:

* UI quality.
* UX quality.
* Visual consistency.
* Interaction complexity.
* Game feel.
* Animation quality.
* Accessibility.
* Responsiveness.
* Whether the design looks generic or polished.

That reviewer should be encouraged to criticize weak work.

Do not accept mediocre UI simply because it technically works.

Iterate when necessary.

# 13. Assets

We want the highest-quality practical result.

Research legal/free/appropriately licensed resources for anything that can improve quality, including where appropriate:

* Fonts.
* Icons.
* Sound effects.
* Music.
* Textures.
* Card assets.
* UI assets.
* Illustrations.
* Shaders.
* VFX.
* Godot plugins.

Verify licenses.

Record attribution requirements if any.

Do not use copyrighted assets without permission.

If a suitable asset cannot be legally obtained, create an original replacement.

Do not settle for crude placeholders in the final product.

Placeholders are acceptable only temporarily during implementation.

# 14. Performance

Performance is a first-class requirement.

The application must feel smooth on reasonable modern Android and iOS devices.

Avoid:

* Keeping Godot running unnecessarily when the user is outside a Godot-powered game.
* Excessive allocations.
* Excessive recomposition.
* Expensive work on the UI thread.
* Overly chatty KMP ↔ Godot bridges.
* Excessive network chatter.
* Massive textures.
* Unbounded caches.
* Resource leaks.
* Background processes that do not stop correctly.

Profile meaningful hot paths when appropriate.

Do not prematurely micro-optimize insignificant code.

# 15. Code quality

Keep the codebase clean and maintainable.

Follow SOLID where it improves the design.

Also follow:

* Clear module boundaries.
* Single source of truth.
* Explicit state ownership.
* Reasonable dependency inversion.
* Immutable state where appropriate.
* Good naming.
* Small focused components.
* No giant god classes.
* No duplicated domain logic across platforms.
* No platform checks scattered throughout common code.
* No unexplained magic numbers.
* No dead code.
* No permanent debug hacks.
* No swallowed exceptions.

However, do not over-engineer.

A straightforward solution is better than five abstraction layers that provide no practical value.

# 16. Testing philosophy

Do not waste project time attempting 100% test coverage.

Create strong tests for **important behavior**.

Prioritize tests for:

* Game state machine.
* Deck creation/shuffling invariants.
* Turn validation.
* Hidden information.
* Bluff/challenge resolution.
* Penalty resolution.
* Win conditions.
* Multiplayer action validation.
* Duplicate action handling.
* Reconnection/state restoration where implemented.
* Serialization/protocol compatibility.
* Critical KMP/Godot boundary behavior.
* Important navigation/session flows.

Add UI tests where they provide meaningful value.

Do not create dozens of trivial tests that merely test getters, constructors, or framework behavior.

# 17. Resource/time efficiency

Do not burn time on low-value work.

Examples:

* Do not run a complete expensive build after every tiny text change.
* Run targeted compilation/tests where enough.
* Group related changes before expensive verification.
* Split large verification tasks into smaller focused checks when that provides the evidence we need faster.
* Do not repeatedly revalidate unchanged areas without a reason.
* Do not spend hours polishing internal documentation while important product work remains unfinished.

Use full builds and wider test suites at meaningful checkpoints and final qualification.

# 18. Git discipline

Keep Git history understandable.

Commit coherent milestones.

Do not leave large amounts of completed work uncommitted indefinitely.

Push important completed milestones to the repository.

Avoid destructive Git operations that can erase another agent's work.

Coordinate branches/worktrees carefully if multiple agents operate concurrently.

# 19. Decision/blocker policy

If there is a genuinely important product decision that cannot be safely inferred, ask me **before major implementation depends on it**.

However:

* Do not ask me questions whose answers can be found through research.
* Do not ask about trivial implementation choices.
* Do not stop the entire project because one isolated area is blocked.
* Continue everything that can safely proceed.

If no genuinely blocking decision is missing after the planning/setup phase, **do not wait for additional permission**.

Begin implementation immediately.

# 20. Definition of success

The goal is not merely:

"It builds."

The goal is:

* Strong architecture.
* Clean code.
* Excellent UI.
* Excellent UX.
* Excellent performance.
* Stable multiplayer.
* Correct gameplay rules.
* Android quality.
* iOS quality.
* Useful automated validation.
* Continuous independent review.
* Polished assets.
* Good game feel.
* Maintainability for future PartyDeck games.

Push quality as high as reasonably possible.

# 21. Start now

Start with:

1. Inspect the repository.
2. Research the required stack.
3. Bootstrap the Linux environment.
4. Create and run focused smoke tests.
5. Have an independent agent verify the setup.
6. Resolve important setup problems.
7. Use the available agents to produce the detailed implementation plan.
8. Check whether any genuinely blocking product decisions are missing.
9. If something genuinely important cannot be determined, ask me clearly and compactly.
10. Otherwise, do not wait for me. Start executing the plan immediately.
11. Divide implementation across the 10 implementation agents.
12. Use the remaining 5 agents for continuous independent review.
13. Integrate, validate, fix, and continue until the planned implementation is complete or only explicitly documented external/device/store constraints remain.

Do not lower quality just to finish quickly, but also do not waste time proving or polishing things that do not materially improve the product.

Act as the project coordinator and technical owner, not merely as another coding agent.