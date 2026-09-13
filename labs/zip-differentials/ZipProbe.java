import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;

/** Observes entries in memory; never extracts or executes archive content. */
public final class ZipProbe {
    private static final int MAX_BYTES = 1_048_576;
    private static final int MAX_ENTRIES = 20;
    private static final byte[] MARKER = "REVIEW-ME\n".getBytes(StandardCharsets.US_ASCII);
    private final List<String> entries = new ArrayList<>();
    private int totalBytes;

    private void observe(ZipEntry entry, InputStream input) throws IOException {
        if (entries.size() >= MAX_ENTRIES) {
            throw new IOException("Harness limit: more than 20 entries");
        }
        ByteArrayOutputStream content = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        while (true) {
            // Read one byte beyond the remaining budget to detect oversized output.
            int count = input.read(buffer, 0, Math.min(buffer.length, MAX_BYTES - totalBytes + 1));
            if (count == -1) {
                break;
            }
            totalBytes += count;
            if (totalBytes > MAX_BYTES) {
                throw new IOException("Harness limit: more than 1048576 uncompressed bytes");
            }
            content.write(buffer, 0, count);
        }
        byte[] bytes = content.toByteArray();
        String hash;
        try {
            hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("Java runtime lacks mandatory SHA-256", impossible);
        }
        entries.add("{\"name\":" + quote(entry.getName()) + ",\"sha256\":" + quote(hash)
                + ",\"size\":" + bytes.length + ",\"marker\":" + containsMarker(bytes) + "}");
    }

    private void inspect(String mode, Path path) throws IOException {
        if (mode.equals("zipfile")) {
            try (ZipFile archive = new ZipFile(path.toFile())) {
                var iterator = archive.entries();
                while (iterator.hasMoreElements()) {
                    ZipEntry entry = iterator.nextElement();
                    // Open immediately after enumeration: do not look up a duplicate by name.
                    try (InputStream input = archive.getInputStream(entry)) {
                        if (input == null) {
                            throw new IOException("Enumerated entry has no input stream");
                        }
                        observe(entry, input);
                    }
                }
            }
        } else if (mode.equals("stream")) {
            try (ZipInputStream archive = new ZipInputStream(Files.newInputStream(path))) {
                ZipEntry entry;
                while ((entry = archive.getNextEntry()) != null) {
                    observe(entry, archive);
                    archive.closeEntry();
                }
            }
        } else {
            throw new IllegalArgumentException("Mode must be zipfile or stream");
        }
    }

    private static boolean containsMarker(byte[] bytes) {
        for (int offset = 0; offset <= bytes.length - MARKER.length; offset++) {
            int index = 0;
            while (index < MARKER.length && bytes[offset + index] == MARKER[index]) {
                index++;
            }
            if (index == MARKER.length) {
                return true;
            }
        }
        return false;
    }

    private static String quote(String value) {
        StringBuilder json = new StringBuilder("\"");
        for (int index = 0; index < value.length(); index++) {
            char ch = value.charAt(index);
            if (ch == '"' || ch == '\\') {
                json.append('\\').append(ch);
            } else if (ch < 0x20 || ch > 0x7e) {
                // Escaping UTF-16 code units also preserves surrogate pairs and lone surrogates.
                json.append(String.format("\\u%04x", (int) ch));
            } else {
                json.append(ch);
            }
        }
        return json.append('"').toString();
    }

    public static void main(String[] args) {
        ZipProbe probe = new ZipProbe();
        String error = null;
        try {
            if (args.length != 2) {
                throw new IllegalArgumentException("Usage: ZipProbe zipfile|stream fixture.zip");
            }
            probe.inspect(args[0], Path.of(args[1]));
        } catch (IOException | RuntimeException exception) {
            error = exception.getClass().getName() + ": " + exception.getMessage();
        }
        System.out.println("{\"status\":" + quote(error == null ? "success" : "rejected")
                + ",\"entries\":[" + String.join(",", probe.entries) + "],\"error\":"
                + (error == null ? "null" : quote(error)) + "}");
        System.exit(error == null ? 0 : 2);
    }
}
