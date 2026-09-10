package dev.partydeck.godot.compare

import android.app.Activity
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import java.util.concurrent.Executors

/** Native, engine-free access to each bundled notice and exact offline source file. */
class NoticesActivity : Activity() {
    private val reader = Executors.newSingleThreadExecutor()
    private lateinit var page: LinearLayout
    private var showingDocument = false
    private var selection = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(16), dp(20), dp(24))
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(button(R.string.back, R.id.exit_game) {
                if (showingDocument) showIndex() else finish()
            })
            addView(ScrollView(this@NoticesActivity).apply { addView(page) },
                LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(root)
        applySafeInsets(root)
        showIndex()
    }

    private fun showIndex() {
        showingDocument = false
        selection += 1
        page.removeAllViews()
        page.addView(label(getString(R.string.native_notices), 24f))
        // Source-availability notes remain reachable without scrolling past large license texts.
        val first = listOf("README.txt", "GODOT_CA_CERTIFICATES_SOURCE.txt", "font_notices.txt")
        val files = assets.list("notices").orEmpty().sortedWith(compareBy<String> {
            first.indexOf(it).let { index -> if (index < 0) first.size else index }
        }.thenBy { it })
        if (files.isEmpty()) page.addView(label(getString(R.string.native_notices_unavailable)))
        files.forEach { file ->
            page.addView(Button(this).apply {
                text = file
                isAllCaps = false
                minHeight = dp(48)
                setOnClickListener { showDocument(file) }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
    }

    private fun showDocument(file: String) {
        showingDocument = true
        val request = ++selection
        page.removeAllViews()
        page.addView(label(file, 20f))
        val content = label(getString(R.string.notices_loading)).apply { setTextIsSelectable(true) }
        page.addView(content)
        reader.execute {
            val text = runCatching {
                assets.open("notices/$file").bufferedReader().use { it.readText() }
            }.getOrDefault("")
            runOnUiThread {
                if (!isFinishing && !isDestroyed && request == selection) {
                    content.text = text.ifEmpty { getString(R.string.native_notices_unavailable) }
                }
            }
        }
    }

    override fun onDestroy() {
        selection += 1
        reader.shutdownNow()
        super.onDestroy()
    }
}
