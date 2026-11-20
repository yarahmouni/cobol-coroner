import java.io.*;
import java.math.BigDecimal;
import java.util.*;

public class MatchMerge {
    private static final String[] BRANCH_CODES = {
        "A01", "B02", "C03", "D04", "E05", "F06", "Z99", "001", "9ZZ"
    };
    
    static class Transaction implements Comparable<Transaction> {
        String caseId;
        String branch;
        BigDecimal amount;
        
        Transaction(String caseId, String branch, BigDecimal amount) {
            this.caseId = caseId;
            this.branch = branch;
            this.amount = amount;
        }
        
        @Override
        public int compareTo(Transaction other) {
            // Sort by CASE-ID using EBCDIC collation, then by BRANCH using EBCDIC
            int caseCompare = ebcdicCompare(this.caseId, other.caseId);
            if (caseCompare != 0) {
                return caseCompare;
            }
            return ebcdicCompare(this.branch, other.branch);
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
            List<Transaction> transactions = readAndSortInput(inputFile);
            processAndWriteOutput(transactions, outputFile);
        } catch (IOException e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(2);
        }
    }
    
    private static List<Transaction> readAndSortInput(String filename) throws IOException {
        List<Transaction> transactions = new ArrayList<>();
        
        try (BufferedReader reader = new BufferedReader(new FileReader(filename))) {
            String header = reader.readLine();
            if (header == null) {
                throw new IOException("Cannot read header");
            }
            
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",", -1);
                if (parts.length >= 3) {
                    String caseId = parts[0];
                    String branch = parts[1];
                    BigDecimal amount = new BigDecimal(parts[2]);
                    transactions.add(new Transaction(caseId, branch, amount));
                }
            }
        }
        
        Collections.sort(transactions);
        return transactions;
    }
    
    private static void processAndWriteOutput(List<Transaction> transactions, String filename) throws IOException {
        try (PrintWriter writer = new PrintWriter(new FileWriter(filename))) {
            writer.println("CASE-ID,BRANCH,SUBTOTAL");
            
            if (transactions.isEmpty()) {
                return;
            }
            
            String prevCaseId = null;
            BigDecimal[] branchSubtotals = new BigDecimal[9];
            BigDecimal suspSubtotal = BigDecimal.ZERO;
            BigDecimal caseTotal = BigDecimal.ZERO;
            
            for (Transaction txn : transactions) {
                if (!txn.caseId.equals(prevCaseId)) {
                    if (prevCaseId != null) {
                        writeCaseResults(writer, prevCaseId, branchSubtotals, suspSubtotal, caseTotal);
                    }
                    initializeCaseTotals(branchSubtotals);
                    suspSubtotal = BigDecimal.ZERO;
                    caseTotal = BigDecimal.ZERO;
                    prevCaseId = txn.caseId;
                }
                
                int branchIndex = findBranchIndex(txn.branch);
                if (branchIndex >= 0) {
                    branchSubtotals[branchIndex] = branchSubtotals[branchIndex].add(txn.amount);
                    caseTotal = caseTotal.add(txn.amount);
                } else {
                    suspSubtotal = suspSubtotal.add(txn.amount);
                    caseTotal = caseTotal.add(txn.amount);
                }
            }
            
            if (prevCaseId != null) {
                writeCaseResults(writer, prevCaseId, branchSubtotals, suspSubtotal, caseTotal);
            }
        }
    }
    
    private static void initializeCaseTotals(BigDecimal[] branchSubtotals) {
        for (int i = 0; i < 9; i++) {
            branchSubtotals[i] = BigDecimal.ZERO;
        }
    }
    

    private static int findBranchIndex(String branch) {
        for (int i = 0; i < BRANCH_CODES.length; i++) {
            int cmp = ebcdicCompare(BRANCH_CODES[i], branch);
            if (cmp < 0) {
                continue;
            } else if (cmp == 0) {
                return i;
            } else {
                return -1;
            }
        }
        return -1;
    }
    
    private static void writeCaseResults(PrintWriter writer, String caseId, 
                                        BigDecimal[] branchSubtotals, 
                                        BigDecimal suspSubtotal, BigDecimal caseTotal) {
        for (int i = 0; i < 9; i++) {
            if (branchSubtotals[i].compareTo(BigDecimal.ZERO) != 0) {
                writer.println(formatOutput(caseId, BRANCH_CODES[i], branchSubtotals[i]));
            }
        }
        if (suspSubtotal.compareTo(BigDecimal.ZERO) != 0) {
            writer.println(formatOutput(caseId, "SUSP", suspSubtotal));
        }
        writer.println(formatOutput(caseId, "TOTAL", caseTotal));
    }
    
    private static String formatOutput(String caseId, String branch, BigDecimal amount) {
        String caseIdPadded = String.format("%-10s", caseId);
        String branchPadded = String.format("%-5s", branch);
        String amountFormatted = String.format("%+010.2f", amount);
        return caseIdPadded + "," + branchPadded + "," + amountFormatted;
    }
    
    private static int ebcdicCompare(String s1, String s2) {
        int len = Math.min(s1.length(), s2.length());
        for (int i = 0; i < len; i++) {
            int c1 = ebcdicValue(s1.charAt(i));
            int c2 = ebcdicValue(s2.charAt(i));
            if (c1 != c2) {
                return c1 - c2;
            }
        }
        return s1.length() - s2.length();
    }
    
    private static int ebcdicValue(char c) {
        // EBCDIC collating sequence approximation for the characters used
        // Space = 0x40, 0-9 = 0xF0-0xF9, A-Z = 0xC1-0xE9 (with gaps)
        // In EBCDIC: space < lowercase < uppercase < digits
        // For our purposes: space < A-Z < 0-9
        if (c == ' ') return 0x40;
        if (c >= 'A' && c <= 'I') return 0xC1 + (c - 'A');
        if (c >= 'J' && c <= 'R') return 0xD1 + (c - 'J');
        if (c >= 'S' && c <= 'Z') return 0xE2 + (c - 'S');
        if (c >= '0' && c <= '9') return 0xF0 + (c - '0');
        // Default for unknown characters
        return (int) c;
    }
}
