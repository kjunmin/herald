package dev.hermeskotlin.ui.workspace

import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.composeunstyled.Text
import com.composeunstyled.theme.Theme
import dev.hermeskotlin.core.chat.ChatMessage
import dev.hermeskotlin.core.storage.KeyValueStore
import dev.hermeskotlin.designsystem.*
import dev.hermeskotlin.designsystem.components.Button
import dev.hermeskotlin.designsystem.components.ButtonSize
import dev.hermeskotlin.designsystem.components.ButtonVariant
import dev.hermeskotlin.designsystem.components.TextField
import dev.hermeskotlin.ui.chat.ChatViewModel
import kotlinx.coroutines.launch
import org.koin.compose.koinInject

/** Keep chat at a stable composition position across folding, resizing and pane switches. */
@Composable
internal fun FoldWorkspace(gateway: String, chat: ChatViewModel, content: @Composable () -> Unit) {
    var pane by rememberSaveable { mutableStateOf("Chat") }
    val state by chat.state.collectAsStateWithLifecycle()
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val availableWidth = maxWidth
        val split = splitWorkspace(availableWidth.value)
        val selectedPane = if (split && pane == "Chat") "Browser" else pane
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
                .padding(horizontal = 8.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                (if (split) listOf("Browser", "Activity") else listOf("Chat", "Browser", "Activity")).forEach { tab ->
                    Button(tab, { pane = tab }, size = ButtonSize.Small,
                        variant = if (selectedPane == tab) ButtonVariant.Secondary else ButtonVariant.Ghost)
                }
                Spacer(Modifier.weight(1f))
                if (state.running) Button("Stop", chat::interrupt, size = ButtonSize.Small, variant = ButtonVariant.Danger)
            }
            val chatWidth = if (split) availableWidth * 0.45f else if (pane == "Chat") availableWidth else 0.dp
            Row(Modifier.weight(1f).fillMaxWidth()) {
                Box(Modifier.width(chatWidth).fillMaxHeight().clipToBounds()) { content() }
                Column(Modifier.weight(1f).fillMaxHeight().clipToBounds().background(Theme[colors][surface2])) {
                    // Both remain composed: hiding a pane never clears chat or the browser session.
                    Box(Modifier.fillMaxWidth().weight(if (pane != "Activity") 1f else 0.0001f)) {
                        BrowserPane(gateway, active = pane != "Activity" && (split || pane == "Browser"))
                    }
                    if (pane == "Activity") {
                        val tools = state.messages.filterIsInstance<ChatMessage.Assistant>().flatMap { it.tools }
                        LazyColumn(Modifier.weight(1f).padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            item { Text("Command and browser activity", color = Theme[colors][text]) }
                            if (tools.isEmpty()) item { Text("Ask Hermes to research a flight or run a command. Tool calls and their results appear here.", color = Theme[colors][textSecondary]) }
                            items(tools.asReversed()) { tool ->
                                Column(Modifier.fillMaxWidth().background(Theme[colors][surface3]).padding(12.dp)) {
                                    Text("${if (tool.running) "Running" else if (tool.failed) "Failed" else "Finished"} · ${tool.name}", color = Theme[colors][text])
                                    tool.input?.let { Text(it.take(8000), color = Theme[colors][textSecondary]) }
                                    (tool.output ?: tool.summary ?: tool.detail)?.let { Text(it.take(16000), color = Theme[colors][textSecondary]) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun BrowserPane(gateway: String, active: Boolean) {
    val store = koinInject<KeyValueStore>()
    val scope = rememberCoroutineScope()
    val key = "fold.companion.$gateway"
    var url by remember(key) { mutableStateOf<String?>(null) }
    var editing by remember(key) { mutableStateOf(false) }
    var error by remember(key) { mutableStateOf<String?>(null) }
    val field = remember(key) { TextFieldState() }
    LaunchedEffect(key) { url = store.get(key)?.takeIf(::validCompanionUrl) }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Mac Chrome", modifier = Modifier.weight(1f), color = Theme[colors][text])
            Button(if (url == null) "Connect" else "Connection", { editing = !editing }, size = ButtonSize.Small, variant = ButtonVariant.Ghost)
        }
        if (url == null || editing) Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Start the Herald Fold companion on your Mac, then paste its phone pairing URL. Hermes must use that companion’s Chrome CDP address.", color = Theme[colors][textSecondary])
            TextField(field, label = "Pairing URL", placeholder = "http://MAC-IP:4318/#token=…", password = true, error = error)
            Button("Save connection", {
                val candidate = field.text.toString().trim()
                if (!validCompanionUrl(candidate)) error = "Use the full http(s) pairing URL, including #token=."
                else scope.launch {
                    try {
                        store.put(key, candidate)
                        url = candidate
                        editing = false
                        field.edit { replace(0, length, "") }
                        error = null
                    } catch (_: Exception) { error = "Could not save the connection. Try again." }
                }
            })
            if (url != null) Button("Forget connection", {
                scope.launch { store.remove(key); url = null; editing = false }
            }, variant = ButtonVariant.Ghost)
        }
        url?.takeIf { !editing }?.let { key(it) { RemoteBrowser(it, active, Modifier.weight(1f).fillMaxWidth()) } }
    }
}
