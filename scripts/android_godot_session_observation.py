"""Bounded production qualification observations; no authority or gameplay injection API."""

import json
import math
import re
import time


PACKAGE = "dev.partydeck.app"
NATIVE_COMPONENT = f"{PACKAGE}/{PACKAGE}.godot.SessionGodotActivity"
RESOURCE = f"{PACKAGE}:id/godot_qualification_observation"
MAX_COUNTER = (1 << 63) - 1
REQUEST_TIMEOUT_MS = 2000
PUBLICATION_TTL_MS = 12000
MAX_INPUT_AGE_SECONDS = 9.0  # Leave time for input transport before native publication expiry.
COUNTERS = ("request", "sequence", "generation", "command", "input", "projectionRevision")
TIMES = ("requestedUptimeMs", "capturedUptimeMs", "expiresUptimeMs")
FIELDS = {"schemaVersion", "mode", *COUNTERS, *TIMES, "surface", "viewport", "sceneStateApplied",
          "handConcealed", "selectedCount", "privateFaceCount", "privateLabelCount", "controls"}
CONTROL_FIELDS = {"role", "slot", "rect", "clip", "visible", "enabled", "selected"}


class ObservationFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ObservationFailure(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate observation field.")
        value[key] = item
    return value


def strict_json(raw):
    def constant(_):
        raise ObservationFailure("Nonfinite JSON constant.")
    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=constant)
    except (ValueError, RecursionError, UnicodeError) as error:
        raise ObservationFailure("Malformed observation JSON.") from error


def counter(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,18}", value) is not None,
            "Invalid canonical observation counter.")
    result = int(value)
    require(result <= MAX_COUNTER, "Observation counter overflow.")
    return result


def integer(value, minimum, maximum):
    require(type(value) is int and minimum <= value <= maximum, "Invalid bounded observation integer.")
    return value


def number(value, minimum=-32768, maximum=32768):
    require(type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value),
            "Invalid finite observation geometry.")
    return value


def rect(value):
    require(type(value) is list and len(value) == 4, "Invalid observation rectangle.")
    return [number(item, 0 if index >= 2 else -32768) for index, item in enumerate(value)]


def encloses(outer, inner):
    return (inner[2] > 0 and inner[3] > 0 and outer[0] <= inner[0] and outer[1] <= inner[1]
            and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


def parse(raw, mode, display_size):
    require(type(raw) is str and len(raw) <= 8192, "Missing or oversized qualification observation.")
    try:
        require(len(raw.encode("utf-8")) <= 8192, "Oversized qualification observation.")
    except UnicodeError as error:
        raise ObservationFailure("Invalid observation Unicode.") from error
    value = strict_json(raw)
    require(type(value) is dict and set(value) == FIELDS, "Unknown or missing qualification observation field.")
    integer(value["schemaVersion"], 1, 1)
    require(mode in ("2d", "3d") and value["mode"] == mode, "Observation has a different admitted mode.")
    for field in COUNTERS:
        counter(value[field])
    for field in TIMES:
        integer(value[field], 0, MAX_COUNTER)
    requested, captured, expires = (value[field] for field in TIMES)
    require(requested <= captured < requested + REQUEST_TIMEOUT_MS
            and expires == captured + PUBLICATION_TTL_MS, "Observation lifetime is not bounded/current.")
    require(value["sceneStateApplied"] is True and type(value["handConcealed"]) is bool,
            "Renderer scene is not applied or concealment is ambiguous.")
    for field, maximum in (("selectedCount", 3), ("privateFaceCount", 30), ("privateLabelCount", 60)):
        integer(value[field], 0, maximum)
    require(not value["handConcealed"] or all(value[field] == 0 for field in
            ("selectedCount", "privateFaceCount", "privateLabelCount")), "Concealed observation retains private bindings.")
    surface = rect(value["surface"])
    require(all(type(item) is int for item in surface) and encloses([0, 0, *display_size], surface),
            "Native render surface is not wholly inside the observed display.")
    viewport = value["viewport"]
    require(type(viewport) is list and len(viewport) == 2, "Invalid root viewport.")
    for dimension in viewport:
        number(dimension, 1)
    scales = [surface[index + 2] / viewport[index] for index in (0, 1)]
    require(all(0.5 <= scale <= 8 for scale in scales) and abs(scales[0] - scales[1]) <= max(scales) * 0.02,
            "Ambiguous stretched/native coordinate mapping.")
    controls = value["controls"]
    require(type(controls) is list and len(controls) <= 8, "Unbounded qualification controls.")
    identities = set()
    for control in controls:
        require(type(control) is dict and set(control) == CONTROL_FIELDS, "Unknown control field.")
        role = control["role"]
        require(role in ("reveal", "hide", "select", "play"), "Unknown qualification control role.")
        integer(control["slot"], 0 if role == "select" else -1, 4 if role == "select" else -1)
        identity = (role, control["slot"])
        require(identity not in identities, "Duplicate qualification control.")
        identities.add(identity)
        target, clip = rect(control["rect"]), rect(control["clip"])
        require(clip[0] >= 0 and clip[1] >= 0 and clip[0] + clip[2] <= viewport[0] + 0.001
                and clip[1] + clip[3] <= viewport[1] + 0.001, "Control clip is outside its root viewport.")
        for field in ("visible", "enabled", "selected"):
            require(type(control[field]) is bool, "Nonboolean qualification control state.")
        require(not control["selected"] or role == "select", "An action control claims card selection.")
        if control["visible"]:
            require(target[2] > 0 and target[3] > 0 and clip[2] > 0 and clip[3] > 0
                    and target[0] < clip[0] + clip[2] and target[0] + target[2] > clip[0]
                    and target[1] < clip[1] + clip[3] and target[1] + target[3] > clip[1],
                    "Visible control has no area in its clip.")
    require(sum(control["selected"] for control in controls) == value["selectedCount"],
            "Observed selection count disagrees with hand slots.")
    return value


def stable_state(value):
    return {field: item for field, item in value.items() if field not in ("request", "sequence", *TIMES)}


def find_control(value, role, slot=-1):
    matches = [control for control in value["controls"] if (control["role"], control["slot"]) == (role, slot)]
    require(len(matches) == 1, "The requested engine control is absent or ambiguous.")
    return matches[0]


def touch_point(value, control):
    require(control["visible"] and control["enabled"] and encloses(control["clip"], control["rect"]),
            "Engine touch target is hidden, disabled or clipped.")
    surface, viewport = value["surface"], value["viewport"]
    x, y, width, height = control["rect"]
    scales = [surface[index + 2] / viewport[index] for index in (0, 1)]
    require(width * scales[0] >= 8 and height * scales[1] >= 8, "Engine target is smaller than safe touch geometry.")
    point = [int(surface[0] + (x + width / 2) * scales[0]), int(surface[1] + (y + height / 2) * scales[1])]
    require(surface[0] < point[0] < surface[0] + surface[2] and surface[1] < point[1] < surface[1] + surface[3],
            "Mapped engine touch is outside the native surface.")
    return point


def scroll_gesture(value, control):
    require(control["enabled"], "Disabled engine control cannot be made actionable by scrolling.")
    target, clip = control["rect"], control["clip"]
    require(clip[2] >= 32 and clip[3] >= 32 and target[2] > 0 and target[3] > 0
            and target[2] <= clip[2] and target[3] <= clip[3], "Control cannot fit its actual scroll clip.")
    for axis in (1, 0):
        if target[axis] < clip[axis]:
            direction, gap = 1, clip[axis] - target[axis]
            break
        if target[axis] + target[axis + 2] > clip[axis] + clip[axis + 2]:
            direction, gap = -1, target[axis] + target[axis + 2] - clip[axis] - clip[axis + 2]
            break
    else:
        raise ObservationFailure("A hidden control inside its clip cannot be recovered by a swipe.")
    distance = min(clip[axis + 2] / 2, 250, gap + min(16, (clip[axis + 2] - target[axis + 2]) / 2))
    start = [clip[0] + clip[2] / 2, clip[1] + clip[3] / 2]
    end = start.copy()
    start[axis] -= direction * distance / 2
    end[axis] += direction * distance / 2
    surface, viewport = value["surface"], value["viewport"]
    scales = [surface[index + 2] / viewport[index] for index in (0, 1)]
    start, end = ([int(surface[index] + point[index] * scales[index]) for index in (0, 1)]
                  for point in (start, end))
    logical_distance = abs(end[axis] - start[axis]) / scales[axis]
    require(0 < logical_distance <= 251, "Swipe distance is empty or unbounded.")
    duration = max(350, math.ceil(logical_distance / 250 * 1000))
    require(duration <= 1004, "Swipe duration exceeds its geometry budget.")
    return start, end, duration


def fresh_for_input(observation, current, now):
    require(now >= observation["requested_host_time"] and now - observation["requested_host_time"] < MAX_INPUT_AGE_SECONDS,
            "Qualification observation expired before real input.")
    require(current == observation["value"], "Published request/state/geometry changed before real input.")


class EngineObservationProbe:
    """Explicit diagnostic refreshes around real adb touch input in one admitted child lifetime."""

    def __init__(self, smoke, platform, mode, pid, task):
        self.smoke, self.platform, self.mode, self.pid, self.task = smoke, platform, mode, pid, task
        self.prefix = f"{mode}-engine"
        self.serial = 0
        self.last_request, self.last_sequence = 0, -1
        self.owner = None
        self.play_attempted = False
        self._owner()

    def _name(self, suffix):
        self.serial += 1
        return f"{self.prefix}-{self.serial:04d}-{suffix}"

    def _owner(self):
        state = self.smoke.state()
        self.smoke.require_shell(state)
        require(state["renderer_pids"] == [self.pid] and self.smoke.matches_activity(state, NATIVE_COMPONENT)
                and state["foreground"]["task_id"] == self.task, "Engine child/task ownership changed.")
        renderer = [item for item in state["processes"] if item["name"] == PACKAGE + ":godot"]
        require(len(renderer) == 1 and renderer[0]["pid"] == self.pid
                and renderer[0]["uid"] == self.smoke.shell_identity["uid"], "Engine process UID/PID changed.")
        activity = (self.smoke.output / "logs/last-activity.log").read_text()
        window = self.smoke.adb("shell", "dumpsys", "window", "displays")
        name = self._name("owner")
        self.smoke.write_text(f"logs/{name}-window.log", window)
        records, resumed = self.platform.activity_records(activity)
        display = self.platform.window_display(window)
        focus = self.platform.attributed_focus(records, resumed, display)
        require(focus is not None and focus["component"] == NATIVE_COMPONENT and focus["task_id"] == self.task
                and focus.get("lifecycle_state") == "RESUMED" and focus.get("visible_requested") is True
                and focus.get("visible") is True and focus.get("client_visible") is True,
                "Exact resumed Activity and focused native window were not established.")
        owner = {"renderer": renderer[0], "task": self.task, "record": focus["record_id"],
                 "user": focus["user_id"], "window": focus["window"]["window_id"],
                 "configuration": focus["configuration"], "display_size": display["size"], "rotation": display["rotation"]}
        require(self.owner is None or owner == self.owner, "Native focus, configuration or lifetime changed during engine input.")
        self.owner = owner
        self.smoke.write_json(f"logs/{name}.json", owner)
        return owner

    def _node(self, root):
        require(self.smoke.native_controls(root) is not None, "Native Ready/cover/Standard controls changed.")
        nodes = [node for node in root.iter("node") if node.get("package") == PACKAGE and node.get("resource-id") == RESOURCE]
        require(len(nodes) == 1, "Qualification-only refresh action is absent or ambiguous.")
        node = nodes[0]
        require(node.get("class") == "android.widget.TextView" and node.get("text") == "Table ready."
                and node.get("clickable") == "true" and node.get("enabled") == "true" and self.smoke.visible(node),
                "Qualification refresh action is not the current native status view.")
        return node

    def _parse(self, raw):
        value = parse(raw, self.mode, self.owner["display_size"])
        bounds = self.owner["configuration"]["bounds"]
        require(encloses([bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1]], value["surface"]),
                "Render surface escaped its focused Activity bounds.")
        return value

    def refresh(self, deadline):
        for _ in range(6):
            require(time.monotonic() < deadline, "Explicit diagnostic refresh did not settle within its budget.")
            self._owner()
            root = self.smoke.dump_ui(deadline)
            node = self._node(root)
            prior = self._parse(node.get("content-desc")) if node.get("content-desc") else None
            request_floor = max(self.last_request, counter(prior["request"]) if prior else 0)
            sequence_floor = max(self.last_sequence, counter(prior["sequence"]) if prior else -1)
            self._owner()
            requested = time.monotonic()
            self.smoke.tap_node(node, "qualification-observation-refresh")
            for _ in range(2):
                root = self.smoke.dump_ui(min(deadline, requested + MAX_INPUT_AGE_SECONDS))
                node = self._node(root)
                raw = node.get("content-desc")
                if not raw:
                    continue
                value = self._parse(raw)
                if counter(value["request"]) <= request_floor or counter(value["sequence"]) <= sequence_floor:
                    continue
                self._owner()
                observation = {"value": value, "requested_host_time": requested, "owner": self.owner}
                fresh_for_input(observation, value, time.monotonic())
                self.last_request, self.last_sequence = counter(value["request"]), counter(value["sequence"])
                observation["receipt"] = self.smoke.retain_standard_ui(self._name("observation"), value)
                return observation
        raise ObservationFailure("No fresh, correlated production observation followed explicit refresh.")

    def settled(self, predicate, seconds=60):
        deadline = time.monotonic() + seconds
        previous = None
        for _ in range(12):
            current = self.refresh(deadline)
            value = current["value"]
            if predicate(value):
                if (previous is not None and stable_state(previous["value"]) == stable_state(value)
                        and value["capturedUptimeMs"] - previous["value"]["capturedUptimeMs"] >= 200):
                    return current
                previous = current
            else:
                previous = None
            require(time.monotonic() < deadline, "Engine local-state/geometry observation did not settle.")
        raise ObservationFailure("Engine local-state/geometry observation exceeded its finite refresh count.")

    def _before_input(self, observation, role, slot, coordinates, action):
        self._owner()
        root = self.smoke.dump_ui(observation["requested_host_time"] + MAX_INPUT_AGE_SECONDS)
        current = self._parse(self._node(root).get("content-desc"))
        self._owner()
        fresh_for_input(observation, current, time.monotonic())
        name = self._name(action)
        receipt = self.smoke.retain_standard_ui(name, {"action": action, "role": role, "slot": slot,
                                                       "coordinates": coordinates, "observation": current})
        fresh_for_input(observation, current, time.monotonic())
        return receipt

    def tap(self, role, predicate, slot=-1):
        require(role in ("reveal", "select", "play"), "This practice scenario does not admit that engine action.")
        require(role != "play" or not self.play_attempted, "An uncertain Play must never be retried.")
        input_floor = -1
        deadline = time.monotonic() + 180
        for attempt in range(9):
            remaining = deadline - time.monotonic()
            require(remaining > 0, "Engine target input exceeded its finite action budget.")
            observation = self.settled(lambda value: predicate(value) and counter(value["input"]) > input_floor,
                                       seconds=min(60, remaining))
            value = observation["value"]
            control = find_control(value, role, slot)
            if control["visible"] and control["enabled"] and encloses(control["clip"], control["rect"]):
                point = touch_point(value, control)
                receipt = self._before_input(observation, role, slot, {"point": point}, "tap")
                if role == "play":
                    self.play_attempted = True  # Set before transport; timeout does not authorize a retry.
                self.smoke.adb("shell", "input", "tap", *(str(part) for part in point), timeout=10)
                return {"before": value, "input_xml": receipt, "point": point}
            require(attempt < 8, "Engine target could not be reached with eight bounded corrective swipes.")
            start, end, duration = scroll_gesture(value, control)
            self._before_input(observation, role, slot, {"start": start, "end": end, "duration_ms": duration}, "swipe")
            self.smoke.adb("shell", "input", "swipe", *(str(part) for part in (*start, *end, duration)), timeout=10)
            input_floor = counter(value["input"])
        raise ObservationFailure("Engine target could not be reached with eight bounded corrective swipes.")
