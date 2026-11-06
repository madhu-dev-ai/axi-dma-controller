# AXI DMA Controller



A simple DMA engine written in SystemVerilog, verified with cocotb and Icarus Verilog.



## Features



- AXI4-Lite slave interface for register and SRAM access

- AXI-Stream master output with `tvalid`/`tready` backpressure and `tlast`

- 16-word internal SRAM



## Register map



| Address | Name | Description |

|---------|------|-------------|

| 0x00 | CTRL | Write 1 to start the DMA |

| 0x04 | STATUS | Bit 0 = DMA active (read only) |

| 0x08 | SRC_ADDR | SRAM word index to start reading from |

| 0x0C | XFER_LEN | Number of words to transfer |

| 0x100-0x13C | SRAM | 16 words of internal memory |



## Waveform



The 1-word transfer (`DEADBEEF`, `tvalid` and `tlast` high together) and the start of the 4-word transfer, viewed in GTKWave:



![DMA waveform](docs/waveform.png)



## Run the test



```

make

```



Requires Python, cocotb and Icarus Verilog.



## Verification



`test_dma.py` contains 5 cocotb tests:



- 1-word transfer

- 4-word transfer

- Random backpressure (8 words, `tready` toggling)

- Non-zero `SRC_ADDR` (start at SRAM[5])

- Back-to-back transfers without reset

