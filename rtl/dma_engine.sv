module dma_engine (
    input  wire        aclk,
    input  wire        aresetn,

    input  wire [31:0] s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output reg         s_axi_awready,

    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output reg         s_axi_wready,

    output reg  [1:0]  s_axi_bresp,
    output reg         s_axi_bvalid,
    input  wire        s_axi_bready,

    input  wire [31:0] s_axi_araddr,
    input  wire        s_axi_arvalid,
    output reg         s_axi_arready,

    output reg  [31:0] s_axi_rdata,
    output reg  [1:0]  s_axi_rresp,
    output reg         s_axi_rvalid,
    input  wire        s_axi_rready,

    output reg  [31:0] m_axis_tdata,
    output reg         m_axis_tvalid,
    input  wire        m_axis_tready,
    output reg         m_axis_tlast
);

    // 16-word SRAM
    reg [31:0] sram [0:15];

    // Simple control
    reg        dma_active;
    reg [3:0]  ptr;
    reg [3:0]  count;
    reg [3:0]  src;      // NEW: SRC_ADDR register (0x08)
    reg [3:0]  length;   // XFER_LEN register (0x0C)

    always @(posedge aclk or negedge aresetn) begin
        if (!aresetn) begin
            s_axi_awready <= 0;
            s_axi_wready  <= 0;
            s_axi_bvalid  <= 0;
            s_axi_bresp   <= 0;
            s_axi_arready <= 0;
            s_axi_rvalid  <= 0;
            s_axi_rdata   <= 0;
            s_axi_rresp   <= 0;

            m_axis_tdata  <= 0;
            m_axis_tvalid <= 0;
            m_axis_tlast  <= 0;

            dma_active    <= 0;
            ptr           <= 0;
            count         <= 0;
            src           <= 0;
            length        <= 0;
        end else begin
            // Clear ready signals by default
            s_axi_awready <= 0;
            s_axi_wready  <= 0;
            s_axi_arready <= 0;

            // Clear responses
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 0;
            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 0;

            // AXI-Lite Write
            if (s_axi_awvalid && s_axi_wvalid && !s_axi_bvalid) begin
                s_axi_awready <= 1;
                s_axi_wready  <= 1;
                s_axi_bvalid  <= 1;

                if (s_axi_awaddr == 32'h00) begin
                    // Start DMA
                    if (s_axi_wdata[0]) begin
                        dma_active <= 1;
                        ptr        <= src;   // start reading at SRC_ADDR
                        count      <= 0;
                    end
                end else if (s_axi_awaddr == 32'h08) begin
                    src <= s_axi_wdata[3:0];      // SRC_ADDR
                end else if (s_axi_awaddr == 32'h0C) begin
                    length <= s_axi_wdata[3:0];   // XFER_LEN
                end else if (s_axi_awaddr >= 32'h100 && s_axi_awaddr < 32'h140) begin
                    sram[s_axi_awaddr[5:2]] <= s_axi_wdata;
                end
            end

            // AXI-Lite Read
            if (s_axi_arvalid && !s_axi_rvalid) begin
                s_axi_arready <= 1;
                s_axi_rvalid  <= 1;

                if (s_axi_araddr == 32'h04) begin
                    s_axi_rdata <= {31'd0, dma_active};
                end else if (s_axi_araddr >= 32'h100 && s_axi_araddr < 32'h140) begin
                    s_axi_rdata <= sram[s_axi_araddr[5:2]];
                end else begin
                    s_axi_rdata <= 0;
                end
            end

            // DMA Output (AXI-Stream: hold tvalid until tready)
            if (dma_active) begin
                if (m_axis_tready || !m_axis_tvalid) begin
                    m_axis_tdata  <= sram[ptr];
                    m_axis_tvalid <= 1;

                    if (count == length - 1) begin
                        m_axis_tlast <= 1;
                        dma_active   <= 0;     // tvalid stays 1 now
                    end else begin
                        m_axis_tlast <= 0;
                        ptr          <= ptr + 1;
                        count        <= count + 1;
                    end
                end
            end else if (m_axis_tvalid && m_axis_tready) begin
                // last word was accepted, so now drop tvalid and tlast
                m_axis_tvalid <= 0;
                m_axis_tlast  <= 0;
            end
        end
    end

endmodule