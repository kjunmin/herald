package dev.hermeskotlin.ui.workspace

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** Displays only the companion controller, never arbitrary web pages or a native JS bridge. */
@Composable
internal expect fun RemoteBrowser(url: String, active: Boolean, modifier: Modifier = Modifier)
