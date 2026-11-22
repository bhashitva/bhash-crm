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
        if (!"\u092b\u093c\u0948\u091c\u093c \u0936\u094d\u0930\u0940\u0935\u093e\u0938\u094d\u0924\u0935 \u0967\u0968".equals(StartCrm.usernameValue("  \u095e\u0948\u095b  \u0936\u094d\u0930\u0940\u0935\u093e\u0938\u094d\u0924\u0935 \u0967\u0968  "))
            || !"legacy-owner".equals(StartCrm.usernameValue("Legacy-Owner"))
            || !"\u0915".repeat(64).equals(StartCrm.usernameValue("\u0915".repeat(64)))
            || StartCrm.usernameValue("\u0915".repeat(65)) != null
            || StartCrm.usernameValue("\u093f\u092e\u0928\u094b\u091c") != null
            || StartCrm.usernameValue("\u092e\u0928\u094b\u091c\u200b") != null)
            throw new AssertionError("Hindi username validation failed");
        System.out.println("PASS: launcher character/UTF-8 bounds and exact password input");
    }
    private static void check(String input, boolean valid) {
        if ((StartCrm.passwordError(input.toCharArray()) == null) != valid)
            throw new AssertionError("Password validation boundary failed");
    }
}
