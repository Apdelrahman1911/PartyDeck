import dev.partydeck.core.*;
import dev.partydeck.games.EnginePayload;
import dev.partydeck.godot.bridge.*;
import kotlinx.serialization.json.*;

import java.nio.file.*;
import java.util.*;

/** Extra scene inputs from real rules, plus reuse of independently captured safe views. */
public final class CompleteEdgeFixtures {
    private static final LastLightWireCodec CODEC = LastLightWireCodec.INSTANCE;
    private static final PresentationPreferences PREFERENCES = new PresentationPreferences(true, false, 1.0);
    private static final List<PlayerIdentity> ROSTER = List.of(
        new PlayerIdentity("seat-1", "Ari"), new PlayerIdentity("seat-2", "Moxie"),
        new PlayerIdentity("seat-3", "Pip"), new PlayerIdentity("seat-4", "Orbit")
    );
    private static final int SEARCH_LIMIT = 256;
    private static final List<Object> CASES = new ArrayList<>();
    private static Path output;

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static Map<String, Object> fields(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }

    // Tooling provenance only. Renderer documents always come from LastLightWireCodec.
    private static JsonElement json(Object value) {
        if (value == null) return JsonNull.INSTANCE;
        if (value instanceof String v) return JsonElementKt.JsonPrimitive(v);
        if (value instanceof Boolean v) return JsonElementKt.JsonPrimitive(v);
        if (value instanceof Number v) return JsonElementKt.JsonPrimitive(v);
        if (value instanceof Map<?, ?> v) {
            Map<String, JsonElement> result = new LinkedHashMap<>();
            v.forEach((key, item) -> result.put((String) key, json(item)));
            return new JsonObject(result);
        }
        if (value instanceof List<?> v) return new JsonArray(v.stream().map(CompleteEdgeFixtures::json).toList());
        throw new IllegalArgumentException("Unsupported provenance value");
    }

    private static JsonObject parse(String document) {
        return (JsonObject) Json.Default.parseToJsonElement(document);
    }

    private static String text(JsonObject value, String key) {
        return ((JsonPrimitive) value.get(key)).getContent();
    }

    private static PresentationControls hostControls(GameView view) {
        return new PresentationControls(true, true, view.getPhase() == GamePhase.ROUND_ENDED, true);
    }

    private static List<String> writePair(String name, String presentationId, long revision,
                                         GameView view, PresentationControls controls,
                                         PresentationPreferences preferences) throws Exception {
        // Both modes use this exact safe projection and trusted control snapshot.
        var payload = CODEC.viewPayload(view, controls);
        require(CODEC.decodeViewPayload(payload).getGame().equals(view), "Projection round trip changed the view");
        var adapter = new LastLightBridgeAdapter(presentationId, revision, view, controls);
        List<String> names = new ArrayList<>();
        for (PresentationMode mode : PresentationMode.values()) {
            String nameWithMode = name + "-" + mode.getWireName() + ".json";
            String document = CODEC.encodeLaunch(adapter.getLaunch(), mode, preferences);
            require(parse(document).get("payload").equals(parse(payload.getDocument())), "Envelope changed the safe payload");
            Files.writeString(output.resolve(nameWithMode), document + "\n");
            names.add(nameWithMode);
        }
        return names;
    }

    private static Map<String, Object> facts(GameView view) {
        var result = fields("viewerId", view.getViewerId(), "phase", view.getPhase().name(),
            "roundNumber", view.getRoundNumber(), "handSize", view.getYourHand().size(),
            "forcedChallenge", view.getForcedChallenge());
        if (view.getRoundOutcome() != null) {
            var proof = view.getRoundOutcome();
            result.put("outcomeRound", proof.getRoundNumber());
            result.put("truthful", proof.getTruthful());
            result.put("burnedOut", proof.getBurnedOut());
            result.put("revealedRanks", proof.getRevealedCards().stream().map(c -> c.getRank().name()).toList());
        }
        return result;
    }

    private static void importCase(Path imports, String name, List<Object> recipe) throws Exception {
        Path input = imports.resolve(name + ".json");
        String document = Files.readString(input);
        JsonObject launch = parse(document);
        var snapshot = CODEC.decodeViewPayload(new EnginePayload(text(launch, "schemaId"), launch.get("payload").toString()));
        var preferencesJson = (JsonObject) launch.get("preferences");
        var preferences = new PresentationPreferences(
            Boolean.parseBoolean(text(preferencesJson, "reduceMotion")),
            Boolean.parseBoolean(text(preferencesJson, "soundEnabled")),
            Double.parseDouble(text(preferencesJson, "textScale")));
        long revision = Long.parseLong(text(launch, "revision"));
        var files = writePair(name, text(launch, "presentationId"), revision, snapshot.getGame(), snapshot.getControls(), preferences);
        require(Files.readString(output.resolve(files.getFirst())).equals(document), "Imported 2D bytes changed: " + name);
        CASES.add(fields("name", name, "origin", "reused-ui-shell-safe-projection", "seed", 2,
            "source", name + ".json", "revision", Long.toString(revision),
            "revisionMeaning", "Standalone launch revision from original generator; not authority transition count",
            "authorityRecipe", recipe, "files", files, "facts", facts(snapshot.getGame())));
    }

    private static final class Trace {
        final int seed;
        final LastLightEngine engine;
        final List<Object> operations = new ArrayList<>();
        GameState state; // Never serialized, copied, reflected into, or supplied to a renderer.
        long revision = 0;

        Trace(int seed) {
            this.seed = seed;
            this.engine = new LastLightEngine(kotlin.random.RandomKt.Random(seed));
            this.state = engine.start(ROSTER);
            operations.add(fields("op", "LastLightEngine.start", "seed", seed,
                "roster", ROSTER.stream().map(p -> fields("id", p.getId(), "displayName", p.getDisplayName())).toList(),
                "revision", "0"));
        }

        GameView view(String recipient) { return engine.viewFor(state, recipient); }
        GameView actorView() { return view(state.getTurnPlayerId()); }

        void apply(GameAction action) {
            GameDecision decision = engine.apply(state, action);
            require(decision instanceof GameDecision.Applied, "Authority rejected generated action");
            state = ((GameDecision.Applied) decision).getState();
            revision++;
            var step = fields("op", "LastLightEngine.apply", "actorId", action.getPlayerId(),
                "action", action instanceof GameAction.Play ? "play" : "challenge",
                "revision", Long.toString(revision));
            if (action instanceof GameAction.Play play) step.put("cardIds", play.getCardIds());
            operations.add(step);
        }

        void emit(String name, String recipient, List<Object> search) throws Exception {
            GameView view = view(recipient);
            var files = writePair(name, "last-light-edge-" + name + "-v1", revision, view, hostControls(view), PREFERENCES);
            List<Object> recorded = new ArrayList<>(operations);
            recorded.add(fields("op", "LastLightEngine.viewFor", "recipientId", recipient, "revision", Long.toString(revision)));
            CASES.add(fields("name", name, "origin", "real-authority-operations", "seed", seed,
                "revision", Long.toString(revision), "authorityOperations", recorded,
                "seedSearchBudget", SEARCH_LIMIT, "seedSearchAttempts", search,
                "files", files, "facts", facts(view)));
            System.out.println(name + ": seed=" + seed + ", revision=" + revision + ", " + json(facts(view)));
        }
    }

    private static void handEdges() throws Exception {
        Trace trace = new Trace(2);
        String recipient = trace.state.getTurnPlayerId();
        for (int step = 0; step < 16; step++) {
            GameView own = trace.view(recipient);
            if (recipient.equals(own.getTurnPlayerId()) && own.getYourHand().size() == 1) {
                require(own.getAvailableActions().getCanPlay(), "One-card recipient cannot play");
                trace.emit("one-card-hand", recipient, List.of());
                trace.apply(new GameAction.Play(recipient, List.of(own.getYourHand().getFirst().getId())));
                GameView empty = trace.view(recipient);
                require(empty.getPhase() == GamePhase.PLAYING && empty.getYourHand().isEmpty(), "Empty-hand phase mismatch");
                require(empty.getPlayers().stream().noneMatch(p -> p.getId().equals(recipient) && p.getEliminated()), "Empty-hand recipient was eliminated");
                trace.emit("zero-card-hand", recipient, List.of());
                return;
            }
            GameView actor = trace.actorView();
            int count = actor.getViewerId().equals(recipient) ? 2 : 1;
            require(actor.getAvailableActions().getMaxPlayableCards() >= count, "Hand policy exceeded projected action limit");
            trace.apply(new GameAction.Play(actor.getViewerId(), actor.getYourHand().subList(0, count).stream().map(Card::getId).toList()));
        }
        throw new AssertionError("Hand edge budget exhausted");
    }

    private static void resultEdge(String name) throws Exception {
        List<Object> attempts = new ArrayList<>();
        for (int seed = 0; seed < SEARCH_LIMIT; seed++) {
            Trace trace = new Trace(seed);
            GameView opener = trace.actorView();
            Card card = opener.getYourHand().stream().filter(c -> switch (name) {
                case "truthful-rank" -> c.getRank() == opener.getTableRank();
                case "truthful-wild" -> c.getRank() == CardRank.WILD;
                case "burnout" -> true;
                default -> throw new IllegalArgumentException(name);
            }).findFirst().orElse(null);
            if (card == null) {
                attempts.add(fields("seed", seed, "result", "no matching projected opener card"));
                continue;
            }
            trace.apply(new GameAction.Play(opener.getViewerId(), List.of(card.getId())));
            GameView challenger = trace.actorView();
            require(challenger.getAvailableActions().getCanChallenge(), "Challenge unavailable after real play");
            trace.apply(new GameAction.Challenge(challenger.getViewerId()));
            GameView resolved = trace.view(opener.getViewerId());
            RoundOutcome proof = Objects.requireNonNull(resolved.getRoundOutcome());
            require(resolved.getPhase() == GamePhase.ROUND_ENDED, "First four-seat result must not finish match");
            boolean accepted = name.equals("burnout") ? proof.getBurnedOut() : proof.getTruthful() && !proof.getBurnedOut();
            attempts.add(fields("seed", seed, "playedCardId", card.getId(), "truthful", proof.getTruthful(),
                "burnedOut", proof.getBurnedOut(), "accepted", accepted));
            if (!accepted) continue;
            require(proof.getRevealedCards().size() == 1 && proof.getRevealedCards().getFirst().getId().equals(card.getId()), "Public proof differs from actual action");
            String recipient = name.equals("burnout") ? proof.getPenalizedPlayerId() : opener.getViewerId();
            trace.emit(name, recipient, attempts);
            return;
        }
        throw new AssertionError("Result seed budget exhausted: " + name);
    }

    public static void main(String[] args) throws Exception {
        require(args.length == 2, "Usage: CompleteEdgeFixtures <frozen-imports> <output>");
        Path imports = Path.of(args[0]);
        output = Path.of(args[1]);
        Files.createDirectories(output);
        var start = fields("op", "LastLightEngine.start", "seed", 2, "rosterSource", "PartyDeck2DEdgeFixtures.java:ROSTER");
        importCase(imports, "six-long-names", List.of(start, fields("op", "viewFor", "recipient", "actual random opener")));
        importCase(imports, "observer", List.of(start, fields("op", "viewFor", "recipient", null)));
        var three = fields("op", "apply", "policy", "Actual opener plays its first three projected cards; actual next actor challenges");
        importCase(imports, "three-card-proof", List.of(start, three, fields("op", "viewFor", "recipient", "original opener")));
        importCase(imports, "eliminated-active-round", List.of(start, three,
            fields("op", "bounded authority loop", "maxSteps", 1000,
                "policy", "On ROUND_ENDED, remember first public eliminated seat then advanceRound; emit its view after advance. Otherwise actual turn actor challenges if available, else plays its first projected card.")));
        importCase(imports, "forced-challenge", List.of(start,
            fields("op", "bounded authority loop", "maxSteps", 40,
                "policy", "Emit actual turn actor view when forcedChallenge; otherwise apply play of first maxPlayableCards projected cards.")));
        handEdges();
        resultEdge("truthful-rank");
        resultEdge("truthful-wild");
        resultEdge("burnout");
        Files.writeString(output.resolve("authority-provenance.json"), json(fields(
            "version", 1, "generator", "CompleteEdgeFixtures.java", "purpose", "isolated scene inputs; not multiplayer integration evidence",
            "controlBasis", "Known recipients are trusted host projections; canReturnToLobby is enabled in active games as supported by HostAuthority. Permissions are not fabricated game outcomes.",
            "importBasis", "Original source recipes and verified safe document bytes; imported states were not regenerated. Recipes are deterministic, not claimed to be original per-operation logs.",
            "newAuthorityBasis", "LastLightEngine.start/apply/viewFor; no GameState constructors, copies, reflection, or outcome dictionaries",
            "cases", CASES)) + "\n");
        System.out.println("Wrote " + CASES.size() + " cases in both modes (20 launch documents). No canonical fixture was used as an output.");
    }
}
