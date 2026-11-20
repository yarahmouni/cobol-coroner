import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStreamWriter;
import java.io.BufferedInputStream;
import java.io.Writer;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Java port of the COBOL program MATCH-MERGE.
 *
 * Behaviour preserved from the COBOL source:
 * - The program runs under PROGRAM COLLATING SEQUENCE IS EBCDIC, so every
 *   alphanumeric ordering comparison (the SORT keys and the branch table
 *   match) uses EBCDIC order, not ASCII order: space < lower case < upper
 *   case < digits.
 * - Input is LINE SEQUENTIAL, records are PIC X(200); the first record is a
 *   header and is skipped.
 * - UNSTRING ... DELIMITED BY "," into X(10), X(3), X(12). Receivers that
 *   receive no data keep their previous contents.
 * - FUNCTION NUMVAL then MOVE to S9(7)V99 (truncation, no rounding).
 * - The branch table is scanned in order; a branch that sorts above every
 *   table entry leaves TABLE-INDEX at 10 and its amount is not accumulated
 *   anywhere (the COBOL ELSE branch after the loop is never taken).
 * - Records whose CASE-ID is all spaces at the start of the sorted stream are
 *   accumulated but never written.
 * - Output lines are OUTPUT-PARTS (28 bytes) written into a 200 byte
 *   LINE SEQUENTIAL record, so trailing spaces are removed.
 */
public final class MatchMerge {

    private static final int INPUT_RECORD_LEN = 200;
    private static final int CASE_ID_LEN = 10;
    private static final int BRANCH_LEN = 3;
    private static final int AMOUNT_LEN = 12;
    private static final int TABLE_SIZE = 9;

    /** S9(7)V99 holds at most 9 digits; S9(9)V99 holds at most 11 digits. */
    private static final long MOD_S9_7_V99 = 1_000_000_000L;
    private static final long MOD_S9_9_V99 = 100_000_000_000L;
    /** +9(7).99 shows 9 digits. */
    private static final long MOD_EDIT = 1_000_000_000L;

    private static final String[] TABLE_CODE = {
        "A01", "B02", "C03", "D04", "E05", "F06", "Z99", "001", "9ZZ"
    };

    /** Weight of each byte value (0..255) in the EBCDIC collating sequence. */
    private static final int[] EBCDIC_WEIGHT = buildEbcdicWeights();

    private MatchMerge() {
    }

    /** One SORT-RECORD. */
    private static final class SortRecord {
        final String caseId;   // X(10), space padded
        final String branch;   // X(3), space padded
        final long amountCents; // S9(7)V99 scaled by 100

        SortRecord(String caseId, String branch, long amountCents) {
            this.caseId = caseId;
            this.branch = branch;
            this.amountCents = amountCents;
        }
    }

    public static void main(String[] args) {
        String inputPath = envOrDefault("INPUT_FILE", "input.csv");
        String outputPath = envOrDefault("OUTPUT_FILE", "output.csv");

        List<SortRecord> records = readInput(inputPath);

        records.sort((a, b) -> {
            int c = compareEbcdic(a.caseId, b.caseId);
            if (c != 0) {
                return c;
            }
            return compareEbcdic(a.branch, b.branch);
        });

        processSorted(records, outputPath);
        System.exit(0);
    }

    // ------------------------------------------------------------------
    // MAIN-LOGIC helpers
    // ------------------------------------------------------------------

    private static String envOrDefault(String name, String dflt) {
        String v = System.getenv(name);
        if (v == null) {
            return dflt;
        }
        // ACCEPT into PIC X(200): truncated to 200, compared against SPACES.
        if (v.length() > 200) {
            v = v.substring(0, 200);
        }
        String trimmed = rtrimSpaces(v);
        if (trimmed.isEmpty() || isAllLowValues(v)) {
            return dflt;
        }
        return trimmed;
    }

    private static boolean isAllLowValues(String s) {
        if (s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != '\0') {
                return false;
            }
        }
        return true;
    }

    // ------------------------------------------------------------------
    // READ-INPUT-SKIP-HEADER
    // ------------------------------------------------------------------

    private static List<SortRecord> readInput(String inputPath) {
        List<SortRecord> out = new ArrayList<>();
        InputStream in;
        try {
            in = new BufferedInputStream(new FileInputStream(inputPath));
        } catch (IOException e) {
            fail("ERROR: Cannot open input file");
            return out; // not reached
        }

        // UNSTRING receivers live in WORKING-STORAGE and keep their values
        // between records when a record supplies fewer fields.
        String inCaseId = spaces(CASE_ID_LEN);
        String inBranch = spaces(BRANCH_LEN);
        String inAmount = spaces(AMOUNT_LEN);

        try {
            String header = readLine(in);
            if (header != null) {
                String line;
                while ((line = readLine(in)) != null) {
                    String record = padRight(line, INPUT_RECORD_LEN);

                    String[] recv = {inCaseId, inBranch, inAmount};
                    int[] sizes = {CASE_ID_LEN, BRANCH_LEN, AMOUNT_LEN};
                    unstring(record, ',', recv, sizes);
                    inCaseId = recv[0];
                    inBranch = recv[1];
                    inAmount = recv[2];

                    long cents = moveToS9_7V99(numval(inAmount));
                    out.add(new SortRecord(inCaseId, inBranch, cents));
                }
            }
        } catch (IOException e) {
            fail("ERROR: Read error");
        } finally {
            try {
                in.close();
            } catch (IOException ignored) {
                // CLOSE status not checked in the COBOL source
            }
        }
        return out;
    }

    /**
     * Reads one LINE SEQUENTIAL record as ISO-8859-1 (one char per byte),
     * without the terminating newline. Returns null at end of file.
     * Data beyond the 200 byte record length is discarded.
     */
    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        int b;
        boolean any = false;
        while ((b = in.read()) != -1) {
            any = true;
            if (b == '\n') {
                break;
            }
            buf.write(b);
        }
        if (!any) {
            return null;
        }
        String s = new String(buf.toByteArray(), StandardCharsets.ISO_8859_1);
        if (s.endsWith("\r")) {
            s = s.substring(0, s.length() - 1);
        }
        if (s.length() > INPUT_RECORD_LEN) {
            s = s.substring(0, INPUT_RECORD_LEN);
        }
        return s;
    }

    /**
     * UNSTRING source DELIMITED BY delim INTO receivers. Each receiver gets
     * the next delimited segment, left justified, space padded or truncated
     * to its size. Receivers past the end of the source keep their values.
     */
    private static void unstring(String source, char delim, String[] receivers, int[] sizes) {
        int pos = 0;
        int len = source.length();
        for (int r = 0; r < receivers.length; r++) {
            if (pos >= len) {
                break;
            }
            int end = source.indexOf(delim, pos);
            String segment;
            if (end < 0) {
                segment = source.substring(pos);
                pos = len;
            } else {
                segment = source.substring(pos, end);
                pos = end + 1;
            }
            receivers[r] = fit(segment, sizes[r]);
        }
    }

    /**
     * FUNCTION NUMVAL on an alphanumeric argument. Returns the value scaled
     * as a BigDecimal-like pair encoded in a String-free way: we return the
     * value multiplied by 10^digitsAfterPoint together with the scale.
     */
    private static long[] numval(String s) {
        String t = s.trim();
        if (t.isEmpty()) {
            return new long[] {0L, 0L};
        }
        boolean negative = false;
        int i = 0;
        int n = t.length();

        // leading sign, optionally followed by spaces
        if (t.charAt(i) == '+' || t.charAt(i) == '-') {
            negative = t.charAt(i) == '-';
            i++;
            while (i < n && t.charAt(i) == ' ') {
                i++;
            }
        }

        long intPart = 0L;
        long fracDigits = 0L;
        long fracVal = 0L;
        boolean seenDigit = false;
        boolean seenPoint = false;
        while (i < n) {
            char c = t.charAt(i);
            if (c >= '0' && c <= '9') {
                seenDigit = true;
                if (seenPoint) {
                    if (fracDigits < 18) {
                        fracVal = fracVal * 10 + (c - '0');
                        fracDigits++;
                    }
                } else {
                    intPart = (intPart * 10 + (c - '0')) % 1_000_000_000_000_000L;
                }
                i++;
            } else if (c == '.' && !seenPoint) {
                seenPoint = true;
                i++;
            } else {
                break;
            }
        }

        // trailing part: spaces, then optional sign / CR / DB (only if no
        // leading sign was given), then spaces
        String rest = t.substring(i).trim();
        boolean valid = seenDigit;
        if (!rest.isEmpty()) {
            boolean hadLeadingSign = t.charAt(0) == '+' || t.charAt(0) == '-';
            String up = rest.toUpperCase();
            if (!hadLeadingSign && (up.equals("+") || up.equals("-")
                    || up.equals("CR") || up.equals("DB"))) {
                negative = !up.equals("+");
            } else {
                valid = false;
            }
        }
        if (!valid) {
            return new long[] {0L, 0L};
        }

        // value scaled to 2 decimals, truncated
        long cents = intPart * 100;
        if (fracDigits >= 2) {
            long div = 1L;
            for (long k = 2; k < fracDigits; k++) {
                div *= 10;
            }
            cents += fracVal / div;
        } else if (fracDigits == 1) {
            cents += fracVal * 10;
        }
        return new long[] {negative ? -cents : cents, 2L};
    }

    /** MOVE numeric to S9(7)V99: high order digits are truncated. */
    private static long moveToS9_7V99(long[] value) {
        long cents = value[0];
        return cents % MOD_S9_7_V99;
    }

    // ------------------------------------------------------------------
    // PROCESS-SORTED-DATA
    // ------------------------------------------------------------------

    private static void processSorted(List<SortRecord> records, String outputPath) {
        Writer w;
        try {
            w = new BufferedWriter(new OutputStreamWriter(
                    new FileOutputStream(outputPath), StandardCharsets.ISO_8859_1));
        } catch (IOException e) {
            fail("ERROR: Cannot open output file");
            return;
        }

        long[] tableSubtotal = new long[TABLE_SIZE];
        long[] suspAndTotal = new long[2]; // [0] SUSP-SUBTOTAL, [1] CASE-TOTAL
        String blankCase = spaces(CASE_ID_LEN);

        try {
            writeRecord(w, "CASE-ID,BRANCH,SUBTOTAL");

            String prevCaseId = blankCase;
            for (SortRecord rec : records) {
                String currentCaseId = rec.caseId;
                if (!currentCaseId.equals(prevCaseId)) {
                    if (!prevCaseId.equals(blankCase)) {
                        writeCaseResults(w, prevCaseId, tableSubtotal, suspAndTotal);
                    }
                    Arrays.fill(tableSubtotal, 0L);
                    suspAndTotal[0] = 0L;
                    suspAndTotal[1] = 0L;
                    prevCaseId = currentCaseId;
                }
                balanceLine(rec.branch, rec.amountCents, tableSubtotal, suspAndTotal);
            }
            if (!prevCaseId.equals(blankCase)) {
                writeCaseResults(w, prevCaseId, tableSubtotal, suspAndTotal);
            }
            w.close();
        } catch (IOException e) {
            fail("ERROR: Write error");
        }
    }

    private static void balanceLine(String txnBranch, long amount,
                                     long[] tableSubtotal, long[] suspAndTotal) {
        int idx = 0; // TABLE-INDEX - 1
        while (idx < TABLE_SIZE) {
            int c = compareEbcdic(TABLE_CODE[idx], txnBranch);
            if (c < 0) {
                idx++;
            } else if (c == 0) {
                tableSubtotal[idx] = add9V99(tableSubtotal[idx], amount);
                suspAndTotal[1] = add9V99(suspAndTotal[1], amount);
                return;
            } else {
                suspAndTotal[0] = add9V99(suspAndTotal[0], amount);
                suspAndTotal[1] = add9V99(suspAndTotal[1], amount);
                return;
            }
        }
        // Loop fell off the end: TABLE-INDEX is 10, so the COBOL takes the
        // CONTINUE branch and the amount is not accumulated.
    }

    /** ADD into S9(9)V99 without ON SIZE ERROR: high order truncation. */
    private static long add9V99(long acc, long amount) {
        return (acc + amount) % MOD_S9_9_V99;
    }

    private static void writeCaseResults(Writer w, String prevCaseId,
                                         long[] tableSubtotal, long[] suspAndTotal)
            throws IOException {
        String outCase = fit(rtrimSpaces(prevCaseId), CASE_ID_LEN);
        for (int i = 0; i < TABLE_SIZE; i++) {
            if (tableSubtotal[i] != 0L) {
                String outBranch = fit(rtrimSpaces(TABLE_CODE[i]), 5);
                writeRecord(w, outCase + "," + outBranch + "," + edit(tableSubtotal[i]));
            }
        }
        if (suspAndTotal[0] != 0L) {
            writeRecord(w, outCase + "," + fit("SUSP", 5) + "," + edit(suspAndTotal[0]));
        }
        writeRecord(w, outCase + "," + fit("TOTAL", 5) + "," + edit(suspAndTotal[1]));
    }

    /** PIC +9(7).99 edit of a value in cents. */
    private static String edit(long cents) {
        boolean negative = cents < 0;
        long abs = Math.abs(cents) % MOD_EDIT;
        if (abs == 0) {
            negative = false;
        }
        long intPart = abs / 100;
        long frac = abs % 100;
        StringBuilder sb = new StringBuilder(11);
        sb.append(negative ? '-' : '+');
        String ip = Long.toString(intPart);
        for (int k = ip.length(); k < 7; k++) {
            sb.append('0');
        }
        sb.append(ip);
        sb.append('.');
        if (frac < 10) {
            sb.append('0');
        }
        sb.append(frac);
        return sb.toString();
    }

    /** WRITE to a LINE SEQUENTIAL file: trailing spaces are not written. */
    private static void writeRecord(Writer w, String data) throws IOException {
        String rec = data.length() > INPUT_RECORD_LEN ? data.substring(0, INPUT_RECORD_LEN) : data;
        w.write(rtrimSpaces(rec));
        w.write('\n');
    }

    // ------------------------------------------------------------------
    // EBCDIC collating sequence
    // ------------------------------------------------------------------

    /**
     * Compares two alphanumeric items under the EBCDIC collating sequence.
     * The shorter item is padded with spaces, as COBOL does.
     */
    static int compareEbcdic(String a, String b) {
        int n = Math.max(a.length(), b.length());
        for (int i = 0; i < n; i++) {
            int ca = i < a.length() ? a.charAt(i) & 0xFF : ' ';
            int cb = i < b.length() ? b.charAt(i) & 0xFF : ' ';
            int wa = EBCDIC_WEIGHT[ca];
            int wb = EBCDIC_WEIGHT[cb];
            if (wa != wb) {
                return wa < wb ? -1 : 1;
            }
        }
        return 0;
    }

    private static int[] buildEbcdicWeights() {
        int[] weights = new int[256];
        Charset cp037 = null;
        try {
            cp037 = Charset.forName("IBM037");
        } catch (RuntimeException e) {
            cp037 = null;
        }
        if (cp037 != null) {
            for (int i = 0; i < 256; i++) {
                byte[] enc = String.valueOf((char) i).getBytes(cp037);
                weights[i] = enc.length == 1 ? (enc[0] & 0xFF) : 256 + i;
            }
            return weights;
        }
        // Fallback: CP037 code points for printable ASCII, raw value otherwise.
        for (int i = 0; i < 256; i++) {
            weights[i] = 256 + i;
        }
        String ascii = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
        int[] ebc = {
            0x40, 0x5A, 0x7F, 0x7B, 0x5B, 0x6C, 0x50, 0x7D, 0x4D, 0x5D, 0x5C, 0x4E, 0x6B, 0x60, 0x4B, 0x61,
            0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0x7A, 0x5E, 0x4C, 0x7E, 0x6E, 0x6F,
            0x7C, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6,
            0xD7, 0xD8, 0xD9, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xBA, 0xE0, 0xBB, 0xB0, 0x6D,
            0x79, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96,
            0x97, 0x98, 0x99, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xC0, 0x4F, 0xD0, 0xA1
        };
        for (int k = 0; k < ascii.length(); k++) {
            weights[ascii.charAt(k)] = ebc[k];
        }
        weights[0] = 0x00;
        return weights;
    }

    // ------------------------------------------------------------------
    // Small helpers
    // ------------------------------------------------------------------

    private static String spaces(int n) {
        char[] c = new char[n];
        Arrays.fill(c, ' ');
        return new String(c);
    }

    /** MOVE alphanumeric to PIC X(size): left justify, pad or truncate. */
    private static String fit(String s, int size) {
        if (s.length() >= size) {
            return s.substring(0, size);
        }
        return padRight(s, size);
    }

    private static String padRight(String s, int size) {
        if (s.length() >= size) {
            return s;
        }
        StringBuilder sb = new StringBuilder(size);
        sb.append(s);
        while (sb.length() < size) {
            sb.append(' ');
        }
        return sb.toString();
    }

    private static String rtrimSpaces(String s) {
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == ' ') {
            end--;
        }
        return s.substring(0, end);
    }

    private static void fail(String message) {
        System.err.println(message);
        System.exit(2);
    }
}
