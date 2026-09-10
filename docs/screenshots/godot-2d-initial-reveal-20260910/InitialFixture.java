import dev.partydeck.core.PlayerIdentity;
import dev.partydeck.godot.bridge.PresentationMode;
import dev.partydeck.godot.bridge.PresentationPreferences;
import dev.partydeck.godot.bridge.QualificationAuthorityDriver;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/** Generates recipient-safe initial views through the same seeded qualification authority. */
class InitialFixture {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        var roster = List.of(new PlayerIdentity("seat-1", "Ari"), new PlayerIdentity("seat-2", "Moxie"),
            new PlayerIdentity("seat-3", "Pip"), new PlayerIdentity("seat-4", "Orbit"));
        for (double scale : new double[] {1.0, 2.0}) {
            var driver = new QualificationAuthorityDriver(kotlin.random.RandomKt.Random(2),
                "initial-reveal-font-" + scale, roster, null);
            String launch = driver.launchDocument(PresentationMode.TWO_D,
                new PresentationPreferences(true, false, scale));
            Files.writeString(output.resolve("launch-font-" + scale + ".json"), launch);
        }
    }
}
