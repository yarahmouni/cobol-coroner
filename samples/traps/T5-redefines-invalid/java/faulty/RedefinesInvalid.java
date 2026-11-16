import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Trap 5: REDEFINES of invalid numeric data (faulty Java port)
 * 
 * This faulty port rejects records with non-digit characters or treats them as zero,
 * diverging from GnuCOBOL's low-nibble rule.
 */
public class RedefinesInvalid {
    
    private static final BigDecimal FIXED_FEE = new BigDecimal("1.00");
    
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
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(16);
        }
    }
    
    private static void processFile(String inputFile, String outputFile) throws IOException {
        List<String> lines = Files.readAllLines(Paths.get(inputFile));
        
        if (lines.isEmpty()) {
            System.err.println("ERROR: Input file is empty");
            System.exit(16);
        }
        
        try (PrintWriter writer = new PrintWriter(new FileWriter(outputFile))) {
            // Write header
            writer.println("CASE-ID,AMOUNT,NUMERIC-OK");
            
            // Skip input header and process data rows
            for (int i = 1; i < lines.size(); i++) {
                String line = lines.get(i);
                if (line.trim().isEmpty()) {  // Only check emptiness after trim
                    continue;
                }
                
                String[] fields = line.split(",", -1);
                if (fields.length != 2) {
                    System.err.println("ERROR: Invalid CSV row (expected 2 fields)");
                    System.exit(16);
                }
                
                String caseId = fields[0].trim();
                String amountText = fields[1];  // Preserve exact bytes including trailing spaces
                
                if (caseId.isEmpty()) {
                    System.err.println("ERROR: CASE-ID is empty");
                    System.exit(16);
                }
                
                // Check if the text is valid numeric (all digits)
                boolean isNumeric = amountText.matches("^\\d+$");
                
                BigDecimal decodedValue;
                if (isNumeric) {
                    // Valid numeric: parse as decimal with 2 decimal places
                    // For PIC 9(5)V99, "0012345" = 123.45
                    long cents = Long.parseLong(amountText);
                    decodedValue = new BigDecimal(cents).movePointLeft(2);
                } else {
                    // FAULTY BEHAVIOR: Treat invalid numeric as zero
                    decodedValue = BigDecimal.ZERO;
                }
                
                // Compute result
                BigDecimal result = decodedValue.add(FIXED_FEE);
                
                // Format output
                String paddedCaseId = String.format("%-10s", caseId);
                String formattedAmount = formatAmount(result);
                String numericOk = isNumeric ? "Y" : "N";
                
                writer.println(paddedCaseId + "," + formattedAmount + "," + numericOk);
            }
        }
    }
    
    /**
     * Format a BigDecimal as +9(7).99 (sign, 7 integer digits, 2 decimals)
     */
    private static String formatAmount(BigDecimal amount) {
        BigDecimal scaled = amount.setScale(2, RoundingMode.HALF_UP);
        String sign = scaled.compareTo(BigDecimal.ZERO) < 0 ? "-" : "+";
        String absValue = scaled.abs().toPlainString();
        
        // Split into integer and decimal parts
        String[] parts = absValue.split("\\.");
        String intPart = parts[0];
        String decPart = parts.length > 1 ? parts[1] : "00";
        
        // Pad decimal part to 2 digits
        while (decPart.length() < 2) {
            decPart += "0";
        }
        
        // Pad integer part to 7 digits
        while (intPart.length() < 7) {
            intPart = "0" + intPart;
        }
        
        return sign + intPart + "." + decPart;
    }
}
