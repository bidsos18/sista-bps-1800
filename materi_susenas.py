"""Pembelajaran Olah Susenas yang menempel pada indikator SISTA.

Di semua halaman indikator (Pendidikan, Kependudukan, Perumahan, Kemiskinan,
Ketenagakerjaan, Pengeluaran Makanan, Lainnya), tiap indikator punya dropdown
"Pembelajaran Olah Susenas" di bawah Metadata Indikator. Isinya video, materi
(PDF/tautan), dan sintaks yang ditautkan ke indikator itu. Bila belum ada,
dropdown tetap tampil dan menyatakan belum ada materi.

Dipanggil dari statistik_menu.py:
    tampilkan_pembelajaran(MENU, ind)   # dropdown di bawah metadata

Mode edit memakai login admin SISTA yang sudah ada (tombol "Edit" di kanan atas).
Data materi ada di project Supabase SISTA (tabel susenas_topik, susenas_materi,
bucket susenas). Bila ingin di project lain, isi secrets SUSENAS_SUPABASE_URL,
SUSENAS_SUPABASE_KEY, SUSENAS_SERVICE_ROLE_KEY.
"""

import re
import time
import uuid
import urllib.request

import streamlit as st
from supabase import create_client

BUCKET = "susenas"
T_TOPIK = "susenas_topik"
T_MATERI = "susenas_materi"
MAKS_MB = 25

JENIS = {
    "Video YouTube (link)": "video",
    "PDF materi (unggah file)": "pdf",
    "Sintaks .sps / .do / .R (unggah file)": "sintaks",
    "Tautan lain (link)": "tautan",
}
EKSTENSI = {"pdf": ["pdf"], "sintaks": ["sps", "do", "r", "txt"]}
BAHASA = {"sps": "SPSS", "do": "Stata", "r": "R", "txt": "Teks"}


def tampilkan_materi(menu):
    """Dipertahankan agar halaman versi lama tidak error. Tidak menampilkan apa pun."""
    return None


# ============================================================
# Koneksi
# ============================================================

def _kredensial():
    """(url, kunci baca, kunci admin). Project Susenas sendiri bila ada, kalau tidak project SISTA."""
    sec = st.secrets
    if "SUSENAS_SUPABASE_URL" in sec:
        return (
            sec["SUSENAS_SUPABASE_URL"],
            sec.get("SUSENAS_SUPABASE_KEY"),
            sec.get("SUSENAS_SERVICE_ROLE_KEY"),
        )
    return sec["SUPABASE_URL"], sec["SUPABASE_KEY"], sec.get("SUPABASE_SERVICE_ROLE_KEY")


@st.cache_resource
def _klien():
    url, kunci, _ = _kredensial()
    return create_client(url, kunci)


@st.cache_resource
def _klien_admin():
    url, _, kunci = _kredensial()
    return create_client(url, kunci) if kunci else None


def _mode_edit():
    return bool(st.session_state.get("is_admin")) and bool(
        st.session_state.get("show_admin_panel")
    )


@st.cache_data(ttl=120, show_spinner=False)
def _muat_indikator(menu, kunci):
    """Topik yang ditautkan ke indikator ini, beserta seluruh materinya."""
    sb = _klien()
    topik = (
        sb.table(T_TOPIK).select("*").eq("menu", menu).contains("indikator", [kunci])
        .order("urutan").order("created_at").execute().data
        or []
    )
    if not topik:
        return [], []
    materi = (
        sb.table(T_MATERI).select("*").in_("topik", [t["id"] for t in topik])
        .order("created_at").execute().data
        or []
    )
    return topik, materi


@st.cache_data(ttl=600, show_spinner=False)
def _teks(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SISTA"})
        mentah = urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        return "* File tidak ditemukan"
    for enc in ("utf-8", "cp1252"):
        try:
            return mentah.decode(enc)
        except UnicodeDecodeError:
            continue
    return mentah.decode("utf-8", errors="replace")


# ============================================================
# Pembantu kecil
# ============================================================

def _md(s):
    """Escape karakter markdown supaya judul seperti 'Indikator 1.4.2*' tampil apa adanya."""
    return re.sub(r"([\\`*_~$\[\]])", r"\\\1", str(s or ""))


def _id(prefix):
    return prefix + uuid.uuid4().hex[:12]


def _youtube(url):
    return bool(re.search(r"(?:v=|youtu\.be/|embed/)[\w-]{11}", str(url or "")))


def _unduh(url):
    url = str(url or "")
    return url + ("&download" if "?" in url else "?download")


def _info_file(path):
    nama = str(path or "").split("?")[0].split("/")[-1]
    nama = re.sub(r"^\d+-", "", nama)
    if "." in nama:
        dasar, ext = nama.rsplit(".", 1)
        return dasar, ext.upper()
    return nama, "TXT"


# ============================================================
# Operasi tulis (khusus admin). Mengembalikan teks error, atau None jika berhasil.
# ============================================================

def pastikan_topik(menu, kunci, nama):
    """Topik pertama yang tertaut ke indikator; dibuat bila belum ada. -> (id_topik, error)"""
    adm = _klien_admin()
    if adm is None:
        return None, "Koneksi admin belum tersedia. Periksa SUSENAS_SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY di Secrets."
    try:
        ada = (
            adm.table(T_TOPIK).select("id").eq("menu", menu)
            .contains("indikator", [kunci]).order("urutan").limit(1).execute().data
        )
        if ada:
            return ada[0]["id"], None
        akhir = (
            adm.table(T_TOPIK).select("urutan").eq("menu", menu)
            .order("urutan", desc=True).limit(1).execute().data
        )
        tid = _id("t")
        adm.table(T_TOPIK).insert({
            "id": tid, "menu": menu, "grup": None, "title": str(nama)[:300],
            "urutan": (akhir[0]["urutan"] if akhir else 0) + 1, "indikator": [kunci],
        }).execute()
    except Exception as e:
        return None, f"Gagal menyiapkan topik: {e}"
    return tid, None


def simpan_materi(topik_id, jenis, judul, deskripsi, link, berkas):
    judul = (judul or "").strip()
    if not judul:
        return "Judul wajib diisi."
    adm = _klien_admin()
    if adm is None:
        return "Koneksi admin belum tersedia. Periksa SUSENAS_SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY di Secrets."

    baris = {
        "id": _id("m"), "topik": topik_id, "type": jenis,
        "title": judul[:300], "deskripsi": (deskripsi or "").strip()[:500] or None,
    }
    path = None

    if jenis in ("video", "tautan"):
        link = (link or "").strip()
        if not re.match(r"^https?://", link, re.I):
            return "Link harus diawali http:// atau https://"
        baris["url"] = link
    else:
        if berkas is None:
            return "Pilih file dulu."
        data = berkas.getvalue()
        ext = berkas.name.rsplit(".", 1)[-1].lower() if "." in berkas.name else ""
        if ext not in EKSTENSI[jenis]:
            return "Hanya file ." + ", .".join(EKSTENSI[jenis]) + "."
        if not data:
            return "File kosong."
        if len(data) > MAKS_MB * 1024 * 1024:
            return f"Ukuran terlalu besar (maks {MAKS_MB} MB)."
        if ext == "pdf" and data[:4] != b"%PDF":
            return "File ini bukan PDF yang valid."
        slug = re.sub(r"[^a-z0-9]+", "-", berkas.name.rsplit(".", 1)[0].lower()).strip("-")[:60] or "file"
        path = f"{int(time.time() * 1000)}-{slug}.{ext}"
        mime = "application/pdf" if ext == "pdf" else "text/plain"
        try:
            adm.storage.from_(BUCKET).upload(path, data, {"content-type": mime})
            url = adm.storage.from_(BUCKET).get_public_url(path)
        except Exception as e:
            return f"Gagal mengunggah file: {e}"
        baris["path"] = path
        if jenis == "pdf":
            baris["url"] = url
        else:
            baris["file"] = url
            baris["lang"] = BAHASA.get(ext, "Teks")

    try:
        adm.table(T_MATERI).insert(baris).execute()
    except Exception as e:
        if path:
            try:
                adm.storage.from_(BUCKET).remove([path])
            except Exception:
                pass
        return f"Gagal menyimpan materi: {e}"
    _muat_indikator.clear()
    return None


def hapus(jenis, id_, paths):
    """jenis: 'topik' atau 'materi'. paths: file di storage yang ikut dihapus."""
    adm = _klien_admin()
    if adm is None:
        return "Koneksi admin belum tersedia."
    tabel = T_TOPIK if jenis == "topik" else T_MATERI
    try:
        adm.table(tabel).delete().eq("id", id_).execute()
        if paths:
            adm.storage.from_(BUCKET).remove(paths)
    except Exception as e:
        return f"Gagal menghapus: {e}"
    _muat_indikator.clear()
    return None


# ============================================================
# Dialog (form tambah dan konfirmasi hapus)
# ============================================================

@st.dialog("Tambah materi", width="large")
def _dlg_materi(menu, kunci, nama, topik_id):
    st.caption(f"Indikator: {nama}")
    jenis = JENIS[st.selectbox("Jenis", list(JENIS))]
    judul = st.text_input(
        "Judul", value="Video tutorial" if jenis == "video" else "",
        max_chars=300, key=f"sus_dj_{jenis}",
    )
    desk = st.text_input("Keterangan (opsional)", max_chars=500)
    link, berkas = "", None
    if jenis in ("pdf", "sintaks"):
        berkas = st.file_uploader(f"File (maks {MAKS_MB} MB)", type=EKSTENSI[jenis])
    else:
        link = st.text_input("Link", placeholder="https://youtu.be/...")
    if st.button("Simpan", type="primary", width="stretch"):
        tid = topik_id
        if tid is None:
            tid, err = pastikan_topik(menu, kunci, nama)
            if err:
                st.error(err)
                return
        err = simpan_materi(tid, jenis, judul, desk, link, berkas)
        if err:
            st.error(err)
        else:
            st.rerun()


@st.dialog("Konfirmasi hapus")
def _dlg_hapus(jenis, id_, nama, paths):
    st.write(f"Hapus {jenis} **{_md(nama)}**?")
    ya, batal = st.columns(2)
    if ya.button("Ya, hapus", type="primary", width="stretch"):
        err = hapus(jenis, id_, paths)
        if err:
            st.error(err)
        else:
            st.rerun()
    if batal.button("Batal", width="stretch"):
        st.rerun()


# ============================================================
# Tampilan dropdown di bawah metadata
# ============================================================

def _tombol_hapus(item, kunci):
    if st.button("Hapus", key=f"sus_del_{kunci}_{item['id']}", width="stretch"):
        _dlg_hapus("materi", item["id"], item["title"], [item["path"]] if item.get("path") else [])


def _kepala(item, kunci, edit, tag):
    if edit:
        kiri, kanan = st.columns([4, 1], vertical_alignment="center")
    else:
        kiri, kanan = st.container(), None
    with kiri:
        st.markdown(f":orange-badge[{tag}] **{_md(item['title'])}**")
        if item.get("deskripsi"):
            st.caption(_md(item["deskripsi"]))
    if kanan is not None:
        with kanan:
            _tombol_hapus(item, kunci)


def _kartu_video(item, kunci, edit):
    with st.container(border=True):
        _kepala(item, kunci, edit, "Video")
        if _youtube(item["url"]):
            st.video(item["url"])
        else:
            st.link_button("Buka video", item["url"], width="stretch")


def _kartu_materi(item, kunci, edit):
    with st.container(border=True):
        pdf = item["type"] == "pdf"
        _kepala(item, kunci, edit, "PDF" if pdf else "Tautan")
        st.link_button("Buka PDF" if pdf else "Buka", item["url"], type="primary")


def _kartu_sintaks(item, kunci, edit):
    nama, ext = _info_file(item["file"])
    with st.container(border=True):
        _kepala(item, kunci, edit, "Sintaks")
        st.caption(f"📄 {nama}.{ext}")
        buka, unduh, _ = st.columns([2, 2, 6])
        tampil = buka.toggle("Lihat isi", key=f"sus_buka_{kunci}_{item['id']}")
        unduh.link_button("Unduh", _unduh(item["file"]))
        if tampil:
            st.code(_teks(item["file"]), language="r" if ext == "R" else None, line_numbers=False)


def tampilkan_pembelajaran(menu_variabel, ind):
    """Dropdown 'Pembelajaran Olah Susenas' untuk satu indikator, di menu mana pun.

    Selalu tampil; bila belum ada materi isinya pesan kosong, dan admin (mode Edit) bisa menambah.
    """
    menu = str(menu_variabel or "").strip().lower()
    if not menu or not ind:
        return
    kunci = str(ind.get("kunci"))
    nama = ind.get("nama_indikator") or kunci

    try:
        topik, materi = _muat_indikator(menu, kunci)
    except Exception as e:
        if st.session_state.get("is_admin"):
            st.warning(
                "Pembelajaran Susenas belum dapat dimuat. Pastikan susenas_schema.sql "
                "(termasuk kolom indikator) sudah dijalankan di Supabase."
            )
            with st.expander("Detail teknis"):
                st.code(str(e))
        return

    edit = _mode_edit()
    if edit and _klien_admin() is None:
        st.error("Mode edit materi butuh kunci admin (SUSENAS_SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY) di Secrets.")
        edit = False
    ada = [
        lbl for lbl, ok in (
            ("🎬 Video", any(i["type"] == "video" for i in materi)),
            ("📄 Materi", any(i["type"] in ("pdf", "tautan") for i in materi)),
            ("💻 Sintaks", any(i["type"] == "sintaks" for i in materi)),
        ) if ok
    ]
    label = "🎓 Pembelajaran Olah Susenas" + (f"  ·  {'  '.join(ada)}" if ada else "")

    with st.expander(label, expanded=edit):
        if edit:
            if st.button(
                "➕ Tambah video / PDF / sintaks", key=f"sus_add_{kunci}", type="primary",
            ):
                _dlg_materi(menu, kunci, nama, topik[0]["id"] if topik else None)
        if not materi:
            st.caption("Belum ada materi untuk indikator ini.")
            return

        video = [i for i in materi if i["type"] == "video"]
        for n in range(0, len(video), 2):
            for kol, it in zip(st.columns(2), video[n:n + 2]):
                with kol:
                    _kartu_video(it, kunci, edit)
        for it in (i for i in materi if i["type"] in ("pdf", "tautan")):
            _kartu_materi(it, kunci, edit)
        for it in (i for i in materi if i["type"] == "sintaks"):
            _kartu_sintaks(it, kunci, edit)
