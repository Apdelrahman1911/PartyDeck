import dev.partydeck.core.*;
import dev.partydeck.games.*;
import dev.partydeck.godot.bridge.*;
import kotlinx.serialization.json.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Replays real authority operations, then accepts the captured, unmodified UI event. */
class AcceptNext {
  static final String ID = "native-2d-scroll-round-four";
  static final LastLightWireCodec CODEC = LastLightWireCodec.INSTANCE;
  static final List<PlayerIdentity> ROSTER = List.of(
      new PlayerIdentity("seat-1", "Ari"), new PlayerIdentity("seat-2", "Moxie"),
      new PlayerIdentity("seat-3", "Pip"), new PlayerIdentity("seat-4", "Orbit"));
  static void require(boolean condition, String message) {
    if (!condition) throw new AssertionError(message);
  }
  static Map<String, Object> fields(Object... pairs) {
    var map = new LinkedHashMap<String, Object>();
    for (int i = 0; i < pairs.length; i += 2) map.put((String) pairs[i], pairs[i + 1]);
    return map;
  }
  static JsonElement json(Object value) {
    if (value == null) return JsonNull.INSTANCE;
    if (value instanceof String s) return JsonElementKt.JsonPrimitive(s);
    if (value instanceof Number n) return JsonElementKt.JsonPrimitive(n);
    if (value instanceof Boolean b) return JsonElementKt.JsonPrimitive(b);
    if (value instanceof Map<?, ?> m) {
      var result = new LinkedHashMap<String, JsonElement>();
      m.forEach((k, v) -> result.put((String) k, json(v)));
      return new JsonObject(result);
    }
    if (value instanceof List<?> a) return new JsonArray(a.stream().map(AcceptNext::json).toList());
    throw new IllegalArgumentException("Unsupported receipt field");
  }
  static String sha256(Path path) throws Exception {
    return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
  }
  static PresentationControls controls(GameView view) {
    return new PresentationControls(true, true, view.getPhase() == GamePhase.ROUND_ENDED,
        view.getPhase() == GamePhase.FINISHED);
  }
  public static void main(String[] args) throws Exception {
    require(args.length == 1, "Usage: AcceptNext <probe-output>");
    Path output = Path.of(args[0]);
    var engine = new LastLightEngine(kotlin.random.RandomKt.Random(2));
    // This internal authority state is never serialized, copied, or reflected into.
    var state = engine.start(ROSTER);
    String viewer = Objects.requireNonNull(state.getTurnPlayerId());
    require(viewer.equals("seat-1"), "Seed 2 opener changed");
    List<Object> trace = new ArrayList<>();
    long revision = 0;
    while (revision < 11) {
      GameDecision result;
      String operation;
      if (state.getPhase() == GamePhase.ROUND_ENDED) {
        result = engine.advanceRound(state);
        operation = "advance_round";
      } else {
        String actor = Objects.requireNonNull(state.getTurnPlayerId());
        GameView actorView = engine.viewFor(state, actor);
        GameAction action;
        if (actorView.getAvailableActions().getCanChallenge()) {
          action = new GameAction.Challenge(actor);
          operation = "challenge by " + actor;
        } else {
          require(actorView.getAvailableActions().getCanPlay(), "No projected reference action");
          action = new GameAction.Play(actor, List.of(actorView.getYourHand().getFirst().getId()));
          operation = "play first projected card by " + actor;
        }
        result = engine.apply(state, action);
      }
      require(result instanceof GameDecision.Applied, "Reference authority operation rejected");
      state = ((GameDecision.Applied) result).getState();
      revision++;
      trace.add(fields("operation", operation, "revision", revision, "round", state.getRoundNumber(),
          "phase", state.getPhase().name()));
    }
    GameView before = engine.viewFor(state, viewer);
    require(before.getRoundNumber() == 4 && before.getPhase() == GamePhase.ROUND_ENDED,
        "Reference state is not round 4 ended");
    var adapter = new LastLightBridgeAdapter(ID, revision, before, controls(before));
    String launch = CODEC.encodeLaunch(adapter.getLaunch(), PresentationMode.TWO_D,
        new PresentationPreferences(true, false, 2.0));
    Path fixture = Path.of("/tmp/partydeck-native-2d-scroll-investigation/round-four-launch-2d.json");
    require((launch + "\n").equals(Files.readString(fixture)), "Regenerated safe launch differs from probe fixture");
    Path raw = output.resolve("bridge-events.jsonl");
    List<String> events = Files.readAllLines(raw);
    require(events.size() == 2, "Expected exactly captured Ready and Next events");
    var ready = adapter.accept(events.get(0));
    require(ready instanceof BridgeDecision.Accepted &&
        ((BridgeDecision.Accepted) ready).getInput() == BridgeInput.Ready.INSTANCE, "Captured Ready rejected");
    var next = adapter.accept(events.get(1));
    require(next instanceof BridgeDecision.Accepted &&
        ((BridgeDecision.Accepted) next).getInput() == BridgeInput.AdvanceRound.INSTANCE, "Captured Next rejected");
    var advanced = engine.advanceRound(state);
    require(advanced instanceof GameDecision.Applied, "Real authority rejected captured Next");
    state = ((GameDecision.Applied) advanced).getState();
    GameView after = engine.viewFor(state, viewer);
    require(after.getRoundNumber() == 5 && after.getPhase() == GamePhase.PLAYING, "Round 5 not reached");
    String command = CODEC.encodeCommand(ID, adapter.showView(++revision, after, controls(after)));
    Files.writeString(output.resolve("accepted-authority-view.json"), command + "\n");
    var replay = adapter.accept(events.get(1));
    require(replay instanceof BridgeDecision.Rejected &&
        ((BridgeDecision.Rejected) replay).getReason() == BridgeRejection.REPLAYED_EVENT,
        "Replayed captured Next was not rejected");
    Files.writeString(output.resolve("authority-receipt.json"), json(fields(
        "kind", "captured-real-ui-next-authority-acceptance", "fixtureSha256", sha256(fixture),
        "regeneratedLaunchByteIdentical", true, "seed", 2, "viewerId", viewer,
        "referenceOperations", trace, "rawBridgeEventsSha256", sha256(raw),
        "readyAccepted", true, "nextAcceptedByBridge", true, "nextAppliedByAuthority", true,
        "newRevision", revision, "newRound", after.getRoundNumber(), "newPhase", after.getPhase().name(),
        "nextReplayRejected", true, "authorityStateSerialized", false,
        "limitation", "Real adapter and Kotlin authority accept the raw event from the desktop geometry probe; this is not an Android execution.")) + "\n");
    System.out.println("Captured Ready and Next accepted; round 5 PLAYING, revision 12; duplicate Next rejected.");
  }
}
