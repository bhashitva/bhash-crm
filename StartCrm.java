// SPDX-License-Identifier: Apache-2.0
// Setup/launch helper only. The CRM application remains compiled Bhash.
import java.io.Console;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Locale;
import java.nio.charset.StandardCharsets;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;

class StartCrm {
    static void configureTerminal() throws Exception {
        // Native Java logs are UTF-8. Match the attached Windows console to those
        // bytes before starting the child JVM; no persistent OS setting is changed.
        if (System.getProperty("os.name").startsWith("Windows")) {
            Process codePage = new ProcessBuilder("cmd.exe", "/d", "/c", "chcp", "65001")
                    // Retain the attached console rather than create a detached
                    // Windows subprocess whose code-page change cannot reach it.
                    .redirectInput(ProcessBuilder.Redirect.INHERIT)
                    .redirectErrorStream(true).start();
            codePage.getInputStream().readAllBytes();
            int exit = codePage.waitFor();
            if (exit != 0 && System.console() != null)
                throw new IllegalStateException("Could not set this terminal to UTF-8 (code page 65001).");
        }
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8));
        System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err), true, StandardCharsets.UTF_8));
    }
    static String passwordError(char[] password) {
        if (Character.codePointCount(password, 0, password.length) < 12)
            return "Password must contain at least 12 characters. Please try again.";
        var encoded = StandardCharsets.UTF_8.encode(java.nio.CharBuffer.wrap(password));
        int byteCount = encoded.remaining();
        if (encoded.hasArray()) Arrays.fill(encoded.array(), (byte) 0);
        if (byteCount > 1024)
            return "Password must use at most 1024 UTF-8 bytes. Please try again.";
        return null;
    }
    static String usernameValue(String input) {
        String value = input.strip().toLowerCase(Locale.ROOT);
        String[] composed = {"ऩ","ऱ","ऴ","क़","ख़","ग़","ज़","ड़","ढ़","फ़","य़"};
        String[] decomposed = {"ऩ","ऱ","ऴ","क़","ख़","ग़","ज़","ड़","ढ़","फ़","य़"};
        for (int i = 0; i < composed.length; i++) value = value.replace(composed[i], decomposed[i]);
        value = value.replace("्‍", "्").replace("्‌", "्").replaceAll(" +", " ");
        int length = value.codePointCount(0, value.length());
        if (length < 3 || length > 64) return null;
        String letters = "अआइईउऊऋऌऍऎएऐऑऒओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलळवशषसहऄॐॠॡ";
        String marks = "ऀँंः़ऺऻािीुूृॄॅॆेैॉॊोौ्ॎॏॕॖॗॢॣ";
        boolean base = false;
        for (int cp : value.codePoints().toArray()) {
            if (letters.indexOf(cp) >= 0) base = true;
            else if (marks.indexOf(cp) >= 0 && base) { }
            else if ("abcdefghijklmnopqrstuvwxyz0123456789०१२३४५६७८९._- ".indexOf(cp) >= 0) base = false;
            else return null;
        }
        return value;
    }
    public static void main(String[] args) throws Exception {
        configureTerminal();
        Path jar = Path.of("target", "crm.jar").toAbsolutePath();
        Path database = Path.of("data", "crm.db").toAbsolutePath();
        int port = 8080;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--help")) {
                System.out.println("Run from the repository root: java StartCrm.java [--jar FILE] [--database FILE] [--port NUMBER] [--terminal-check]");
                return;
            }
            if (args[i].equals("--terminal-check")) {
                System.out.println("\u0939\u093f\u0928\u094d\u0926\u0940 \u092a\u093e\u0920 \u0920\u0940\u0915 \u0939\u0948\u0964");
                System.err.println("\u0939\u093f\u0928\u094d\u0926\u0940 \u0924\u094d\u0930\u0941\u091f\u093f \u0938\u0902\u0926\u0947\u0936 \u0920\u0940\u0915 \u0939\u0948\u0964");
                return;
            }
            if (i + 1 >= args.length) throw new IllegalArgumentException("Missing option value: " + args[i]);
            switch (args[i++]) {
                case "--jar" -> jar = Path.of(args[i]).toAbsolutePath();
                case "--database" -> database = Path.of(args[i]).toAbsolutePath();
                case "--port" -> port = Integer.parseInt(args[i]);
                default -> throw new IllegalArgumentException("Unknown option: " + args[i - 1]);
            }
        }
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Port must be 1-65535.");
        if (!Files.isRegularFile(jar)) throw new IllegalArgumentException("Compiled CRM not found: " + jar);
        Files.createDirectories(database.getParent());
        String java = Path.of(System.getProperty("java.home"), "bin",
                System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java").toString();
        // A failed bootstrap can leave a valid schema without any accounts.
        // Inspect account state; file existence is not a completed-setup signal.
        Process status = new ProcessBuilder(java, "-Dfile.encoding=UTF-8", "-jar", jar.toString(),
                "--db=" + database, "--setup-status=true").redirectErrorStream(true).start();
        String setupStatus = new String(status.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (status.waitFor() != 0) throw new IllegalStateException("Could not check account setup. Database was preserved. " + setupStatus);
        if (!setupStatus.lines().anyMatch("SETUP_REQUIRED"::equals)
                && !setupStatus.lines().anyMatch("SETUP_READY"::equals))
            throw new IllegalStateException("CRM JAR does not support setup detection. Rebuild target/crm.jar.");
        if (setupStatus.lines().anyMatch("SETUP_REQUIRED"::equals)) {
            Console console = System.console();
            if (console == null) throw new IllegalStateException("Run this launcher directly in your terminal so it can hide the password.");
            String username;
            do {
                username = console.readLine("First owner username (3-64 Hindi/English characters, digits, spaces, . _ -): ");
                if (username == null) throw new IllegalStateException("Setup cancelled.");
                username = usernameValue(username);
                if (username != null) break;
                console.printf("Use 3-64 Hindi/English characters, digits, spaces, dot, underscore or hyphen.%n");
            } while (true);
            String tenant;
            do {
                tenant = console.readLine("Organization name: ");
                if (tenant == null) throw new IllegalStateException("Setup cancelled.");
                tenant = tenant.strip();
                if (!tenant.isEmpty() && tenant.getBytes(StandardCharsets.UTF_8).length <= 200) break;
                console.printf("Organization name must contain 1-200 UTF-8 bytes.%n");
            } while (true);
            char[] password;
            do {
                password = console.readPassword("Password (at least 12 characters; input is hidden): ");
                if (password == null) throw new IllegalStateException("Setup cancelled.");
                String error = passwordError(password);
                if (error == null) break;
                Arrays.fill(password, '\0');
                console.printf("%s%n", error);
            } while (true);
            ProcessBuilder setup = new ProcessBuilder(java, "-Dfile.encoding=UTF-8", "-jar", jar.toString(),
                    "--db=" + database, "--bootstrap=true").redirectErrorStream(true);
            int result;
            try {
                setup.environment().put("BHASH_CRM_USER", username);
                setup.environment().put("BHASH_CRM_TENANT", tenant);
                setup.environment().put("BHASH_CRM_PASSWORD", new String(password));
                Process child = setup.start();
                setup.environment().remove("BHASH_CRM_PASSWORD");
                String output = new String(child.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
                result = child.waitFor();
                if (result == 0) console.printf("Initial account created successfully.%n");
                else console.printf("Account setup failed. Database was preserved; rerun this launcher to retry.%n%s%n", output);
            } finally {
                Arrays.fill(password, '\0');
                setup.environment().remove("BHASH_CRM_PASSWORD");
            }
            if (result != 0) throw new IllegalStateException("Initial account setup failed; the CRM was not started.");
        }
        System.out.println("Open http://localhost:" + port + " or http://127.0.0.1:" + port);
        ProcessBuilder run = new ProcessBuilder(java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8", "-jar", jar.toString(),
                "--db=" + database, "--port=" + port, "--local=true").inheritIO();
        run.environment().remove("BHASH_CRM_PASSWORD");
        run.environment().remove("BHASH_CRM_USER");
        run.environment().remove("BHASH_CRM_TENANT");
        System.exit(run.start().waitFor());
    }
}
