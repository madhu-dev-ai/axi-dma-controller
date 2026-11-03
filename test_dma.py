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
    """1-word transfer: write SRAM, program registers, check data and tlast."""
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0  # backpressure during setup

    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    await axi_write(dut, 0x100, 0xDEADBEEF)   # SRAM[0]
    await axi_write(dut, 0x08, 0x00)          # SRC_ADDR = 0
    await axi_write(dut, 0x0C, 0x1)           # XFER_LEN = 1
    await axi_write(dut, 0x00, 0x1)           # START (tready still 0)

    for _ in range(100):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value == 1:
            break
    else:
        assert False, "Timeout: tvalid never went high"

    assert dut.m_axis_tdata.value == 0xDEADBEEF, f"Data mismatch! Got {dut.m_axis_tdata.value}"
    assert dut.m_axis_tlast.value == 1, "TLAST should be high for a 1-word transfer!"

    dut.m_axis_tready.value = 1
    dut._log.info("SUCCESS: 1-word transfer verified.")


@cocotb.test()
async def test_dma_multi_word(dut):
    """4-word transfer: check data order and that tlast is only on the last word."""
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0

    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    expected = [0x11111111, 0x22222222, 0x33333333, 0x44444444]

    # Fill SRAM[0..3] (addresses 0x100, 0x104, 0x108, 0x10C)
    for i, word in enumerate(expected):
        await axi_write(dut, 0x100 + 4 * i, word)

    await axi_write(dut, 0x08, 0x0)   # SRC_ADDR = 0
    await axi_write(dut, 0x0C, 0x4)   # XFER_LEN = 4

    received = []
    lasts = []

    async def monitor():
        while True:
            await RisingEdge(dut.aclk)
            if dut.m_axis_tvalid.value == 1 and dut.m_axis_tready.value == 1:
                received.append(int(dut.m_axis_tdata.value))
                lasts.append(int(dut.m_axis_tlast.value))

    cocotb.start_soon(monitor())

    dut.m_axis_tready.value = 1
    await axi_write(dut, 0x00, 0x1)   # START

    for _ in range(50):
        await RisingEdge(dut.aclk)

    assert received == expected, f"Data mismatch! Got {[hex(x) for x in received]}"
    assert lasts == [0, 0, 0, 1], f"TLAST wrong! Got {lasts}"
    dut._log.info("SUCCESS: 4-word transfer verified.")
    
@cocotb.test()
async def test_dma_backpressure(dut):
    """8-word transfer with tready toggling randomly. No word lost or repeated."""
    import random
    random.seed(1)

    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0

    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    expected = [0xA0 + i for i in range(8)]

    for i, word in enumerate(expected):
        await axi_write(dut, 0x100 + 4 * i, word)

    await axi_write(dut, 0x08, 0x0)   # SRC_ADDR = 0
    await axi_write(dut, 0x0C, 0x8)   # XFER_LEN = 8

    received = []
    lasts = []

    async def monitor():
        while True:
            await RisingEdge(dut.aclk)
            if dut.m_axis_tvalid.value == 1 and dut.m_axis_tready.value == 1:
                received.append(int(dut.m_axis_tdata.value))
                lasts.append(int(dut.m_axis_tlast.value))

    async def tready_driver():
        while True:
            await RisingEdge(dut.aclk)
            dut.m_axis_tready.value = random.randint(0, 1)

    cocotb.start_soon(monitor())
    cocotb.start_soon(tready_driver())

    await axi_write(dut, 0x00, 0x1)   # START

    for _ in range(200):
        await RisingEdge(dut.aclk)

    assert received == expected, f"Data wrong! Got {[hex(x) for x in received]}"
    assert lasts == [0] * 7 + [1], f"TLAST wrong! Got {lasts}"
    dut._log.info("SUCCESS: backpressure test passed.")
    
@cocotb.test()
async def test_dma_nonzero_src(dut):
    """Start at SRAM[5], move 3 words. Neighbours must NOT be sent."""
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0

    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    # SRAM[4] and SRAM[8] are "guard" words that must never appear in the output
    await axi_write(dut, 0x100 + 4 * 4, 0xBAD00004)
    await axi_write(dut, 0x100 + 4 * 5, 0x55555555)
    await axi_write(dut, 0x100 + 4 * 6, 0x66666666)
    await axi_write(dut, 0x100 + 4 * 7, 0x77777777)
    await axi_write(dut, 0x100 + 4 * 8, 0xBAD00008)

    await axi_write(dut, 0x08, 0x5)   # SRC_ADDR = 5
    await axi_write(dut, 0x0C, 0x3)   # XFER_LEN = 3

    received = []
    lasts = []

    async def monitor():
        while True:
            await RisingEdge(dut.aclk)
            if dut.m_axis_tvalid.value == 1 and dut.m_axis_tready.value == 1:
                received.append(int(dut.m_axis_tdata.value))
                lasts.append(int(dut.m_axis_tlast.value))

    cocotb.start_soon(monitor())

    dut.m_axis_tready.value = 1
    await axi_write(dut, 0x00, 0x1)   # START

    for _ in range(50):
        await RisingEdge(dut.aclk)

    assert received == [0x55555555, 0x66666666, 0x77777777], f"Data wrong! Got {[hex(x) for x in received]}"
    assert lasts == [0, 0, 1], f"TLAST wrong! Got {lasts}"
    dut._log.info("SUCCESS: non-zero SRC_ADDR test passed.")
    
@cocotb.test()
async def test_dma_back_to_back(dut):
    """Two transfers in a row, no reset between them."""
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())

    dut.aresetn.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_awaddr.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_bready.value = 0
    dut.m_axis_tready.value = 0

    for _ in range(3):
        await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)

    first = [0x10, 0x20]
    second = [0xA1, 0xA2, 0xA3]

    for i, word in enumerate(first):
        await axi_write(dut, 0x100 + 4 * i, word)          # SRAM[0..1]
    for i, word in enumerate(second):
        await axi_write(dut, 0x100 + 4 * (4 + i), word)    # SRAM[4..6]

    received = []
    lasts = []

    async def monitor():
        while True:
            await RisingEdge(dut.aclk)
            if dut.m_axis_tvalid.value == 1 and dut.m_axis_tready.value == 1:
                received.append(int(dut.m_axis_tdata.value))
                lasts.append(int(dut.m_axis_tlast.value))

    cocotb.start_soon(monitor())
    dut.m_axis_tready.value = 1

    # Transfer 1: SRAM[0], 2 words
    await axi_write(dut, 0x08, 0x0)
    await axi_write(dut, 0x0C, 0x2)
    await axi_write(dut, 0x00, 0x1)
    for _ in range(30):
        await RisingEdge(dut.aclk)

    assert received == first, f"Transfer 1 data wrong! Got {[hex(x) for x in received]}"
    assert lasts == [0, 1], f"Transfer 1 TLAST wrong! Got {lasts}"

    received.clear()
    lasts.clear()

    # Transfer 2: SRAM[4], 3 words, NO reset
    await axi_write(dut, 0x08, 0x4)
    await axi_write(dut, 0x0C, 0x3)
    await axi_write(dut, 0x00, 0x1)
    for _ in range(30):
        await RisingEdge(dut.aclk)

    assert received == second, f"Transfer 2 data wrong! Got {[hex(x) for x in received]}"
    assert lasts == [0, 0, 1], f"Transfer 2 TLAST wrong! Got {lasts}"
    dut._log.info("SUCCESS: back-to-back transfers passed.")