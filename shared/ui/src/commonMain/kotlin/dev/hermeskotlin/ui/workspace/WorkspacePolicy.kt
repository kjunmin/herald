package dev.hermeskotlin.ui.workspace

import dev.hermeskotlin.core.chat.ChatMessage
import dev.hermeskotlin.core.chat.ChatState
import dev.hermeskotlin.core.chat.ToolActivity
import io.ktor.http.URLProtocol
import io.ktor.http.Url

/** Leave both panes usable on an unfolded phone, including while the keyboard is open. */
internal fun splitWorkspace(widthDp: Float): Boolean = widthDp >= 720f

internal fun validCompanionUrl(value: String): Boolean = runCatching {
    val url = Url(value.trim())
    (url.protocol == URLProtocol.HTTP || url.protocol == URLProtocol.HTTPS) &&
        url.host.isNotBlank() && url.user.isNullOrEmpty() && url.password.isNullOrEmpty() &&
        url.encodedPath in listOf("", "/") && url.parameters.isEmpty() &&
        url.fragment.startsWith("token=") && url.fragment.removePrefix("token=").length >= 32
}.getOrDefault(false)

/** Only the current turn can reveal the browser; queued prompts do not hide an ongoing run. */
internal data class BrowserObservation(val turnKey: String?, val tools: List<ToolActivity>, val browsing: Boolean)

internal fun observeBrowser(state: ChatState): BrowserObservation {
    val prompt = state.messages.indexOfLast { it is ChatMessage.User && !it.queued && !it.pending }
    val replies = if (prompt >= 0) state.messages.drop(prompt + 1).filterIsInstance<ChatMessage.Assistant>()
        else state.messages.filterIsInstance<ChatMessage.Assistant>().takeLast(1)
    val tools = replies.flatMap { it.tools }
    val turnKey = state.messages.getOrNull(prompt)?.key ?: replies.lastOrNull()?.key
    return BrowserObservation(turnKey, tools, state.running && tools.any { isBrowserTool(it.name) })
}

internal fun isBrowserTool(name: String): Boolean {
    val normalized = name.lowercase().substringAfterLast('/').substringAfterLast("__")
    return normalized == "browser" || normalized.startsWith("browser_") || normalized.startsWith("browser.")
}
