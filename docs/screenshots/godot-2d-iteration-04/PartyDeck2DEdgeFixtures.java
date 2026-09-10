import dev.partydeck.core.*;
import dev.partydeck.godot.bridge.*;
import java.nio.file.*;
import java.util.*;

/** Reproducible scene fixtures from the existing Kotlin authority; never serializes GameState. */
class PartyDeck2DEdgeFixtures {
  static final Path OUTPUT = Path.of("/tmp/partydeck-2d-edge-fixtures");
  static final List<PlayerIdentity> ROSTER = List.of(
    new PlayerIdentity("seat-1", "Alexandria Cassandra"),
    new PlayerIdentity("seat-2", "Alexandria Cassandra"),
    new PlayerIdentity("seat-3", "Maximilian Rutherford"),
    new PlayerIdentity("seat-4", "Francesca Montenegro"),
    new PlayerIdentity("seat-5", "Bartholomew Beaumont"),
    new PlayerIdentity("seat-6", "ABCDEFGHIJKLMNOPQRSTUVWX")
  );
  static GameState applied(GameDecision decision) {
    if (!(decision instanceof GameDecision.Applied success)) throw new AssertionError("Authority rejected a projected legal request");
    return success.getState();
  }
  static void write(String name, GameView view) throws Exception {
    boolean host = view.getViewerId() != null;
    var controls = new PresentationControls(host, host, host && view.getPhase() == GamePhase.ROUND_ENDED, host);
    var adapter = new LastLightBridgeAdapter("2d-edge-" + name, 0L, view, controls);
    String document = LastLightWireCodec.INSTANCE.encodeLaunch(adapter.getLaunch(), PresentationMode.TWO_D, new PresentationPreferences(true, false, 1.0));
    Files.writeString(OUTPUT.resolve(name + ".json"), document + "\n");
  }
  public static void main(String[] args) throws Exception {
    Files.createDirectories(OUTPUT);
    var engine = new LastLightEngine(kotlin.random.RandomKt.Random(2));
    GameState state = engine.start(ROSTER);
    String opener = state.getTurnPlayerId();
    write("six-long-names", engine.viewFor(state, opener));
    write("observer", engine.viewFor(state, null));
    GameView actor = engine.viewFor(state, opener);
    state = applied(engine.apply(state, new GameAction.Play(opener, actor.getYourHand().subList(0, 3).stream().map(Card::getId).toList())));
    state = applied(engine.apply(state, new GameAction.Challenge(state.getTurnPlayerId())));
    write("three-card-proof", engine.viewFor(state, opener));
    boolean eliminatedCaptured = false;
    for (int step = 0; step < 1000 && state.getPhase() != GamePhase.FINISHED; step++) {
      if (state.getPhase() == GamePhase.ROUND_ENDED) {
        String eliminated = engine.viewFor(state, null).getPlayers().stream().filter(PlayerView::getEliminated).map(PlayerView::getId).findFirst().orElse(null);
        state = applied(engine.advanceRound(state));
        if (eliminated != null) {
          write("eliminated-active-round", engine.viewFor(state, eliminated));
          eliminatedCaptured = true;
          break;
        }
      } else {
        String turn = state.getTurnPlayerId();
        GameView view = engine.viewFor(state, turn);
        GameAction request = view.getAvailableActions().getCanChallenge() ? new GameAction.Challenge(turn) : new GameAction.Play(turn, List.of(view.getYourHand().getFirst().getId()));
        state = applied(engine.apply(state, request));
      }
    }
    if (!eliminatedCaptured) throw new AssertionError("No active eliminated fixture reached");
    var forcedEngine = new LastLightEngine(kotlin.random.RandomKt.Random(2));
    state = forcedEngine.start(ROSTER);
    boolean forcedCaptured = false;
    for (int step = 0; step < 40; step++) {
      String turn = state.getTurnPlayerId();
      GameView view = forcedEngine.viewFor(state, turn);
      if (view.getForcedChallenge()) {
        write("forced-challenge", view);
        forcedCaptured = true;
        break;
      }
      int count = view.getAvailableActions().getMaxPlayableCards();
      state = applied(forcedEngine.apply(state, new GameAction.Play(turn, view.getYourHand().subList(0, count).stream().map(Card::getId).toList())));
    }
    if (!forcedCaptured) throw new AssertionError("No forced challenge fixture reached");
    System.out.println("Generated five safe launch fixtures from LastLightEngine with seed 2: " + OUTPUT);
  }
}
