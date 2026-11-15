import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Correct Java port: sorts and compares by IBM1047 byte order (EBCDIC).
 */
public class MatchMerge {
    private static final Charset IBM1047 = Charset.forName("IBM1047");
    
    static class Transaction {
        String caseId;
        String branch;
        BigDecimal amount;
        
        Transaction(String caseId, String branch, BigDecimal amount) {
            this.caseId = caseId;
            this.branch = branch;
            this.amount = amount;
        }
    }
    
    static class BranchEntry {
        String code;
        BigDecimal subtotal;
        
        BranchEntry(String code) {
            this.code = code;
            this.subtotal = BigDecimal.ZERO;
        }
    }
    
    public static void main(String[] args) {
        try {
            String inputFile = System.getenv("INPUT_FILE");
            String outputFile = System.getenv("OUTPUT_FILE");
            
            if (inputFile == null || inputFile.isEmpty()) {
                inputFile = "input.csv";
            }
            if (outputFile == null || outputFile.isEmpty()) {
                outputFile = "output.csv";
            }
            
            List<Transaction> transactions = readTransactions(inputFile);
            
            transactions.sort((t1, t2) -> {
                int caseCompare = t1.caseId.compareTo(t2.caseId);
                if (caseCompare != 0) {
                    return caseCompare;
                }
                return compareEBCDIC(t1.branch, t2.branch);
            });
            
            List<String> results = new ArrayList<>();
            results.add("CASE-ID,BRANCH,SUBTOTAL");
            
            String currentCaseId = null;
            List<BranchEntry> branchTable = null;
            BigDecimal suspSubtotal = BigDecimal.ZERO;
            BigDecimal caseTotal = BigDecimal.ZERO;
            
            for (Transaction txn : transactions) {
                if (!txn.caseId.equals(currentCaseId)) {
                    if (currentCaseId != null) {
                        writeCaseResults(currentCaseId, branchTable, suspSubtotal, caseTotal, results);
                    }
                    currentCaseId = txn.caseId;
                    branchTable = initializeBranchTable();
                    suspSubtotal = BigDecimal.ZERO;
                    caseTotal = BigDecimal.ZERO;
                }
                
                int i = 0;
                while (i < 9 && compareEBCDIC(branchTable.get(i).code, txn.branch) < 0) {
                    i++;
                }
                
                if (i < 9 && compareEBCDIC(branchTable.get(i).code, txn.branch) == 0) {
                    branchTable.get(i).subtotal = branchTable.get(i).subtotal.add(txn.amount);
                } else {
                    suspSubtotal = suspSubtotal.add(txn.amount);
                }
                caseTotal = caseTotal.add(txn.amount);
            }
            
            if (currentCaseId != null) {
                writeCaseResults(currentCaseId, branchTable, suspSubtotal, caseTotal, results);
            }
            
            writeOutput(outputFile, results);
            System.exit(0);
            
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(2);
        }
    }
    
    private static int compareEBCDIC(String s1, String s2) {
        byte[] b1 = s1.getBytes(IBM1047);
        byte[] b2 = s2.getBytes(IBM1047);
        
        int len = Math.min(b1.length, b2.length);
        for (int i = 0; i < len; i++) {
            int cmp = Byte.compareUnsigned(b1[i], b2[i]);
            if (cmp != 0) {
                return cmp;
            }
        }
        return Integer.compare(b1.length, b2.length);
    }
    
    private static List<BranchEntry> initializeBranchTable() {
        List<BranchEntry> table = new ArrayList<>();
        table.add(new BranchEntry("A01"));
        table.add(new BranchEntry("B02"));
        table.add(new BranchEntry("C03"));
        table.add(new BranchEntry("D04"));
        table.add(new BranchEntry("E05"));
        table.add(new BranchEntry("F06"));
        table.add(new BranchEntry("Z99"));
        table.add(new BranchEntry("001"));
        table.add(new BranchEntry("9ZZ"));
        return table;
    }
    
    private static List<Transaction> readTransactions(String filename) throws IOException {
        List<Transaction> transactions = new ArrayList<>();
        List<String> lines = Files.readAllLines(Paths.get(filename));
        
        for (int i = 1; i < lines.size(); i++) {
            String line = lines.get(i);
            String[] fields = line.split(",", -1);
            if (fields.length >= 3) {
                String caseId = fields[0];
                String branch = fields[1];
                BigDecimal amount = new BigDecimal(fields[2]);
                transactions.add(new Transaction(caseId, branch, amount));
            }
        }
        
        return transactions;
    }
    
    private static void writeCaseResults(String caseId, List<BranchEntry> branchTable,
                                         BigDecimal suspSubtotal, BigDecimal caseTotal,
                                         List<String> results) {
        for (BranchEntry entry : branchTable) {
            if (entry.subtotal.compareTo(BigDecimal.ZERO) != 0) {
                results.add(padRight(caseId.trim(), 10) + "," + padRight(entry.code.trim(), 5) + "," + formatAmount(entry.subtotal));
            }
        }
        if (suspSubtotal.compareTo(BigDecimal.ZERO) != 0) {
            results.add(padRight(caseId.trim(), 10) + "," + padRight("SUSP", 5) + "," + formatAmount(suspSubtotal));
        }
        results.add(padRight(caseId.trim(), 10) + "," + padRight("TOTAL", 5) + "," + formatAmount(caseTotal));
    }
    
    private static String padRight(String s, int length) {
        if (s.length() >= length) {
            return s.substring(0, length);
        }
        return s + " ".repeat(length - s.length());
    }
    
    private static String formatAmount(BigDecimal amount) {
        BigDecimal scaled = amount.setScale(2, BigDecimal.ROUND_DOWN);
        long wholePart = scaled.longValue();
        long cents = scaled.remainder(BigDecimal.ONE).multiply(new BigDecimal("100")).abs().longValue();
        
        // Truncate to 7 integer digits to match +9(7).99
        boolean negative = wholePart < 0;
        long absWhole = Math.abs(wholePart);
        if (absWhole > 9999999) {
            absWhole = absWhole % 10000000;
        }
        
        if (scaled.compareTo(BigDecimal.ZERO) >= 0) {
            return String.format("+%07d.%02d", absWhole, cents);
        } else {
            return String.format("-%07d.%02d", absWhole, cents);
        }
    }
    
    private static void writeOutput(String filename, List<String> lines) throws IOException {
        try (PrintWriter writer = new PrintWriter(new FileWriter(filename))) {
            for (String line : lines) {
                writer.println(line);
            }
        }
    }
}
