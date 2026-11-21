# CardDemo CBACT04C Makefile

SRC := $(CURDIR)
# Absolute default under the repository build/ folder; override with BUILD_DIR=...
BUILD_DIR ?= $(abspath $(CURDIR)/../../build/carddemo)
PROBE_DIR = probe
ADAPTED = adapted
UPSTREAM = upstream
# Compiler option used for every program of this sample. The upstream data
# marks signs with the EBCDIC zoned overpunch ("{" is +0, "}" is -0); under
# the default ASCII convention GnuCOBOL reads them inconsistently (see
# PROBE.md). The same flag must be used for the harness (see "make harness").
COBFLAGS ?= -fsign=EBCDIC

.PHONY: all clean harness probe-upstream probe-nonzero probe-missing-default probe-sign harness-helpers

# The harness builds these helpers itself at start (make harness-helpers), so
# all does not build the harness. "make harness" builds it by hand with the
# flags the engine uses (cobc -x -Wall -I <copybooks>) plus COBFLAGS. The
# harness reads and writes the sample's signed text records, so it must be
# compiled with the same sign convention as the helpers: the engine takes it
# from cobc_flags in the schema, and the helpers it builds use COBFLAGS here.
all: harness-helpers

harness: $(BUILD_DIR)/HARNESS-CBACT04C

harness-helpers: $(BUILD_DIR)/LOAD-FILES $(BUILD_DIR)/RUN-CBACT04C $(BUILD_DIR)/CEE3ABD $(BUILD_DIR)/DUMP-ACCT

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/LOAD-FILES: $(ADAPTED)/LOAD-FILES.cob | $(BUILD_DIR)
	cobc $(COBFLAGS) -x -o $@ -I$(SRC)/$(UPSTREAM)/cpy $<

$(BUILD_DIR)/RUN-CBACT04C: $(ADAPTED)/RUN-CBACT04C.cob $(ADAPTED)/CBACT04C.cob | $(BUILD_DIR)
	cd $(BUILD_DIR) && cobc $(COBFLAGS) -m -I$(SRC)/$(ADAPTED) -I$(SRC)/$(UPSTREAM)/cpy $(SRC)/$(ADAPTED)/CBACT04C.cob
	cobc $(COBFLAGS) -x -o $@ -I$(SRC)/$(ADAPTED) $(SRC)/$(ADAPTED)/RUN-CBACT04C.cob

$(BUILD_DIR)/CEE3ABD: $(ADAPTED)/CEE3ABD.cob | $(BUILD_DIR)
	cd $(BUILD_DIR) && cobc $(COBFLAGS) -m $(SRC)/$(ADAPTED)/CEE3ABD.cob

$(BUILD_DIR)/DUMP-ACCT: $(ADAPTED)/DUMP-ACCT.cob | $(BUILD_DIR)
	cobc $(COBFLAGS) -x -o $@ -I$(SRC)/$(UPSTREAM)/cpy $<

$(BUILD_DIR)/HARNESS-CBACT04C: $(ADAPTED)/HARNESS-CBACT04C.cob | $(BUILD_DIR)
	cobc $(COBFLAGS) -x -Wall -o $@ -I$(SRC)/$(UPSTREAM)/cpy $<

probe-upstream: $(BUILD_DIR)/RUN-CBACT04C $(BUILD_DIR)/LOAD-FILES $(BUILD_DIR)/DUMP-ACCT
	@echo "Running probe with upstream data (all zero balances)..."
	mkdir -p $(PROBE_DIR)/upstream-sample
	cd $(BUILD_DIR) && \
	TCATBALTEXT=$(SRC)/$(UPSTREAM)/data/tcatbal.txt \
	XREFTEXT=$(SRC)/$(UPSTREAM)/data/cardxref.txt \
	ACCTTEXT=$(SRC)/$(UPSTREAM)/data/acctdata.txt \
	DISCGRPTEXT=$(SRC)/$(UPSTREAM)/data/discgrp.txt \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	./LOAD-FILES && \
	COB_LIBRARY_PATH=. \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	TRANSACT=transact-upstream.txt \
	./RUN-CBACT04C > $(abspath $(PROBE_DIR))/upstream-sample/display.txt 2>&1
	cp $(SRC)/$(UPSTREAM)/data/acctdata.txt $(abspath $(PROBE_DIR))/upstream-sample/acctdata-before.txt
	cd $(BUILD_DIR) && ACCTFILE=acctdata.dat ./DUMP-ACCT > $(abspath $(PROBE_DIR))/upstream-sample/acctdata-after.txt
	@if [ -f $(BUILD_DIR)/transact-upstream.txt ]; then \
		fold -w 350 $(BUILD_DIR)/transact-upstream.txt > $(abspath $(PROBE_DIR))/upstream-sample/transact.txt; \
	fi

probe-nonzero: $(BUILD_DIR)/RUN-CBACT04C $(BUILD_DIR)/LOAD-FILES $(BUILD_DIR)/DUMP-ACCT
	@echo "Running probe with non-zero balance dataset..."
	mkdir -p $(PROBE_DIR)/probe-nonzero
	cd $(BUILD_DIR) && \
	TCATBALTEXT=$(SRC)/datasets/probe-nonzero/tcatbal.txt \
	XREFTEXT=$(SRC)/datasets/probe-nonzero/cardxref.txt \
	ACCTTEXT=$(SRC)/datasets/probe-nonzero/acctdata.txt \
	DISCGRPTEXT=$(SRC)/datasets/probe-nonzero/discgrp.txt \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	./LOAD-FILES && \
	COB_LIBRARY_PATH=. \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	TRANSACT=transact-nonzero.txt \
	./RUN-CBACT04C > $(abspath $(PROBE_DIR))/probe-nonzero/display.txt 2>&1
	cp $(SRC)/datasets/probe-nonzero/acctdata.txt $(abspath $(PROBE_DIR))/probe-nonzero/acctdata-before.txt
	cd $(BUILD_DIR) && ACCTFILE=acctdata.dat ./DUMP-ACCT > $(abspath $(PROBE_DIR))/probe-nonzero/acctdata-after.txt
	@if [ -f $(BUILD_DIR)/transact-nonzero.txt ]; then \
		fold -w 350 $(BUILD_DIR)/transact-nonzero.txt > $(abspath $(PROBE_DIR))/probe-nonzero/transact.txt; \
	fi
	@echo ""
	@echo "Probe complete. Results in $(PROBE_DIR)/probe-nonzero/"

probe-missing-default: $(BUILD_DIR)/RUN-CBACT04C $(BUILD_DIR)/LOAD-FILES $(BUILD_DIR)/CEE3ABD $(BUILD_DIR)/DUMP-ACCT
	@echo "Running probe with missing-default dataset (exercises CEE3ABD abend)..."
	mkdir -p $(PROBE_DIR)/missing-default
	cd $(BUILD_DIR) && \
	TCATBALTEXT=$(SRC)/datasets/missing-default/tcatbal.txt \
	XREFTEXT=$(SRC)/datasets/missing-default/cardxref.txt \
	ACCTTEXT=$(SRC)/datasets/missing-default/account.txt \
	DISCGRPTEXT=$(SRC)/datasets/missing-default/discgrp.txt \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	./LOAD-FILES && \
	COB_LIBRARY_PATH=. \
	TCATBALF=tcatbal.dat XREFFILE=cardxref.dat ACCTFILE=acctdata.dat DISCGRP=discgrp.dat \
	TRANSACT=transact-missing-default.txt \
	./RUN-CBACT04C > $(abspath $(PROBE_DIR))/missing-default/display.txt 2>&1; \
	echo $$? > $(abspath $(PROBE_DIR))/missing-default/exit-code.txt
	cp $(SRC)/datasets/missing-default/account.txt $(abspath $(PROBE_DIR))/missing-default/acctdata-before.txt
	cd $(BUILD_DIR) && ACCTFILE=acctdata.dat ./DUMP-ACCT > $(abspath $(PROBE_DIR))/missing-default/acctdata-after.txt 2>&1 || true
	@if [ -f $(BUILD_DIR)/transact-missing-default.txt ]; then \
		fold -w 350 $(BUILD_DIR)/transact-missing-default.txt > $(abspath $(PROBE_DIR))/missing-default/transact.txt; \
	fi
	@EXIT_CODE=$$(cat $(abspath $(PROBE_DIR))/missing-default/exit-code.txt); \
	if [ "$$EXIT_CODE" = "231" ]; then \
		echo "Expected abend code 231 recorded."; \
	else \
		echo "Unexpected exit code: $$EXIT_CODE (expected 231)"; \
		exit 1; \
	fi
	@echo ""
	@echo "Probe complete. Results in $(PROBE_DIR)/missing-default/"

# The same source compiled with the default (ASCII) sign convention and with
# -fsign=EBCDIC, to record how GnuCOBOL reads the upstream overpunch fields.
SIGN_SRC = probe/sign-convention/SIGN-PROBE.cob

probe-sign: $(SIGN_SRC) | $(BUILD_DIR)
	mkdir -p $(PROBE_DIR)/sign-convention
	cobc -x -o $(BUILD_DIR)/SIGN-PROBE-ASCII $(SIGN_SRC)
	cobc -fsign=EBCDIC -x -o $(BUILD_DIR)/SIGN-PROBE-EBCDIC $(SIGN_SRC)
	$(BUILD_DIR)/SIGN-PROBE-ASCII > $(PROBE_DIR)/sign-convention/ascii.txt 2>&1
	$(BUILD_DIR)/SIGN-PROBE-EBCDIC > $(PROBE_DIR)/sign-convention/ebcdic.txt 2>&1

clean:
	rm -rf $(BUILD_DIR)
