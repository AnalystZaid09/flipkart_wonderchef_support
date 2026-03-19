import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Wonderchef Flipkart Support Report",
    page_icon="🍳",
    layout="wide",
)

st.title("🍳 Wonderchef Flipkart Support Report Processor")
st.markdown(
    "Upload the two required Excel files to calculate **Qty Sold**, "
    "**Support Required**, and **Total Support** per product."
)

# ── File Uploaders ──────────────────────────────────────────────────────────
st.header("📁 Step 1: Upload Input Files")

col1, col2 = st.columns(2)
with col1:
    support_file_upload = st.file_uploader(
        "Wonderchef Support Flipkart.xlsx  (header on row 2)",
        type=["xlsx"],
        key="support",
    )
with col2:
    earn_more_upload = st.file_uploader(
        "EarnMoreReport.xlsx  (sales data)",
        type=["xlsx"],
        key="earn",
    )

# ── Processing ──────────────────────────────────────────────────────────────
if support_file_upload and earn_more_upload:
    st.header("⚙️ Step 2: Processing Data")

    # ── Read & clean Support file ───────────────────────────────────────────
    with st.spinner("Reading Wonderchef Support file..."):
        support_wonder = pd.read_excel(support_file_upload, header=1)

    # ── Read & clean EarnMore report ────────────────────────────────────────
    with st.spinner("Reading and cleaning EarnMore Report..."):
        df = pd.read_excel(earn_more_upload)

        numeric_cols = [
            "Gross Units", "GMV",
            "Cancellation Units", "Cancellation Amount",
            "Return Units", "Return Amount",
            "Final Sale Units", "Final Sale Amount",
        ]
        # Strip commas then coerce
        for col in numeric_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", "", regex=False)
                )
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

        # Floor negative Final Sale values at 0
        for col in ["Final Sale Units", "Final Sale Amount"]:
            if col in df.columns:
                df.loc[df[col] < 0, col] = 0

    # ── Pivot: Final Sale Units per Product Id ──────────────────────────────
    with st.spinner("Building sales pivot..."):
        pivot = (
            df.pivot_table(index="Product Id", values="Final Sale Units", aggfunc="sum")
            .reset_index()
            .sort_values("Final Sale Units", ascending=False)
        )

    # ── Map qty sold onto support file ─────────────────────────────────────
    with st.spinner("Merging qty sold into support file..."):
        qty_map = pivot.set_index("Product Id")["Final Sale Units"]
        support_wonder["Qty Sold"] = support_wonder["Flipkart Serial Number"].map(qty_map)

        support_col = "Support\nRequired"
        support_wonder[support_col] = pd.to_numeric(
            support_wonder[support_col], errors="coerce"
        )
        support_wonder["Qty Sold"] = pd.to_numeric(
            support_wonder["Qty Sold"], errors="coerce"
        )
        support_wonder["Total Support"] = (
            support_wonder[support_col] * support_wonder["Qty Sold"]
        )

    # ── Grand Total row ─────────────────────────────────────────────────────
    grand_total = pd.DataFrame(
        {
            support_col: [support_wonder[support_col].sum()],
            "Qty Sold": [support_wonder["Qty Sold"].sum()],
            "Total Support": [support_wonder["Total Support"].sum()],
            "Flipkart Serial Number": ["Grand Total"],
        }
    )
    support_with_total = pd.concat(
        [support_wonder, grand_total], ignore_index=True
    )

    st.success("✅ Processing complete!")

    # ── KPI Summary ─────────────────────────────────────────────────────────
    st.header("📊 Step 3: Summary")

    total_products = len(support_wonder)
    total_qty = support_wonder["Qty Sold"].sum()
    total_support_req = support_wonder[support_col].sum()
    total_support_val = support_wonder["Total Support"].sum()
    matched = support_wonder["Qty Sold"].notna().sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Products in Support File", total_products)
    k2.metric("Products Matched (with sales)", int(matched))
    k3.metric("Total Qty Sold", int(total_qty))
    k4.metric("Total Support Required (₹)", f"₹{total_support_req:,.2f}")
    k5.metric("Total Support Value (₹)", f"₹{total_support_val:,.2f}")

    # ── Tabs ────────────────────────────────────────────────────────────────
    st.header("📋 Step 4: Detailed Data")
    tab1, tab2, tab3 = st.tabs([
        "Support Summary (with Grand Total)",
        "EarnMore Raw Data",
        "Sales Pivot by Product",
    ])

    # ── Tab 1 : Support Summary ─────────────────────────────────────────────
    with tab1:
        st.subheader("Wonderchef Support File — Qty Sold · Support Required · Total Support")

        last_idx = len(support_with_total) - 1

        def highlight_grand_total(row):
            if row.name == last_idx:
                return ["background-color: #1f3864; color: white; font-weight: bold"] * len(row)
            elif pd.notna(row.get("Total Support", None)) and row.get("Total Support", 0) > 0:
                return ["background-color: #d4edda"] * len(row)
            elif pd.notna(row.get("Total Support", None)) and row.get("Total Support", 0) < 0:
                return ["background-color: #fde8e8"] * len(row)
            return [""] * len(row)

        styled = support_with_total.style.apply(highlight_grand_total, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        buf1 = io.BytesIO()
        support_with_total.to_excel(buf1, index=False)
        st.download_button(
            "⬇️ Download Support Summary",
            buf1.getvalue(),
            "wonderchef_support_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Tab 2 : EarnMore Raw Data ───────────────────────────────────────────
    with tab2:
        st.subheader(f"EarnMore Report — {len(df):,} rows")

        # Optional brand filter
        if "Brand" in df.columns:
            brands = sorted(df["Brand"].dropna().unique().tolist())
            selected_brands = st.multiselect(
                "Filter by Brand", brands, default=[], key="brand_filter"
            )
            display_df = df[df["Brand"].isin(selected_brands)] if selected_brands else df
        else:
            display_df = df

        st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

        buf2 = io.BytesIO()
        df.to_excel(buf2, index=False)
        st.download_button(
            "⬇️ Download EarnMore Data",
            buf2.getvalue(),
            "earn_more_cleaned.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Tab 3 : Sales Pivot ─────────────────────────────────────────────────
    with tab3:
        st.subheader(f"Final Sale Units by Product ID — {len(pivot):,} products")
        st.dataframe(pivot.reset_index(drop=True), use_container_width=True)

        buf3 = io.BytesIO()
        pivot.to_excel(buf3, index=False)
        st.download_button(
            "⬇️ Download Sales Pivot",
            buf3.getvalue(),
            "wonderchef_sales_pivot.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.info("👆 Please upload both files above to begin processing.")
    with st.expander("ℹ️ What does this app do?"):
        st.markdown("""
This tool replicates the **Wonderchef Flipkart** processing notebook:

1. **Wonderchef Support Flipkart.xlsx** — Reads the commercial support file (header on row 2).
   Contains product-level pricing, payout, margin, and `Support\\nRequired` per unit.

2. **EarnMoreReport.xlsx** — Full Flipkart sales report. Numeric columns are cleaned
   (comma removal, type coercion) and negative `Final Sale Units` / `Final Sale Amount` are
   floored to zero.

3. **Sales Pivot** — `Final Sale Units` is summed per `Product Id`.

4. **Qty Sold Lookup** — Pivoted qty is mapped onto the support file using the
   `Flipkart Serial Number` → `Product Id` key.

5. **Total Support** = `Support\\nRequired × Qty Sold` per row.

6. **Grand Total row** — Sums `Support\\nRequired`, `Qty Sold`, and `Total Support`
   at the bottom, highlighted in dark blue.

**Row colours in Support Summary:**
- 🟩 Green = positive Total Support (product is profitable)
- 🟥 Red = negative Total Support (product needs support)
- 🟦 Dark blue = Grand Total row
        """)