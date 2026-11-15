import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Java 17 version of CREDIT-FEES COBOL program.
 * Computes credit file fees with segment discounts and eligibility checks.
 * Produces byte-identical output to the COBOL reference program.
 */
public class CreditFees {
    
    // Constants matching COBOL WORKING-STORAGE
    private static final BigDecimal MIN_FEE = new BigDecimal("10.00");
    private static final BigDecimal MIN_INCOME = new BigDecimal("25000.00");
    private static final int MIN_DURATION = 12;
    private static final BigDecimal MAX_FEE = new BigDecimal("9999999.99");
    private static final BigDecimal MAX_PRINCIPAL = new BigDecimal("999999999.99");
    private static final BigDecimal MAX_FEE_RATE = new BigDecimal("1.00");
    private static final BigDecimal MAX_INCOME = new BigDecimal("999999999.99");
    private static final int MAX_DURATION = 999;
    
    public static void main(String[] args) {
        // Error counter (mutable reference)
        int[] errorCount = new int[1];
        
        // Validate environment variables
        String inputPath = System.getenv("INPUT_FILE");
        String outputPath = System.getenv("OUTPUT_FILE");
        
        if (inputPath == null || outputPath == null) {
            System.err.println("ERROR: INPUT_FILE or OUTPUT_FILE not set");
            System.exit(16);
        }
        
        BufferedReader reader = null;
        BufferedWriter writer = null;
        
        try {
            // Open input file
            try {
                reader = new BufferedReader(new FileReader(inputPath));
            } catch (IOException e) {
                System.err.println("ERROR: Cannot open input file " + inputPath);
                System.exit(16);
            }
            
            // Open output file
            try {
                writer = new BufferedWriter(new FileWriter(outputPath));
            } catch (IOException e) {
                System.err.println("ERROR: Cannot open output file " + outputPath);
                if (reader != null) reader.close();
                System.exit(16);
            }
            
            // Read header line
            String headerLine = reader.readLine();
            if (headerLine == null) {
                // Empty input: write header and exit 0
                writer.write("CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE\n");
                writer.close();
                reader.close();
                System.exit(0);
            }
            
            // Write output header
            writer.write("CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE\n");
            
            // Process data lines
            String line;
            while ((line = reader.readLine()) != null) {
                processRecord(line, writer, errorCount);
            }
            
            // Close files
            writer.close();
            reader.close();
            
            // Exit with appropriate code
            if (errorCount[0] > 0) {
                System.exit(4);
            } else {
                System.exit(0);
            }
            
        } catch (IOException e) {
            System.err.println("ERROR: I/O error during processing");
            try {
                if (writer != null) writer.close();
                if (reader != null) reader.close();
            } catch (IOException closeEx) {
                // Ignore close errors
            }
            System.exit(16);
        }
    }
    
    /**
     * Process one input record: parse, validate, compute, format, write.
     */
    private static void processRecord(String line, BufferedWriter writer, int[] errorCount) throws IOException {
        // Truncate to 200 characters (COBOL PIC X(200))
        if (line.length() > 200) {
            line = line.substring(0, 200);
        }
        
        // Remove trailing CR if present (CRLF input)
        if (line.endsWith("\r")) {
            line = line.substring(0, line.length() - 1);
        }
        
        // Parse fields
        String[] fields = parseLine(line);
        
        // Validate record
        ValidationResult validation = validateRecord(fields);
        
        if (!validation.valid) {
            // E01 record
            errorCount[0]++;
            String outputLine = formatOutputLine(validation.caseId, BigDecimal.ZERO, "N", "E01");
            writer.write(outputLine + "\n");
            return;
        }
        
        // Compute fee
        FeeResult fee = computeFee(validation);
        
        if (fee.reasonCode.equals("E01")) {
            // Overflow
            errorCount[0]++;
            String outputLine = formatOutputLine(validation.caseId, BigDecimal.ZERO, "N", "E01");
            writer.write(outputLine + "\n");
            return;
        }
        
        // Check eligibility
        EligibilityResult eligibility = checkEligibility(validation, fee);
        
        // Write output line
        String outputLine = formatOutputLine(validation.caseId, fee.feeAmount, 
                                             eligibility.eligible, eligibility.reasonCode);
        writer.write(outputLine + "\n");
    }
    
    /**
     * Split CSV line on commas, keeping trailing empty fields.
     */
    private static String[] parseLine(String line) {
        return line.split(",", -1);
    }
    
    /**
     * Validate field count and all input fields.
     */
    private static ValidationResult validateRecord(String[] fields) {
        ValidationResult result = new ValidationResult();
        result.valid = true;
        
        // Validate field count
        if (fields.length != 6) {
            result.valid = false;
            // CASE-ID for output (field 0, trimmed and cut to 10)
            if (fields.length > 0) {
                String caseIdRaw = fields[0];
                if (caseIdRaw.length() > 20) {
                    caseIdRaw = caseIdRaw.substring(0, 20);
                }
                result.caseId = trimTrailing(caseIdRaw);
                if (result.caseId.length() > 10) {
                    result.caseId = result.caseId.substring(0, 10);
                }
            } else {
                result.caseId = "";
            }
            return result;
        }
        
        // Validate CASE-ID
        String caseIdRaw = fields[0];
        if (caseIdRaw.length() > 20) {
            caseIdRaw = caseIdRaw.substring(0, 20);
        }
        
        String caseIdTrimmed = trimTrailing(caseIdRaw);
        
        if (caseIdTrimmed.isEmpty()) {
            result.valid = false;
            result.caseId = "";
            return result;
        }
        
        if (caseIdTrimmed.length() > 10) {
            result.valid = false;
            result.caseId = caseIdTrimmed.substring(0, 10);
            return result;
        }
        
        result.caseId = caseIdTrimmed;
        
        // Validate PRINCIPAL
        BigDecimal principalValue = parseNumeric(fields[1]);
        if (principalValue == null) {
            result.valid = false;
            return result;
        }
        
        // Check by-value range
        if (principalValue.abs().compareTo(MAX_PRINCIPAL) > 0) {
            result.valid = false;
            return result;
        }
        
        // Check value fits S9(9)V99: truncate to scale 2 and compare
        BigDecimal truncated = principalValue.setScale(2, RoundingMode.DOWN);
        if (truncated.compareTo(principalValue) != 0) {
            result.valid = false;
            return result;
        }
        
        result.principal = principalValue;
        
        // Validate FEE-RATE
        BigDecimal feeRateValue = parseNumeric(fields[2]);
        if (feeRateValue == null) {
            result.valid = false;
            return result;
        }
        
        // Check range [0, 1)
        if (feeRateValue.compareTo(BigDecimal.ZERO) < 0 || 
            feeRateValue.compareTo(MAX_FEE_RATE) >= 0) {
            result.valid = false;
            return result;
        }
        
        // Check value fits V9(5) (scale 5)
        truncated = feeRateValue.setScale(5, RoundingMode.DOWN);
        if (truncated.compareTo(feeRateValue) != 0) {
            result.valid = false;
            return result;
        }
        
        result.feeRate = feeRateValue;
        
        // Validate DURATION-MONTHS
        BigDecimal durationValue = parseNumeric(fields[3]);
        if (durationValue == null) {
            result.valid = false;
            return result;
        }
        
        // Check integer (scale 0)
        truncated = durationValue.setScale(0, RoundingMode.DOWN);
        if (truncated.compareTo(durationValue) != 0) {
            result.valid = false;
            return result;
        }
        
        // Check range 0 to 999
        if (durationValue.compareTo(BigDecimal.ZERO) < 0 || 
            durationValue.compareTo(new BigDecimal(MAX_DURATION)) > 0) {
            result.valid = false;
            return result;
        }
        
        result.durationMonths = durationValue.intValueExact();
        
        // Validate CUSTOMER-SEGMENT
        String segmentRaw = fields[4];
        String segmentTrimmed = trimTrailing(segmentRaw);
        if (segmentTrimmed.length() > 1) {
            result.valid = false;
            return result;
        }
        result.customerSegment = segmentTrimmed;
        
        // Validate INCOME
        BigDecimal incomeValue = parseNumeric(fields[5]);
        if (incomeValue == null) {
            result.valid = false;
            return result;
        }
        
        // Check non-negative
        if (incomeValue.compareTo(BigDecimal.ZERO) < 0) {
            result.valid = false;
            return result;
        }
        
        // Check range
        if (incomeValue.compareTo(MAX_INCOME) > 0) {
            result.valid = false;
            return result;
        }
        
        // Check value fits 9(9)V99 (scale 2)
        truncated = incomeValue.setScale(2, RoundingMode.DOWN);
        if (truncated.compareTo(incomeValue) != 0) {
            result.valid = false;
            return result;
        }
        
        result.income = incomeValue;
        
        return result;
    }
    
    /**
     * Compute base fee, apply discount, apply minimum fee, detect overflow.
     */
    private static FeeResult computeFee(ValidationResult input) {
        FeeResult result = new FeeResult();
        
        // Compute base fee with ROUNDED (HALF_UP)
        BigDecimal baseFee = input.principal.multiply(input.feeRate);
        baseFee = baseFee.setScale(2, RoundingMode.HALF_UP);
        
        // Check overflow after rounding
        if (baseFee.abs().compareTo(MAX_FEE) > 0) {
            result.reasonCode = "E01";
            result.feeAmount = BigDecimal.ZERO;
            return result;
        }
        
        // Apply segment discount
        BigDecimal discountedFee = baseFee;
        String segment = input.customerSegment;
        
        if (segment.equals("P")) {
            BigDecimal discountRate = new BigDecimal("0.10");
            discountedFee = baseFee.multiply(BigDecimal.ONE.subtract(discountRate));
            discountedFee = discountedFee.setScale(2, RoundingMode.HALF_UP);
        } else if (segment.equals("S")) {
            BigDecimal discountRate = new BigDecimal("0.05");
            discountedFee = baseFee.multiply(BigDecimal.ONE.subtract(discountRate));
            discountedFee = discountedFee.setScale(2, RoundingMode.HALF_UP);
        }
        // B and other segments: no discount
        
        // Check overflow after discount
        if (discountedFee.abs().compareTo(MAX_FEE) > 0) {
            result.reasonCode = "E01";
            result.feeAmount = BigDecimal.ZERO;
            return result;
        }
        
        // Apply minimum fee rule (positive fees only)
        if (discountedFee.compareTo(BigDecimal.ZERO) > 0 && 
            discountedFee.compareTo(MIN_FEE) < 0) {
            result.feeAmount = MIN_FEE;
            result.reasonCode = "A01";
        } else {
            result.feeAmount = discountedFee;
            result.reasonCode = "A00";
        }
        
        return result;
    }
    
    /**
     * Check income and duration eligibility rules.
     */
    private static EligibilityResult checkEligibility(ValidationResult input, FeeResult fee) {
        EligibilityResult result = new EligibilityResult();
        
        if (input.income.compareTo(MIN_INCOME) < 0) {
            result.eligible = "N";
            result.reasonCode = "R01";
        } else if (input.durationMonths < MIN_DURATION) {
            result.eligible = "N";
            result.reasonCode = "R02";
        } else {
            result.eligible = "Y";
            result.reasonCode = fee.reasonCode;  // A00 or A01
        }
        
        return result;
    }
    
    /**
     * Format output CSV line with COBOL PIC +9(7).99 format.
     */
    private static String formatOutputLine(String caseId, BigDecimal feeAmount, 
                                           String eligible, String reasonCode) {
        // Format: sign + 7 integer digits zero-padded + point + 2 decimals = 11 characters
        String sign = (feeAmount.signum() >= 0) ? "+" : "-";
        String absValue = feeAmount.abs().setScale(2).toPlainString();
        
        // Left-pad absValue to 10 characters (7 integer + point + 2 decimals)
        String feeFormatted = sign + padLeft(absValue, 10, '0');
        
        return caseId + "," + feeFormatted + "," + eligible + "," + reasonCode;
    }
    
    /**
     * Parse numeric text after trimming spaces.
     * Accepts: optional sign, digits, optional decimal point with optional digits.
     * Rejects: blank, exponent notation, non-numeric text.
     */
    private static BigDecimal parseNumeric(String text) {
        if (text == null) return null;
        String trimmed = text.trim();
        if (trimmed.isEmpty()) return null;
        // Regex: accepts leading +/-, digits with optional decimal point, or decimal-only form
        // Accepts: "10.500", "+100.00", "12.5", "5.", ".50", ".01000", " 100.00 " (after trim)
        // Rejects: "1E2" (exponent), blank, "."
        if (!trimmed.matches("^[+-]?(\\d+\\.?\\d*|\\.\\d+)$")) return null;
        try {
            return new BigDecimal(trimmed);
        } catch (NumberFormatException e) {
            return null;
        }
    }
    
    /**
     * Trim trailing spaces only (COBOL FUNCTION TRIM ... TRAILING).
     */
    private static String trimTrailing(String s) {
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == ' ') {
            end--;
        }
        return s.substring(0, end);
    }
    
    /**
     * Left-pad string to target length with fill character.
     */
    private static String padLeft(String s, int length, char fillChar) {
        if (s.length() >= length) return s;
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length - s.length(); i++) {
            sb.append(fillChar);
        }
        sb.append(s);
        return sb.toString();
    }
    
    // Data structures
    
    private static class ValidationResult {
        boolean valid;
        String caseId;
        BigDecimal principal;
        BigDecimal feeRate;
        int durationMonths;
        String customerSegment;
        BigDecimal income;
    }
    
    private static class FeeResult {
        BigDecimal feeAmount;
        String reasonCode;
    }
    
    private static class EligibilityResult {
        String eligible;
        String reasonCode;
    }
}
