import dev.partydeck.core.PlayerIdentity;
import dev.partydeck.godot.bridge.LastLightBridgeAdapter;
import dev.partydeck.godot.bridge.LastLightWireCodec;
import dev.partydeck.godot.bridge.PresentationControls;
import dev.partydeck.godot.bridge.PresentationMode;
import dev.partydeck.godot.bridge.PresentationPreferences;
import dev.partydeck.godot.bridge.QualificationAuthorityDriver;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;

/** Uses the same safe initial authority view with a native host's early-lobby permission.
 * This is a static renderer fixture; it does not claim authority acceptance of an intent.
 */
class InitialHostFixture {
    public static void main(String[] args) throws Exception {
        var roster = List.of(new PlayerIdentity("seat-1", "Ari"), new PlayerIdentity("seat-2", "Moxie"),
            new PlayerIdentity("seat-3", "Pip"), new PlayerIdentity("seat-4", "Orbit"));
        var driver = new QualificationAuthorityDriver(kotlin.random.RandomKt.Random(2),
            "initial-reveal-host-font-1.0", roster, null);
        var adapter = new LastLightBridgeAdapter(driver.getPresentationId(), 0L, driver.getView(),
            new PresentationControls(true, true, false, true));
        String launch = LastLightWireCodec.INSTANCE.encodeLaunch(adapter.getLaunch(),
            PresentationMode.TWO_D, new PresentationPreferences(true, false, 1.0));
        Files.writeString(Path.of(args[0]), launch, StandardOpenOption.CREATE_NEW);
    }
}
