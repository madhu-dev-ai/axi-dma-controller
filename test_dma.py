import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


async def axi_write(dut, addr, data):
    """
    Custom AXI4-Lite Write Task.
    Handles the awvalid/awready, wvalid/wready, and bvalid/bready handshakes.
    """
    dut.s_axi_awaddr.value = addr
    dut.s_axi_wdata.value = data
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_awvalid.value = 1
    dut.s_axi_wvalid.value = 1
    dut.s_axi_bready.value = 1

    aw_done = False
    w_done = False
    
    while not (aw_done and w_done):
        await RisingEdge(dut.aclk)
        # Values read here are the ones present at the clock edge (real handshake)
        if dut.s_axi_awvalid.value == 1 and dut.s_axi_awready.value == 1:
            aw_done = True
            dut.s_axi_awvalid.value = 0
        if dut.s_axi_wvalid.value == 1 and dut.s_axi_wready.value == 1:
            w_done = True
            dut.s_axi_wvalid.value = 0

    # Wait for write response (BVALID)
    while dut.s_axi_bvalid.value != 1:
        await RisingEdge(dut.aclk)
    
    await RisingEdge(dut.aclk)
    dut.s_axi_bready.value = 0


@cocotb.test()
async def test_dma_basic(dut):
    """
    Main Testbench: Verifies DMA memory write, register programming, and AXI-Stream output.
    """
    # 1. Start the clock (10ns period = 100MHz)
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    # 2. Initialize all inputs to safe default values
    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0  # Keep tready 0 to apply backpressure during setup

    # 3. Apply Reset
    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    # 4. Write test data (0xDEADBEEF) to internal SRAM at address 0x100 (maps to SRAM[0])
    await axi_write(dut, 0x100, 0xDEADBEEF)
    
    # 5. Program DMA Registers
    await axi_write(dut, 0x08, 0x00)          # SRC_ADDR = 0 (Start reading from SRAM[0])
    await axi_write(dut, 0x0C, 0x1)           # XFER_LEN = 1 (Transfer exactly 1 word)
    
    # 6. Start the DMA engine (Write 1 to CTRL_REG at 0x00)
    # NOTE: We do NOT set tready=1 yet. If we did, the DMA would finish its 1-word 
    # transfer and drop tvalid back to 0 before this axi_write call even returns, 
    # causing the subsequent loop to time out. Backpressure saves the day!
    await axi_write(dut, 0x00, 0x1)           

    # 7. Wait for the DMA to output the data
    for _ in range(100):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value == 1:
            break
    else:
        assert False, "Timeout: tvalid never went high"

    # 8. Verify Data Integrity and Protocol Signals
    # (tvalid is safely held high by the RTL because tready is still 0)
    assert dut.m_axis_tdata.value == 0xDEADBEEF, f"Data mismatch! Got {dut.m_axis_tdata.value}"
    assert dut.m_axis_tlast.value == 1, "TLAST should be high for a 1-word transfer!"
    
    # 9. Release backpressure and log success
    dut.m_axis_tready.value = 1
    dut._log.info("🎉 SUCCESS: DMA Controller Verified! Data moved perfectly.")