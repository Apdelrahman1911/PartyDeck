package dev.partydeck.qualification.input;

import android.app.Activity;
import android.app.Instrumentation;
import android.app.UiAutomation;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.MotionEvent;

import org.json.JSONArray;
import org.json.JSONObject;

/** Separate, self-target instrumentation. It never reads or launches PartyDeck. */
public final class ContinuousTouchInstrumentation extends Instrumentation {
    private static final String RESULT_KEY = "partydeckContinuousTouch";
    private static final int AUTOMATION_FLAGS =
            UiAutomation.FLAG_DONT_USE_ACCESSIBILITY
                    | UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES;
    // AOSP InputShellCommand's nominal swipe frequency; actual injection times are used.
    private static final long EVENTS_PER_SECOND = 120;
    private static final long TAIL_MS = 200;

    private Bundle arguments;
    private UiAutomation automation;
    private String requestId = "";
    private String phase = "arguments";
    private String failureClass = "";
    private String releaseFailureClass = "";
    private int x0, y0, x1, y1;
    private long moveMs, startDeadline, stopDeadline;
    private long downTime = -1, downAck = -1, endpointAck = -1;
    private long tailStart = -1, tailEnd = -1, upTime = -1, upAck = -1;
    private int attempted, acknowledged, stationaryMoves;
    private boolean downAttempted, upAttempted, tailCompleted, inputUncertain;
    private float lastX, lastY;

    @Override public void onCreate(Bundle supplied) {
        super.onCreate(supplied);
        arguments = supplied == null ? new Bundle() : new Bundle(supplied);
        start();
    }

    @Override public void onStart() {
        try {
            parseArguments();
            phase = "connect";
            automation = getUiAutomation(AUTOMATION_FLAGS);
            check(automation != null, "Automation connection unavailable");
            // Startup is outside the touch stream. A slow start must not use stale geometry.
            check(SystemClock.uptimeMillis() < startDeadline, "Start deadline expired");
            check(SystemClock.uptimeMillis() + moveMs + TAIL_MS < stopDeadline,
                    "Insufficient input budget");
            downTime = SystemClock.uptimeMillis();
            phase = "down";
            inject(MotionEvent.ACTION_DOWN, x0, y0);
            // The public API synchronizes window transactions before DOWN. Check its completed
            // injection too, so that this internal wait cannot silently extend geometry freshness.
            check(downAck < startDeadline, "DOWN completed after its freshness deadline");
            phase = "moving";
            final long moveEnd = downTime + moveMs;
            long sample = 1;
            while (SystemClock.uptimeMillis() < moveEnd) {
                long due = Math.min(moveEnd, downTime + sample * 1000 / EVENTS_PER_SECOND);
                sleepUntil(due);
                long now = SystemClock.uptimeMillis();
                if (now >= moveEnd) break;
                float fraction = Math.min(1f, (float) (now - downTime) / moveMs);
                inject(MotionEvent.ACTION_MOVE, x0 + (x1 - x0) * fraction,
                        y0 + (y1 - y0) * fraction);
                // Do not replay old scheduled samples in a catch-up burst after a stalled call.
                sample = Math.max(sample + 1,
                        (SystemClock.uptimeMillis() - downTime) * EVENTS_PER_SECOND / 1000 + 1);
            }
            inject(MotionEvent.ACTION_MOVE, x1, y1);
            endpointAck = SystemClock.uptimeMillis();
            phase = "stationary-tail";
            tailStart = endpointAck;
            long tailSample = 0;
            do {
                sleepUntil(Math.min(tailStart + TAIL_MS,
                        tailStart + tailSample * 1000 / EVENTS_PER_SECOND));
                inject(MotionEvent.ACTION_MOVE, x1, y1);
                stationaryMoves++;
                tailSample = Math.max(tailSample + 1,
                        (SystemClock.uptimeMillis() - tailStart) * EVENTS_PER_SECOND / 1000 + 1);
            } while (SystemClock.uptimeMillis() - tailStart < TAIL_MS);
            tailEnd = SystemClock.uptimeMillis();
            check(stationaryMoves >= 2 && tailEnd - tailStart >= TAIL_MS,
                    "Endpoint tail did not complete");
            check(tailEnd < stopDeadline, "Tail exceeded input budget");
            tailCompleted = true;
        } catch (Exception failure) {
            failureClass = failure.getClass().getSimpleName();
        } finally {
            // One terminal release after acknowledged input, including a local scheduling
            // failure before another injection. A false/throwing injection is uncertain and
            // forbids even this release. Process death cannot guarantee that finally executes.
            // A release never turns an earlier failed stroke into a successful one.
            if (downAck >= 0 && !inputUncertain && !upAttempted) {
                try {
                    inject(MotionEvent.ACTION_UP, lastX, lastY);
                } catch (Exception failure) {
                    releaseFailureClass = failure.getClass().getSimpleName();
                }
            }
        }
        boolean ok = failureClass.isEmpty() && releaseFailureClass.isEmpty()
                && !inputUncertain && tailCompleted && upAttempted
                && upAck >= upTime && upAck < stopDeadline;
        Bundle result = new Bundle();
        try {
            JSONObject receipt = new JSONObject();
            receipt.put("schemaVersion", 1);
            receipt.put("requestId", requestId);
            receipt.put("ok", ok);
            receipt.put("phase", ok ? "completed" : phase);
            receipt.put("failureClass", failureClass);
            receipt.put("releaseFailureClass", releaseFailureClass);
            receipt.put("start", new JSONArray(new int[]{x0, y0}));
            receipt.put("end", new JSONArray(new int[]{x1, y1}));
            receipt.put("moveDurationMs", moveMs);
            receipt.put("tailDurationMs", TAIL_MS);
            receipt.put("startDeadlineUptimeMs", startDeadline);
            receipt.put("stopDeadlineUptimeMs", stopDeadline);
            receipt.put("downTimeUptimeMs", downTime);
            receipt.put("downAckUptimeMs", downAck);
            receipt.put("endpointAckUptimeMs", endpointAck);
            receipt.put("tailStartUptimeMs", tailStart);
            receipt.put("tailEndUptimeMs", tailEnd);
            receipt.put("upEventUptimeMs", upTime);
            receipt.put("upAckUptimeMs", upAck);
            receipt.put("eventsAttempted", attempted);
            receipt.put("eventsAcknowledged", acknowledged);
            receipt.put("stationaryMoveEvents", stationaryMoves);
            receipt.put("downAttempted", downAttempted);
            receipt.put("upAttempted", upAttempted);
            receipt.put("tailCompleted", tailCompleted);
            receipt.put("inputUncertain", inputUncertain);
            receipt.put("automationFlags", AUTOMATION_FLAGS);
            receipt.put("pointerCount", 1);
            receipt.put("pointerId", 0);
            receipt.put("inputSource", InputDevice.SOURCE_TOUCHSCREEN);
            result.putString(RESULT_KEY, receipt.toString());
        } catch (Exception failure) {
            ok = false;
            result.putString(RESULT_KEY, "{\"ok\":false,\"phase\":\"receipt-failed\"}");
        }
        // Framework finish disconnects automation and ends only this helper's instrumentation.
        finish(ok ? Activity.RESULT_OK : Activity.RESULT_CANCELED, result);
    }

    private void parseArguments() {
        check(arguments.keySet().equals(java.util.Set.of("request_id", "x0", "y0", "x1", "y1",
                "move_ms", "start_deadline", "stop_deadline")), "Unexpected arguments");
        requestId = arguments.getString("request_id", "");
        check(requestId.matches("[0-9a-f]{32}"), "Invalid request id");
        x0 = coordinate("x0"); y0 = coordinate("y0");
        x1 = coordinate("x1"); y1 = coordinate("y1");
        check(x0 == x1 && y0 > y1, "Only the admitted upward body swipe is supported");
        moveMs = positiveLong("move_ms");
        startDeadline = positiveLong("start_deadline");
        stopDeadline = positiveLong("stop_deadline");
        // The host keeps its existing ten-second input-command cap and shorter sweep remainder.
        check(moveMs + TAIL_MS < 10000 && moveMs < 10000, "Oversized gesture");
        check(startDeadline <= stopDeadline, "Inconsistent deadlines");
    }

    private int coordinate(String key) {
        long value = positiveLong(key);
        check(value <= Integer.MAX_VALUE, "Coordinate overflow");
        return (int) value;
    }

    private long positiveLong(String key) {
        String raw = arguments.getString(key, "");
        check(raw.matches("[1-9][0-9]{0,15}"), "Invalid positive integer");
        return Long.parseLong(raw);
    }

    private void sleepUntil(long due) {
        long remaining = due - SystemClock.uptimeMillis();
        if (remaining > 0) SystemClock.sleep(remaining);
    }

    private void inject(int action, float x, float y) {
        check(!inputUncertain, "Uncertain prior injection forbids further input");
        // A synchronous call may outlast the host command. Even a subsequent true return
        // cannot authorize another injection after its deadline, including terminal UP.
        check(SystemClock.uptimeMillis() < stopDeadline, "Input budget expired");
        MotionEvent.PointerProperties pointer = new MotionEvent.PointerProperties();
        pointer.id = 0;
        pointer.toolType = MotionEvent.TOOL_TYPE_FINGER;
        MotionEvent.PointerCoords coords = new MotionEvent.PointerCoords();
        coords.x = x; coords.y = y;
        coords.pressure = action == MotionEvent.ACTION_UP ? 0f : 1f;
        coords.size = 1f;
        long eventTime = SystemClock.uptimeMillis();
        MotionEvent event = MotionEvent.obtain(downTime, eventTime, action, 1,
                new MotionEvent.PointerProperties[]{pointer}, new MotionEvent.PointerCoords[]{coords},
                0, 0, 1f, 1f, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            // Recheck after allocation too; a local pause must not knowingly submit expired input.
            long submitTime = SystemClock.uptimeMillis();
            check(submitTime < stopDeadline, "Input budget expired before submission");
            check(action != MotionEvent.ACTION_DOWN || submitTime < startDeadline,
                    "Start deadline expired before submission");
            lastX = x; lastY = y;
            attempted++;
            if (action == MotionEvent.ACTION_DOWN) downAttempted = true;
            if (action == MotionEvent.ACTION_UP) { upAttempted = true; upTime = eventTime; }
            // false includes a caught remote failure; it does not prove non-delivery.
            inputUncertain = true;
            check(automation.injectInputEvent(event, true), "Input injection returned false");
            inputUncertain = false;
            acknowledged++;
            if (action == MotionEvent.ACTION_DOWN) downAck = SystemClock.uptimeMillis();
            if (action == MotionEvent.ACTION_UP) upAck = SystemClock.uptimeMillis();
        } finally {
            event.recycle();
        }
    }

    private static void check(boolean valid, String message) {
        if (!valid) throw new IllegalStateException(message);
    }
}
