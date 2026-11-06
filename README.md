\# AXI DMA Controller



A simple DMA engine written in SystemVerilog, verified with cocotb and Icarus Verilog.



\## Features

\- AXI4-Lite slave interface for register and SRAM access

\- AXI-Stream master output with `tvalid`/`tready` backpressure and `tlast`

\- 16-word internal SRAM



\## Register map

| Address | Name | Description |

|---------|------|-------------|

| 0x00 | CTRL | Write 1 to start the DMA |

| 0x04 | STATUS | Bit 0 = DMA active (read only) |

| 0x08 | SRC\_ADDR | SRAM word index to start reading from |

| 0x0C | XFER\_LEN | Number of words to transfer |

| 0x100-0x13C | SRAM | 16 words of internal memory |



\## Waveform



The 1-word transfer (`DEADBEEF`, `tvalid` and `tlast` high together) and the start of the 4-word transfer, viewed in GTKWave:



!\[DMA waveform](docs/waveform.png)



\## Run the test





```

make

```



Requires Python, cocotb and Icarus Verilog.



\## Verification



`test\_dma.py` writes `0xDEADBEEF` into SRAM over AXI-Lite, programs the registers, starts the DMA, and checks that the AXI-Stream output has the right data and `tlast`.

