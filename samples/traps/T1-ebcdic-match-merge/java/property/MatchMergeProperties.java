import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.Assume;
import net.jqwik.api.Combinators;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;
import net.jqwik.api.Tuple;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Properties of the two Java ports of MATCH-MERGE.cob (trap T1), checked with jqwik.
 *
 * The ports are run as they are used by Coroner: the compiled MatchMerge class reads the file in
 * INPUT_FILE and writes the file in OUTPUT_FILE. The class folders come from the system properties
 * pbt.faulty and pbt.correct (set by "make pbt"). No port logic is copied here.
 *
 * No COBOL output is asserted in this file. The first two properties state a conservation law of
 * the output of one port. The third property compares the two Java ports with each other: it states
 * what the faulty code does, it is not an expected business output.
 */
public class MatchMergeProperties {

    private static final int TRIES = 30;
    private static final String SEED = "42";
    private static final String CASE_ID = "CASE000001";

    // The BRANCH domain of schema.json (the ten codes the generator draws).
    private static final List<String> SCHEMA_DOMAIN =
            List.of("A01", "B02", "C03", "D04", "E05", "F06", "Z99", "001", "9ZZ", "X77");

    private static final Path FAULTY = Paths.get(System.getProperty("pbt.faulty", "build/pbt/faulty"));
    private static final Path CORRECT = Paths.get(System.getProperty("pbt.correct", "build/pbt/correct"));

    public record Txn(String branch, BigDecimal amount) {
    }

    /** What a port wrote: branch subtotals (rows other than SUSP and TOTAL), suspense and total. */
    record Output(Map<String, BigDecimal> branches, BigDecimal suspense, BigDecimal total) {
        BigDecimal branch(String code) {
            return branches.getOrDefault(code, BigDecimal.ZERO);
        }

        BigDecimal branchesSum() {
            return branches.values().stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        }
    }

    // ---------------------------------------------------------------- generators

    /** Branch codes of the T1 domain, plus any 3-character code of letters and digits (mostly not in the table). */
    @Provide
    Arbitrary<String> branches() {
        Arbitrary<String> fromSchema = Arbitraries.of(SCHEMA_DOMAIN);
        Arbitrary<String> anyCode = Arbitraries.strings().withCharRange('A', 'Z').withCharRange('0', '9').ofLength(3);
        return Arbitraries.frequencyOf(Tuple.of(7, fromSchema), Tuple.of(3, anyCode));
    }

    /** Amounts at scale 2, within the range of the T1 schema (reversals included). */
    @Provide
    Arbitrary<BigDecimal> amounts() {
        return Arbitraries.bigDecimals()
                .between(new BigDecimal("-9999.99"), new BigDecimal("9999.99"))
                .ofScale(2);
    }

    /** One batch (one CASE-ID) of 1 to 25 transactions. */
    @Provide
    Arbitrary<List<Txn>> batches() {
        Arbitrary<Txn> txn = Combinators.combine(branches(), amounts()).as(Txn::new);
        return txn.list().ofMinSize(1).ofMaxSize(25);
    }

    /** A batch that contains at least one transaction for branch 001 with a non-zero amount. */
    @Provide
    Arbitrary<List<Txn>> batchesWith001() {
        Arbitrary<Txn> txn = Combinators.combine(branches(), amounts()).as(Txn::new);
        Arbitrary<Txn> txn001 = amounts().filter(a -> a.signum() != 0).map(a -> new Txn("001", a));
        return Combinators.combine(txn.list().ofMaxSize(24), txn001).as((others, extra) -> {
            List<Txn> batch = new ArrayList<>(others);
            batch.add(extra);
            return batch;
        });
    }

    // ---------------------------------------------------------------- properties

    /** Correct port: branch subtotals plus suspense equal the grand total, and the grand total equals the sum of the inputs. */
    @Property(tries = TRIES, seed = SEED)
    void correctPortConservesTheTotal(@ForAll("batches") List<Txn> batch) throws Exception {
        assertConserved(batch, run(CORRECT, batch));
    }

    /** The point of Case 1: the faulty port conserves the total too. A total-only reconciliation cannot see it. */
    @Property(tries = TRIES, seed = SEED)
    void totalIsConservedEvenByTheFaultyPort(@ForAll("batches") List<Txn> batch) throws Exception {
        assertConserved(batch, run(FAULTY, batch));
    }

    /**
     * Faulty code, stated by comparing the two Java ports (no COBOL output is asserted): for a batch
     * with a transaction for branch 001, the correct port posts the 001 amount to branch 001 and the
     * faulty port posts it to suspense. The faulty port does the same for 9ZZ, the other digit-led
     * code of the branch table, so the suspense difference is the sum of both.
     */
    @Property(tries = TRIES, seed = SEED)
    void faultyPortPostsBranch001ToSuspense(@ForAll("batchesWith001") List<Txn> batch) throws Exception {
        BigDecimal in001 = sumFor(batch, "001");
        BigDecimal in9ZZ = sumFor(batch, "9ZZ");
        Assume.that(in001.signum() != 0);

        Output correct = run(CORRECT, batch);
        Output faulty = run(FAULTY, batch);

        assertSame("correct port, branch 001", in001, correct.branch("001"));
        assertSame("faulty port, branch 001", BigDecimal.ZERO, faulty.branch("001"));
        assertSame("faulty port, branch 9ZZ", BigDecimal.ZERO, faulty.branch("9ZZ"));
        assertSame("suspense, faulty minus correct", in001.add(in9ZZ), faulty.suspense().subtract(correct.suspense()));
    }

    // ---------------------------------------------------------------- checks

    private static void assertConserved(List<Txn> batch, Output out) {
        BigDecimal inputs = batch.stream().map(Txn::amount).reduce(BigDecimal.ZERO, BigDecimal::add);
        assertSame("branch subtotals plus suspense, against the grand total",
                out.total(), out.branchesSum().add(out.suspense()));
        assertSame("grand total, against the sum of the input amounts", inputs, out.total());
    }

    private static BigDecimal sumFor(List<Txn> batch, String code) {
        return batch.stream().filter(t -> t.branch().equals(code)).map(Txn::amount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    private static void assertSame(String what, BigDecimal expected, BigDecimal actual) {
        assertEquals(0, expected.compareTo(actual), what + ": expected " + expected + " but was " + actual);
    }

    // ---------------------------------------------------------------- running a port

    /** Runs one compiled port on one batch, the way the engine does (environment variables, one JVM, exit status). */
    private static Output run(Path classes, List<Txn> batch) throws IOException, InterruptedException {
        Path dir = Files.createTempDirectory("coroner-pbt-");
        Path input = dir.resolve("input.csv");
        Path output = dir.resolve("output.csv");
        Path log = dir.resolve("log.txt");
        try {
            StringBuilder csv = new StringBuilder("CASE-ID,BRANCH,AMOUNT\n");
            for (Txn t : batch) {
                csv.append(CASE_ID).append(',').append(t.branch()).append(',').append(t.amount().toPlainString()).append('\n');
            }
            Files.writeString(input, csv);

            String java = Paths.get(System.getProperty("java.home"), "bin", "java").toString();
            // Same fixed locale as the engine (coroner/run/__init__.py JAVA_LOCALE_PROPERTIES).
            ProcessBuilder pb = new ProcessBuilder(java, "-Duser.language=en", "-Duser.country=US",
                    "-Duser.variant=", "-Dfile.encoding=UTF-8", "-cp", classes.toString(), "MatchMerge");
            pb.environment().put("INPUT_FILE", input.toString());
            pb.environment().put("OUTPUT_FILE", output.toString());
            pb.redirectErrorStream(true);
            pb.redirectOutput(log.toFile());
            Process process = pb.start();
            if (!process.waitFor(60, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                fail("port did not finish in 60 s: " + classes);
            }
            if (process.exitValue() != 0) {
                fail("port exited with " + process.exitValue() + ": " + Files.readString(log));
            }
            return parse(Files.readAllLines(output));
        } finally {
            Files.deleteIfExists(input);
            Files.deleteIfExists(output);
            Files.deleteIfExists(log);
            Files.deleteIfExists(dir);
        }
    }

    private static Output parse(List<String> lines) {
        assertEquals("CASE-ID,BRANCH,SUBTOTAL", lines.get(0).trim(), "output header");
        Map<String, BigDecimal> branches = new HashMap<>();
        BigDecimal suspense = BigDecimal.ZERO;
        BigDecimal total = null;
        for (String line : lines.subList(1, lines.size())) {
            String[] fields = line.split(",", -1);
            assertEquals(3, fields.length, "output row: " + line);
            assertEquals(CASE_ID, fields[0].trim(), "case id in row: " + line);
            String code = fields[1].trim();
            BigDecimal amount = new BigDecimal(fields[2].trim());
            if (code.equals("TOTAL")) {
                assertTrue(total == null, "more than one TOTAL row");
                total = amount;
            } else if (code.equals("SUSP")) {
                suspense = amount;
            } else {
                assertTrue(branches.put(code, amount) == null, "two rows for branch " + code);
            }
        }
        assertTrue(total != null, "no TOTAL row");
        return new Output(branches, suspense, total);
    }
}
