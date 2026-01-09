import streamlit as st
import pandas as pd
import re
from io import BytesIO

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Bundling PC Pro", layout="wide")

st.title("🖥️ Sistem Bundling PC - Table Selection Mode")
st.markdown("Pilih komponen langsung dari tabel. Klik pada baris produk untuk memilihnya.")

# --- FUNGSI PEMROSESAN DATA ---
def process_data(df):
    # Filter Stock > 0 dan kolom yang diperlukan
    # Pastikan nama kolom sesuai dengan file asli Anda
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Mapping Kolom Baru
    df['Office'] = False
    df['Std/2D'] = False # Gaming Standard
    df['Adv/3D'] = False # Gaming Advanced
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

# --- HELPER: FUNGSI MEMILIH KOMPONEN DENGAN TABEL ---
def component_selector(label, df_source, key_prefix):
    """Menampilkan dataframe interaktif untuk pemilihan komponen"""
    st.markdown(f"### {label}")
    
    if df_source.empty:
        st.warning(f"Tidak ada produk {label} yang cocok dengan kategori ini.")
        return None

    # Konfigurasi Kolom agar rapi
    col_config = {
        "Nama Accurate": st.column_config.TextColumn("Nama Produk", width="medium"),
        "Web": st.column_config.NumberColumn("Harga", format="Rp %d"),
        "Stock Total": st.column_config.NumberColumn("Stok", help="Sisa stok gudang"),
        "Office": st.column_config.CheckboxColumn("Office"),
        "Std/2D": st.column_config.CheckboxColumn("Std/2D"),
        "Adv/3D": st.column_config.CheckboxColumn("Adv/3D"),
    }
    
    # Tampilkan kolom-kolom penting saja
    display_cols = ["Nama Accurate", "Web", "Stock Total", "Office", "Std/2D", "Adv/3D"]
    
    # Widget Dataframe dengan Selection Mode
    selection = st.dataframe(
        df_source[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        selection_mode="single-row", # Hanya boleh pilih 1
        on_select="rerun",
        key=f"table_{key_prefix}"
    )
    
    # Mengambil data baris yang dipilih
    if selection.selection.rows:
        selected_index = selection.selection.rows[0]
        return df_source.iloc[selected_index]
    return None

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

        # Tab untuk melihat raw data hasil mapping (opsional)
        with st.expander("📂 Lihat Data Mentah Hasil Mapping (Klik untuk buka)"):
            st.dataframe(data)
            st.download_button(
                label="📥 Download Data Mapping (Excel)",
                data=to_excel(data),
                file_name="data_mapping_pc.xlsx",
                mime="application/vnd.ms-excel"
            )
        
        # --- PILIH KATEGORI ---
        st.divider()
        bundle_type_map = {
            "Office": "Office",
            "Gaming Standard / Design 2D": "Std/2D",
            "Gaming Advanced / Design 3D": "Adv/3D"
        }
        
        bundle_label = st.radio("Pilih Kategori Peruntukan PC:", list(bundle_type_map.keys()), horizontal=True)
        bundle_col = bundle_type_map[bundle_label] # Ambil nama kolom pendek (misal: Std/2D)
        
        st.info(f"Menampilkan komponen yang cocok untuk: **{bundle_label}** (Stock tersedia)")
        
        # Filter global berdasarkan kategori bundle
        filtered_data = data[data[bundle_col] == True].sort_values('Web')

        selected_bundle = {}

        # 1. PROCESSOR
        procs = filtered_data[filtered_data['Kategori'] == 'Processor']
        sel_proc = component_selector("1. Pilih Processor", procs, "proc")
        if sel_proc is not None:
            selected_bundle['Processor'] = sel_proc

        # 2. MOTHERBOARD
        mobs = filtered_data[filtered_data['Kategori'] == 'Motherboard']
        sel_mobo = component_selector("2. Pilih Motherboard", mobs, "mobo")
        if sel_mobo is not None:
            selected_bundle['Motherboard'] = sel_mobo

        # 3. RAM
        rams = filtered_data[filtered_data['Kategori'] == 'Memory RAM']
        sel_ram = component_selector("3. Pilih RAM", rams, "ram")
        if sel_ram is not None:
            selected_bundle['RAM'] = sel_ram

        # 4. SSD
        ssds = filtered_data[filtered_data['Kategori'] == 'SSD Internal']
        sel_ssd = component_selector("4. Pilih SSD", ssds, "ssd")
        if sel_ssd is not None:
            selected_bundle['SSD'] = sel_ssd

        # 5. VGA (Kondisional)
        if 'Processor' in selected_bundle:
            need_vga = selected_bundle['Processor']['NeedVGA']
            
            # Siapkan data VGA
            vgas = filtered_data[filtered_data['Kategori'] == 'VGA']
            
            if need_vga:
                st.warning("⚠️ Processor seri 'F' terdeteksi. Wajib memilih VGA.")
                sel_vga = component_selector("5. Pilih VGA (Wajib)", vgas, "vga")
                if sel_vga is not None:
                    selected_bundle['VGA'] = sel_vga
            else:
                st.success("✅ Processor memiliki IGPU. VGA Opsional.")
                show_vga = st.checkbox("Tambah VGA card terpisah?")
                if show_vga:
                    sel_vga = component_selector("5. Pilih VGA (Opsional)", vgas, "vga")
                    if sel_vga is not None:
                        selected_bundle['VGA'] = sel_vga

        # 6. CASING
        cases = filtered_data[filtered_data['Kategori'] == 'Casing PC']
        sel_case = component_selector("6. Pilih Casing", cases, "case")
        if sel_case is not None:
            selected_bundle['Casing'] = sel_case

        # 7. PSU (Kondisional)
        if 'Casing' in selected_bundle:
            has_psu = selected_bundle['Casing']['HasPSU']
            if not has_psu:
                psus = filtered_data[filtered_data['Kategori'] == 'Power Supply']
                sel_psu = component_selector("7. Pilih Power Supply", psus, "psu")
                if sel_psu is not None:
                    selected_bundle['PSU'] = sel_psu
            else:
                st.info("ℹ️ Casing yang dipilih sudah termasuk PSU bawaan.")

        # --- RINGKASAN & DOWNLOAD ---
        st.divider()
        st.subheader("🧾 Ringkasan Estimasi Rakitan")
        
        if selected_bundle:
            # Convert dict to DataFrame for display
            summary_list = []
            total_price = 0
            
            for part, row in selected_bundle.items():
                summary_list.append({
                    "Komponen": part,
                    "Nama Produk": row['Nama Accurate'],
                    "Harga": row['Web']
                })
                total_price += row['Web']
            
            summary_df = pd.DataFrame(summary_list)
            
            # Tampilkan Tabel Ringkasan
            st.dataframe(
                summary_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={"Harga": st.column_config.NumberColumn(format="Rp %d")}
            )
            
            st.markdown(f"### Total Estimasi: **Rp {total_price:,.0f}**")
            
            # Tombol Download Hasil
            st.download_button(
                label="📥 Download Rincian Rakitan (.xlsx)",
                data=to_excel(summary_df),
                file_name=f"rakitan_pc_{bundle_label}.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.caption("Belum ada komponen yang dipilih.")
            
    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
        st.write("Pastikan file memiliki kolom: 'Nama Accurate', 'Web', 'Stock Total', 'Kategori'")

else:
    st.info("Silakan upload file data stok untuk memulai.")
