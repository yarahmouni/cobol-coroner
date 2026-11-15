#!/usr/bin/env python3
"""Generate complete parity-cases.csv with specific byte patterns."""

def main():
    """Create parity-cases.csv with all parity test cases."""
    fixture_path = "samples/credit-fees/fixtures/parity-cases.csv"
    
    # Build the CSV content
    lines = []
    lines.append("CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME\n")
    lines.append("PAR-01,10.500,0.01000,12,B,50000.00\n")
    lines.append("PAR-02,10.505,0.01000,12,B,50000.00\n")
    lines.append("PAR-03, 100.00 ,0.01000,12,B,50000.00\n")
    lines.append("PAR-04,+100.00,0.01000,12,B,50000.00\n")
    lines.append("PAR-05,1E2,0.01000,12,B,50000.00\n")
    lines.append("PAR-06,12.5,0.01000,12,B,50000.00\n")
    lines.append("PAR-07,5.,0.01000,12,B,50000.00\n")
    lines.append("PAR-08,100.00,0.01000,12,B,50000.00,extra,field\n")
    lines.append("PAR-09,100.00,0.01000,12,B\n")
    lines.append("PAR-10,\n")
    
    # PAR-11: 201+ character line (cut to 200 by COBOL PIC X(200))
    # Make the line longer than 200 characters
    # Standard line with 5 fields is about 40 chars, so add 165 Xs to CASE-ID
    long_case_id = "PAR11" + "X" * 165
    lines.append(f"{long_case_id},100.00,0.01000,12,B,50000.00\n")
    
    # PAR-12: CASE-ID longer than 10 characters (11 chars after trim)
    lines.append("PAR12345678901,100.00,0.01000,12,B,50000.00\n")
    
    # PAR-13: CUSTOMER-SEGMENT " B" (two characters after trim trailing)
    lines.append("PAR-13,100.00,0.01000,12, B,50000.00\n")
    
    # PAR-14: CUSTOMER-SEGMENT empty
    lines.append("PAR-14,100.00,0.01000,12,,50000.00\n")
    
    # PAR-15: Negative zero fee case
    lines.append("PAR-15,-0.40,0.01000,12,B,50000.00\n")
    
    # PAR-16: CRLF line ending (CR should be removed before parsing)
    lines.append("PAR-16,200.00,0.01000,12,B,50000.00\r\n")
    
    # PAR-17: FEE-RATE written ".01000" (no leading zero), otherwise a valid B row
    lines.append("PAR-17,100.00,.01000,12,B,50000.00\n")
    
    # PAR-18: PRINCIPAL ".50"
    lines.append("PAR-18,.50,0.01000,12,B,50000.00\n")
    
    # PAR-19: DURATION-MONTHS "12.0"
    lines.append("PAR-19,100.00,0.01000,12.0,B,50000.00\n")
    
    # PAR-20: DURATION-MONTHS " 24 " (spaces around)
    lines.append("PAR-20,100.00,0.01000, 24 ,B,50000.00\n")
    
    # PAR-21: INCOME "50000.000" (3 decimals, valid by value)
    lines.append("PAR-21,100.00,0.01000,12,B,50000.000\n")
    
    # PAR-22: CASE-ID "A B" (embedded space)
    lines.append("A B,100.00,0.01000,12,B,50000.00\n")
    
    # Empty data line (zero characters, just LF)
    lines.append("\n")
    
    # Write all lines in binary mode to control exact bytes
    with open(fixture_path, "wb") as f:
        for line in lines:
            f.write(line.encode("utf-8"))
    
    print(f"Created {fixture_path} with {len(lines)} lines (including header)")
    print(f"Line 12 (PAR-11) has {len(lines[11])} bytes")

if __name__ == "__main__":
    main()
