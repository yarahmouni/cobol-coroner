# CardDemo CBACT04C Makefile

SRC := $(CURDIR)
BUILD_DIR = ../../build/carddemo
PROBE_DIR = probe
ADAPTED = adapted
UPSTREAM = upstream

.PHONY: all clean probe-upstream probe-nonzero probe-missing-default

all: $(BUILD_DIR)/LOAD-FILES $(BUILD_DIR)/RUN-CBACT04C $(BUILD_DIR)/CEE3ABD $(BUILD_DIR)/DUMP-ACCT

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/LOAD-FILES: $(ADAPTED)/LOAD-FILES.cob | $(BUILD_DIR)
	cobc -x -o $@ -I$(SRC)/$(UPSTREAM)/cpy $<

$(BUILD_DIR)/RUN-CBACT04C: $(ADAPTED)/RUN-CBACT04C.cob $(ADAPTED)/CBACT04C.cob | $(BUILD_DIR)
	cd $(BUILD_DIR) && cobc -m -I$(SRC)/$(ADAPTED) -I$(SRC)/$(UPSTREAM)/cpy $(SRC)/$(ADAPTED)/CBACT04C.cob
	cobc -x -o $@ -I$(SRC)/$(ADAPTED) $(SRC)/$(ADAPTED)/RUN-CBACT04C.cob

$(BUILD_DIR)/CEE3ABD: $(ADAPTED)/CEE3ABD.cob | $(BUILD_DIR)
	cd $(BUILD_DIR) && cobc -m $(SRC)/$(ADAPTED)/CEE3ABD.cob

$(BUILD_DIR)/DUMP-ACCT: $(ADAPTED)/DUMP-ACCT.cob | $(BUILD_DIR)
	cobc -x -o $@ -I$(SRC)/$(UPSTREAM)/cpy $<

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

clean:
	rm -rf $(BUILD_DIR)
