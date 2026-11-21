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
        System.out.println("PASS: launcher character/UTF-8 bounds and exact password input");
    }
    private static void check(String input, boolean valid) {
        if ((StartCrm.passwordError(input.toCharArray()) == null) != valid)
            throw new AssertionError("Password validation boundary failed");
    }
}
