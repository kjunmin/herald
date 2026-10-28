package dev.hermeskotlin.ui.workspace

import android.graphics.Bitmap
import android.net.Uri
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.currentStateAsState
import com.composeunstyled.Text

@Composable
internal actual fun RemoteBrowser(url: String, active: Boolean, modifier: Modifier) {
    var failure by remember(url) { mutableStateOf<String?>(null) }
    val origin = remember(url) { Uri.parse(url) }
    val lifecycleState by LocalLifecycleOwner.current.lifecycle.currentStateAsState()
    val visible = active && lifecycleState.isAtLeast(Lifecycle.State.STARTED)
    val currentActive by rememberUpdatedState(visible)
    Box(modifier) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                WebView(context).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = false
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.setSupportMultipleWindows(false)
                    settings.cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                            val target = request.url
                            return target.scheme != origin.scheme || target.host != origin.host || target.port != origin.port || target.path !in listOf("", "/")
                        }
                        override fun onPageStarted(view: WebView, target: String?, favicon: Bitmap?) { failure = null }
                        override fun onPageFinished(view: WebView, target: String?) {
                            view.evaluateJavascript("window.heraldSetActive?.($currentActive)", null)
                        }
                        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                            if (request.isForMainFrame) failure = "Cannot reach the Mac companion. Check its process, Wi-Fi address and port 4318. Open Connection to retry."
                        }
                    }
                    loadUrl(url)
                }
            },
            update = {
                if (visible) it.onResume() else it.onPause()
                it.evaluateJavascript("window.heraldSetActive?.($visible)", null)
            },
            onRelease = { it.stopLoading(); it.destroy() },
        )
        failure?.let { Text(it) }
    }
}
