package dev.partydeck.godot.bridge

import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import kotlin.test.Test
import kotlin.test.assertFailsWith

/** Checks the newly public platform preflight contract without repeating the bridge suite. */
class BoundedJsonApiReviewTest {
    @Test
    fun callerLimitsCannotDisableTheSharedCeilingAndCountUtf8Bytes() {
        for (limit in listOf(Int.MIN_VALUE, -1, 0, MAX_ENGINE_PAYLOAD_BYTES + 1, Int.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> { validateBoundedJson("{}", limit) }
        }
        // This API checks grammar, not an object schema; a one-byte JSON scalar is valid.
        validateBoundedJson("0", 1)
        assertFailsWith<IllegalArgumentException> { validateBoundedJson("{}", 1) }
        val diagnostic = "\"" + "é".repeat(8_191) + "\""
        validateBoundedJson(diagnostic, 16_384)
        assertFailsWith<IllegalArgumentException> { validateBoundedJson(diagnostic + " ", 16_384) }
        validateBoundedJson(diagnostic + " ", MAX_ENGINE_PAYLOAD_BYTES)
    }

    @Test
    fun publicPreflightRejectsTheFormsAcceptedByPermissivePlatformParsers() {
        for (document in listOf(
            "{'field':1}",
            "/* comment */ {\"field\":1}",
            "// comment\n{\"field\":1}",
            "{\"field\":1,}",
            "{\"field\":1}{}",
            """{"field":1,"\u0066ield":2}""",
            "{\"field\":\"\uD800\"}",
            "{\"field\":/* \" */" + "[".repeat(40) + "0" + "]".repeat(40) + "}",
        )) {
            assertFailsWith<IllegalArgumentException> { validateBoundedJson(document, 16_384) }
        }
        // A valid nested object remains accepted; platform schema checks run afterwards.
        validateBoundedJson("""{"field":{"values":[true,false,null,0,"é"]}}""", 16_384)
    }
}
