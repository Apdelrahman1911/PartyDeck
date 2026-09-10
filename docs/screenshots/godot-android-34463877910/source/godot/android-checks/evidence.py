"""Validate observations from the real Godot host and map its scene controls."""

from dataclasses import dataclass
import json
import math
import re
import struct
import uuid
import zlib


MAX_DOCUMENT_BYTES = 131_072
MAX_COUNTER = 9_223_372_036_854_775_807
ACTION_PREFIX = "partydeck_action_"
CARD_GROUP = "partydeck_hand_card"
CONTROL_GROUPS = {
    ACTION_PREFIX + name for name in (
        "reveal", "hide", "play", "challenge", "next_round", "lobby", "exit",
        "lobby_confirm", "lobby_cancel",
    )
} | {CARD_GROUP}
HOST_COUNTERS = (
    "evidenceRevision", "revision", "startedElapsedRealtimeMs", "receivedEvents", "receivedIntents",
    "acceptedIntents", "rejectedEvents", "authorityRejections", "botActions", "submittedCommands",
    "diagnosticsRequested",
)
HOST_FLAGS = (
    "foreground", "coverVisible", "foregroundFrameReady", "setupCompleted", "mainLoopStarted",
    "readyAccepted", "bridgeClosed", "nativeDestroyRequested", "nativeDestroyReturned",
    "nativeTerminating", "nativeForceQuitCallback", "processExitRequested", "diagnosticsTimedOut",
)


class CheckFailure(RuntimeError):
    """An observation is invalid or fails a required acceptance condition."""


def require(condition, description):
    if not condition:
        raise CheckFailure(description)


def counter(value, name):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,18}", value) is not None,
            f"{name} must be an exact nonnegative decimal string.")
    number = int(value)
    require(number <= MAX_COUNTER, f"{name} exceeds the bridge counter range.")
    return number


def integer(value, name, minimum=0, maximum=MAX_COUNTER):
    require(type(value) is int and minimum <= value <= maximum, f"Invalid {name}.")
    return value


def boolean(value, name):
    require(type(value) is bool, f"{name} must be a boolean.")
    return value


def number(value, name):
    require(type(value) in (int, float) and -1_000_000_000 <= value <= 1_000_000_000
            and math.isfinite(value), f"Invalid {name}.")
    return float(value)


def parse_document(text):
    require(isinstance(text, str) and len(text.encode("utf-8")) <= MAX_DOCUMENT_BYTES,
            "Host evidence exceeds the bounded document size.")

    def members(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Host evidence contains a duplicate JSON member.")
            result[key] = value
        return result

    def invalid_constant(_):
        raise CheckFailure("Host evidence contains a non-finite JSON number.")

    try:
        value = json.loads(text, object_pairs_hook=members, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as error:
        raise CheckFailure("Host evidence is not valid bounded JSON.") from error
    require(isinstance(value, dict), "Host evidence must be a JSON object.")
    return value


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def read(cls, value, name):
        require(isinstance(value, list) and len(value) == 4, f"Invalid {name} rectangle.")
        rect = cls(*(number(part, name) for part in value))
        require(rect.width >= 0 and rect.height >= 0, f"Negative {name} size.")
        return rect

    def clipped(self, outer):
        left = max(self.x, outer.x)
        top = max(self.y, outer.y)
        right = min(self.x + self.width, outer.x + outer.width)
        bottom = min(self.y + self.height, outer.y + outer.height)
        return Rect(left, top, max(0.0, right - left), max(0.0, bottom - top))

    @property
    def usable(self):
        return self.width > 0 and self.height > 0

    def encloses(self, other):
        # Compare edges directly. Reconstructing a float width via intersection
        # can change it by an ulp even when nothing was clipped (Android dp scale).
        return (self.usable and other.usable and self.x <= other.x and self.y <= other.y
                and other.x + other.width <= self.x + self.width
                and other.y + other.height <= self.y + self.height)


def validate_diagnostics(value, presentation_id, mode):
    fields = {"schemaVersion", "requestId", "sequence", "presentationId", "revision", "presentationMode",
              "coordinateSpace", "foreground", "viewport", "handConcealed", "selectedCount",
              "privateFaceCount", "privateLabelCount", "controls"}
    require(isinstance(value, dict) and set(value) == fields
            and type(value.get("schemaVersion")) is int and value["schemaVersion"] == 1,
            "Missing supported renderer diagnostics.")
    require(value.get("presentationId") == presentation_id, "Diagnostics belong to another presentation.")
    require(value.get("presentationMode") == mode, "Diagnostics identify the wrong presentation mode.")
    require(value.get("coordinateSpace") == "root_viewport", "Unknown renderer coordinate space.")
    for name in ("requestId", "sequence", "revision"):
        counter(value.get(name), f"diagnostics.{name}")
    for name in ("foreground", "handConcealed"):
        boolean(value.get(name), f"diagnostics.{name}")
    for name, maximum in (("selectedCount", 3), ("privateFaceCount", 30), ("privateLabelCount", 60)):
        integer(value.get(name), f"diagnostics.{name}", maximum=maximum)
    viewport = value.get("viewport")
    require(isinstance(viewport, dict) and set(viewport) == {"width", "height"}, "Missing renderer viewport.")
    require(number(viewport.get("width"), "viewport width") > 0 and
            number(viewport.get("height"), "viewport height") > 0, "Empty renderer viewport.")
    controls = value.get("controls")
    require(isinstance(controls, list) and len(controls) <= 32, "Invalid renderer control collection.")
    identities = set()
    for control in controls:
        require(isinstance(control, dict) and set(control) == {
            "group", "cardIndex", "rect", "clipRect", "visible", "enabled", "selected"}, "Invalid renderer control.")
        group = control.get("group")
        require(isinstance(group, str) and group in CONTROL_GROUPS, "Unknown renderer control group.")
        index = integer(control.get("cardIndex"), "card index", minimum=-1, maximum=4)
        require((index >= 0) == (group == CARD_GROUP), "Control has the wrong card index kind.")
        identity = (group, index)
        require(identity not in identities, "Renderer diagnostics contain ambiguous controls.")
        identities.add(identity)
        Rect.read(control.get("rect"), "control")
        clip = Rect.read(control.get("clipRect"), "control clip")
        root = Rect(0, 0, viewport["width"], viewport["height"])
        require(not clip.usable or root.encloses(clip), "Control clip exceeds the root viewport.")
        for name in ("visible", "enabled", "selected"):
            boolean(control.get(name), f"control.{name}")
    selected = sum(control["selected"] for control in controls if control["group"] == CARD_GROUP)
    require(selected == value["selectedCount"], "Selection count disagrees with actual card controls.")
    return value


def concealed(diagnostics):
    return (diagnostics["handConcealed"] and diagnostics["selectedCount"] == 0
            and diagnostics["privateFaceCount"] == 0 and diagnostics["privateLabelCount"] == 0)


def control_named(diagnostics, action, card_index=-1):
    group = CARD_GROUP if action == "card" else ACTION_PREFIX + action
    return next((control for control in diagnostics["controls"]
                 if control["group"] == group and control["cardIndex"] == card_index), None)


def surface_geometry(diagnostics, surface, display_size):
    require(isinstance(surface, dict), "Missing native engine surface bounds.")
    host = Rect(*(number(surface.get(name), f"engine surface {name}") for name in ("x", "y", "width", "height")))
    display = Rect(0, 0, *display_size)
    require(display.encloses(host), "Engine surface is outside the device display.")
    viewport = Rect(0, 0, diagnostics["viewport"]["width"], diagnostics["viewport"]["height"])
    scale_x, scale_y = host.width / viewport.width, host.height / viewport.height
    require(abs(scale_x - scale_y) <= max(scale_x, scale_y) * 0.02,
            "Native and renderer bounds disagree; refusing an ambiguous stretched tap.")
    return host, viewport, scale_x, scale_y


def touch_point(diagnostics, control, surface, display_size):
    require(control is not None and control["visible"] and control["enabled"],
            "Requested scene control is not visible and enabled.")
    host, viewport, scale_x, scale_y = surface_geometry(diagnostics, surface, display_size)
    clip = Rect.read(control["clipRect"], "control clip")
    require(viewport.encloses(clip), "Control clip is outside the renderer viewport.")
    target = Rect.read(control["rect"], "control")
    require(clip.encloses(target),
            "Requested scene control is not fully inside its actual clip viewport.")
    x = int(host.x + (target.x + target.width / 2) * scale_x)
    y = int(host.y + (target.y + target.height / 2) * scale_y)
    require(host.x <= x < host.x + host.width and host.y <= y < host.y + host.height,
            "Mapped scene tap is outside the native engine surface.")
    return x, y


def scroll_gesture(diagnostics, control, surface, display_size):
    require(control is not None and control["enabled"], "Requested scene control is absent or disabled.")
    host, viewport, scale_x, scale_y = surface_geometry(diagnostics, surface, display_size)
    clip = Rect.read(control["clipRect"], "control clip")
    require(viewport.encloses(clip), "Control clip is outside the renderer viewport.")
    target = Rect.read(control["rect"], "control")
    require(clip.width >= 32 and clip.height >= 32 and target.usable
            and target.width <= clip.width and target.height <= clip.height,
            "Control cannot fit wholly inside its actual scroll clip.")
    x, y = clip.x + clip.width / 2, clip.y + clip.height / 2
    if target.y < clip.y:
        axis, direction, gap = 1, 1, clip.y - target.y
    elif target.y + target.height > clip.y + clip.height:
        axis, direction, gap = 1, -1, target.y + target.height - clip.y - clip.height
    elif target.x < clip.x:
        axis, direction, gap = 0, 1, clip.x - target.x
    elif target.x + target.width > clip.x + clip.width:
        axis, direction, gap = 0, -1, target.x + target.width - clip.x - clip.width
    else:
        raise CheckFailure("A hidden control inside its clip cannot be recovered by scrolling.")
    span, target_span, scale = ((clip.width, target.width, scale_x) if axis == 0
                                else (clip.height, target.height, scale_y))
    # A fixed fast fling overshoots narrow controls after ScrollContainer's
    # inertial release. Correct the measured gap with modest interior clearance,
    # then obtain fresh settled geometry; never infer that a gesture succeeded.
    distance = min(span / 2, 250, gap + min(16, (span - target_span) / 2))
    start, end = [x, y], [x, y]
    start[axis] -= direction * distance / 2
    end[axis] += direction * distance / 2
    start, end = ([int(host.x + point[0] * scale_x), int(host.y + point[1] * scale_y)]
                  for point in (start, end))
    end[axis] = start[axis] + direction * min(abs(end[axis] - start[axis]), int(250 * scale))
    logical_distance = abs(end[axis] - start[axis]) / scale
    require(logical_distance > 0, "The required scroll is smaller than a device pixel.")
    # Bound speed at 250 logical units/s, with a slow floor for small corrections.
    # Use the rounded physical endpoints so density cannot increase that speed.
    duration_ms = max(350, math.ceil(logical_distance / 250 * 1000))
    return tuple(start), tuple(end), duration_ms


def validate_host(value):
    """Validate the app-private allowlisted host document, without accepting a pass flag."""
    required = set(HOST_COUNTERS) | set(HOST_FLAGS) | {
        "schemaVersion", "presentationId", "mode", "randomness", "enginePid", "taskId", "lifecycle",
        "publicState", "capturePolicy", "displayDensity",
    }
    optional = {
        "diagnostics", "engineSurface", "lastIntentType", "staleDiagnosticsRejected", "lastBridgeRejection",
        "lastAuthorityRejection", "closeSignalAcknowledged", "nativeDestroyElapsedMs", "closeReason", "failureCode",
    }
    require(isinstance(value, dict) and required <= value.keys() <= required | optional,
            "Host evidence has missing or unknown fields.")
    require(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1, "Unsupported host evidence schema.")
    identity = value["presentationId"]
    try:
        require(isinstance(identity, str) and str(uuid.UUID(identity)) == identity,
                "Host presentation identity is not a canonical UUID.")
    except ValueError as error:
        raise CheckFailure("Host presentation identity is not a canonical UUID.") from error
    require(value["mode"] in ("2d", "3d"), "Unknown host presentation mode.")
    require(value["randomness"] == "reference_seed_2", "The explicit native reference scenario was not selected.")
    require(value["capturePolicy"] in ("recents_disabled", "secure_window"), "Unknown native capture policy.")
    require(value["lifecycle"] in ("opening", "active", "background", "closing", "process_exit_requested"),
            "Unknown host lifecycle.")
    for name in HOST_COUNTERS:
        counter(value[name], name)
    for name in HOST_FLAGS:
        boolean(value[name], name)
    integer(value["enginePid"], "engine PID", minimum=1, maximum=2_147_483_647)
    integer(value["taskId"], "task ID", minimum=1, maximum=2_147_483_647)
    require(0.5 <= number(value["displayDensity"], "display density") <= 8, "Invalid display density.")
    require(counter(value["acceptedIntents"], "accepted intents") <= counter(value["receivedIntents"], "received intents")
            <= counter(value["receivedEvents"], "received events"), "Host event counters are inconsistent.")
    for name in ("staleDiagnosticsRejected", "closeSignalAcknowledged"):
        if name in value:
            boolean(value[name], name)
    if "nativeDestroyElapsedMs" in value:
        counter(value["nativeDestroyElapsedMs"], "native destruction duration")
    for name in ("lastIntentType", "lastBridgeRejection", "lastAuthorityRejection", "closeReason", "failureCode"):
        if name in value:
            require(isinstance(value[name], str) and re.fullmatch(r"[A-Za-z_0-9]{1,100}", value[name]) is not None,
                    "Host status field is not a bounded enum/code.")
    public = value["publicState"]
    public_required = {"phase", "roundNumber", "viewerHandCount", "canPlay", "canChallenge", "canAdvanceRound", "winnerPresent"}
    outcome = {"outcomeRoundNumber", "truthful", "burnedOut"}
    require(isinstance(public, dict) and set(public) in (public_required, public_required | outcome),
            "Invalid host public-state shape.")
    require(public["phase"] in ("PLAYING", "ROUND_ENDED", "FINISHED"), "Invalid authority phase.")
    integer(public["roundNumber"], "round number", minimum=1, maximum=2_147_483_647)
    integer(public["viewerHandCount"], "viewer hand count", maximum=5)
    for name in ("canPlay", "canChallenge", "canAdvanceRound", "winnerPresent"):
        boolean(public[name], name)
    require(public["canAdvanceRound"] == (public["phase"] == "ROUND_ENDED")
            and public["winnerPresent"] == (public["phase"] == "FINISHED"), "Authority phase flags disagree.")
    if outcome <= public.keys():
        integer(public["outcomeRoundNumber"], "outcome round", minimum=1, maximum=public["roundNumber"])
        boolean(public["truthful"], "truthful outcome")
        boolean(public["burnedOut"], "burnout outcome")
    require(public["phase"] == "PLAYING" or (outcome <= public.keys()
            and public["outcomeRoundNumber"] == public["roundNumber"]), "A completed round has no current authority outcome.")
    if "engineSurface" in value:
        surface = value["engineSurface"]
        require(isinstance(surface, dict) and set(surface) == {"x", "y", "width", "height"}, "Invalid native surface.")
        for name in surface:
            integer(surface[name], f"native surface {name}", maximum=32_768)
    if "diagnostics" in value:
        diagnostic = validate_diagnostics(value["diagnostics"], identity, value["mode"])
        require(counter(diagnostic["requestId"], "request ID") <= counter(value["diagnosticsRequested"], "requests")
                and counter(diagnostic["revision"], "scene revision") <= counter(value["revision"], "host revision"),
                "Renderer diagnostics are ahead of the native host.")
    return value


def healthy(value):
    require("failureCode" not in value, "Native host failed: " + value.get("failureCode", ""))
    require(not value["diagnosticsTimedOut"], "A native diagnostic request timed out.")
    require(value["rejectedEvents"] == "0" and value["authorityRejections"] == "0",
            "The real bridge or authority rejected a renderer submission.")


def active(value):
    diagnostic = value.get("diagnostics")
    surface = value.get("engineSurface")
    return (value["lifecycle"] == "active" and all(value[name] for name in (
        "foreground", "foregroundFrameReady", "setupCompleted", "mainLoopStarted", "readyAccepted"))
        and not value["coverVisible"] and not value["bridgeClosed"]
        and counter(value["receivedEvents"], "received events") > 0
        and counter(value["submittedCommands"], "submitted commands") > 0
        and diagnostic is not None and diagnostic["foreground"]
        and surface is not None and surface["width"] > 0 and surface["height"] > 0
        and diagnostic["requestId"] == value["diagnosticsRequested"]
        and diagnostic["revision"] == value["revision"]
        and counter(diagnostic["requestId"], "request ID") > 0)


class HostTrace:
    """Bind every observation to one actual native lifetime and monotonic evidence."""
    def __init__(self, presentation_id, mode, pid):
        self.presentation_id, self.mode, self.pid = presentation_id, mode, pid
        self.last = None

    def accept(self, value):
        validate_host(value)
        require((value["presentationId"], value["mode"], value["enginePid"])
                == (self.presentation_id, self.mode, self.pid), "Host evidence belongs to another native lifetime.")
        if self.last is not None:
            for name in ("taskId", "startedElapsedRealtimeMs", "displayDensity", "capturePolicy"):
                require(value[name] == self.last[name], "Native lifetime or display identity changed.")
            for name in HOST_COUNTERS:
                require(counter(value[name], name) >= counter(self.last[name], name), "Host evidence counter moved backwards.")
            if value["evidenceRevision"] == self.last["evidenceRevision"]:
                require(value == self.last, "Host evidence changed without a new evidence revision.")
            if "diagnostics" in self.last and "diagnostics" in value:
                require(counter(value["diagnostics"]["sequence"], "diagnostic sequence") >=
                        counter(self.last["diagnostics"]["sequence"], "diagnostic sequence"),
                        "Renderer diagnostic sequence moved backwards.")
        self.last = value
        return value


def local_transition(before, after):
    for name in ("revision", "receivedEvents", "receivedIntents", "acceptedIntents"):
        require(after[name] == before[name], "A local hand interaction emitted an authority event or changed the game.")


def accepted_intent(before, after, kind, changes_view=True):
    require(after.get("lastIntentType") == kind, "Native host accepted the wrong intent type.")
    for name in ("receivedEvents", "receivedIntents", "acceptedIntents"):
        require(counter(after[name], name) == counter(before[name], name) + 1,
                "Scene input did not make exactly one accepted native intent round trip.")
    if changes_view:
        require(counter(after["revision"], "revision") > counter(before["revision"], "revision")
                and counter(after["submittedCommands"], "commands") > counter(before["submittedCommands"], "commands"),
                "Accepted intent produced no newer real authority view for the renderer.")


def completed_teardown(value, reason):
    healthy(value)
    require(value["lifecycle"] == "process_exit_requested" and value.get("closeReason") == reason,
            "Native host did not finish the expected close route.")
    for name in ("bridgeClosed", "nativeDestroyRequested", "nativeDestroyReturned", "nativeTerminating",
                 "processExitRequested", "closeSignalAcknowledged"):
        require(value.get(name) is True, "Missing actual native teardown marker: " + name)
    require(not value["foreground"] and value["coverVisible"] and not value["foregroundFrameReady"],
            "Closing native host did not conceal the surface and reject foreground input.")
    counter(value.get("nativeDestroyElapsedMs"), "native destruction duration")


@dataclass(frozen=True)
class PngImage:
    width: int
    height: int
    rgb: bytes

    def crop(self, surface):
        rect = Rect(*(number(surface.get(name), f"capture surface {name}") for name in ("x", "y", "width", "height")))
        left, top = math.ceil(rect.x), math.ceil(rect.y)
        right, bottom = math.floor(rect.x + rect.width), math.floor(rect.y + rect.height)
        require(0 <= left < right <= self.width and 0 <= top < bottom <= self.height,
                "Capture surface is outside the PNG.")
        return b"".join(self.rgb[(row * self.width + left) * 3:(row * self.width + right) * 3]
                        for row in range(top, bottom))


def read_png(data):
    """Decode the bounded, noninterlaced RGB/RGBA PNG emitted by Android screencap."""
    require(data.startswith(b"\x89PNG\r\n\x1a\n"), "Android did not return a PNG capture.")
    position, header, compressed, ended = 8, None, bytearray(), False
    while position + 12 <= len(data):
        size = struct.unpack_from(">I", data, position)[0]
        require(size <= 64 * 1024 * 1024 and position + size + 12 <= len(data), "Truncated PNG chunk.")
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + size]
        checksum = struct.unpack_from(">I", data, position + 8 + size)[0]
        require(zlib.crc32(kind + payload) == checksum, "PNG chunk checksum failed.")
        if kind == b"IHDR":
            require(header is None and size == 13 and position == 8, "Invalid PNG header.")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            ended = True
            require(size == 0 and position + 12 == len(data), "Invalid PNG end marker.")
            break
        position += size + 12
    require(header is not None and ended and compressed, "PNG is incomplete.")
    width, height, depth, colour, compression, filtering, interlace = header
    require(0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16_777_216,
            "PNG dimensions exceed the capture bound.")
    require(depth == 8 and colour in (2, 6) and (compression, filtering, interlace) == (0, 0, 0),
            "Capture must use noninterlaced 8-bit RGB or RGBA PNG.")
    channels = 3 if colour == 2 else 4
    stride = width * channels
    expected = height * (stride + 1)
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(bytes(compressed), expected + 1)
    except zlib.error as error:
        raise CheckFailure("PNG image data is corrupt.") from error
    require(len(raw) == expected and inflater.eof and not inflater.unused_data,
            "PNG decompressed size is invalid.")
    previous = bytearray(stride)
    rgb = bytearray(width * height * 3)
    for y in range(height):
        start = y * (stride + 1)
        kind = raw[start]
        require(kind <= 4, "Unknown PNG scanline filter.")
        row = bytearray(raw[start + 1:start + stride + 1])
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = previous[x]
            upper_left = previous[x - channels] if x >= channels else 0
            if kind == 1:
                predictor = left
            elif kind == 2:
                predictor = up
            elif kind == 3:
                predictor = (left + up) // 2
            elif kind == 4:
                estimate = left + up - upper_left
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
            else:
                predictor = 0
            row[x] = (row[x] + predictor) & 255
        if channels == 3:
            rgb[y * width * 3:(y + 1) * width * 3] = row
        else:
            for x in range(width):
                offset = (y * width + x) * 3
                rgb[offset:offset + 3] = row[x * 4:x * 4 + 3]
        previous = row
    return PngImage(width, height, bytes(rgb))


def require_rendered_pixels(pixels):
    require(len(pixels) >= 3 and len(pixels) % 3 == 0, "Engine capture contains no RGB pixels.")
    colours = set()
    for index in range(0, len(pixels), 3):
        colours.add(pixels[index:index + 3])
        if len(colours) > 16:
            return
    raise CheckFailure("Engine surface is blank or nearly flat; rendered evidence is missing.")
