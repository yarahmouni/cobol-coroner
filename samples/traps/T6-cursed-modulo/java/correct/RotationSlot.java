import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/**
 * Trap 6: rotation slot from a signed day offset (correct Java port).
 *
 * COBOL FUNCTION MOD takes the sign of the divisor, so MOD(-11, 7) is 3.
 * Math.floorMod gives the same result. The slot is always 0 to 6.
 */
public class RotationSlot {

    private static final int SLOTS = 7;

    public static void main(String[] args) {
        String inputFile = System.getenv("INPUT_FILE");
        String outputFile = System.getenv("OUTPUT_FILE");

        if (inputFile == null || outputFile == null) {
            System.err.println("ERROR: INPUT_FILE or OUTPUT_FILE not set");
            System.exit(16);
        }

        try {
            processFile(inputFile, outputFile);
            System.exit(0);
        } catch (IOException | NumberFormatException e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(16);
        }
    }

    private static void processFile(String inputFile, String outputFile) throws IOException {
        List<String> lines = Files.readAllLines(Paths.get(inputFile), StandardCharsets.UTF_8);

        try (PrintWriter writer = new PrintWriter(Files.newBufferedWriter(Paths.get(outputFile), StandardCharsets.UTF_8))) {
            writer.print("CASE-ID,DAY-OFFSET,SLOT\n");

            // Skip the input header, process the data rows
            for (int i = 1; i < lines.size(); i++) {
                String line = lines.get(i);
                if (line.trim().isEmpty()) {
                    continue;
                }

                String[] fields = line.split(",", -1);
                if (fields.length != 2) {
                    System.err.println("ERROR: Invalid CSV row (expected 2 fields)");
                    System.exit(16);
                }

                String caseId = fields[0].trim();
                if (caseId.isEmpty()) {
                    System.err.println("ERROR: CASE-ID is empty");
                    System.exit(16);
                }

                int offset = Integer.parseInt(fields[1].trim());
                if (offset > 999 || offset < -999) {
                    System.err.println("ERROR: DAY-OFFSET out of range");
                    System.exit(16);
                }

                int slot = Math.floorMod(offset, SLOTS);

                writer.print(pad(caseId) + "," + signed(offset, 3) + "," + signed(slot, 1) + "\n");
            }
        }
    }

    /** Left-justify the case id in 10 characters, as the COBOL field does. */
    private static String pad(String caseId) {
        StringBuilder padded = new StringBuilder(caseId);
        while (padded.length() < 10) {
            padded.append(' ');
        }
        return padded.toString();
    }

    /** Sign, then the magnitude zero-padded to the given digits, like the COBOL edited picture. */
    private static String signed(int value, int digits) {
        StringBuilder text = new StringBuilder(Integer.toString(Math.abs(value)));
        while (text.length() < digits) {
            text.insert(0, '0');
        }
        return (value < 0 ? "-" : "+") + text;
    }
}
