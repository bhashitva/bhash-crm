// SPDX-License-Identifier: Apache-2.0
class LauncherChecks {
    public static void main(String[] args) {
        check("short", false);
        check("12345678901", false);
        check("123456789012", true);
        check("  exact input  ", true);
        check("\uD83D\uDE00".repeat(6), false);
        check("\uD83D\uDE00".repeat(12), true);
        check("a".repeat(1024), true);
        check("a".repeat(1025), false);
        check("\u0905".repeat(342), false);
        if (!"फ़ैज़ श्रीवास्तव १२".equals(StartCrm.usernameValue("  फ़ैज़  श्रीवास्तव १२  "))
            || !"legacy-owner".equals(StartCrm.usernameValue("Legacy-Owner"))
            || !"क".repeat(64).equals(StartCrm.usernameValue("क".repeat(64)))
            || StartCrm.usernameValue("क".repeat(65)) != null
            || StartCrm.usernameValue("िमनोज") != null
            || StartCrm.usernameValue("मनोज\u200b") != null)
            throw new AssertionError("Hindi username validation failed");
        System.out.println("PASS: launcher character/UTF-8 bounds and exact password input");
    }
    private static void check(String input, boolean valid) {
        if ((StartCrm.passwordError(input.toCharArray()) == null) != valid)
            throw new AssertionError("Password validation boundary failed");
    }
}
