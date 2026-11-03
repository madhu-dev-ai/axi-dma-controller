SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += rtl/dma_engine.sv

TOPLEVEL = dma_engine
COCOTB_TEST_MODULES = test_dma

include $(shell cocotb-config --makefiles)/Makefile.sim