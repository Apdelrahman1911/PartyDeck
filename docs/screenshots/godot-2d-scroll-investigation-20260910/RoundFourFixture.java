import dev.partydeck.core.*;
import dev.partydeck.games.*;
import dev.partydeck.godot.bridge.*;
import java.nio.file.*;
import java.util.*;

/** Uses the existing authority/adapter and reference driver policy; serializes only its safe view. */
class RoundFourFixture {
  static final Path OUTPUT = Path.of("/tmp/partydeck-native-2d-scroll-investigation");
  static final String ID = "native-2d-scroll-round-four";
  static long sequence = 0;
  static final List<String> trace = new ArrayList<>();
  static void accept(QualificationAuthorityDriver driver, RendererIntent intent) {
    String event = LastLightWireCodec.INSTANCE.encodeEvent(new EngineEvent(ID, 1, ++sequence,
        new EngineEventBody.PlayerIntent(driver.getRevision(), LastLightWireCodec.INSTANCE.intentPayload(intent))));
    QualificationStep result = driver.handleEvent(event);
    if (!(result.getDecision() instanceof BridgeDecision.Accepted) || result.getAuthorityRejection() != null)
      throw new AssertionError("Reference operation rejected");
    trace.add(intent.getClass().getSimpleName() + " -> revision " + driver.getRevision() + ", round " + driver.getView().getRoundNumber());
  }
  public static void main(String[] args) throws Exception {
    var roster = List.of(new PlayerIdentity("seat-1", "Ari"), new PlayerIdentity("seat-2", "Moxie"),
        new PlayerIdentity("seat-3", "Pip"), new PlayerIdentity("seat-4", "Orbit"));
    var driver = new QualificationAuthorityDriver(kotlin.random.RandomKt.Random(2), ID, roster, null);
    var ready = new EngineEvent(ID, 1, sequence, EngineEventBody.Ready.INSTANCE);
    if (!(driver.handleEvent(LastLightWireCodec.INSTANCE.encodeEvent(ready)).getDecision() instanceof BridgeDecision.Accepted))
      throw new AssertionError("Ready rejected");
    for (int steps = 0; steps < 40; steps++) {
      GameView view = driver.getView();
      if (view.getRoundNumber() == 4 && view.getPhase() == GamePhase.ROUND_ENDED) break;
      if (view.getPhase() == GamePhase.ROUND_ENDED) accept(driver, RendererIntent.AdvanceRound.INSTANCE);
      else if (!Objects.equals(view.getViewerId(), view.getTurnPlayerId())) {
        var bots = driver.advanceOtherPlayers(32);
        if (bots.isEmpty()) throw new AssertionError("No opponent progression");
        trace.add("Opponent steps " + bots.size() + " -> revision " + driver.getRevision() + ", round " + driver.getView().getRoundNumber());
      } else if (view.getAvailableActions().getCanChallenge()) accept(driver, RendererIntent.Challenge.INSTANCE);
      else if (view.getAvailableActions().getCanPlay()) accept(driver, new RendererIntent.Play(List.of(view.getYourHand().getFirst().getId())));
      else throw new AssertionError("No projected reference action");
    }
    GameView view = driver.getView();
    if (driver.getRevision() != 11 || view.getRoundNumber() != 4 || view.getPhase() != GamePhase.ROUND_ENDED)
      throw new AssertionError("Reference state does not match native revision 11 / round 4");
    var adapter = new LastLightBridgeAdapter(ID, driver.getRevision(), view, new PresentationControls(true, true, true, false));
    String launch = LastLightWireCodec.INSTANCE.encodeLaunch(adapter.getLaunch(), PresentationMode.TWO_D,
        new PresentationPreferences(true, false, 2.0));
    Files.writeString(OUTPUT.resolve("round-four-launch-2d.json"), launch + "\n");
    Files.write(OUTPUT.resolve("authority-trace.txt"), trace);
    System.out.println("Exact reference revision 11, round 4 launch generated from existing authority: " + OUTPUT);
  }
}
