import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Trap 5: REDEFINES of invalid numeric data (correct Java port)
 * 
 * This port replicates GnuCOBOL's low-nibble rule: when an alphanumeric field
 * with non-digit characters is read through a REDEFINES as PIC 9(n), each byte
 * contributes its low nibble as the digit value.
 * 
 * Examples:
 * - 'A' (0x41) -> low nibble 1
 * - 'J' (0x4A) -> low nibble 10 (carries to next position)
 * - ' ' (0x20) -> low nibble 0
 * 
 * Evidence: docs/evidence/gnucobol-encodings.md
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
                
                // Decode using low-nibble rule
                BigDecimal decodedValue = decodeWithLowNibbleRule(amountText);
                
                // Compute result
                BigDecimal result = decodedValue.add(FIXED_FEE);
                
                // Format output (pad CASE-ID to 10 characters, format amount with sign and 2 decimals)
                String paddedCaseId = String.format("%-10s", caseId);
                String formattedAmount = formatAmount(result);
                String numericOk = isNumeric ? "Y" : "N";
                
                writer.println(paddedCaseId + "," + formattedAmount + "," + numericOk);
            }
        }
    }
    
    /**
     * Decode a string using GnuCOBOL's low-nibble rule.
     * Each byte contributes its low nibble (low 4 bits) as a digit value.
     * When a low nibble is >= 10, it carries to the next position.
     * 
     * For PIC 9(5)V99, the text "0012345" represents 123.45
     */
    private static BigDecimal decodeWithLowNibbleRule(String text) {
        // Ensure exactly 7 characters for PIC 9(5)V99
        String padded;
        if (text.length() >= 7) {
            // Take the first 7 characters (or trim if longer)
            padded = text.substring(0, 7);
        } else {
            // Pad left with zeros if shorter
            padded = String.format("%7s", text).replace(' ', '0');
        }
        
        long value = 0;
        long multiplier = 1;
        
        // Process from right to left (least significant to most significant)
        for (int i = padded.length() - 1; i >= 0; i--) {
            char c = padded.charAt(i);
            int lowNibble = c & 0x0F;  // Extract low 4 bits
            
            value += lowNibble * multiplier;
            multiplier *= 10;
        }
        
        // The value represents cents (2 decimal places)
        return new BigDecimal(value).movePointLeft(2);
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
