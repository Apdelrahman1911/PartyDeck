import dev.partydeck.core.GamePhase;
import dev.partydeck.core.PlayerIdentity;
import dev.partydeck.games.EngineEvent;
import dev.partydeck.games.EngineEventBody;
import dev.partydeck.godot.bridge.*;
import java.nio.file.*;
import java.util.*;

/** Private focused fixtures from the existing authority and codec, with no rule implementation. */
public final class ClaimFixtures {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        for (boolean longNames : List.of(false, true)) {
            String prefix = longNames ? "duplicate-name" : "ordinary";
            String id = "context-fit-" + prefix;
            List<PlayerIdentity> roster = new ArrayList<>();
            String[] names = {"Ari", "Moxie", "Pip", "Orbit"};
            for (int i = 0; i < 4; i++) {
                roster.add(new PlayerIdentity("seat-" + (i + 1), longNames ? "Alexandria Montgomery" : names[i]));
            }
            QualificationAuthorityDriver driver = new QualificationAuthorityDriver(
                kotlin.random.RandomKt.Random(2), id, roster, null);
            Files.writeString(output.resolve(prefix + "-initial-launch.json"),
                driver.launchDocument(PresentationMode.THREE_D, new PresentationPreferences(true, false, 2.0)) + "\n");
            QualificationStep ready = driver.handleEvent(LastLightWireCodec.INSTANCE.encodeEvent(
                new EngineEvent(id, 1, 0L, EngineEventBody.Ready.INSTANCE)));
            if (!(ready.getDecision() instanceof BridgeDecision.Accepted)) throw new IllegalStateException("Ready rejected");
            long sequence = 0;
            String lastView = null;
            List<String> trace = new ArrayList<>();
            for (int step = 0; step < 300; step++) {
                var view = driver.getView();
                if (view.getPhase() == GamePhase.PLAYING && view.getLatestClaim() != null
                    && view.getAvailableActions().getCanPlay() && view.getAvailableActions().getCanChallenge()) {
                    if (lastView == null) throw new IllegalStateException("Claim has no authority document");
                    Files.writeString(output.resolve(prefix + "-claim-view.json"), lastView + "\n");
                    Files.write(output.resolve(prefix + "-authority-trace.txt"), trace);
                    System.out.println(prefix + ": revision " + driver.getRevision() + ", round " + view.getRoundNumber()
                        + ", rank " + view.getTableRank() + ", claim by " + view.getLatestClaim().getPlayerId());
                    break;
                }
                if (view.getPhase() == GamePhase.FINISHED) throw new IllegalStateException("No actionable claim before winner");
                if (view.getPhase() == GamePhase.PLAYING && !driver.getViewerId().equals(view.getTurnPlayerId())) {
                    var steps = driver.advanceOtherPlayers(32);
                    if (steps.isEmpty()) throw new IllegalStateException("No opponent progress");
                    for (var outcome : steps) {
                        if (outcome.getAuthorityRejection() != null) throw new IllegalStateException("Authority rejected bot");
                        lastView = outcome.getDocuments().getLast();
                    }
                    trace.add("opponent policy -> revision " + driver.getRevision());
                } else {
                    RendererIntent intent;
                    if (view.getPhase() == GamePhase.ROUND_ENDED) intent = RendererIntent.AdvanceRound.INSTANCE;
                    else if (view.getAvailableActions().getCanChallenge()) intent = RendererIntent.Challenge.INSTANCE;
                    else if (view.getAvailableActions().getCanPlay())
                        intent = new RendererIntent.Play(List.of(view.getYourHand().getFirst().getId()));
                    else throw new IllegalStateException("No projected action");
                    var event = new EngineEvent(id, 1, ++sequence, new EngineEventBody.PlayerIntent(
                        driver.getRevision(), LastLightWireCodec.INSTANCE.intentPayload(intent)));
                    QualificationStep outcome = driver.handleEvent(LastLightWireCodec.INSTANCE.encodeEvent(event));
                    if (!(outcome.getDecision() instanceof BridgeDecision.Accepted) || outcome.getAuthorityRejection() != null)
                        throw new IllegalStateException("Authority rejected viewer intent");
                    lastView = outcome.getDocuments().getLast();
                    trace.add(intent.getClass().getSimpleName() + " -> revision " + driver.getRevision());
                }
            }
            if (!Files.isRegularFile(output.resolve(prefix + "-claim-view.json"))) throw new IllegalStateException("Step budget exhausted");
        }
    }
}
