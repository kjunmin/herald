package dev.hermeskotlin.ui.workspace

import dev.hermeskotlin.core.chat.ChatMessage
import dev.hermeskotlin.core.chat.ChatState
import dev.hermeskotlin.core.chat.ToolActivity
import kotlin.test.assertEquals
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WorkspacePolicyTest {
    @Test fun coverAndSplitWindowUseTabs() { assertFalse(splitWorkspace(719f)) }
    @Test fun unfoldedUsesTwoPanes() { assertTrue(splitWorkspace(720f)) }
    @Test fun pairingRequiresHttpOriginAndToken() {
        val token = "a".repeat(48)
        assertTrue(validCompanionUrl("http://192.168.0.2:4318/#token=$token"))
        assertFalse(validCompanionUrl("javascript:alert(1)#token=$token"))
        assertFalse(validCompanionUrl("http://192.168.0.2:4318/"))
        assertFalse(validCompanionUrl("http://user:pass@192.168.0.2:4318/#token=$token"))
        assertFalse(validCompanionUrl("http://192.168.0.2:4318/other#token=$token"))
    }
    @Test fun browserTaskRemainsVisibleBetweenToolCalls() {
        val state = ChatState(running = true, messages = listOf(
            ChatMessage.User("prompt", "Find flights"),
            ChatMessage.Assistant("reply", tools = listOf(ToolActivity("navigate", "browser_exec", running = false))),
        ))
        assertTrue(observeBrowser(state).browsing)
    }
    @Test fun previousFlightResearchDoesNotRevealBrowserForNewTask() {
        val state = ChatState(running = true, messages = listOf(
            ChatMessage.User("old", "Flights"),
            ChatMessage.Assistant("old-reply", tools = listOf(ToolActivity("nav", "browser_navigate"))),
            ChatMessage.User("new", "Explain this Japanese word"),
            ChatMessage.Assistant("new-reply", tools = listOf(ToolActivity("shell", "terminal"))),
        ))
        assertFalse(observeBrowser(state).browsing)
        assertEquals("new", observeBrowser(state).turnKey)
    }
    @Test fun queuedPromptDoesNotHideOngoingBrowserTask() {
        val state = ChatState(running = true, messages = listOf(
            ChatMessage.User("active", "Flights"),
            ChatMessage.Assistant("reply", tools = listOf(ToolActivity("nav", "mcp__playwright__browser_click", running = true))),
            ChatMessage.User("queued", "And hotels", queued = true),
        ))
        assertTrue(observeBrowser(state).browsing)
        assertEquals("active", observeBrowser(state).turnKey)
    }
    @Test fun finishedRunNoLongerSignalsAgentControl() {
        val state = ChatState(running = false, messages = listOf(
            ChatMessage.User("prompt", "Flights"),
            ChatMessage.Assistant("reply", tools = listOf(ToolActivity("nav", "browser_exec"))),
        ))
        assertFalse(observeBrowser(state).browsing)
    }
    @Test fun browserFamiliesAreRecognizedWithoutTreatingWebSearchAsBrowserControl() {
        assertTrue(isBrowserTool("browser_exec"))
        assertTrue(isBrowserTool("browser.navigate"))
        assertTrue(isBrowserTool("mcp__playwright__browser_click"))
        assertFalse(isBrowserTool("web_search"))
        assertFalse(isBrowserTool("terminal"))
    }

}
