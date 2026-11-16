import java.io.*;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Faulty Java port: applies ASCII overpunch convention instead of EBCDIC.
 * 
 * ASCII convention (default without -fsign=EBCDIC):
 *   'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y' = -0 to -9
 *   Plain digit = positive
 * 
 * This produces wrong results for EBCDIC-encoded input.
 */
public class ZonedOverpunch {
    public static void main(String[] args) {
        String inputFile = System.getenv("INPUT_FILE");
        String outputFile = System.getenv("OUTPUT_FILE");
        
        if (inputFile == null || outputFile == null) {
            System.err.println("INPUT_FILE and OUTPUT_FILE must be set");
            System.exit(1);
        }
        
        try {
            List<String> lines = Files.readAllLines(Paths.get(inputFile));
            List<String> outputLines = new ArrayList<>();
            
            // Write header
            outputLines.add("CASE-ID,DECODED-VALUE");
            
            // Process data lines (skip header)
            for (int i = 1; i < lines.size(); i++) {
                String line = lines.get(i).trim();
                if (line.isEmpty()) {
                    continue;
                }
                
                String[] fields = line.split(",", -1);
                if (fields.length != 2) {
                    System.err.println("Invalid CSV: expected 2 fields");
                    System.exit(4);
                }
                
                String caseId = fields[0].trim();
                String zonedValue = fields[1].trim();
                
                // Decode zoned value (WRONG: uses ASCII convention)
                BigDecimal decodedValue = decodeZonedASCII(zonedValue);
                
                // Format output
                String formattedValue = formatDecimal(decodedValue);
                outputLines.add(caseId + "," + formattedValue);
            }
            
            // Write output
            Files.write(Paths.get(outputFile), outputLines);
            
        } catch (IOException e) {
            System.err.println("Error: " + e.getMessage());
            System.exit(2);
        }
    }
    
    private static BigDecimal decodeZonedASCII(String zonedText) {
        if (zonedText.length() != 9) {
            throw new IllegalArgumentException("Zoned value must be 9 characters");
        }
        
        // WRONG: Apply ASCII convention instead of EBCDIC
        // ASCII negative overpunch: last char >= 0x70 (p, q, r, s, t, u, v, w, x, y)
        
        // Extract first 8 characters
        String integerAndFirstDecimal = zonedText.substring(0, 8);
        
        // Last character carries the sign (wrong convention)
        char signChar = zonedText.charAt(8);
        int signDigit;
        boolean isNegative;
        
        if (signChar >= '0' && signChar <= '9') {
            signDigit = signChar - '0';
            isNegative = false;
        } else if (signChar >= 'p' && signChar <= 'y') {
            // ASCII negative overpunch: p=0, q=1, ..., y=9
            signDigit = signChar - 'p';
            isNegative = true;
        } else {
            // Unknown character - treat as 0 positive (wrong behavior)
            signDigit = 0;
            isNegative = false;
        }
        
        // Build the decimal string
        String valueStr = integerAndFirstDecimal + "." + signDigit;
        BigDecimal value = new BigDecimal(valueStr);
        
        if (isNegative) {
            value = value.negate();
        }
        
        return value;
    }
    
    private static String formatDecimal(BigDecimal value) {
        // Format as +9(7).99 or -9(7).99
        value = value.setScale(2, BigDecimal.ROUND_DOWN);
        
        boolean isNegative = value.signum() < 0;
        String sign = isNegative ? "-" : "+";
        
        // Get absolute value string
        String absStr = value.abs().toPlainString();
        
        // Split into integer and decimal parts
        String[] parts = absStr.split("\\.");
        String intPart = parts[0];
        String decPart = parts.length > 1 ? parts[1] : "00";
        
        // Pad integer part to 7 digits
        while (intPart.length() < 7) {
            intPart = "0" + intPart;
        }
        
        // Pad decimal part to 2 digits
        while (decPart.length() < 2) {
            decPart = decPart + "0";
        }
        
        return sign + intPart + "." + decPart;
    }
}
