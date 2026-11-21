# CardDemo CBACT04C Design

## Existing Files (Read-Only)

### Upstream (commit 59cc6c2f)

- samples/carddemo-cbact04c/upstream/cbl/CBACT04C.cbl: original program
- samples/carddemo-cbact04c/upstream/cpy/*.cpy: copybooks (CVTRA01Y, CVACT03Y, CVTRA02Y, CVACT01Y, CVTRA05Y)
- samples/carddemo-cbact04c/upstream/data/*.txt: data files
- samples/carddemo-cbact04c/LICENSE: Apache 2.0
- samples/carddemo-cbact04c/NOTICE: source URL and commit

### Adapted (Already Built)

- samples/carddemo-cbact04c/adapted/CBACT04C.cob: lines 614-621 changed (PARM-DATE replaces FUNCTION CURRENT-DATE), rest unchanged
- samples/carddemo-cbact04c/adapted/RUN-CBACT04C.cob: driver, calls CBACT04C with PARM-DATE from environment
- samples/carddemo-cbact04c/adapted/CEE3ABD.cob: stub that DISPLAYs abend code, sets RETURN-CODE, STOPs RUN
- samples/carddemo-cbact04c/adapted/LOAD-FILES.cob: loads text files into indexed .dat files
- samples/carddemo-cbact04c/adapted/DUMP-ACCT.cob: reads account .dat file, DISPLAYs ACCT-ID and ACCT-CURR-BAL per line
- samples/carddemo-cbact04c/Makefile: builds adapted/*.cob with `cobc -I<upstream>/cpy`
- samples/carddemo-cbact04c/CHANGES.md: documents the timestamp change and new files
- samples/carddemo-cbact04c/probe/*: outputs from three probe runs (upstream-sample, probe-nonzero, missing-default)

## New File: Harness

### adapted/HARNESS-CBACT04C.cob

**Purpose**: Wraps CBACT04C for differential testing. Reads one input CSV row per case, writes text files for that case, calls LOAD-FILES / RUN-CBACT04C / DUMP-ACCT as subprocesses through CALL "SYSTEM", extracts outputs, writes one output CSV row.

**Why CALL "SYSTEM"**: CBACT04C maintains state in WORKING-STORAGE between calls (WS-LAST-ACCT-NUM, WS-FIRST-TIME, WS-TRANID-SUFFIX). If called directly multiple times from one process, state leaks from one case to the next. CANCEL would reset state, but when an abend occurs, CEE3ABD.cob STOPs RUN and ends the whole process (no case after an abend would execute). CALL "SYSTEM" runs each case in a separate subprocess: state is isolated and abends affect only that case.

**Structure**:

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. HARNESS-CBACT04C.

ENVIRONMENT DIVISION.
INPUT-OUTPUT SECTION.
FILE-CONTROL.
    SELECT INPUT-CSV ASSIGN TO EXTERNAL INPUT-FILE
           ORGANIZATION IS LINE SEQUENTIAL.
    SELECT OUTPUT-CSV ASSIGN TO EXTERNAL OUTPUT-FILE
           ORGANIZATION IS LINE SEQUENTIAL.

DATA DIVISION.
FILE SECTION.
FD  INPUT-CSV.
01  INPUT-RECORD                PIC X(2000).

FD  OUTPUT-CSV.
01  OUTPUT-RECORD               PIC X(3000).

WORKING-STORAGE SECTION.
01  WS-TMP-DIR                  PIC X(200).
01  WS-TMPDIR-ENV               PIC X(200).
01  WS-COMMAND                  PIC X(500).
01  WS-EXIT-CODE                PIC S9(9) BINARY.
01  WS-CASE-ID                  PIC X(10).
01  WS-PARM-DATE                PIC X(10).
01  WS-NUM-ACCOUNTS             PIC 9(1) VALUE 5.
01  WS-NUM-CATBALS              PIC 9(2) VALUE 10.
01  WS-NUM-RATES                PIC 9(2) VALUE 20.

* Account slots (5)
01  WS-ACCOUNTS OCCURS 5 TIMES.
    05  WS-ACCT-ID              PIC 9(11).
    05  WS-ACCT-GROUP-ID        PIC X(10).
    05  WS-ACCT-CURR-BAL        PIC S9(09)V99.
    05  WS-ACCT-CYC-CREDIT      PIC S9(09)V99.
    05  WS-ACCT-CYC-DEBIT       PIC S9(09)V99.
    05  WS-XREF-CARD-NUM        PIC X(16).
    05  WS-XREF-EXISTS          PIC X(1).

* Category balance slots (10)
01  WS-CATBALS OCCURS 10 TIMES.
    05  WS-CATBAL-ACCT-INDEX    PIC 9(1).
    05  WS-CATBAL-TYPE          PIC X(02).
    05  WS-CATBAL-CAT           PIC 9(04).
    05  WS-CATBAL-BAL           PIC S9(09)V99.

* Rate slots (20)
01  WS-RATES OCCURS 20 TIMES.
    05  WS-RATE-GROUP           PIC X(10).
    05  WS-RATE-TYPE            PIC X(02).
    05  WS-RATE-CAT             PIC 9(04).
    05  WS-RATE-VALUE           PIC S9(04)V99.

* Output arrays (updated balances and transactions)
01  WS-UPDATED-BALS OCCURS 5 TIMES  PIC S9(09)V99.
01  WS-UPDATED-CREDITS OCCURS 5 TIMES PIC S9(09)V99.
01  WS-UPDATED-DEBITS OCCURS 5 TIMES  PIC S9(09)V99.
01  WS-NUM-TRANSACTIONS         PIC 9(2).
01  WS-TRANSACTIONS OCCURS 10 TIMES.
    05  WS-TX-ID                PIC X(16).
    05  WS-TX-TYPE              PIC X(02).
    05  WS-TX-CAT               PIC 9(04).
    05  WS-TX-SOURCE            PIC X(10).
    05  WS-TX-DESC              PIC X(100).
    05  WS-TX-AMT               PIC S9(09)V99.
    05  WS-TX-CARD-NUM          PIC X(16).
    05  WS-TX-ORIG-TS           PIC X(26).
    05  WS-TX-PROC-TS           PIC X(26).

PROCEDURE DIVISION.
    OPEN INPUT INPUT-CSV.
    OPEN OUTPUT OUTPUT-CSV.
    
    * Write output CSV header
    STRING "CASE-ID,EXIT-CODE,"
           "UPDATED-BAL-1,UPDATED-CYC-CREDIT-1,UPDATED-CYC-DEBIT-1,"
           "..."
           "NUM-TRANSACTIONS,"
           "TX-1-ID,TX-1-TYPE,..."
        DELIMITED BY SIZE INTO OUTPUT-RECORD
    END-STRING.
    WRITE OUTPUT-RECORD.
    
    * Read and skip input CSV header
    READ INPUT-CSV.
    
    * Process each case
    PERFORM UNTIL INPUT-CSV EOF
        READ INPUT-CSV
            NOT AT END
                PERFORM PROCESS-ONE-CASE
        END-READ
    END-PERFORM.
    
    CLOSE INPUT-CSV.
    CLOSE OUTPUT-CSV.
    STOP RUN.

PROCESS-ONE-CASE.
    * Parse input CSV row into WS-CASE-ID, WS-PARM-DATE, WS-ACCOUNTS,
    * WS-CATBALS, WS-RATES
    * (CSV parsing logic, unstring or split by comma)
    
    * Get TMPDIR from environment or use current directory
    ACCEPT WS-TMPDIR-ENV FROM ENVIRONMENT "TMPDIR".
    IF WS-TMPDIR-ENV = SPACES
        MOVE "." TO WS-TMPDIR-ENV
    END-IF.
    
    * Build temporary directory name under TMPDIR
    STRING WS-TMPDIR-ENV "/cbact04c-" WS-CASE-ID
        DELIMITED BY SIZE INTO WS-TMP-DIR
    END-STRING.
    
    * Create temporary directory
    STRING "mkdir -p " WS-TMP-DIR
        DELIMITED BY SIZE INTO WS-COMMAND
    END-STRING.
    CALL "SYSTEM" USING WS-COMMAND RETURNING WS-EXIT-CODE.
    
    * Write text files (tcatbal.txt, cardxref.txt, acctdata.txt, discgrp.txt)
    PERFORM WRITE-TEXT-FILES.
    
    * Call LOAD-FILES
    STRING "cd " WS-TMP-DIR " && "
           "TCATBALTEXT=" WS-TMP-DIR "/tcatbal.txt "
           "XREFTEXT=" WS-TMP-DIR "/cardxref.txt "
           "ACCTTEXT=" WS-TMP-DIR "/acctdata.txt "
           "DISCGRPTEXT=" WS-TMP-DIR "/discgrp.txt "
           "TCATBALF=" WS-TMP-DIR "/tcatbal.dat "
           "XREFFILE=" WS-TMP-DIR "/cardxref.dat "
           "ACCTFILE=" WS-TMP-DIR "/acctdata.dat "
           "DISCGRP=" WS-TMP-DIR "/discgrp.dat "
           "../../build/carddemo/LOAD-FILES 2>&1"
        DELIMITED BY SIZE INTO WS-COMMAND
    END-STRING.
    CALL "SYSTEM" USING WS-COMMAND RETURNING WS-EXIT-CODE.
    
    * Call RUN-CBACT04C
    STRING "cd " WS-TMP-DIR " && "
           "COB_LIBRARY_PATH=../../build/carddemo "
           "CARDDEMO_PARM_DATE=" WS-PARM-DATE " "
           "TCATBALF=" WS-TMP-DIR "/tcatbal.dat "
           "XREFFILE=" WS-TMP-DIR "/cardxref.dat "
           "ACCTFILE=" WS-TMP-DIR "/acctdata.dat "
           "DISCGRP=" WS-TMP-DIR "/discgrp.dat "
           "TRANSACT=" WS-TMP-DIR "/transact.txt "
           "../../build/carddemo/RUN-CBACT04C 2>&1"
        DELIMITED BY SIZE INTO WS-COMMAND
    END-STRING.
    CALL "SYSTEM" USING WS-COMMAND RETURNING WS-EXIT-CODE.
    
    * Call DUMP-ACCT
    STRING "cd " WS-TMP-DIR " && "
           "ACCTFILE=" WS-TMP-DIR "/acctdata.dat "
           "../../build/carddemo/DUMP-ACCT 2>&1"
        DELIMITED BY SIZE INTO WS-COMMAND
    END-STRING.
    CALL "SYSTEM" USING WS-COMMAND.
    
    * Read transact.txt (350 bytes per record, extract WS-TRANSACTIONS)
    PERFORM READ-TRANSACTIONS.
    
    * Read DUMP-ACCT output (parse lines "ACCT-ID BAL")
    PERFORM READ-UPDATED-BALANCES.
    
    * Write one output CSV row
    STRING WS-CASE-ID "," WS-EXIT-CODE ","
           WS-UPDATED-BAL-1 "," WS-UPDATED-CREDIT-1 "," WS-UPDATED-DEBIT-1 ","
           "..."
           WS-NUM-TRANSACTIONS ","
           WS-TX-ID (1) "," WS-TX-TYPE (1) "," ...
        DELIMITED BY SIZE INTO OUTPUT-RECORD
    END-STRING.
    WRITE OUTPUT-RECORD.
    
    * Clean up
    STRING "rm -rf " WS-TMP-DIR
        DELIMITED BY SIZE INTO WS-COMMAND
    END-STRING.
    CALL "SYSTEM" USING WS-COMMAND.
```

**Compilation**:
The engine compiles only the one COBOL file it is given: `cobc -x -Wall -I<copybooks> -o <output> <source>` (from coroner/run/__init__.py compile_cobol, line 220: `cmd = ['cobc', '-x', '-Wall', '-I', copybooks, '-o', str(temp_output), source] + flags`).

The harness needs three helper programs built separately before it can run:
- LOAD-FILES: `cobc -x -Wall -Iupstream/cpy -o build/carddemo/LOAD-FILES adapted/LOAD-FILES.cob`
- RUN-CBACT04C + CBACT04C + CEE3ABD: `cobc -m -Wall -Iupstream/cpy -o build/carddemo/CBACT04C.so adapted/CBACT04C.cob` and `cobc -m -Wall -o build/carddemo/CEE3ABD.so adapted/CEE3ABD.cob`, then `cobc -x -Wall -Iupstream/cpy -o build/carddemo/RUN-CBACT04C adapted/RUN-CBACT04C.cob`
- DUMP-ACCT: `cobc -x -Wall -Iupstream/cpy -o build/carddemo/DUMP-ACCT adapted/DUMP-ACCT.cob`

These are built by the Makefile before `coroner verify` runs. In the image, the Makefile runs at image build time and the binaries are copied into /app/build/carddemo/. On a Mac, the operator runs `make -C samples/carddemo-cbact04c` before calling `coroner verify`.

Coverage is measured from an instrumented build of adapted/HARNESS-CBACT04C.cob (the harness), not CBACT04C.cob itself. The verdict shows "Paragraph coverage" and "Branch coverage (Coroner definition)" of the harness's control flow (which paragraphs and branches in HARNESS-CBACT04C.cob were executed). This is accurate: the harness is the COBOL program under test. The coverage does not show CBACT04C.cob's internal branches; those are opaque subprocess calls.

**Runtime**:
The engine runs the harness with INPUT_FILE and OUTPUT_FILE: `subprocess.run([binary], ..., env={..., 'INPUT_FILE': input_csv, 'OUTPUT_FILE': output_csv})` (from coroner/run/__init__.py run_cobol, line 389).

**Per-case cost**: The probe runs one case in well under a second. A 200-case audit will complete in reasonable time (estimated under 2 minutes, dominated by subprocess overhead).

## Schema Design

### Option 1: Generator Script (Chosen)

**schema.json** contains:
```json
{
  "program": "CBACT04C",
  "description": "CardDemo interest calculation",
  "generator_script": "samples/carddemo-cbact04c/generator.py",
  "input": {
    "file": "generated_cases.csv",
    "columns": [
      {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case identifier"},
      {"name": "PARM-DATE", "type": "string", "pic": "X(10)", "description": "Parameter date YYYY-MM-DD"},
      ... (5 accounts x 7 fields each, 10 category balances x 4 fields each, 20 rates x 4 fields each)
    ]
  },
  "output": {
    "file": "output.csv",
    "columns": [
      {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case identifier"},
      {"name": "EXIT-CODE", "type": "integer", "pic": "9(3)", "description": "Actual exit code"},
      ... (5 updated balances x 3 fields, 10 transactions x 9 fields each, 1 count)
    ]
  }
}
```

**generator.py** (samples/carddemo-cbact04c/generator.py):
```python
import random
from decimal import Decimal

def generate_cases(schema, rng: random.Random, num_cases: int) -> list[dict]:
    """Generate CardDemo test cases with controlled edge cases."""
    cases = []
    
    for i in range(num_cases):
        case = {}
        case['CASE-ID'] = f"GEN-{i+1:06d}"
        case['PARM-DATE'] = "2026-01-15"
        
        # Generate 1 to 5 accounts
        num_accounts = rng.randint(1, 5)
        for a in range(1, 6):
            if a <= num_accounts:
                case[f'ACCT-ID-{a}'] = 10000000000 + a
                case[f'ACCT-GROUP-ID-{a}'] = rng.choice(['GROUP01', 'GROUP02', 'DEFAULT'])
                case[f'ACCT-CURR-BAL-{a}'] = draw_decimal_by_magnitude(rng, 2, signed=True)
                case[f'ACCT-CURR-CYC-CREDIT-{a}'] = draw_decimal_by_magnitude(rng, 2, signed=False)
                case[f'ACCT-CURR-CYC-DEBIT-{a}'] = draw_decimal_by_magnitude(rng, 2, signed=False)
                case[f'XREF-CARD-NUM-{a}'] = f"{10000000000 + a:016d}"
                case[f'XREF-EXISTS-{a}'] = 'Y' if rng.random() > 0.1 else 'N'  # 10% missing
            else:
                case[f'ACCT-ID-{a}'] = 0
                case[f'ACCT-GROUP-ID-{a}'] = ''
                case[f'ACCT-CURR-BAL-{a}'] = Decimal('0.00')
                case[f'ACCT-CURR-CYC-CREDIT-{a}'] = Decimal('0.00')
                case[f'ACCT-CURR-CYC-DEBIT-{a}'] = Decimal('0.00')
                case[f'XREF-CARD-NUM-{a}'] = ''
                case[f'XREF-EXISTS-{a}'] = ''
        
        # Generate 1 to 10 category balances
        num_catbals = rng.randint(1, 10)
        for cb in range(1, 11):
            if cb <= num_catbals:
                case[f'CATBAL-ACCT-INDEX-{cb}'] = rng.randint(1, num_accounts)
                case[f'CATBAL-TYPE-{cb}'] = '01'
                case[f'CATBAL-CAT-{cb}'] = rng.randint(1, 10)
                case[f'CATBAL-BAL-{cb}'] = draw_decimal_by_magnitude(rng, 2, signed=True)
            else:
                case[f'CATBAL-ACCT-INDEX-{cb}'] = 0
                case[f'CATBAL-TYPE-{cb}'] = ''
                case[f'CATBAL-CAT-{cb}'] = 0
                case[f'CATBAL-BAL-{cb}'] = Decimal('0.00')
        
        # Generate 5 to 20 rates
        num_rates = rng.randint(5, 20)
        has_default = rng.random() > 0.3  # 70% have DEFAULT rates
        for r in range(1, 21):
            if r <= num_rates:
                case[f'RATE-GROUP-{r}'] = 'DEFAULT' if r <= 5 and has_default else rng.choice(['GROUP01', 'GROUP02'])
                case[f'RATE-TYPE-{r}'] = '01'
                case[f'RATE-CAT-{r}'] = rng.randint(1, 10)
                case[f'RATE-VALUE-{r}'] = Decimal(rng.randint(0, 2500)) / Decimal(100)  # 0.00 to 25.00
            else:
                case[f'RATE-GROUP-{r}'] = ''
                case[f'RATE-TYPE-{r}'] = ''
                case[f'RATE-CAT-{r}'] = 0
                case[f'RATE-VALUE-{r}'] = Decimal('0.00')
        
        cases.append(case)
    
    return cases
```

**Engine extension** (new task, after harness and Java port):

coroner/gen/__init__.py gains:
```python
def generate_cases(schema: Schema, num_cases: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    
    if hasattr(schema, 'generator_script') and schema.generator_script:
        # Security: script must be inside schema directory
        import pathlib
        schema_dir = pathlib.Path(schema.file_path).parent.resolve()
        script_path = pathlib.Path(schema.generator_script).resolve()
        
        if not script_path.is_relative_to(schema_dir):
            raise RuntimeError(f"generator script outside schema directory: {script_path}")
        
        # Load and call the external script
        import importlib.util
        spec = importlib.util.spec_from_file_location("generator", schema.generator_script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.generate_cases(schema, rng, num_cases)
    
    # Existing generate_cases logic for simple schemas
    ...
```

Note for SECURITY.md: The generator_script path must resolve inside the schema directory after resolving symlinks. A script outside the directory stops the run with ERROR.

### Option 2: Complex Schema (Not Chosen)

Extend schema.json with array types, index references, conditional rules. Cost: larger engine change, not bounded to one sample.

## Java Port Structure

The Kiro agent ports adapted/CBACT04C.cob (interest calculation logic only, not the harness). The Java reads the same input CSV contract as the harness, implements the interest calculation, and writes the same output CSV.

**Expected structure** (agent figures out the details):

```java
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.io.*;
import java.util.*;

public class Cbact04cInterest {
    public static void main(String[] args) throws IOException {
        String inputFile = System.getenv("INPUT_FILE");
        String outputFile = System.getenv("OUTPUT_FILE");
        
        Cbact04cInterest program = new Cbact04cInterest();
        program.processFile(inputFile, outputFile);
    }
    
    private void processFile(String inputFile, String outputFile) throws IOException {
        BufferedReader reader = new BufferedReader(new FileReader(inputFile));
        String header = reader.readLine();
        
        PrintWriter writer = new PrintWriter(new FileWriter(outputFile));
        writer.println("CASE-ID,EXIT-CODE,UPDATED-BAL-1,...");
        
        String line;
        while ((line = reader.readLine()) != null) {
            String[] fields = line.split(",");
            String caseId = fields[0];
            
            // Parse accounts, catbals, rates
            // ... (agent figures this out)
            
            // Process each catbal:
            //   Look up rate by (group, type, cat)
            //   If not found, try DEFAULT
            //   If DEFAULT not found, System.exit(231)
            //   If rate != 0, compute interest = (balance * rate) / 1200
            //   Accumulate per account
            
            // Build output row
            writer.println(caseId + "," + exitCode + "," + ...);
        }
        
        reader.close();
        writer.close();
    }
}
```

The agent reads adapted/CBACT04C.cob lines 186-231 (the interest loop) and replicates its logic without hints about the formula or rounding.

## Comparison Process

The engine (run_verify in coroner/cli.py) runs both programs on the same generated input CSV and compares output CSVs field by field using compare_outputs.

**COBOL Run**:
1. Engine calls compile_cobol on adapted/HARNESS-CBACT04C.cob
2. Engine calls run_cobol with HARNESS_INPUT=generated_cases.csv, HARNESS_OUTPUT=cobol_output.csv
3. Harness reads each input row, writes text files, calls LOAD-FILES / RUN-CBACT04C / DUMP-ACCT, extracts outputs, writes one output row
4. Exit code 0 on success

**Java Run**:
1. Engine calls compile_java on Cbact04cInterest.java
2. Engine calls run_java with INPUT_FILE=generated_cases.csv, OUTPUT_FILE=java_output.csv
3. Java reads each input row, computes interest per COBOL logic, writes one output row
4. Exit code 0 on success

**Comparison**:
- compare_outputs compares cobol_output.csv and java_output.csv field by field
- Interest amounts: exact BigDecimal comparison at scale 2 (no tolerance, per D-09)
- Account balances: exact BigDecimal comparison at scale 2
- Transaction fields: string exact match
- Exit code: exact integer match

## Coverage

The harness runs adapted/CBACT04C.cob, so coverage is measured from its instrumented build:
- Paragraphs: 1000-TCATBALF-GET-NEXT, 1050-UPDATE-ACCOUNT, 1100-GET-ACCT-DATA, 1110-GET-XREF-DATA, 1200-GET-INTEREST-RATE, 1200-A-GET-DEFAULT-INT-RATE, 1300-COMPUTE-INTEREST, 1300-B-WRITE-TX, 1400-COMPUTE-FEES, Z-GET-DB2-FORMAT-TIMESTAMP
- Branches: IFs inside those paragraphs (file status checks, rate != 0, DEFAULT fallback, XREF INVALID KEY)

The generator mixes missing XREF (exit 231), missing DEFAULT (exit 231), zero rates, negative balances, and zero balances to exercise the error paths.

## Public Documentation

samples/carddemo-cbact04c/README.md includes the required public wording verbatim. The verdict output from `coroner verify` uses the standard sub-labels "PASS: business behavior preserved on N cases" or "FAIL: business behavior diverged on M cases", with no sample-specific wording.

## Uncertain

1. CALL "SYSTEM" behavior on non-zero exit codes: Does GnuCOBOL capture the child's exit status in the RETURNING variable? (Measured: yes, the probe shows exit code 231 in the returned value.)

2. CSV parsing in COBOL: UNSTRING with DELIMITED BY "," handles quoted fields and embedded commas? (Accepted: the harness can use a simpler fixed-position parse or delegate CSV reading to a helper if UNSTRING is insufficient.)

3. Generator script integration: The engine's generate_cases function signature and how it's called. (Checked: coroner/gen/__init__.py line 1 defines generate_cases(schema, num_cases, seed). The script will be called with those arguments and schema carries the generator_script path.)
