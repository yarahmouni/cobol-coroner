import java.io.*;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Correct Java port: applies EBCDIC overpunch table for zoned decimal input.
 * 
 * EBCDIC overpunch convention (GnuCOBOL with -fsign=EBCDIC):
 *   '{' and 'A' to 'I' = +0 to +9
 *   '}' and 'J' to 'R' = -0 to -9
 *   Plain digit '0' to '9' = positive
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
                
                // Decode zoned value
                BigDecimal decodedValue = decodeZonedEBCDIC(zonedValue);
                
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
    
    private static BigDecimal decodeZonedEBCDIC(String zonedText) {
        if (zonedText.length() != 9) {
            throw new IllegalArgumentException("Zoned value must be 9 characters");
        }
        
        // For S9(7)V99: 7 integer digits + 2 decimal digits = 9 characters total
        // Layout: positions 0-6 are integer, positions 7-8 are decimal
        // The LAST character (position 8) carries the sign
        
        // Extract integer part (first 7 characters)
        String integerPart = zonedText.substring(0, 7);
        
        // Extract first decimal digit (position 7)
        char firstDecimalChar = zonedText.charAt(7);
        if (firstDecimalChar < '0' || firstDecimalChar > '9') {
            throw new IllegalArgumentException("Invalid decimal digit: " + firstDecimalChar);
        }
        int firstDecimalDigit = firstDecimalChar - '0';
        
        // Extract last character (position 8) which carries the sign
        char signChar = zonedText.charAt(8);
        int lastDecimalDigit;
        boolean isNegative;
        
        if (signChar >= '0' && signChar <= '9') {
            // Plain digit = positive
            lastDecimalDigit = signChar - '0';
            isNegative = false;
        } else if (signChar == '{') {
            // { = +0
            lastDecimalDigit = 0;
            isNegative = false;
        } else if (signChar >= 'A' && signChar <= 'I') {
            // A to I = +1 to +9
            lastDecimalDigit = signChar - 'A' + 1;
            isNegative = false;
        } else if (signChar == '}') {
            // } = -0
            lastDecimalDigit = 0;
            isNegative = true;
        } else if (signChar >= 'J' && signChar <= 'R') {
            // J to R = -1 to -9
            lastDecimalDigit = signChar - 'J' + 1;
            isNegative = true;
        } else {
            throw new IllegalArgumentException("Invalid EBCDIC overpunch character: " + signChar);
        }
        
        // Build the decimal string: integer.decimal1decimal2
        String valueStr = integerPart + "." + firstDecimalDigit + lastDecimalDigit;
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
