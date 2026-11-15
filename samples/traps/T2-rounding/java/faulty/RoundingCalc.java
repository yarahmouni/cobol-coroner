import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.*;

/**
 * Trap 2: Faulty Java implementation
 * FEE1: uses HALF_UP (should be DOWN for truncation)
 * FEE2: uses HALF_EVEN (should be HALF_UP for COBOL ROUNDED)
 */
public class RoundingCalc {
    public static void main(String[] args) {
        String inputPath = System.getenv("INPUT_FILE");
        String outputPath = System.getenv("OUTPUT_FILE");

        if (inputPath == null || outputPath == null) {
            System.err.println("ERROR: INPUT_FILE or OUTPUT_FILE not set");
            System.exit(16);
        }

        try {
            processFile(inputPath, outputPath);
            System.exit(0);
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(16);
        }
    }

    private static void processFile(String inputPath, String outputPath) throws IOException {
        Path input = Paths.get(inputPath);
        Path output = Paths.get(outputPath);

        try (BufferedReader reader = Files.newBufferedReader(input);
             BufferedWriter writer = Files.newBufferedWriter(output)) {

            // Read and discard header
            String header = reader.readLine();
            if (header == null) {
                throw new IOException("Empty input file");
            }

            // Write output header
            writer.write("CASE-ID,FEE1,FEE2");
            writer.newLine();

            // Process each record
            String line;
            while ((line = reader.readLine()) != null) {
                processRecord(line, writer);
            }
        }
    }

    private static void processRecord(String line, BufferedWriter writer) throws IOException {
        String[] fields = line.split(",", -1);
        if (fields.length != 3) {
            return;
        }

        String caseId = fields[0].trim();
        String principalStr = fields[1].trim();
        String rateStr = fields[2].trim();

        try {
            BigDecimal principal = new BigDecimal(principalStr);
            BigDecimal rate = new BigDecimal(rateStr);

            BigDecimal product = principal.multiply(rate);

            // Check for overflow (result must fit in S9(7)V99: -9999999.99 to +9999999.99)
            BigDecimal maxFee = new BigDecimal("9999999.99");
            BigDecimal minFee = new BigDecimal("-9999999.99");
            
            BigDecimal fee1, fee2;
            
            if (product.abs().compareTo(maxFee) > 0) {
                // Overflow - set to zero like COBOL ON SIZE ERROR
                fee1 = BigDecimal.ZERO.setScale(2);
                fee2 = BigDecimal.ZERO.setScale(2);
            } else {
                // FAULTY: FEE1 uses HALF_UP instead of DOWN
                fee1 = product.setScale(2, RoundingMode.HALF_UP);

                // FAULTY: FEE2 uses HALF_EVEN instead of HALF_UP
                fee2 = product.setScale(2, RoundingMode.HALF_EVEN);
            }

            // Format output with leading sign and zero-padding
            String fee1Str = formatAmount(fee1);
            String fee2Str = formatAmount(fee2);

            writer.write(caseId + "," + fee1Str + "," + fee2Str);
            writer.newLine();

        } catch (NumberFormatException e) {
            // Skip invalid records
        }
    }

    private static String formatAmount(BigDecimal amount) {
        // Format as +9(7).99 to match COBOL output
        String sign = amount.signum() >= 0 ? "+" : "-";
        BigDecimal abs = amount.abs();
        String value = abs.setScale(2).toPlainString();
        
        // Pad to 10 digits before decimal (7 + 3 for "000")
        String[] parts = value.split("\\.");
        String intPart = parts[0];
        String decPart = parts.length > 1 ? parts[1] : "00";
        
        // Ensure decimal part is exactly 2 digits
        if (decPart.length() == 1) {
            decPart = decPart + "0";
        }
        
        // Pad integer part to 7 digits
        intPart = String.format("%07d", new BigDecimal(intPart).longValue());
        
        return sign + intPart + "." + decPart;
    }
}
