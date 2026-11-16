import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;

/**
 * Faulty Java version: treats F sign nibble as negative (or rejects it).
 * This diverges from GnuCOBOL which reads F as positive.
 */
public class Comp3Sign {
    public static void main(String[] args) {
        String inputFile = System.getenv("INPUT_FILE");
        String outputFile = System.getenv("OUTPUT_FILE");
        
        if (inputFile == null || outputFile == null) {
            System.err.println("INPUT_FILE and OUTPUT_FILE must be set");
            System.exit(1);
        }
        
        try (BufferedReader reader = new BufferedReader(new FileReader(inputFile, StandardCharsets.UTF_8));
             BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile, StandardCharsets.UTF_8))) {
            
            // Write header
            writer.write("CASE-ID   ,DECODED-VALUE");
            writer.newLine();
            
            // Skip header line
            String line = reader.readLine();
            
            // Process data lines
            while ((line = reader.readLine()) != null) {
                String[] fields = line.split(",", -1);
                if (fields.length < 2) {
                    continue;
                }
                
                String caseId = fields[0].trim();
                String hexValue = fields[1].trim();
                
                // Decode packed decimal from hex string
                BigDecimal decodedValue = decodeComp3(hexValue, 7, 2);
                
                // Format output: CASE-ID padded to 10, comma, signed value
                String formattedCaseId = String.format("%-10s", caseId);
                String formattedValue = formatSignedDecimal(decodedValue, 7, 2);
                
                writer.write(formattedCaseId + "," + formattedValue);
                writer.newLine();
            }
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
        
        System.exit(0);
    }
    
    /**
     * Decode COMP-3 packed decimal from hex string.
     * FAULTY: treats F sign nibble as negative (diverges from GnuCOBOL).
     */
    private static BigDecimal decodeComp3(String hexString, int integerDigits, int decimalPlaces) {
        // Convert hex string to bytes
        byte[] bytes = hexToBytes(hexString);
        
        // Extract digits and sign nibble
        StringBuilder digitsBuilder = new StringBuilder();
        for (int i = 0; i < bytes.length - 1; i++) {
            int highNibble = (bytes[i] >> 4) & 0x0F;
            int lowNibble = bytes[i] & 0x0F;
            digitsBuilder.append(highNibble);
            digitsBuilder.append(lowNibble);
        }
        
        // Last byte: high nibble is a digit, low nibble is the sign
        int highNibble = (bytes[bytes.length - 1] >> 4) & 0x0F;
        int signNibble = bytes[bytes.length - 1] & 0x0F;
        digitsBuilder.append(highNibble);
        
        // Determine sign: C (0x0C) = positive, D (0x0D) = negative
        // FAULTY: F (0x0F) treated as negative instead of positive
        boolean negative = (signNibble == 0x0D) || (signNibble == 0x0F);
        
        // Build the decimal value
        String digitsString = digitsBuilder.toString();
        BigDecimal value = new BigDecimal(digitsString);
        
        // Apply decimal point
        if (decimalPlaces > 0) {
            value = value.movePointLeft(decimalPlaces);
        }
        
        // Apply sign
        if (negative) {
            value = value.negate();
        }
        
        return value;
    }
    
    /**
     * Convert hex string to bytes.
     */
    private static byte[] hexToBytes(String hexString) {
        int len = hexString.length();
        byte[] bytes = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            bytes[i / 2] = (byte) ((Character.digit(hexString.charAt(i), 16) << 4)
                                 + Character.digit(hexString.charAt(i + 1), 16));
        }
        return bytes;
    }
    
    /**
     * Format a signed decimal value to match COBOL output format.
     */
    private static String formatSignedDecimal(BigDecimal value, int integerDigits, int decimalPlaces) {
        value = value.setScale(decimalPlaces, RoundingMode.DOWN);
        
        String sign = value.compareTo(BigDecimal.ZERO) >= 0 ? "+" : "-";
        BigDecimal absValue = value.abs();
        
        String intPart = String.format("%0" + integerDigits + "d", absValue.toBigInteger());
        String decPart = String.format("%02d", absValue.remainder(BigDecimal.ONE).multiply(new BigDecimal("100")).intValue());
        
        return sign + intPart + "." + decPart;
    }
}
