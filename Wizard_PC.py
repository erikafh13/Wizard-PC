import streamlit as st
import pandas as pd
import re
from io import BytesIO

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Bundling PC Pro", layout="wide")

st.title("🖥️ Sistem Bundling PC - Auto Selection")
st.markdown("Sistem otomatis merekomendasikan item teratas. Klik baris pada tabel untuk mengubah pilihan.")

# --- FUNGSI PEMROSESAN DATA ---
def process_data(df):
    # Bersihkan nama kolom (hilangkan spasi berlebih)
    df.columns = df.columns.str.strip()
    
    # Pastikan kolom numerik aman
    cols_to_numeric = ['Web', 'Stock Total', 'Current SO']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Filter Stock > 0
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    
    # Mapping Kolom Baru
    df['Office'] = False
    df['Std/2D'] = False 
    df['Adv/3D'] = False 
    df['NeedVGA'] = False
    df['HasPSU'] = False

    # 1. PROCESSOR
    proc_mask = df['Kategori'] == 'Processor'
    def map_processor(row):
        name = row['Nama Accurate'].upper()
        if re.search(r'\d+[0-9]F\b', name): row['NeedVGA'] = True
        if 'I3' in name or 'I5' in name:
            row['Office'] = True
            row['Std/2D'] = True
        if 'I5' in name or 'I7' in name or 'I9' in name:
            row['Adv/3D'] = True
        return row
    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # 2. MOTHERBOARD
    mb_mask = df['Kategori'] == 'Motherboard'
    h_intel = ['H410', 'H510', 'H610', 'H810', 'H81', 'H110', 'H310']
    b_intel, z_intel = ['B660', 'B760', 'B860'], ['Z790', 'Z890']
    a_amd, b_amd, x_amd = ['A520', 'A620'], ['B450', 'B550', 'B650', 'B840', 'B850'], ['X870']
    
    def map_mobo(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if any(x in name for x in h_intel) or any(x in name for x in a_amd): row['Office'] = True
        if (any(x in name for x in b_intel) and price < 2000000) or any(x in name for x in b_amd):
            row['Std/2D'] = True
        if (any(x in name for x in b_intel) and price >= 2000000) or any(x in name for x in z_intel) or \
           any(x in name for x in b_amd) or any(x in name for x in x_amd):
            row['Adv/3D'] = True
        return row
    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # 3. RAM
    ram_mask = df['Kategori'] == 'Memory RAM'
    def map_ram(row):
        name = re.sub(r'\(.*?\)', '', row['Nama Accurate'].upper())
        match = re.search(r'(\d+)\s*GB', name)
        if match:
            size = int(match.group(1))
            if 8 <= size <= 16: row['Office'] = True
            if 16 <= size <= 32: row['Std/2D'] = True
            if 32 <= size <= 128: row['Adv/3D'] = True
        return row
    df.loc[ram_mask] = df[ram_mask].apply(map_ram, axis=1)

    # 4. SSD
    df.loc[df['Kategori'] == 'SSD Internal', ['Office', 'Std/2D', 'Adv/3D']] = True

    # 5. VGA
    vga_mask = df['Kategori'] == 'VGA'
    gt_off = ['GT710', 'GT730']
    vga_std = ['GT1030', 'GTX1650', 'RTX3050', 'RTX3060', 'RTX5050', 'RTX4060']
    vga_adv = ['RTX5060', 'RTX5070', 'RTX5080', 'RTX5090']
    def map_vga(row):
        name = row['Nama Accurate'].upper()
        if any(x in name for x in gt_off): row['Office'] = True
        if any(x in name for x in vga_std): row['Std/2D'] = True
        if any(x in name for x in vga_adv) or 'TI' in name: row['Adv/3D'] = True
        return row
    df.loc[vga_mask] = df[vga_mask].apply(map_vga, axis=1)

    # 6. CASING
    case_mask = df['Kategori'] == 'Casing PC'
    def map_case(row):
        if 'PSU' in row['Nama Accurate'].upper():
            row['Office'], row['HasPSU'] = True, True
        else:
            row['Std/2D'], row['Adv/3D'] = True, True
        return row
    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # 7. PSU
    psu_mask = df['Kategori'] == 'Power Supply'
    certs = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'TITANIUM']
    def map_psu(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if price < 500000: row['Office'] = True
        if price >= 500000: row['Std/2D'] = True
        if any(c in name for c in certs): row['Adv/3D'] = True
        return row
    df.loc[psu_mask] = df[psu_mask].apply(map_psu, axis=1)
    
    return df

# --- HELPER: FUNGSI MEMILIH KOMPONEN ---
def component_selector(label, df_source, key_prefix):
    """Menampilkan dataframe interaktif. Jika user belum pilih, otomatis ambil baris pertama."""
    st.markdown(f"**{label}**")
    
    if df_source.empty:
        st.warning(f"Stok kosong untuk {label}.")
        return None

    # Konfigurasi Kolom Tampilan
    col_config = {
        "Nama Accurate": st.column_config.TextColumn("Nama Produk", width="medium"),
        "Brand": st.column_config.TextColumn("Brand", width="small"),
        "Web": st.column_config.NumberColumn("Harga", format="Rp %d"),
        "Stock Total": st.column_config.NumberColumn("Stock", help="Total Stok"),
        "Current SO": st.column_config.NumberColumn("SO", help="Current Sales Order"),
    }
    
    # Kolom yang ditampilkan di tabel pemilihan (Sesuai Request)
    display_cols = ["Nama Accurate", "Brand", "Web", "Stock Total", "Current SO"]
    
    # Pastikan kolom ada di dataframe
    valid_cols = [c for c in display_cols if c in df_source.columns]

    selection = st.dataframe(
        df_source[valid_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        selection_mode="single-row",
        on_select="rerun",
        key=f"table_{key_prefix}"
    )
    
    # LOGIKA AUTO-SELECT
    if selection.selection.rows:
        # User memilih manual
        selected_index = selection.selection.rows[0]
        return df_source.iloc[selected_index]
    else:
        # Default: Ambil baris pertama (Top Recommendation)
        return df_source.iloc[0]

# --- HELPER: EXCEL DOWNLOADER ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- INPUT DATA ---
uploaded_file = st.file_uploader("Upload Data Portal (CSV/Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_df = pd.read_csv(uploaded_file)
        else:
            raw_df = pd.read_excel(uploaded_file)

        data = process_data(raw_df)

        # --- PILIH KATEGORI ---
        st.divider()
        bundle_type_map = {
            "Office": "Office",
            "Gaming Standard / Design 2D": "Std/2D",
            "Gaming Advanced / Design 3D": "Adv/3D"
        }
        
        bundle_label = st.radio("Pilih Kategori Peruntukan PC:", list(bundle_type_map.keys()), horizontal=True)
        bundle_col = bundle_type_map[bundle_label]
        
        # Filter global berdasarkan kategori bundle
        filtered_data = data[data[bundle_col] == True].sort_values('Web')

        # --- TAMPILAN RAW DATA (SESUAI REQUEST) ---
        with st.expander(f"📂 Lihat Data Stok: {bundle_label} (Klik untuk buka)"):
            # Cari semua kolom yang mengandung kata 'Stock'
            stock_cols = [c for c in data.columns if 'Stock' in c]
            
            # Kolom wajib yang diminta
            base_cols = ['SKU', 'Kategori', 'Brand', 'Nama Accurate', 'Current SO', 'ABC Category']
            
            # Gabungkan kolom (pastikan kolom ada di data)
            final_raw_cols = [c for c in base_cols if c in data.columns] + stock_cols + [bundle_col]
            
            # Tampilkan data yang sudah difilter kategori
            st.dataframe(filtered_data[final_raw_cols], use_container_width=True, hide_index=True)
            
            st.download_button(
                label="📥 Download Data Filtered (Excel)",
                data=to_excel(filtered_data[final_raw_cols]),
                file_name=f"data_stok_{bundle_col.replace('/','_')}.xlsx",
                mime="application/vnd.ms-excel"
            )

        st.divider()
        st.info(f"Komponen otomatis terpilih berdasarkan harga terendah untuk: **{bundle_label}**. Silakan sesuaikan.")
        
        selected_bundle = {}

        # 1. PROCESSOR
        procs = filtered_data[filtered_data['Kategori'] == 'Processor']
        sel_proc = component_selector("1. Processor", procs, "proc")
        if sel_proc is not None: selected_bundle['Processor'] = sel_proc

        # 2. MOTHERBOARD
        mobs = filtered_data[filtered_data['Kategori'] == 'Motherboard']
        sel_mobo = component_selector("2. Motherboard", mobs, "mobo")
        if sel_mobo is not None: selected_bundle['Motherboard'] = sel_mobo

        # 3. RAM
        rams = filtered_data[filtered_data['Kategori'] == 'Memory RAM']
        sel_ram = component_selector("3. Memory RAM", rams, "ram")
        if sel_ram is not None: selected_bundle['RAM'] = sel_ram

        # 4. SSD
        ssds = filtered_data[filtered_data['Kategori'] == 'SSD Internal']
        sel_ssd = component_selector("4. SSD Internal", ssds, "ssd")
        if sel_ssd is not None: selected_bundle['SSD'] = sel_ssd

        # 5. VGA (Logic)
        if 'Processor' in selected_bundle:
            need_vga = selected_bundle['Processor']['NeedVGA']
            vgas = filtered_data[filtered_data['Kategori'] == 'VGA']
            
            if need_vga:
                st.warning("⚠️ Processor Seri F (Wajib VGA)")
                sel_vga = component_selector("5. VGA (Wajib)", vgas, "vga")
                if sel_vga is not None: selected_bundle['VGA'] = sel_vga
            else:
                st.success("✅ IGPU Available")
                # Untuk opsional, kita pakai checkbox. Jika dicentang, baru muncul tabel.
                use_vga = st.checkbox("Tambah VGA Card (Opsional)?", value=False)
                if use_vga:
                    sel_vga = component_selector("5. VGA (Opsional)", vgas, "vga")
                    if sel_vga is not None: selected_bundle['VGA'] = sel_vga

        # 6. CASING
        cases = filtered_data[filtered_data['Kategori'] == 'Casing PC']
        sel_case = component_selector("6. Casing PC", cases, "case")
        if sel_case is not None: selected_bundle['Casing'] = sel_case

        # 7. PSU (Logic)
        if 'Casing' in selected_bundle:
            has_psu = selected_bundle['Casing']['HasPSU']
            if not has_psu:
                psus = filtered_data[filtered_data['Kategori'] == 'Power Supply']
                sel_psu = component_selector("7. Power Supply", psus, "psu")
                if sel_psu is not None: selected_bundle['PSU'] = sel_psu
            else:
                st.caption("ℹ️ Casing sudah termasuk PSU.")

        # --- RINGKASAN & DOWNLOAD ---
        st.divider()
        st.subheader("🧾 Ringkasan Bundling")
        
        if selected_bundle:
            summary_list = []
            total_price = 0
            
            for part, row in selected_bundle.items():
                summary_list.append({
                    "Komponen": part,
                    "Nama Produk": row['Nama Accurate'],
                    "Brand": row['Brand'] if 'Brand' in row else '-',
                    "Harga": row['Web']
                })
                total_price += row['Web']
            
            summary_df = pd.DataFrame(summary_list)
            
            st.dataframe(
                summary_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={"Harga": st.column_config.NumberColumn(format="Rp %d")}
            )
            
            st.markdown(f"### Total Estimasi: **Rp {total_price:,.0f}**")
            
            st.download_button(
                label="📥 Download Hasil Rakitan (.xlsx)",
                data=to_excel(summary_df),
                file_name=f"rakitan_{bundle_col}.xlsx",
                mime="application/vnd.ms-excel"
            )
            
    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
        st.write("Detail Error untuk debugging:", str(e))

else:
    st.info("Silakan upload file data stok untuk memulai.")
