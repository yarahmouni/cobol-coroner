import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class MatchMerge {
    private static final String[] BRANCH_TABLE = {
        "A01", "B02", "C03", "D04", "E05", "F06", "Z99", "001", "9ZZ", ""
    };
    
    private static class Transaction {
        String caseId;
        String branch;
        BigDecimal amount;
        
        Transaction(String caseId, String branch, BigDecimal amount) {
            this.caseId = caseId;
            this.branch = branch;
            this.amount = amount;
        }
    }
    
    public static void main(String[] args) {
        String inputFile = System.getenv("INPUT_FILE");
        String outputFile = System.getenv("OUTPUT_FILE");
        
        if (inputFile == null || inputFile.trim().isEmpty()) {
            inputFile = "input.csv";
        }
        if (outputFile == null || outputFile.trim().isEmpty()) {
            outputFile = "output.csv";
        }
        
        try {
            List<Transaction> transactions = readAndSortTransactions(inputFile);
            processAndWrite(transactions, outputFile);
            System.exit(0);
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(2);
        }
    }
    
    private static List<Transaction> readAndSortTransactions(String inputFile) throws IOException {
        List<Transaction> transactions = new ArrayList<>();
        
        try (BufferedReader reader = new BufferedReader(new FileReader(inputFile))) {
            String line = reader.readLine(); // Skip header
            
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",", -1);
                if (parts.length >= 3) {
                    String caseId = parts[0];
                    String branch = parts[1];
                    BigDecimal amount = new BigDecimal(parts[2].trim());
                    transactions.add(new Transaction(caseId, branch, amount));
                }
            }
        }
        
        // Sort by case ID, then by branch (ASCII order)
        transactions.sort(Comparator.comparing((Transaction t) -> t.caseId)
                                    .thenComparing(t -> t.branch));
        
        return transactions;
    }
    
    private static void processAndWrite(List<Transaction> transactions, String outputFile) throws IOException {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile))) {
            writer.write("CASE-ID,BRANCH,SUBTOTAL\n");
            
            String prevCaseId = null;
            Map<String, BigDecimal> branchSubtotals = new HashMap<>();
            BigDecimal suspSubtotal = BigDecimal.ZERO;
            BigDecimal caseTotal = BigDecimal.ZERO;
            
            for (Transaction txn : transactions) {
                if (!txn.caseId.equals(prevCaseId)) {
                    if (prevCaseId != null) {
                        writeCaseResults(writer, prevCaseId, branchSubtotals, suspSubtotal, caseTotal);
                    }
                    // Initialize new case
                    branchSubtotals.clear();
                    for (String code : BRANCH_TABLE) {
                        if (!code.isEmpty()) {
                            branchSubtotals.put(code, BigDecimal.ZERO);
                        }
                    }
                    suspSubtotal = BigDecimal.ZERO;
                    caseTotal = BigDecimal.ZERO;
                    prevCaseId = txn.caseId;
                }
                
                // Balance line logic - sequential match
                boolean matched = false;
                for (int i = 0; i < BRANCH_TABLE.length - 1; i++) {
                    String tableCode = BRANCH_TABLE[i];
                    int cmp = tableCode.compareTo(txn.branch);
                    
                    if (cmp < 0) {
                        // Table code is less than transaction branch, continue
                        continue;
                    } else if (cmp == 0) {
                        // Match found
                        branchSubtotals.put(tableCode, branchSubtotals.get(tableCode).add(txn.amount));
                        caseTotal = caseTotal.add(txn.amount);
                        matched = true;
                        break;
                    } else {
                        // Table code is greater, transaction goes to suspense
                        suspSubtotal = suspSubtotal.add(txn.amount);
                        caseTotal = caseTotal.add(txn.amount);
                        matched = true;
                        break;
                    }
                }
                
                if (!matched) {
                    // Fell off the end of the table
                    suspSubtotal = suspSubtotal.add(txn.amount);
                    caseTotal = caseTotal.add(txn.amount);
                }
            }
            
            if (prevCaseId != null) {
                writeCaseResults(writer, prevCaseId, branchSubtotals, suspSubtotal, caseTotal);
            }
        }
    }
    
    private static void writeCaseResults(BufferedWriter writer, String caseId, 
                                        Map<String, BigDecimal> branchSubtotals,
                                        BigDecimal suspSubtotal, BigDecimal caseTotal) throws IOException {
        // Write non-zero branch subtotals
        for (String code : BRANCH_TABLE) {
            if (!code.isEmpty() && branchSubtotals.containsKey(code)) {
                BigDecimal subtotal = branchSubtotals.get(code);
                if (subtotal.compareTo(BigDecimal.ZERO) != 0) {
                    writer.write(formatOutput(caseId, code, subtotal));
                    writer.write("\n");
                }
            }
        }
        
        // Write suspense if non-zero
        if (suspSubtotal.compareTo(BigDecimal.ZERO) != 0) {
            writer.write(formatOutput(caseId, "SUSP", suspSubtotal));
            writer.write("\n");
        }
        
        // Write total
        writer.write(formatOutput(caseId, "TOTAL", caseTotal));
        writer.write("\n");
    }
    
    private static String formatOutput(String caseId, String branch, BigDecimal amount) {
        // Pad case ID to 10 characters with trailing spaces
        String paddedCaseId = String.format("%-10s", caseId.trim());
        
        // Pad branch to 5 characters with trailing spaces
        String paddedBranch = String.format("%-5s", branch.trim());
        
        // Format amount as +9(7).99
        String sign = amount.signum() >= 0 ? "+" : "-";
        BigDecimal absAmount = amount.abs();
        String formatted = absAmount.setScale(2, RoundingMode.DOWN).toPlainString();
        
        // Pad to 10 digits (7 before decimal, 2 after, plus decimal point)
        String[] parts = formatted.split("\\.");
        String intPart = parts[0];
        String decPart = parts.length > 1 ? parts[1] : "00";
        
        // Ensure decimal part is exactly 2 digits
        while (decPart.length() < 2) {
            decPart += "0";
        }
        
        // Pad integer part to 7 digits
        while (intPart.length() < 7) {
            intPart = "0" + intPart;
        }
        
        return paddedCaseId + "," + paddedBranch + "," + sign + intPart + "." + decPart;
    }
}
