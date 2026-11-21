import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Port of CardDemo CBACT04C (interest calculator) as exercised through
 * HARNESS-CBACT04C: one CSV row in, one CSV row out.
 *
 * The harness writes four text files, LOAD-FILES loads them into indexed
 * files (stopping at the first failed write), RUN-CBACT04C runs the program,
 * DUMP-ACCT lists the accounts. This class simulates that chain in memory.
 */
public class Cbact04c {

    private static final int EXIT_ABEND = 231; // RETURN-CODE 999 seen as a process exit status
    private static final int EXIT_MALFORMED = 252;

    /** Abnormal end of the simulated CBACT04C (9999-ABEND-PROGRAM). */
    private static final class Abend extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Abend() {
            super(null, null, false, false);
        }
    }

    private static final class AcctRec {
        String id;       // 11 digits
        String group;    // 10 chars
        BigDecimal bal;  // S9(10)V99
    }

    private static final class Tx {
        String id;
        String type;
        String cat;
        String source;
        String desc;
        BigDecimal amt;
        String card;
        String orig;
        String proc;
    }

    // ------------------------------------------------------------ helpers

    private static String padRight(String s, int n) {
        if (s.length() >= n) {
            return s.substring(0, n);
        }
        StringBuilder sb = new StringBuilder(s);
        while (sb.length() < n) {
            sb.append(' ');
        }
        return sb.toString();
    }

    private static String zeroPad(BigInteger v, int n) {
        String s = v.toString();
        StringBuilder sb = new StringBuilder();
        for (int i = s.length(); i < n; i++) {
            sb.append('0');
        }
        return sb.append(s).toString();
    }

    /** FUNCTION NUMVAL as GnuCOBOL scans it: invalid characters are skipped. */
    static BigDecimal numval(String s) {
        StringBuilder digits = new StringBuilder();
        int decimals = 0;
        boolean decimalSeen = false;
        boolean negative = false;
        int count = 0;
        int len = s.length();
        for (int i = 0; i < len; i++) {
            char c = s.charAt(i);
            if (i < len - 1) {
                char u = Character.toUpperCase(c);
                char d = Character.toUpperCase(s.charAt(i + 1));
                if ((u == 'C' && d == 'R') || (u == 'D' && d == 'B')) {
                    negative = true;
                    break;
                }
            }
            if (c >= '0' && c <= '9') {
                if (count < 38) {
                    digits.append(c);
                    count++;
                    if (decimalSeen) {
                        decimals++;
                    }
                }
            } else if (c == '-') {
                negative = true;
            } else if (c == '.') {
                decimalSeen = true;
            }
        }
        BigInteger unscaled = digits.length() == 0 ? BigInteger.ZERO : new BigInteger(digits.toString());
        if (negative) {
            unscaled = unscaled.negate();
        }
        return new BigDecimal(unscaled, decimals);
    }

    /** Store into a signed numeric DISPLAY field with 2 decimals: truncate, drop high-order digits. */
    private static BigDecimal signed2(BigDecimal v, int totalDigits) {
        BigInteger u = v.setScale(2, RoundingMode.DOWN).unscaledValue();
        BigInteger mod = BigInteger.TEN.pow(totalDigits);
        BigInteger r = u.abs().mod(mod);
        if (u.signum() < 0) {
            r = r.negate();
        }
        return new BigDecimal(r, 2);
    }

    /** Store into an unsigned integer DISPLAY field: absolute value, integer part, low-order digits. */
    private static BigInteger unsignedInt(BigDecimal v, int digits) {
        return v.toBigInteger().abs().mod(BigInteger.TEN.pow(digits));
    }

    private static String fmtNum(BigDecimal v) {
        if (v.signum() == 0) {
            return "0.00";
        }
        return v.setScale(2, RoundingMode.DOWN).toPlainString();
    }

    private static String rtrim(String s) {
        int n = s.length();
        while (n > 0 && s.charAt(n - 1) == ' ') {
            n--;
        }
        return s.substring(0, n);
    }

    // ------------------------------------------------------------ result row

    private static final class Result {
        String caseId = "";
        int exitCode;
        boolean rowOk;
        String[] updBal = new String[5];
        int txCount;
        List<Tx> tx = new ArrayList<>();
    }

    // ------------------------------------------------------------ one case

    private static Result processRow(String line) {
        Result res = new Result();
        res.rowOk = true;
        int commas = 0;
        for (int i = 0; i < line.length(); i++) {
            if (line.charAt(i) == ',') {
                commas++;
            }
        }
        if (commas != 156) {
            res.rowOk = false;
            res.exitCode = EXIT_MALFORMED;
            return res;
        }
        String[] raw = line.split(",", -1);
        String[] fld = new String[158]; // 1-based
        for (int i = 1; i <= 157; i++) {
            String f = raw[i - 1];
            fld[i] = f.length() > 40 ? f.substring(0, 40) : f;
        }
        res.caseId = padRight(fld[1], 10);
        String parmDate = padRight(fld[2], 10);

        // VALIDATE-DATE
        String f2 = padRight(fld[2], 40);
        boolean dateOk = true;
        for (int i = 10; i < 40; i++) {
            if (f2.charAt(i) != ' ') {
                dateOk = false;
            }
        }
        boolean seenSpace = false;
        for (int k = 0; k < 10; k++) {
            char c = parmDate.charAt(k);
            if (c == ' ') {
                seenSpace = true;
            } else if (seenSpace) {
                dateOk = false;
            } else if (!((c >= '0' && c <= '9') || c == '-')) {
                dateOk = false;
            }
        }
        if (!dateOk) {
            res.rowOk = false;
            res.exitCode = EXIT_MALFORMED;
            return res;
        }

        // LOAD-TABLES
        BigInteger[] aId = new BigInteger[5];
        String[] aGroup = new String[5];
        BigDecimal[] aBal = new BigDecimal[5];
        String[] aCard = new String[5];
        boolean[] aXref = new boolean[5];
        for (int a = 0; a < 5; a++) {
            int base = 3 + a * 7;
            aId[a] = unsignedInt(numval(fld[base]), 11);
            aGroup[a] = padRight(fld[base + 1], 10);
            aBal[a] = signed2(numval(fld[base + 2]), 12);
            // credit and debit (base+3, base+4) never reach the output
            aCard[a] = padRight(fld[base + 5], 16);
            String x = padRight(fld[base + 6], 1);
            aXref[a] = x.charAt(0) == 'Y';
        }
        int[] cbIdx = new int[10];
        String[] cbType = new String[10];
        BigInteger[] cbCat = new BigInteger[10];
        BigDecimal[] cbBal = new BigDecimal[10];
        for (int c = 0; c < 10; c++) {
            int base = 38 + c * 4;
            cbIdx[c] = unsignedInt(numval(fld[base]), 3).intValue();
            if (cbIdx[c] > 5) {
                res.rowOk = false;
            }
            cbType[c] = padRight(fld[base + 1], 2);
            cbCat[c] = unsignedInt(numval(fld[base + 2]), 4);
            cbBal[c] = signed2(numval(fld[base + 3]), 11);
        }
        String[] rtGroup = new String[20];
        String[] rtType = new String[20];
        BigInteger[] rtCat = new BigInteger[20];
        BigDecimal[] rtVal = new BigDecimal[20];
        for (int r = 0; r < 20; r++) {
            int base = 78 + r * 4;
            rtGroup[r] = padRight(fld[base], 10);
            rtType[r] = padRight(fld[base + 1], 2);
            rtCat[r] = unsignedInt(numval(fld[base + 2]), 4);
            rtVal[r] = signed2(numval(fld[base + 3]), 6);
        }
        if (!res.rowOk) {
            res.exitCode = EXIT_MALFORMED;
            return res;
        }

        // ---- LOAD-FILES: each file is loaded in turn; the first failed write stops everything
        TreeMap<String, BigDecimal> tcat = new TreeMap<>();
        LinkedHashMap<String, String> xrefByCard = new LinkedHashMap<>(); // card -> acct id
        TreeMap<String, AcctRec> acct = new TreeMap<>();
        TreeMap<String, BigDecimal> disc = new TreeMap<>();
        boolean xrefExists = false;
        boolean acctExists = false;
        boolean discExists = false;

        boolean ok = true;
        for (int c = 0; c < 10 && ok; c++) {
            if (cbIdx[c] > 0) {
                BigInteger id = aId[cbIdx[c] - 1];
                String key = zeroPad(id, 11) + cbType[c] + zeroPad(cbCat[c], 4);
                if (tcat.containsKey(key)) {
                    ok = false;
                } else {
                    tcat.put(key, cbBal[c]);
                }
            }
        }
        if (ok) {
            xrefExists = true;
            for (int a = 0; a < 5 && ok; a++) {
                if (aId[a].signum() > 0 && aXref[a]) {
                    if (xrefByCard.containsKey(aCard[a])) {
                        ok = false;
                    } else {
                        xrefByCard.put(aCard[a], zeroPad(aId[a], 11));
                    }
                }
            }
        }
        if (ok) {
            acctExists = true;
            for (int a = 0; a < 5 && ok; a++) {
                if (aId[a].signum() > 0) {
                    String key = zeroPad(aId[a], 11);
                    if (acct.containsKey(key)) {
                        ok = false;
                    } else {
                        AcctRec rec = new AcctRec();
                        rec.id = key;
                        rec.group = aGroup[a];
                        rec.bal = aBal[a];
                        acct.put(key, rec);
                    }
                }
            }
        }
        if (ok) {
            discExists = true;
            for (int r = 0; r < 20 && ok; r++) {
                if (!rtGroup[r].equals("          ")) {
                    String key = rtGroup[r] + rtType[r] + zeroPad(rtCat[r], 4);
                    if (disc.containsKey(key)) {
                        ok = false;
                    } else {
                        disc.put(key, rtVal[r]);
                    }
                }
            }
        }

        // ---- RUN-CBACT04C
        List<Tx> txList = new ArrayList<>();
        boolean txFileExists = false;
        int exit = 0;
        try {
            if (!xrefExists || !discExists || !acctExists) {
                throw new Abend(); // OPEN of a file that was never created
            }
            txFileExists = true;
            runProgram(parmDate, tcat, xrefByCard, acct, disc, txList);
        } catch (Abend e) {
            exit = EXIT_ABEND;
        }
        res.exitCode = exit;

        // ---- DUMP-ACCT and READ-BALANCES
        if (acctExists) {
            for (int a = 0; a < 5; a++) {
                if (aId[a].signum() > 0) {
                    AcctRec rec = acct.get(zeroPad(aId[a], 11));
                    if (rec != null) {
                        res.updBal[a] = fmtNum(rec.bal);
                    }
                }
            }
        }
        if (txFileExists) {
            res.txCount = txList.size();
            res.tx = txList;
        }
        return res;
    }

    // ------------------------------------------------------------ the program itself

    private static void runProgram(String parmDate,
                                   TreeMap<String, BigDecimal> tcat,
                                   LinkedHashMap<String, String> xrefByCard,
                                   TreeMap<String, AcctRec> acct,
                                   TreeMap<String, BigDecimal> disc,
                                   List<Tx> out) {
        String ts = parmDate.substring(0, 4) + "-" + parmDate.substring(5, 7) + "-"
                + parmDate.substring(8, 10) + "-12.00.00.000000";
        String lastAcct = "           "; // WS-LAST-ACCT-NUM, 11 spaces
        boolean firstTime = true;
        BigDecimal totalInt = new BigDecimal(BigInteger.ZERO, 2);
        int suffix = 0;
        AcctRec cur = null;     // ACCOUNT-RECORD
        String curCard = null;  // XREF-CARD-NUM

        for (Map.Entry<String, BigDecimal> e : tcat.entrySet()) {
            String key = e.getKey();
            BigDecimal balance = e.getValue();
            String acctId = key.substring(0, 11);
            String typeCd = key.substring(11, 13);
            String catCd = key.substring(13, 17);

            if (!acctId.equals(lastAcct)) {
                if (!firstTime) {
                    // 1050-UPDATE-ACCOUNT
                    cur.bal = signed2(cur.bal.add(totalInt), 12);
                    acct.put(cur.id, cur);
                } else {
                    firstTime = false;
                }
                totalInt = new BigDecimal(BigInteger.ZERO, 2);
                lastAcct = acctId;
                // 1100-GET-ACCT-DATA
                AcctRec stored = acct.get(acctId);
                if (stored == null) {
                    throw new Abend();
                }
                cur = new AcctRec();
                cur.id = stored.id;
                cur.group = stored.group;
                cur.bal = stored.bal;
                // 1110-GET-XREF-DATA (read by alternate key: first record for the account)
                curCard = null;
                for (Map.Entry<String, String> x : xrefByCard.entrySet()) {
                    if (x.getValue().equals(acctId)) {
                        curCard = x.getKey();
                        break;
                    }
                }
                if (curCard == null) {
                    throw new Abend();
                }
            }

            // 1200-GET-INTEREST-RATE
            BigDecimal rate = disc.get(cur.group + typeCd + catCd);
            if (rate == null) {
                rate = disc.get("DEFAULT   " + typeCd + catCd);
                if (rate == null) {
                    throw new Abend();
                }
            }

            if (rate.signum() != 0) {
                // 1300-COMPUTE-INTEREST
                BigDecimal monthly = signed2(
                        balance.multiply(rate).divide(new BigDecimal(1200), 2, RoundingMode.DOWN), 11);
                totalInt = signed2(totalInt.add(monthly), 11);
                // 1300-B-WRITE-TX
                suffix = (suffix + 1) % 1000000;
                Tx t = new Tx();
                t.id = parmDate + zeroPad(BigInteger.valueOf(suffix), 6);
                t.type = "01";
                t.cat = "0005";
                t.source = "System";
                t.desc = "Int. for a/c " + cur.id;
                t.amt = monthly;
                t.card = curCard;
                t.orig = ts;
                t.proc = ts;
                out.add(t);
            }
        }
        // End of file: the last account is never updated (1050 is not reached).
    }

    // ------------------------------------------------------------ CSV output

    private static final class RowWriter {
        private final StringBuilder sb = new StringBuilder();
        private boolean first = true;

        void text(String v) {
            if (first) {
                first = false;
            } else {
                sb.append(',');
            }
            String s = v.length() > 120 ? v.substring(0, 120) : v;
            sb.append(rtrim(s));
        }

        String line() {
            return sb.toString();
        }
    }

    private static String header() {
        RowWriter w = new RowWriter();
        w.text("CASE-ID");
        w.text("EXIT-CODE");
        for (int a = 1; a <= 5; a++) {
            w.text("UPDATED-BAL-" + a);
        }
        w.text("NUM-TRANSACTIONS");
        String[] names = {"ID", "TYPE", "CAT", "SOURCE", "DESC", "AMT", "CARD-NUM", "ORIG-TS", "PROC-TS"};
        for (int t = 1; t <= 10; t++) {
            for (String n : names) {
                w.text("TX-" + t + "-" + n);
            }
        }
        return w.line();
    }

    private static String outputRow(Result r) {
        RowWriter w = new RowWriter();
        w.text(r.caseId);
        w.text(Integer.toString(r.exitCode));
        for (int a = 0; a < 5; a++) {
            if (r.rowOk && r.updBal[a] != null) {
                w.text(r.updBal[a]);
            } else {
                w.text("");
            }
        }
        w.text(r.rowOk ? Integer.toString(r.txCount) : "");
        for (int t = 0; t < 10; t++) {
            if (r.rowOk && t < r.txCount && t < r.tx.size()) {
                Tx x = r.tx.get(t);
                w.text(x.id);
                w.text(x.type);
                w.text(x.cat);
                w.text(x.source);
                w.text(x.desc);
                w.text(fmtNum(x.amt));
                w.text(x.card);
                w.text(x.orig);
                w.text(x.proc);
            } else {
                for (int k = 0; k < 9; k++) {
                    w.text("");
                }
            }
        }
        return w.line();
    }

    // ------------------------------------------------------------ main

    private static List<String> readRecords(String path) throws IOException {
        byte[] data;
        try (InputStream in = Files.newInputStream(Paths.get(path))) {
            data = in.readAllBytes();
        }
        List<String> recs = new ArrayList<>();
        int start = 0;
        for (int i = 0; i <= data.length; i++) {
            if (i == data.length) {
                if (i > start) {
                    recs.add(new String(data, start, i - start, StandardCharsets.ISO_8859_1));
                }
            } else if (data[i] == '\n') {
                recs.add(new String(data, start, i - start, StandardCharsets.ISO_8859_1));
                start = i + 1;
            }
        }
        // INPUT-REC is PIC X(4000): longer lines are cut
        for (int i = 0; i < recs.size(); i++) {
            String s = recs.get(i);
            if (s.length() > 4000) {
                recs.set(i, s.substring(0, 4000));
            }
        }
        return recs;
    }

    public static void main(String[] args) {
        String inPath = System.getenv("INPUT_FILE");
        String outPath = System.getenv("OUTPUT_FILE");
        if (inPath == null || inPath.trim().isEmpty() || outPath == null || outPath.trim().isEmpty()) {
            System.err.println("HARNESS: INPUT_FILE, OUTPUT_FILE required");
            System.exit(2);
            return;
        }
        List<String> recs;
        try {
            recs = readRecords(inPath);
        } catch (IOException e) {
            System.err.println("HARNESS: cannot open INPUT_FILE");
            System.exit(2);
            return;
        }
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        try {
            buf.write((header() + "\n").getBytes(StandardCharsets.ISO_8859_1));
            // the first record is the header line and is skipped
            for (int i = 1; i < recs.size(); i++) {
                Result r = processRow(recs.get(i));
                buf.write((outputRow(r) + "\n").getBytes(StandardCharsets.ISO_8859_1));
            }
            try (OutputStream os = new FileOutputStream(outPath)) {
                buf.writeTo(os);
            }
        } catch (IOException e) {
            System.err.println("HARNESS: cannot open OUTPUT_FILE");
            System.exit(2);
        }
    }
}
