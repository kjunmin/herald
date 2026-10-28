package dev.hermeskotlin.ui.workspace

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
}
