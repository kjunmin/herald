package dev.hermeskotlin.ui.workspace

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
