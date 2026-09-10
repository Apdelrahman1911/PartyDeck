"""Fail-closed parsers for Android 16 dumps; host tests are not device evidence.

See proposal.md and source-provenance.json for the exact upstream contracts.
These observers do not alter the accepted session checker's focus parser.
"""

import re


class ObservationFailure(RuntimeError):
    pass


class Unavailable(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ObservationFailure(message)


def one(pattern, value, label, flags=0):
    matches = list(re.finditer(pattern, value, flags))
    require(len(matches) == 1, f"Expected one {label}; observed {len(matches)}.")
    return matches[0]


def component(value):
    require(re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", value), "Invalid Activity component.")
    package, activity = value.split("/", 1)
    return package + "/" + (package + activity if activity.startswith(".") else activity)


RECORD = re.compile(r"ActivityRecord\{([0-9a-f]+)\s+u(\d+)\s+([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)\s+t(\d+)(?:[^{}\n]*)\}")


def activity_identity(value, display_id=0):
    match = one(RECORD.pattern, value, "ActivityRecord")
    return dict(record_id=match[1], user_id=int(match[2]), component=component(match[3]),
                task_id=int(match[4]), display_id=display_id)


def rectangle(value):
    match = one(r"Rect\((-?\d+),\s*(-?\d+)\s*-\s*(-?\d+),\s*(-?\d+)\)", value, "rectangle")
    bounds = [int(field) for field in match.groups()]
    require(bounds[2] > bounds[0] and bounds[3] > bounds[1], "Rectangle has no positive area.")
    return bounds


def size(bounds):
    return [bounds[2] - bounds[0], bounds[3] - bounds[1]]


def configuration(value):
    font = one(r"^\{([0-9]+(?:\.[0-9]+)?)\s", value, "font scale")
    orientation = one(r"\s(land|port)\s", value, "defined Activity orientation")
    direction = one(r"\s(ldltr|ldrtl)\s", value, "layout direction")
    result = dict(font_scale=float(font[1]), orientation=orientation[1], layout_direction=direction[1])
    for key, pattern in (("width_dp", r"\sw(\d+)dp\s"), ("height_dp", r"\sh(\d+)dp\s"),
                         ("density_dpi", r"\s(\d+)dpi\s")):
        result[key] = int(one(pattern, value, key)[1])
        require(result[key] > 0, f"Undefined {key}.")
    result["bounds"] = rectangle(one(r"\bmBounds=(Rect\([^\n)]+\))", value, "Activity bounds")[1])
    result["window_size"] = size(result["bounds"])
    result["windowing_mode"] = one(r"\bmWindowingMode=([a-z-]+)\b", value, "windowing mode")[1]
    result["display_rotation"] = rotation_name(one(r"\bmDisplayRotation=(ROTATION_\d+)\b", value, "Activity display rotation")[1])
    require(result["font_scale"] > 0, "Undefined font scale.")
    return result


def rotation_name(value):
    names = {"ROTATION_0": 0, "ROTATION_90": 1, "ROTATION_180": 2, "ROTATION_270": 3}
    require(value in names, "Unrecognized rotation value.")
    return names[value]


def activity_records(value):
    """Attribute CurrentConfiguration to its full historical Activity block.

    Resumed lines are retained separately; they are never chosen by list order.
    """
    display = None
    records, resumed, current = [], [], None
    current_indent = None
    saw_default = False
    for line in value.splitlines():
        header = re.match(r"^Display #(\d+) \(activities from top to bottom\):", line)
        if header:
            display, current, current_indent = int(header[1]), None, None
            saw_default |= display == 0
        if display is None:
            continue
        if re.match(r"^\s+Resumed:\s", line):
            resumed.append(activity_identity(line, display))
        # dumpHistoryList prints '* Hist #N: ActivityRecord{...}'.
        if re.match(r"^\s*\*?\s*Hist #\d+:\s+ActivityRecord\{", line):
            current = activity_identity(line, display)
            current_indent = len(line) - len(line.lstrip())
            records.append(current)
        elif current is not None:
            # A Fin/Stop list or the next task summary is outside this full
            # Activity block. Its configuration must never attach to this one.
            if line.strip() and len(line) - len(line.lstrip()) <= current_indent:
                current, current_indent = None, None
                continue
            match = re.match(r"^\s+CurrentConfiguration=(.*)$", line)
            if match:
                require("configuration" not in current, "Duplicate CurrentConfiguration in an Activity block.")
                current["configuration"] = configuration(match[1])
            match = re.match(r"^\s+app=ProcessRecord\{[^{} ]+\s+(\d+):([^/\s]+)/[^{}]+\}", line)
            if match:
                current.update(app_pid=int(match[1]), process_name=match[2])
            match = re.match(r"^\s+state=([A-Z_]+)\s", line)
            if match:
                current["lifecycle_state"] = match[1]
            match = re.match(r"^\s+mVisibleRequested=(true|false) mVisible=(true|false) mClientVisible=(true|false)\b", line)
            if match:
                current.update(visible_requested=match[1] == "true", visible=match[2] == "true",
                               client_visible=match[3] == "true")
    require(saw_default, "No verified default display in Activity dump.")
    keyed = {}
    for record in records:
        key = (record["display_id"], record["record_id"])
        require(key not in keyed, "Duplicate full Activity record.")
        keyed[key] = record
    return records, resumed


def window_display(value):
    headers = list(re.finditer(r"^\s*Display: mDisplayId=(\d+)[^\n]*$", value, re.M))
    selected = [(match.end(), headers[i + 1].start() if i + 1 < len(headers) else len(value))
                for i, match in enumerate(headers) if match[1] == "0"]
    require(len(selected) == 1, "Expected one default-display window section.")
    section = value[slice(*selected[0])]
    dimensions = one(r"\bcur=(\d+)x(\d+)\b", section, "actual default-display size")
    rotation = one(r"^\s+mRotation=([0-3]) mDeferredRotationPauseCount=\d+\s*$", section,
                   "actual DisplayRotation", re.M)
    result = dict(display_id=0, size=[int(dimensions[1]), int(dimensions[2])], rotation=int(rotation[1]))
    for label, field in (("landscape", "mLandscapeRotation"), ("seascape", "mSeascapeRotation"),
                         ("portrait", "mPortraitRotation")):
        result[label] = rotation_name(one(rf"\b{field}=(ROTATION_\d+)\b", section, label + " rotation")[1])
    focus = one(r"^\s*mCurrentFocus=(.*)$", section, "current window focus", re.M)[1]
    app = one(r"^\s*mFocusedApp=(.*)$", section, "focused app", re.M)[1]
    result["focused_app"] = None if app == "null" else activity_identity(app)
    result["window"] = None
    if focus != "null":
        match = re.fullmatch(r"Window\{([0-9a-f]+) u(\d+) (.+)\}", focus)
        require(match, "Unrecognized current-focus window.")
        title = match[3]
        result["window"] = dict(window_id=match[1], user_id=int(match[2]), title=title,
                                input_name=match[1] + " " + title)
        # A system window, exiting window, or a differently titled dialog cannot
        # prove the Activity's exact foreground window for this runner.
        if re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", title):
            result["window"]["component"] = component(title)
    return result


def attributed_focus(records, resumed, display):
    focused, window = display["focused_app"], display["window"]
    if focused is None or window is None or window.get("component") != focused["component"]:
        return None
    if window["user_id"] != focused["user_id"]:
        return None
    if focused not in resumed:
        return None
    matching = [record for record in records if all(record.get(key) == item for key, item in focused.items())]
    require(len(matching) <= 1, "Ambiguous full record for focused app.")
    if not matching or "configuration" not in matching[0]:
        return None
    return matching[0] | {"window": window}


def tracked_changes(before, after):
    """Position, windowing-mode labels and half-turns alone promise no fallback."""
    fields = ("orientation", "width_dp", "height_dp", "density_dpi", "font_scale",
              "layout_direction", "window_size")
    return {field: {"before": before[field], "after": after[field]}
            for field in fields if before[field] != after[field]}


def stable_key(state):
    focus = state["foreground"]
    return None if focus is None else (focus["record_id"], focus["task_id"],
                                      focus["configuration"], focus["window"], state["display"]["rotation"])


def section(value, label):
    header = one(rf"^([ \t]*){re.escape(label)}:[^\n]*$", value, label + " section", re.M)
    indent = len(header[1])
    tail = value[header.end():]
    end = len(tail)
    for match in re.finditer(r"^([ \t]*)\S", tail, re.M):
        if len(match[1]) <= indent:
            end = match.start()
            break
    return value[header.start():header.end()] + tail[:end]


def input_clock(value):
    """RecentQueue supplies only a clock interval, NEVER delivery evidence.

    Android's one currentTime snapshot and integer ns2ms age give an interval
    less than 1 ms wide. Non-debuggable platform builds omit eventTime entirely.
    """
    recent = section(value, "RecentQueue")
    intervals = []
    for line in recent.splitlines()[1:]:
        if not re.search(r"\b(?:KeyEvent|MotionEvent)\b", line):
            continue
        match = re.search(r"\beventTime=(\d+),.*\bage=(-?\d+)ms\s*$", line)
        if match is None:
            raise Unavailable("Platform RecentQueue omits precise event times; held-input deadline is unobservable.")
        timestamp, age = map(int, match.groups())
        require(timestamp > 0 and age >= 0, "Negative age or undefined InputDispatcher event time.")
        intervals.append((timestamp + age * 1_000_000, timestamp + (age + 1) * 1_000_000))
    if not intervals:
        raise Unavailable("RecentQueue has no precise clock sample; held-input deadline is unobservable.")
    lower, upper = max(item[0] for item in intervals), min(item[1] for item in intervals)
    require(lower < upper, "InputDispatcher clock intervals do not intersect.")
    return dict(lower_ns=lower, upper_exclusive_ns=upper, samples=len(intervals),
                domain="InputDispatcher CLOCK_MONOTONIC; eventTime + integer age, clock evidence only")


def before_up(clock, held, duration_ms):
    require(type(duration_ms) is int and 10_000 <= duration_ms <= 45_000, "Invalid bounded hold duration.")
    earliest_up = held["down_time_ns"] + duration_ms * 1_000_000
    require(clock["lower_ns"] >= held["down_time_ns"], "Clock sample precedes the held DOWN.")
    require(clock["upper_exclusive_ns"] <= earliest_up,
            "The full device clock interval does not precede the scheduled matching UP.")
    return dict(earliest_up_ns=earliest_up, remaining_lower_bound_ns=earliest_up - clock["upper_exclusive_ns"])


def touch_rows(value):
    """Consume the whole touch section; this runner supports one device per row.

    PrintTools.dumpMap emits extra devices on continuation lines. Such a row,
    unknown state, hovering or a multi-pointer stream is rejected conservatively
    instead of being silently ignored by the single-finger observer.
    """
    touch = section(value, "TouchStatesByDisplay")
    if re.fullmatch(r"\s*TouchStatesByDisplay: <no displays touched>\s*", touch):
        return []
    lines = touch.splitlines()
    require(lines[0].strip() == "TouchStatesByDisplay:", "Unrecognized touch-state section header.")
    rows, displays, display, empty = [], set(), None, False
    for line in lines[1:]:
        if not line.strip():
            continue
        header = re.fullmatch(r"\s*(\d+)\s*:\s*Windows:( <none>)?\s*", line)
        if header:
            display, empty = int(header[1]), header[2] is not None
            require(display not in displays, "Duplicate display in touch-state dump.")
            displays.add(display)
            continue
        require(display is not None and not empty, "Touch row lacks a nonempty display section.")
        row = re.fullmatch(r"\s*\d+\s*:\s*name='([^'\n]+)', targetFlags=(.*?), forwardingWindowToken=([^,\s]+), mDeviceStates=(.*?)\s*", line)
        require(row is not None, "Unparsed touch-state row or additional device continuation.")
        state = re.fullmatch(
            r"(-?\d+):\[touchingPointers=(\[\]|\[Pointer\(id=(\d+), ([A-Z_]+)\)\]), "
            r"downTimeInTarget=(\d+|<not set>), hoveringPointers=\[\], pilferingPointerIds=<none>\]", row[4])
        require(state is not None, "Unparsed or unsupported complete device touch state.")
        rows.append(dict(display_id=display, name=row[1], target_flags=row[2], device_id=int(state[1]),
                         pointer_id=int(state[3]) if state[3] is not None else None,
                         tool=state[4], down_time_ns=int(state[5]) if state[5].isdigit() else None))
    require(displays, "Touch section has no recognized display state.")
    for item in displays:
        # A bare 'Windows:' without rows is not an explicit absence observation.
        require(any(row["display_id"] == item for row in rows)
                or re.search(rf"^\s*{item}\s*:\s*Windows: <none>\s*$", touch, re.M),
                "Touch display state is incomplete.")
    return rows


def no_active_touch(value):
    return not any(row["pointer_id"] is not None for row in touch_rows(value))


def held_touch(value, window, pid, uid, point):
    """Match target ownership, live touch state and a dispatched motion memento."""
    name = window["input_name"]
    info = one(rf"^\s*\d+: name={re.escape(name)}, id=\d+, displayId=0, ([^\n]+)$", value,
               "target InputDispatcher WindowInfo", re.M)
    require(int(one(r"\bownerPid=(\d+)\b", info[1], "input window PID")[1]) == pid
            and int(one(r"\bownerUid=(\d+)\b", info[1], "input window UID")[1]) == uid,
            "Held touch window does not belong to the exact renderer process.")
    frame = [int(item) for item in one(r"\bframe=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", info[1], "input frame").groups()]
    require(frame[0] < point[0] < frame[2] and frame[1] < point[1] < frame[3], "Observed control point is outside the target input frame.")
    require(not re.search(r"\b(NOT_VISIBLE|NOT_TOUCHABLE|DROP_INPUT)\b", info[1]), "Target window cannot accept this touch.")
    targets = [row for row in touch_rows(value) if row["display_id"] == 0 and row["name"] == name]
    require(len(targets) == 1, "No sole live touch target on the default display.")
    target = targets[0]
    require(re.search(r"\bFOREGROUND\b", target["target_flags"]), "Touch target lacks FOREGROUND delivery.")
    device, pointer, down = target["device_id"], target["pointer_id"], target["down_time_ns"]
    require(pointer == 0 and target["tool"] == "FINGER" and down is not None and down > 0,
            "Held input is not the injected single-finger stream.")
    connections = section(value, "Connections")
    header = one(rf"^([ \t]*)\d+: channelName='{re.escape(name)}', status=NORMAL, monitor=false, responsive=true\s*$",
                 connections, "responsive target connection", re.M)
    tail = connections[header.end():]
    next_connection = re.search(r"^\s*\d+: channelName=", tail, re.M)
    block = tail[:next_connection.start()] if next_connection else tail
    # Motion mementos are tracked before publication. A blocked publication can
    # leave a NORMAL/responsive connection with a pending OutboundQueue.
    require(not re.search(r"^[ \t]*OutboundQueue:", block, re.M),
            "Target connection still has outbound input awaiting publication.")
    state = one(r"^[ \t]*InputState: mMotionMementos: ([^\n]+)$", block, "connection motion state", re.M)
    require(not block[state.end():].strip(), "Unparsed continuation after connection motion state.")
    memento = re.fullmatch(r"\{deviceId=(-?\d+), hovering=([01]), downTime=(\d+)\},\s*", state[1])
    require(memento is not None and memento.groups() == (str(device), "0", str(down)),
            "Complete connection motion state does not match the sole target touch.")
    return dict(device_id=device, pointer_id=pointer, down_time_ns=down, input_window_name=name,
                renderer_pid=pid, uid=uid, point=list(point), input_frame=frame,
                evidence="Matching live target touch and connection motion memento with no pending outbound input")


def split_capability(multi, split, help_text):
    require(multi.strip() in ("true", "false") and split.strip() in ("true", "false"), "Unrecognized Android multi-window capability output.")
    if multi.strip() != "true" or split.strip() != "true":
        raise Unavailable("Android advertises no multi-window/split-screen support.")
    match = re.search(r"^  splitscreen\s*$([\s\S]*?)(?=^  \S|\Z)", help_text, re.M)
    if match is None or not all(command in match[1] for command in
                                ("moveToSideStage <taskId> <SideStagePosition>", "exitSplitScreen <taskId>")):
        raise Unavailable("Platform supports split-screen but does not advertise the verified WM Shell automation route.")
    return {"platform_support": True, "automation_route": "wm shell splitscreen"}


def split_pair(records, first_task, second_task, display_size):
    panes = []
    for task in (first_task, second_task):
        matches = [item for item in records if item["display_id"] == 0 and item["task_id"] == task
                   and item.get("visible") and item.get("client_visible") and "configuration" in item]
        require(len(matches) == 1, "Split pane lacks one actually visible Activity.")
        require(matches[0]["configuration"]["windowing_mode"] == "multi-window", "Activity did not enter actual multi-window mode.")
        panes.append(matches[0])
    require(first_task != second_task, "Split panes refer to the same task.")
    a, b = [item["configuration"]["bounds"] for item in panes]
    for bounds in (a, b):
        require(0 <= bounds[0] < bounds[2] <= display_size[0] and 0 <= bounds[1] < bounds[3] <= display_size[1],
                "Split pane lies outside the actual display.")
        require(size(bounds) != display_size, "Split pane still occupies the full display.")
    require(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], "Split pane bounds overlap.")
    return panes
