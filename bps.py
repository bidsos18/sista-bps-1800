import os
import streamlit as st
import base64
import ast
from pathlib import Path
from supabase import create_client
from utils import (
    load_css,
    login_dialog,
    show_login_dialog_if_requested
)


# ============================================================
# KONFIGURASI HALAMAN
# ============================================================

st.set_page_config(
    page_title="SISTA - Sistem Informasi Statistik Sosial",
    page_icon="logo_bps.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# LOAD CSS
# ============================================================

load_css()
show_login_dialog_if_requested()

# ============================================================
# SESSION STATE
# ============================================================

if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

if "mobile_nav_open" not in st.session_state:
    st.session_state["mobile_nav_open"] = False

# ============================================================
# DAFTAR HALAMAN
# ============================================================

home = st.Page(
    "pages/Home.py",
    title="Beranda",
    icon=":material/home:",
    default=True
)

dashboard = st.Page(
    "pages/Dashboard.py",
    title="Dashboard",
    icon=":material/dashboard:"
)

dokumen = st.Page(
    "pages/Dokumen.py",
    title="Dokumen",
    icon=":material/description:"
)

kemiskinan = st.Page(
    "pages/Kemiskinan.py",
    title="Kemiskinan",
    icon=":material/payments:"
)

ketenagakerjaan = st.Page(
    "pages/Ketenagakerjaan.py",
    title="Ketenagakerjaan",
    icon=":material/work:"
)

pendidikan = st.Page(
    "pages/Pendidikan.py",
    title="Pendidikan",
    icon=":material/school:"
)

penduduk = st.Page(
    "pages/Penduduk.py",
    title="Kependudukan",
    icon=":material/groups:"
)

pengeluaran = st.Page(
    "pages/Pengeluaran_Makanan.py",
    title="Pengeluaran Makanan",
    icon=":material/restaurant:"
)

perumahan = st.Page(
    "pages/Perumahan.py",
    title="Perumahan",
    icon=":material/home:"
)

statistik_lainnya = st.Page(
    "pages/Statistik_Sosial_Lainnya.py",
    title="Lainnya",
    icon=":material/category:"
)

# ============================================================
# CEK HALAMAN STATISTIK SOSIAL YANG AKTIF
# ============================================================
pg = st.navigation(
    [
        home,
        dashboard,
        dokumen,
        kemiskinan,
        ketenagakerjaan,
        pendidikan,
        penduduk,
        pengeluaran,
        perumahan,
        statistik_lainnya
    ],
    position="hidden"
)

# ------------------------------------------------------------
# True jika sedang berada di salah satu halaman Statistik Sosial
# ------------------------------------------------------------
statistik_sosial_aktif = pg in [
    kemiskinan,
    ketenagakerjaan,
    pendidikan,
    penduduk,
    pengeluaran,
    perumahan,
    statistik_lainnya,
]

# ============================================================
# DATA PENCARIAN
# ============================================================
# Format: "Nama Halaman": (halaman, "kata kunci dipisah spasi")
# Tambahkan kata kunci sesuai indikator yang ada di tiap halaman.

HALAMAN_CARI = {
    "Dashboard": (
        dashboard,
        "ringkasan grafik indikator utama"
    ),
    "Kemiskinan": (
        kemiskinan,
        "miskin garis p0 p1 p2 kedalaman keparahan gini"
    ),
    "Ketenagakerjaan": (
        ketenagakerjaan,
        "kerja tenaga pengangguran tpt tpak sakernas upah"
    ),
    "Pendidikan": (
        pendidikan,
        "sekolah apm apk rls hls literasi melek huruf"
    ),
    "Kependudukan": (
        penduduk,
        "penduduk populasi kepadatan jiwa laju pertumbuhan"
    ),
    "Pengeluaran Makanan": (
        pengeluaran,
        "makan makanan pengeluaran konsumsi pangan"
    ),
    "Perumahan": (
        perumahan,
        "rumah hunian sanitasi air minum listrik atap lantai"
    ),
    "Statistik Sosial Lainnya": (
        statistik_lainnya,
        "lainnya sosial"
    ),
    "Dokumen": (
        dokumen,
        "dokumen publikasi unduh download file"
    ),
}

PANDUAN_FILE = "panduan.pdf"


# ============================================================
# DATA PENCARIAN INDIKATOR
# ============================================================
# Pencarian juga mencari NAMA INDIKATOR (bawaan di file halaman + yang ditambah
# admin di database), bukan hanya halaman. Tidak perlu menambah kata kunci manual.
# Format: (halaman, file halaman)

HALAMAN_INDIKATOR = [
    (kemiskinan, "pages/Kemiskinan.py"),
    (ketenagakerjaan, "pages/Ketenagakerjaan.py"),
    (pendidikan, "pages/Pendidikan.py"),
    (penduduk, "pages/Penduduk.py"),
    (pengeluaran, "pages/Pengeluaran_Makanan.py"),
    (perumahan, "pages/Perumahan.py"),
    (statistik_lainnya, "pages/Statistik_Sosial_Lainnya.py"),
]

MAKS_HASIL_INDIKATOR = 10


@st.cache_data(show_spinner=False)
def _baca_halaman_indikator(file):
    """Baca menu, prefix, dan indikator bawaan dari file halaman TANPA menjalankannya.

    Mengembalikan (menu, prefix, [(nama, tabel), ...]) atau None bila gagal dibaca.
    """
    try:
        tree = ast.parse((Path(__file__).parent / file).read_text(encoding="utf-8"))
    except Exception:
        return None

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Dict)):
            continue
        cfg = {
            k.value: v for k, v in zip(node.args[0].keys, node.args[0].values)
            if isinstance(k, ast.Constant)
        }
        if not (isinstance(cfg.get("menu"), ast.Constant) and isinstance(cfg.get("prefix"), ast.Constant)):
            continue

        bawaan = []
        if isinstance(cfg.get("indikator_bawaan"), ast.List):
            for el in cfg["indikator_bawaan"].elts:
                if not isinstance(el, ast.Dict):
                    continue
                kv = {
                    k.value: v.value for k, v in zip(el.keys, el.values)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                }
                if "nama" in kv and "tabel" in kv:
                    bawaan.append((kv["nama"], kv["tabel"]))
        return cfg["menu"].value, cfg["prefix"].value, bawaan
    return None


@st.cache_data(ttl=60, show_spinner=False)
def _indikator_dari_database():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        return (
            sb.table("statistik_variabel")
            .select("id,nama_indikator,menu_variabel,nama_tabel_lama")
            .execute().data
            or []
        )
    except Exception:
        return []


def daftar_indikator():
    """Semua indikator beserta halaman tujuannya (aturan penggabungan sama dengan statistik_menu.py)."""
    baris_db = _indikator_dari_database()
    hasil = []

    for halaman, file in HALAMAN_INDIKATOR:
        info = _baca_halaman_indikator(file)
        if not info:
            continue
        menu, prefix, bawaan = info
        milik_menu = [r for r in baris_db if r.get("menu_variabel") == menu]
        per_tabel = {r["nama_tabel_lama"]: r for r in milik_menu if r.get("nama_tabel_lama")}

        dipakai = set()
        for nama, tabel in bawaan:
            dipakai.add(tabel)
            r = per_tabel.get(tabel) or {}
            hasil.append({
                "nama": r.get("nama_indikator") or nama, "menu": menu, "halaman": halaman,
                "prefix": prefix, "kunci": f"t_{tabel}",
            })

        for r in milik_menu:
            if r.get("nama_tabel_lama") in dipakai:
                continue
            hasil.append({
                "nama": r.get("nama_indikator") or "", "menu": menu, "halaman": halaman,
                "prefix": prefix, "kunci": r["id"],
            })
    return hasil


# ============================================================
# FUNGSI PANEL PENCARIAN
# ============================================================

def panel_pencarian(prefix):

    q = st.text_input(
        "Cari halaman atau indikator",
        placeholder="mis. miskin, amh, rumah",
        key=f"{prefix}_q"
    ).strip().lower()

    if not q:
        st.caption("Ketik kata kunci lalu tekan Enter.")
        return

    kata_dicari = q.split()

    # Indikator: semua kata harus ada pada nama indikator atau nama menunya
    cocok_indikator = [
        i for i in daftar_indikator()
        if all(k in f"{i['nama']} {i['menu']}".lower() for k in kata_dicari)
    ]

    # Halaman: salah satu kata cocok dengan nama atau kata kunci halaman
    cocok = []

    for nama, (halaman, kata_kunci) in HALAMAN_CARI.items():

        teks = f"{nama.lower()} {kata_kunci}"

        if any(k in teks for k in kata_dicari):
            cocok.append((nama, halaman))

    if cocok_indikator:

        st.caption("Indikator yang cocok:")

        for i in cocok_indikator[:MAKS_HASIL_INDIKATOR]:
            label = f"{i['nama']} · {i['menu']}".replace("*", "\\*").replace("_", "\\_")
            if st.button(
                label,
                key=f"{prefix}_ind_{i['prefix']}_{i['kunci']}",
                width="stretch"
            ):
                # Pilih indikator ini di dropdown halaman tujuan, lalu pindah halaman
                st.session_state[f"indikator_{i['prefix']}"] = i["kunci"]
                st.switch_page(i["halaman"])

        sisa = len(cocok_indikator) - MAKS_HASIL_INDIKATOR
        if sisa > 0:
            st.caption(f"…dan {sisa} indikator lain. Perpanjang kata kunci untuk menyempitkan.")

    if cocok:

        st.caption("Halaman yang cocok:")

        for nama, halaman in cocok:
            st.page_link(halaman, label=nama)

    if not cocok_indikator and not cocok:

        st.caption(
            "Tidak ada halaman atau indikator yang cocok. "
            "Coba kata lain, misalnya: miskin, sekolah, rumah."
        )


# ============================================================
# FUNGSI PANEL PANDUAN
# ============================================================

def panel_panduan(prefix):

    # Penanda agar popover panduan dilebarkan oleh CSS
    st.markdown(
        '<div class="panduan-lebar"></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        """
**Panduan Singkat SISTA**

1. **Beranda**: pengantar dan jalan pintas.
2. **Dashboard**: ringkasan visual indikator utama.
3. **Statistik Sosial**: pilih bidang, lalu atur tahun dan wilayah.
4. **Dokumen**: baca dan unduh dokumen.
5. **Pencarian**: cari halaman dengan kata kunci.
6. **Login Admin**: khusus petugas pengelola data.

Panduan lengkap dapat diunduh di bawah ini.
        """
    )

    if os.path.exists(PANDUAN_FILE):

        with open(PANDUAN_FILE, "rb") as f:

            st.download_button(
                "Unduh Panduan",
                data=f.read(),
                file_name=PANDUAN_FILE,
                mime="application/pdf",
                icon=":material/download:",
                key=f"{prefix}_unduh",
                use_container_width=True
            )

    else:

        st.caption("File panduan belum tersedia.")


# ============================================================
# FUNGSI DAFTAR LINK STATISTIK SOSIAL
# ============================================================

def link_statistik_sosial():

    st.page_link(
        kemiskinan,
        label="Kemiskinan",
        icon=":material/payments:"
    )

    st.page_link(
        ketenagakerjaan,
        label="Ketenagakerjaan",
        icon=":material/work:"
    )

    st.page_link(
        pendidikan,
        label="Pendidikan",
        icon=":material/school:"
    )

    st.page_link(
        penduduk,
        label="Kependudukan",
        icon=":material/groups:"
    )

    st.page_link(
        pengeluaran,
        label="Pengeluaran Makanan",
        icon=":material/restaurant:"
    )

    st.page_link(
        perumahan,
        label="Perumahan",
        icon=":material/home:"
    )

    st.page_link(
        statistik_lainnya,
        label="Lainnya",
        icon=":material/category:"
    )


# ============================================================
# HEADER STICKY
# ============================================================
header_container = st.container(key="sista_sticky_header")

with header_container:
    header_logo, header_menu, header_login = st.columns(
        [2.0, 5.0, 0.7],
        vertical_alignment="center"
    )

    # ========================================================
    # LOGO BPS
    # ========================================================
    with header_logo:
        logo_col, text_col = st.columns(
            [0.5, 2.2],
            vertical_alignment="center"
        )
        with logo_col:

            st.image(
                "logo_bps.png",
                width=48
            )

        with text_col:

            st.markdown(
                """
                <div class="bps-name">
                    BADAN PUSAT STATISTIK
                </div>

                <div class="bps-province">
                    PROVINSI LAMPUNG
                </div>
                """,
                unsafe_allow_html=True
            )

    # ========================================================
    # MENU NAVBAR
    # ========================================================
    with header_menu:
        menu1, menu2, menu3, menu4, menu5, menu6 = st.columns(
            [0.8, 0.8, 1.15, 1.15, 0.65, 0.65],
            vertical_alignment="center"
        )

        # ====================================================
        # BERANDA
        # ====================================================
        with menu1:

            if pg == home:
                with st.container(key="beranda_aktif"):
                    st.page_link(
                        home,
                        label="Beranda",
                        icon=":material/home:"
                    )
            else:
                with st.container(key="beranda_normal"):
                    st.page_link(
                        home,
                        label="Beranda",
                        icon=":material/home:"
                    )

        # ====================================================
        # DASHBOARD
        # ====================================================
        with menu2:

            if pg == dashboard:
                with st.container(key="dashboard_aktif"):
                    st.page_link(
                        dashboard,
                        label="Dashboard",
                        icon=":material/dashboard:"
                    )
            else:
                with st.container(key="dashboard_normal"):
                    st.page_link(
                        dashboard,
                        label="Dashboard",
                        icon=":material/dashboard:"
                    )

        # ====================================================
        # STATISTIK SOSIAL
        # ====================================================
        with menu3:

            container_key = (
                "statistik_sosial_aktif"
                if statistik_sosial_aktif
                else "statistik_sosial_normal"
            )

            with st.container(key=container_key):

                with st.popover(
                    "Statistik Sosial",
                    use_container_width=True
                ):
                    link_statistik_sosial()

        # ====================================================
        # DOKUMEN
        # ====================================================
        with menu4:

            if pg == dokumen:
                with st.container(key="dokumen_aktif"):
                    st.page_link(
                        dokumen,
                        label="Dokumen",
                        icon=":material/description:"
                    )
            else:
                with st.container(key="dokumen_normal"):
                    st.page_link(
                        dokumen,
                        label="Dokumen",
                        icon=":material/description:"
                    )

        # ====================================================
        # PENCARIAN
        # ====================================================
        with menu5:

            with st.popover(
                "🔎Pencarian",
                use_container_width=True,
                key="desktop_search_button"
            ):
                panel_pencarian("desktop_search")

        # ====================================================
        # PANDUAN (menggantikan tombol lokasi)
        # key "desktop_location_button" sengaja dipertahankan
        # agar CSS ukuran & gaya yang lama tetap berlaku.
        # ====================================================
        with menu6:

            with st.popover(
                "📖Panduan",
                use_container_width=True,
                key="desktop_location_button"
            ):
                panel_panduan("desktop_panduan")

    # ========================================================
    # AKSI HEADER / LOGIN
    # ========================================================

    with header_login:

        with st.container(
            key="mobile_header_actions",
            horizontal=True,
            horizontal_alignment="right",
            vertical_alignment="center",
            gap="small"
        ):

            # ------------------------------------------------
            # PENCARIAN MOBILE
            # ------------------------------------------------

            with st.popover(
                "Cari",
                icon=":material/search:",
                key="mobile_search_button",
                help="Cari halaman",
                use_container_width=True
            ):
                panel_pencarian("mobile_search")

            # ------------------------------------------------
            # TOMBOL MENU MOBILE
            # ------------------------------------------------

            if st.button(
                "Menu",
                icon=":material/menu:",
                key="mobile_menu_open",
                help="Buka navigasi",
                use_container_width=True
            ):

                st.session_state["mobile_nav_open"] = True
                st.rerun()

        # ----------------------------------------------------
        # LOGIN / LOGOUT ADMIN
        # ----------------------------------------------------

        if st.session_state["is_admin"]:

            if st.button(
                "Logout",
                key="header_logout",
                use_container_width=True
            ):

                st.session_state["is_admin"] = False
                st.rerun()

        else:

            if st.button(
                "Login Admin",
                key="header_login_button",
                type="primary",
                use_container_width=True
            ):

                login_dialog()


# ============================================================
# FUNGSI NAVIGASI MOBILE
# ============================================================

def mobile_navigation_button(
    label,
    page,
    icon,
    key
):

    is_active = pg == page

    container_key = (
        f"mobile_nav_item_{key}_active"
        if is_active
        else f"mobile_nav_item_{key}"
    )

    with st.container(
        key=container_key
    ):

        if st.button(
            label,
            icon=icon,
            key=f"mobile_go_{key}",
            type="tertiary",
            use_container_width=True
        ):

            st.session_state["mobile_nav_open"] = False
            st.switch_page(page)

# ============================================================
# NAVIGASI DRAWER MOBILE
# ============================================================

if st.session_state["mobile_nav_open"]:

    with st.container(key="mobile_nav_overlay"):

        with st.container(key="mobile_nav_drawer"):

            drawer_title, drawer_close = st.columns(
                [5, 1],
                vertical_alignment="center"
            )

            # ------------------------------------------------
            # JUDUL DRAWER
            # ------------------------------------------------
            with drawer_title:

                st.markdown(
                    """
                    <div class="mobile-drawer-brand">
                        <div class="mobile-drawer-brand-name">
                            SISTA
                        </div>
                        <div class="mobile-drawer-brand-subtitle">
                            BPS Provinsi Lampung
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # ------------------------------------------------
            # TOMBOL TUTUP
            # ------------------------------------------------

            with drawer_close:

                if st.button(
                    "Tutup",
                    icon=":material/close:",
                    key="mobile_menu_close",
                    help="Tutup navigasi",
                    use_container_width=True
                ):

                    st.session_state["mobile_nav_open"] = False
                    st.rerun()


            # ------------------------------------------------
            # LABEL NAVIGASI
            # ------------------------------------------------
            st.markdown(
                '<div class="mobile-nav-label">Navigasi</div>',
                unsafe_allow_html=True
            )

            # ------------------------------------------------
            # BERANDA
            # ------------------------------------------------
            mobile_navigation_button(
                "Beranda",
                home,
                ":material/home:",
                "home"
            )

            # ------------------------------------------------
            # DASHBOARD
            # ------------------------------------------------
            mobile_navigation_button(
                "Dashboard",
                dashboard,
                ":material/dashboard:",
                "dashboard"
            )

            # ------------------------------------------------
            # DOKUMEN
            # ------------------------------------------------
            mobile_navigation_button(
                "Dokumen",
                dokumen,
                ":material/description:",
                "dokumen"
            )

            # ------------------------------------------------
            # STATISTIK SOSIAL MOBILE
            # ------------------------------------------------
            with st.expander(
                "Statistik Sosial",
                expanded=statistik_sosial_aktif,
                icon=":material/bar_chart:",
                key="mobile_stats_dropdown"
            ):

                mobile_navigation_button(
                    "Kemiskinan",
                    kemiskinan,
                    ":material/payments:",
                    "kemiskinan"
                )

                mobile_navigation_button(
                    "Ketenagakerjaan",
                    ketenagakerjaan,
                    ":material/work:",
                    "ketenagakerjaan"
                )

                mobile_navigation_button(
                    "Pendidikan",
                    pendidikan,
                    ":material/school:",
                    "pendidikan"
                )

                mobile_navigation_button(
                    "Kependudukan",
                    penduduk,
                    ":material/groups:",
                    "penduduk"
                )

                mobile_navigation_button(
                    "Pengeluaran Makanan",
                    pengeluaran,
                    ":material/restaurant:",
                    "pengeluaran"
                )

                mobile_navigation_button(
                    "Perumahan",
                    perumahan,
                    ":material/home:",
                    "perumahan"
                )

                mobile_navigation_button(
                    "Statistik Sosial Lainnya",
                    statistik_lainnya,
                    ":material/category:",
                    "statistik_sosial_lainnya"
                )


            # ------------------------------------------------
            # FOOTER DRAWER
            # ------------------------------------------------
            with st.container(key="mobile_nav_footer"):

                # --------------------------------------------
                # PANDUAN (menggantikan pilihan wilayah)
                # --------------------------------------------
                with st.expander(
                    "Panduan Penggunaan",
                    icon=":material/help:",
                    key="mobile_guide_dropdown"
                ):
                    panel_panduan("mobile_panduan")


                # --------------------------------------------
                # ADMIN MOBILE
                # --------------------------------------------
                if st.session_state["is_admin"]:

                    if st.button(
                        "Logout Admin",
                        icon=":material/logout:",
                        key="mobile_admin_logout",
                        type="primary",
                        use_container_width=True
                    ):

                        st.session_state["is_admin"] = False
                        st.session_state["mobile_nav_open"] = False
                        st.rerun()

                else:

                    if st.button(
                        "Login Admin",
                        icon=":material/login:",
                        key="mobile_admin_login",
                        type="primary",
                        use_container_width=True
                    ):

                        st.session_state["mobile_nav_open"] = False
                        st.session_state["mobile_login_requested"] = True
                        st.rerun()


# ============================================================
# LOGIN MOBILE
# ============================================================

if st.session_state.pop("mobile_login_requested", False):
    login_dialog()

# ============================================================
# JALANKAN HALAMAN
# ============================================================

pg.run()

@st.cache_data
def logo_base64():
    return base64.b64encode(Path("logo_bps.png").read_bytes()).decode()

st.html(f"""
<div class="sista-footer">
<div class="sf-kiri">
<p class="sf-judul">Dikompilasi oleh Tim Sosial BPS Provinsi Lampung</p>
<p>Produksi Video oleh Dhani Arief Hartanto</p>
<p class="sf-judul">Tim Penyusun</p>
<p>Febiyana Qomariyah, Ranggi Aditya Nugraha, Reny Andriati, Anisa Fitri</p>
<p class="sf-judul">Pengembang Website</p>
<p>Anisa Fitri</p>
</div>
<div class="sf-kanan">
<p>© 2026 Badan Pusat Statistik Provinsi Lampung</p>
<p>Sumber Data: Badan Pusat Statistik</p>
</div>
</div>
""")