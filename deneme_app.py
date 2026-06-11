# -*- coding: utf-8 -*-
"""Beşiktaş-Üsküdar Vapur Hattı — Yönetici Dashboard (Tek Dosya)."""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import time as dt_time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# Veri Yükleme ve Temel İşlemler
# =============================================================================

PROJE_KOK = Path(__file__).resolve().parent
DATA_DIR = PROJE_KOK / "data"

def _excel_yolu() -> Path:
    adaylar = [
        DATA_DIR / "veri.xlsx",
        DATA_DIR / "MUDUR_BEY_GOREV.xlsx",
        DATA_DIR / "MÜDÜR BEY GÖREV.xlsx",
    ]
    for p in adaylar:
        if p.exists():
            return p
    raise FileNotFoundError("Excel dosyası bulunamadı. 'data' klasörüne veri.xlsx koyun.")

INPUT = _excel_yolu()

YON_USK_BES = "ÜSKÜDAR → BEŞİKTAŞ"
YON_BES_USK = "BEŞİKTAŞ → ÜSKÜDAR"

YON_ETIKET = {
    YON_BES_USK: "Beşiktaş → Üsküdar",
    YON_USK_BES: "Üsküdar → Beşiktaş",
}

@dataclass
class TahminSonucu:
    yon: str
    hedef_saat: str
    tahmini_yolcu: int
    alt_sinir: int
    ust_sinir: int
    guven_yuzde: int
    aciklama: str
    yontem: str
    mevcut_saat_talep: int
    onerilen_sefer_sayisi: int

def load_data(path: Path | None = None) -> pd.DataFrame:
    path = path or INPUT
    xls = pd.ExcelFile(path)
    if "Sayfa2" not in xls.sheet_names:
        raise ValueError("Excel'de 'Sayfa2' sayfası bulunamadı.")
    df = pd.read_excel(path, sheet_name="Sayfa2")
    if df.empty:
        raise ValueError("Excel 'Sayfa2' sayfası boş.")
    df.columns = [str(c).strip() for c in df.columns]

    rename = {
        "yön": "yon",
        "anonim_kart_no": "kart_no",
        "saat_2.sıra": "saat_vapur",
        "saat_1.sıra": "saat_onceki",
        "onceki_hat_adi_ok_1.sıra": "onceki_hat",
        "sonraki_hat_adi_ok_3.sıra": "sonraki_hat",
        "onceki_operator_adi": "onceki_operator",
        "onceki_operator_grubu": "onceki_operator_grubu",
        "kart_tipi": "kart_tipi",
        "BEKLEME SAATİ": "bekleme_suresi",
        "merkez_trn_ts": "islem_zamani",
        "merkez_hat_adi": "vapur_hatti",
        "merkez_aktarma_no": "aktarma_sayisi",
        "onceki_aktarma_no": "onceki_aktarma",
    }
    for old, new in rename.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    if "islem_zamani" not in df.columns:
        warnings.warn("'islem_zamani' yok, varsayılan 00:00 atanıyor.")
        df["islem_zamani"] = pd.NaT
    df["islem_zamani"] = pd.to_datetime(df["islem_zamani"], format="mixed", errors="coerce")
    df["tarih"] = df["islem_zamani"].dt.date
    df["saat"] = df["islem_zamani"].dt.hour.fillna(0).astype(int)
    df["dakika"] = df["islem_zamani"].dt.minute.fillna(0).astype(int)
    df["dakika_toplam"] = df["saat"] * 60 + df["dakika"]
    df["saat_dakika"] = df["islem_zamani"].dt.strftime("%H:%M")

    if "yon" not in df.columns:
        raise KeyError("Excel'de 'yön' (veya 'yön') sütunu bulunamadı.")
    df["yon_etiket"] = df["yon"].map(YON_ETIKET)

    if "kart_no" not in df.columns:
        warnings.warn("'kart_no' yok, satır numarası kullanılıyor.")
        df["kart_no"] = range(len(df))

    for col in ("onceki_hat", "sonraki_hat"):
        if col in df.columns:
            df[col] = df[col].fillna("BİLİNMİYOR").astype(str).str.strip().replace({"": "BİLİNMİYOR", "nan": "BİLİNMİYOR"})
        else:
            df[col] = "BİLİNMİYOR"

    if "kart_tipi" in df.columns:
        df["kart_tipi"] = df["kart_tipi"].fillna("Belirtilmemiş").astype(str).str.strip().replace({"": "Belirtilmemiş", "nan": "Belirtilmemiş", "boş": "Belirtilmemiş"})
    else:
        df["kart_tipi"] = "Belirtilmemiş"

    if "bekleme_suresi" in df.columns:
        def _bekleme_dakika(val) -> float:
            if pd.isna(val):
                return np.nan
            if isinstance(val, dt_time):
                return val.hour * 60 + val.minute + val.second / 60
            td = pd.to_timedelta(val, errors="coerce")
            if pd.notna(td):
                return td.total_seconds() / 60
            s = str(val).strip()
            if not s or s.lower() in ("nan", "nat"):
                return np.nan
            parts = s.split(":")
            if len(parts) >= 2:
                try:
                    h, m = int(parts[0]), int(parts[1])
                    sec = int(float(parts[2])) if len(parts) > 2 else 0
                    return h * 60 + m + sec / 60
                except ValueError:
                    return np.nan
            return np.nan
        df["bekleme_dk"] = df["bekleme_suresi"].apply(_bekleme_dakika)
    else:
        df["bekleme_dk"] = 0.0

    if "onceki_aktarma" in df.columns:
        df["onceki_aktarma"] = pd.to_numeric(df["onceki_aktarma"], errors="coerce").fillna(0).astype(int)
    else:
        df["onceki_aktarma"] = 0

    return df

# ---------- Analiz Fonksiyonları ----------
def veri_ozeti(df: pd.DataFrame) -> dict:
    gun_sayisi = df["tarih"].nunique()
    tarihler = sorted(df["tarih"].dropna().unique())
    return {
        "toplam_kayit": len(df),
        "gun_sayisi": gun_sayisi,
        "tarih_baslangic": str(tarihler[0]) if tarihler else "-",
        "tarih_bitis": str(tarihler[-1]) if tarihler else "-",
        "bes_usk": int((df["yon"] == YON_BES_USK).sum()),
        "usk_bes": int((df["yon"] == YON_USK_BES).sum()),
    }

def saatlik_seri(df: pd.DataFrame, yon: str) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    if sub.empty:
        h = pd.DataFrame({"saat": range(24), "yolcu": 0})
        h["yon"] = YON_ETIKET.get(yon, yon)
        h["yuzde"] = 0.0
        return h
    h = sub.groupby("saat").size().reindex(range(24), fill_value=0).reset_index(name="yolcu")
    h["yon"] = YON_ETIKET.get(yon, yon)
    h["yuzde"] = (h["yolcu"] / h["yolcu"].sum() * 100).round(1)
    return h

def onbes_dakika_seri(df: pd.DataFrame, yon: str) -> pd.DataFrame:
    sub = df[df["yon"] == yon].copy()
    if sub.empty:
        return pd.DataFrame(columns=["dilim", "yolcu", "saat_etiket", "saat"])
    sub["dilim"] = (sub["dakika_toplam"] // 15) * 15
    seri = sub.groupby("dilim").size().reset_index(name="yolcu")
    seri["saat_etiket"] = seri["dilim"].apply(lambda x: f"{x // 60:02d}:{x % 60:02d}")
    seri["saat"] = seri["dilim"] // 60
    return seri

def kaynak_hatlar(df: pd.DataFrame, yon: str, top_n: int = 15) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    if sub.empty:
        return pd.DataFrame(columns=["onceki_hat", "yolcu", "yuzde"])
    t = sub.groupby("onceki_hat").size().sort_values(ascending=False).reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t.head(top_n)

def guvenilirlik_raporu(df: pd.DataFrame) -> pd.DataFrame:
    ozet = veri_ozeti(df)
    gun = ozet["gun_sayisi"]
    n = ozet["toplam_kayit"]
    maddeler = [
        ("Örneklem büyüklüğü", f"{n:,} kayıt", "Güçlü", "19 binden fazla gözlem; tanımlayıcı istatistikler güvenilir."),
        ("Veri süresi", f"{gun} gün ({ozet['tarih_baslangic']})", "Sınırlı" if gun <= 1 else "Orta",
         "Tek günlük veri: günlük/haftalık mevsimsellik yakalanamaz."),
        ("Tanımlayıcı analiz", "Kaynak hat, saat dağılımı", "Güvenilir",
         "Kim nereden geliyor, hangi saatte yoğunluk var — net cevaplanabilir."),
        ("Zaman serisi tahmini", "Saatlik / 15 dk desen", "Orta güven",
         "Tek gün verisiyle desen çıkarılır; %95 güven aralığı Poisson dağılımına dayanır."),
        ("Sefer ekleme tahmini", "Saat X'e sefer koyarsak kaç yolcu?", "Orta güven",
         "Mevcut saat talebi ÷ önerilen sefer sayısı mantığı; hava, tatil, etkinlik etkiler."),
        ("Öneri", "Karar desteği", "Kullanılabilir",
         "Yönetici özeti 'yaklaşık X yolcu, %95 ihtimalle Y–Z arası' şeklinde sunulmalı."),
    ]
    return pd.DataFrame(maddeler, columns=["Kriter", "Durum", "Güven Seviyesi", "Açıklama"])

def tahmin_sefer_yolcu(df, yon, hedef_saat, hedef_dakika=0, pencere_dk=15):
    sub = df[df["yon"] == yon].copy()
    hedef_dk = hedef_saat * 60 + hedef_dakika
    alt = hedef_dk - pencere_dk
    ust = hedef_dk + pencere_dk
    pencere = sub[(sub["dakika_toplam"] >= alt) & (sub["dakika_toplam"] <= ust)]
    saat_talep = int(sub[sub["saat"] == hedef_saat].shape[0])
    ayni_saat = sub[sub["saat"] == hedef_saat]
    mevcut_sefer = max(ayni_saat["dakika_toplam"].nunique() // 5, 1)
    if saat_talep == 0:
        mevcut_sefer = 1
    pencere_yolcu = len(pencere)
    if pencere_yolcu > 0:
        tahmin = max(1, round(pencere_yolcu / max(mevcut_sefer, 1)))
    else:
        komsu = sub[sub["saat"].between(max(0, hedef_saat - 1), min(23, hedef_saat + 1))]
        tahmin = max(1, round(len(komsu) / (3 * max(mevcut_sefer, 1))))
    lam = max(pencere_yolcu / max(mevcut_sefer, 1), tahmin * 0.7)
    alt_sinir = max(0, int(lam - 1.96 * np.sqrt(lam)))
    ust_sinir = int(lam + 1.96 * np.sqrt(lam)) + 1
    yogunluk = "yüksek" if saat_talep >= sub.groupby("saat").size().quantile(0.75) else "orta" if saat_talep >= sub.groupby("saat").size().median() else "düşük"
    onerilen = 4 if yogunluk == "yüksek" else 3 if yogunluk == "orta" else 2
    saat_str = f"{hedef_saat:02d}:{hedef_dakika:02d}"
    yon_adi = YON_ETIKET.get(yon, yon)
    aciklama = (
        f"Saat {saat_str}'de {yon_adi} yönünde yaklaşık **{tahmin} yolcu** biner. "
        f"%95 güvenle **{alt_sinir}–{ust_sinir}** aralığında beklenir. "
        f"Bu saatte toplam talep {saat_talep} yolcu; yoğunluk seviyesi: {yogunluk}."
    )
    return TahminSonucu(
        yon=yon_adi, hedef_saat=saat_str, tahmini_yolcu=tahmin,
        alt_sinir=alt_sinir, ust_sinir=ust_sinir, guven_yuzde=95,
        aciklama=aciklama,
        yontem="15 dk pencere + saatlik talep / mevcut sefer yoğunluğu (Poisson CI)",
        mevcut_saat_talep=saat_talep, onerilen_sefer_sayisi=onerilen,
    )

def karar_ozet_cumlesi(df, yon, saat, dakika=0):
    t = tahmin_sefer_yolcu(df, yon, saat, dakika)
    yon_kisa = "Beşiktaş'tan Üsküdar'a" if yon == YON_BES_USK else "Üsküdar'dan Beşiktaş'a"
    return (
        f"Saat {t.hedef_saat} itibarıyla {yon_kisa} yönünde ek sefer planlanması halinde "
        f"yaklaşık {t.tahmini_yolcu} yolcu biner (%95 güven: {t.alt_sinir}–{t.ust_sinir}). "
        f"İlgili saatte saatlik toplam yolcu sayısı {t.mevcut_saat_talep}."
    )

def zaman_serisi_ozet(df, yon):
    seri = onbes_dakika_seri(df, yon)
    if seri.empty:
        return seri
    seri["hareketli_ort"] = seri["yolcu"].rolling(4, min_periods=1, center=True).mean().round(1)
    seri["yon"] = YON_ETIKET.get(yon, yon)
    return seri

def tarife_onerisi(df):
    rows = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        h = saatlik_seri(df, yon)
        if h["yolcu"].sum() == 0:
            continue
        ort = h["yolcu"].mean()
        for _, row in h.iterrows():
            saat = int(row["saat"])
            talep = int(row["yolcu"])
            katsayi = talep / ort if ort > 0 else 0
            if katsayi >= 1.5:
                frekans, sefer = "10-15 dk", 4
            elif katsayi >= 1.0:
                frekans, sefer = "20 dk", 3
            elif katsayi >= 0.5:
                frekans, sefer = "30 dk", 2
            else:
                frekans, sefer = "45-60 dk", 1
            rows.append({
                "yon": YON_ETIKET[yon],
                "saat": f"{saat:02d}:00",
                "saat_int": saat,
                "talep": talep,
                "talep_katsayisi": round(katsayi, 2),
                "onerilen_frekans": frekans,
                "saatte_sefer": sefer,
                "sefer_basina_yolcu": max(1, round(talep / sefer)),
            })
    return pd.DataFrame(rows)

def _filtre_yon(df, yon=None):
    return df if yon is None else df[df["yon"] == yon]

def bekleme_analizi(df, yon=None):
    sub = _filtre_yon(df, yon)
    if "bekleme_dk" not in sub.columns or sub["bekleme_dk"].isna().all():
        return {"ortalama_dk": 0, "medyan_dk": 0, "uzun_bekleme_yuzde": 0, "cok_uzun_yuzde": 0,
                "saatlik": pd.DataFrame(), "toplam": 0}
    sub = sub.dropna(subset=["bekleme_dk"])
    sub = sub[sub["bekleme_dk"] >= 0]
    if sub.empty:
        return {"ortalama_dk": 0, "medyan_dk": 0, "uzun_bekleme_yuzde": 0, "cok_uzun_yuzde": 0,
                "saatlik": pd.DataFrame(), "toplam": 0}
    saatlik = sub.groupby("saat")["bekleme_dk"].agg(ortalama="mean", medyan="median", yolcu="count").reset_index().round(1)
    uzun = (sub["bekleme_dk"] >= 15).mean() * 100
    return {
        "ortalama_dk": round(sub["bekleme_dk"].mean(), 1),
        "medyan_dk": round(sub["bekleme_dk"].median(), 1),
        "uzun_bekleme_yuzde": round(uzun, 1),
        "cok_uzun_yuzde": round((sub["bekleme_dk"] >= 30).mean() * 100, 1),
        "saatlik": saatlik,
        "toplam": len(sub),
    }

def koridor_rotalari(df, yon, top_n=15):
    sub = df[df["yon"] == yon]
    if sub.empty:
        return pd.DataFrame(columns=["onceki_hat", "sonraki_hat", "yolcu", "koridor", "yuzde"])
    t = sub.groupby(["onceki_hat", "sonraki_hat"]).size().sort_values(ascending=False).reset_index(name="yolcu")
    t["koridor"] = t["onceki_hat"] + " → Vapur → " + t["sonraki_hat"]
    t["yuzde"] = (t["yolcu"] / len(sub) * 100).round(1)
    return t.head(top_n)

def kart_tipi_dagilimi(df, yon=None):
    sub = _filtre_yon(df, yon)
    if sub.empty:
        return pd.DataFrame(columns=["kart_tipi", "yolcu", "yuzde"])
    t = sub.groupby("kart_tipi").size().sort_values(ascending=False).reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t

def kart_tipi_saatlik(df, yon, top_tipler=5):
    sub = df[df["yon"] == yon]
    if sub.empty:
        return pd.DataFrame(columns=["saat", "kart_tipi", "yolcu"])
    top = kart_tipi_dagilimi(sub).head(top_tipler)["kart_tipi"].tolist()
    sub = sub[sub["kart_tipi"].isin(top)]
    return sub.groupby(["saat", "kart_tipi"]).size().reset_index(name="yolcu")

def aktarma_dagilimi(df, yon=None):
    sub = _filtre_yon(df, yon).copy()
    if sub.empty:
        return pd.DataFrame(columns=["aktarma_grup", "yolcu", "yuzde"])
    sub["aktarma_grup"] = sub["onceki_aktarma"].apply(lambda x: "Doğrudan (0 aktarma)" if x == 0 else "1 aktarma" if x == 1 else "2+ aktarma")
    t = sub.groupby("aktarma_grup").size().reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t

def gidis_donus_ozet(df):
    if "kart_no" not in df.columns:
        return {"toplam_benzersiz_kart": 0, "gidis_donus_kart": 0, "gidis_donus_yuzde": 0, "tek_yon_kart": 0}
    kart_yon = df.groupby("kart_no")["yon"].apply(set)
    cift = kart_yon[kart_yon.apply(lambda s: YON_BES_USK in s and YON_USK_BES in s)]
    toplam = df["kart_no"].nunique()
    cift_say = len(cift)
    return {
        "toplam_benzersiz_kart": toplam,
        "gidis_donus_kart": cift_say,
        "gidis_donus_yuzde": round(cift_say / toplam * 100, 1) if toplam else 0,
        "tek_yon_kart": toplam - cift_say,
    }

def saat_kaynak_isi(df, yon, top_hats=10):
    sub = df[df["yon"] == yon]
    if sub.empty:
        return pd.DataFrame()
    top = kaynak_hatlar(sub, yon, top_hats)["onceki_hat"].tolist()
    sub = sub[sub["onceki_hat"].isin(top)]
    p = sub.pivot_table(index="onceki_hat", columns="saat", values="kart_no", aggfunc="count", fill_value=0)
    return p.reindex(columns=range(24), fill_value=0)

def yonetici_bulgular(df):
    bulgular = []
    bes_seri = saatlik_seri(df, YON_USK_BES)
    usk_seri = saatlik_seri(df, YON_BES_USK)

    if bes_seri["yolcu"].sum() == 0 and usk_seri["yolcu"].sum() == 0:
        return [{"baslik": "Yetersiz veri", "bulgu": "Her iki yönde kayıt yok.",
                 "anlam": "Analiz yapılamaz.", "oneri": "Excel'i kontrol edin."}]

    try:
        bes_peak = bes_seri.loc[bes_seri["yolcu"].idxmax()]
        usk_peak = usk_seri.loc[usk_seri["yolcu"].idxmax()]
    except ValueError:
        return [{"baslik": "Hata", "bulgu": "Pik hesaplanamadı.", "anlam": "", "oneri": ""}]

    bes_kaynak = kaynak_hatlar(df, YON_USK_BES, 1)
    usk_kaynak = kaynak_hatlar(df, YON_BES_USK, 1)

    if not bes_kaynak.empty:
        bk = bes_kaynak.iloc[0]
        bulgular.append({
            "baslik": "Beşiktaş sabah yoğunluğu",
            "bulgu": f"%{bk['yuzde']} {bk['onceki_hat']} hattından, pik {int(bes_peak['saat']):02d}:00 ({int(bes_peak['yolcu']):,} yolcu).",
            "anlam": "Anadolu yakası beslemesi. Demiryolu önemli.",
            "oneri": "07:30–08:30 Marmaray–vapur senkronizasyonu.",
        })

    if not usk_kaynak.empty:
        uk = usk_kaynak.iloc[0]
        bulgular.append({
            "baslik": "Üsküdar akşam yoğunluğu",
            "bulgu": f"1. kaynak {uk['onceki_hat']} (%{uk['yuzde']}), pik {int(usk_peak['saat']):02d}:00 ({int(usk_peak['yolcu']):,} yolcu).",
            "anlam": "Dağınık Avrupa yakası beslemesi.",
            "oneri": "17:00–19:00 besleyici hat koordinasyonu.",
        })

    bekleme_bes = bekleme_analizi(df, YON_USK_BES)
    bulgular.append({
        "baslik": "İskele bekleme süresi",
        "bulgu": f"Beşiktaş yönü ort. {bekleme_bes['ortalama_dk']} dk, %{bekleme_bes['uzun_bekleme_yuzde']} yolcu 15+ dk bekliyor.",
        "anlam": "Uzun bekleme memnuniyetsizlik yaratır.",
        "oneri": "Yoğun saatlerde sefer sıklığını artırın.",
    })

    koridor = koridor_rotalari(df, YON_USK_BES, 1)
    if not koridor.empty:
        k = koridor.iloc[0]
        bulgular.append({
            "baslik": "En yoğun yolculuk zinciri",
            "bulgu": f"{k['koridor']} ({int(k['yolcu']):,} yolcu, %{k['yuzde']}).",
            "anlam": "Üçlü zincir planlaması gerekli.",
            "oneri": "Aktarma noktalarında bilgilendirme artırın.",
        })

    kart = kart_tipi_dagilimi(df, YON_USK_BES)
    if not kart.empty:
        kt = kart.iloc[0]
        bulgular.append({
            "baslik": "Yolcu profili",
            "bulgu": f"En yaygın kart: {kt['kart_tipi']} (%{kt['yuzde']}).",
            "anlam": "Tarife ve kampanya hedeflemesi için önemli.",
            "oneri": "Pik saatlerde baskın segmente göre kapasite ayarlayın.",
        })

    aktarma = aktarma_dagilimi(df, YON_USK_BES)
    dogrudan = aktarma[aktarma["aktarma_grup"].str.contains("Doğrudan")]
    dogrudan_pct = float(dogrudan["yuzde"].iloc[0]) if not dogrudan.empty else 0
    bulgular.append({
        "baslik": "Aktarma derinliği",
        "bulgu": f"Beşiktaş yönünde yolcuların %{dogrudan_pct}'i doğrudan geliyor.",
        "anlam": "Çok aktarmalı yolcular için bağlantı riski var.",
        "oneri": "Aktarma sürelerini vapurla uyumlu hale getirin.",
    })

    gd = gidis_donus_ozet(df)
    bulgular.append({
        "baslik": "Gidiş-dönüş yolcuları",
        "bulgu": f"%{gd['gidis_donus_yuzde']} aynı gün çift yön kullanmış.",
        "anlam": "Sabah-akşam simetrisi önemli.",
        "oneri": "Her iki yönü birlikte planlayın.",
    })

    ozet = veri_ozeti(df)
    bulgular.append({
        "baslik": "Veri kapsamı sınırı",
        "bulgu": f"Analiz {ozet['tarih_baslangic']} tarihli tek güne dayanıyor.",
        "anlam": "Mevsimsellik ve hafta sonu etkisi henüz yok.",
        "oneri": "En az 4–8 haftalık veri toplayın.",
    })

    return bulgular

# ========== YENİ FONKSİYONLAR ==========
def memnuniyet_skoru(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        bek = bekleme_analizi(df, yon)
        if bek["saatlik"].empty:
            continue
        saatlik_df = bek["saatlik"].copy()
        talep = saatlik_seri(df, yon)[["saat", "yolcu"]]
        saatlik_df = saatlik_df.merge(talep, on="saat", how="left")
        sub = _filtre_yon(df, yon)
        if not sub.empty:
            akt_ort = sub.groupby("saat")["onceki_aktarma"].mean().reindex(range(24), fill_value=0).reset_index()
            akt_ort.columns = ["saat", "akt_ort"]
            saatlik_df = saatlik_df.merge(akt_ort, on="saat", how="left")
        else:
            saatlik_df["akt_ort"] = 0
        max_bek = saatlik_df["ortalama"].max() or 1
        max_yolcu = saatlik_df["yolcu"].max() or 1
        saatlik_df["skor"] = (
            100
            - (saatlik_df["ortalama"] / max_bek) * 40
            - (saatlik_df["akt_ort"] / max(2, saatlik_df["akt_ort"].max())) * 30
            - (saatlik_df["yolcu"] / max_yolcu) * 20
        ).clip(0, 100).round(1)
        saatlik_df["yon"] = YON_ETIKET[yon]
        rows.append(saatlik_df[["saat", "yon", "ortalama", "yolcu", "akt_ort", "skor"]])
    if not rows:
        return pd.DataFrame(columns=["saat", "yon", "ortalama", "yolcu", "akt_ort", "skor"])
    return pd.concat(rows, ignore_index=True)

def anomali_tespiti(df: pd.DataFrame) -> pd.DataFrame:
    sonuc = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        seri = saatlik_seri(df, yon)
        if seri.empty or seri["yolcu"].sum() == 0:
            continue
        Q1 = seri["yolcu"].quantile(0.25)
        Q3 = seri["yolcu"].quantile(0.75)
        IQR = Q3 - Q1
        alt = Q1 - 1.5 * IQR
        ust = Q3 + 1.5 * IQR
        seri["anomali"] = seri["yolcu"].apply(lambda x: "Yüksek" if x > ust else ("Düşük" if x < alt else "Normal"))
        seri["esik_ust"] = ust
        seri["esik_alt"] = alt
        seri["yon"] = YON_ETIKET[yon]
        sonuc.append(seri[["saat", "yon", "yolcu", "anomali", "esik_ust", "esik_alt"]])
    if not sonuc:
        return pd.DataFrame(columns=["saat", "yon", "yolcu", "anomali", "esik_ust", "esik_alt"])
    return pd.concat(sonuc, ignore_index=True)

def sefer_dakiklik_simulasyonu(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        seri = saatlik_seri(df, yon)
        for _, row in seri.iterrows():
            saat = int(row["saat"])
            sefer_sayisi = max(1, round(row["yolcu"] / 150))
            for s in range(sefer_sayisi):
                gecikme = int(np.random.normal(2, 5))
                gecikme = max(0, gecikme)
                rows.append({
                    "yon": YON_ETIKET[yon],
                    "saat": saat,
                    "sefer_no": s + 1,
                    "gecikme_dk": gecikme,
                    "durum": "Zamanında" if gecikme <= 5 else "Gecikmeli"
                })
    if not rows:
        return pd.DataFrame(columns=["yon", "saat", "sefer_no", "gecikme_dk", "durum"])
    return pd.DataFrame(rows)

def hava_durumu_simulasyonu(df: pd.DataFrame, yagis_orani: float = 0.0) -> pd.DataFrame:
    sonuc = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        seri = saatlik_seri(df, yon)
        carpan = 1 + yagis_orani / 100 * 0.4
        seri["yolcu_yagmurlu"] = (seri["yolcu"] * carpan).round(0).astype(int)
        seri["yolcu_normal"] = seri["yolcu"]
        seri["yon"] = YON_ETIKET[yon]
        sonuc.append(seri[["saat", "yon", "yolcu_normal", "yolcu_yagmurlu"]])
    if not sonuc:
        return pd.DataFrame(columns=["saat", "yon", "yolcu_normal", "yolcu_yagmurlu"])
    return pd.concat(sonuc, ignore_index=True)

def koridor_kapasite(df: pd.DataFrame, kapasite: int = 600) -> pd.DataFrame:
    rows = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        koridorlar = koridor_rotalari(df, yon, top_n=20)
        if koridorlar.empty:
            continue
        koridorlar["doluluk"] = (koridorlar["yolcu"] / kapasite * 100).round(1)
        koridorlar["yon"] = YON_ETIKET[yon]
        rows.append(koridorlar)
    if not rows:
        return pd.DataFrame(columns=["onceki_hat", "sonraki_hat", "yolcu", "koridor", "yuzde", "doluluk", "yon"])
    return pd.concat(rows, ignore_index=True)

def talep_tahmin_basit(df: pd.DataFrame, yon: str) -> pd.DataFrame:
    try:
        from sklearn.linear_model import LinearRegression
    except ImportError:
        st.error("scikit-learn yüklü değil. Lütfen `pip install scikit-learn` yapın.")
        return pd.DataFrame()
    seri = saatlik_seri(df, yon)
    if seri.empty or seri["yolcu"].sum() == 0:
        return pd.DataFrame()
    X = seri[["saat"]].values
    y = seri["yolcu"].values
    model = LinearRegression()
    model.fit(X, y)
    tahmin = model.predict(X)
    seri["tahmin"] = tahmin.round(0).astype(int)
    seri["hata"] = (seri["yolcu"] - seri["tahmin"]).abs()
    return seri

# =============================================================================
# Streamlit Arayüzü
# =============================================================================

st.set_page_config(page_title="Beşiktaş-Üsküdar Hat Analizi", page_icon="⛴️", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .main-title { font-size: 1.9rem; font-weight: 700; color: #1d3557; margin-bottom: 0; }
    .sub-title { color: #4a4a4a; font-size: 1rem; margin-top: 4px; }
    .kpi-box { background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%); color: white; padding: 1.2rem; border-radius: 12px; text-align: center; }
    .kpi-box h2 { margin: 0; font-size: 2rem; color: white; }
    .kpi-box p { margin: 4px 0 0; opacity: 0.9; font-size: 0.85rem; color: white; }
    .ozet-kutu { background: #fff3cd; border-left: 5px solid #e63946; padding: 1rem 1.2rem; border-radius: 8px; font-size: 1.05rem; line-height: 1.6; color: #222; }
    .guven-iyi { color: #2d6a4f; font-weight: 600; }
    .guven-orta { color: #b8860b; font-weight: 600; }
    .guven-sinirli { color: #b22222; font-weight: 600; }
    .anlam-kutu { background: #e8f4fd; border-left: 5px solid #457b9d; padding: 0.9rem 1.1rem; border-radius: 8px; margin: 0.5rem 0; color: #222; }
    .oneri-kutu { background: #e8f5e9; border-left: 5px solid #2d6a4f; padding: 0.9rem 1.1rem; border-radius: 8px; margin: 0.5rem 0; color: #222; }
    </style>
    """,
    unsafe_allow_html=True,
)

def bulgu_karti(b: dict) -> None:
    st.markdown(f"#### {b['baslik']}")
    st.markdown(f'<div class="ozet-kutu"><b>Bulgumuz:</b> {b["bulgu"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>{b["anlam"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="oneri-kutu"><b>Operasyonel öneri:</b> {b["oneri"]}</div>', unsafe_allow_html=True)
    st.markdown("")

@st.cache_data(show_spinner="Veri yükleniyor...")
def get_data():
    return load_data()

df = get_data()
ozet = veri_ozeti(df)

# Sidebar
sayfa = st.sidebar.radio("Sayfa seçin", [
    "📋 Yönetici Brifingi", "🏠 Genel Özet", "📍 Yolcu Nereden Geliyor?", "🔗 Yolculuk Zinciri",
    "⏱️ Bekleme Süresi", "👥 Yolcu Profili", "📈 Zaman Serisi Analizi",
    "🎯 Sefer Tahmini (Saat X'e kaç yolcu?)", "🕐 Tarife Önerisi", "✅ Güvenilirlik Raporu",
    "🔮 What-If Analizi", "🗺️ Rota Haritası", "🙂 Yolcu Memnuniyet Endeksi",
    "⚠️ Anomali Tespiti", "⛴️ Sefer Dakiklik (Simülasyon)", "🌧️ Hava Durumu Etkisi",
    "📊 Koridor Kapasite Doluluğu", "📥 Rapor İndirme Merkezi", "📈 Talep Tahmin Modeli"
], label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.metric("Toplam Kayıt", f"{ozet['toplam_kayit']:,}")
st.sidebar.metric("Analiz Günü", ozet["tarih_baslangic"])

# ---------- SAYFALAR ----------
try:
    if sayfa == "📋 Yönetici Brifingi":
        st.markdown('<p class="main-title">Yönetici Brifingi</p>', unsafe_allow_html=True)
        for b in yonetici_bulgular(df):
            bulgu_karti(b)

    elif sayfa == "🏠 Genel Özet":
        st.markdown('<p class="main-title">Beşiktaş – Üsküdar Vapur Hattı Yönetici Özeti</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">Tek günlük yolcu hareket verisine dayalı karar destek paneli</p>', unsafe_allow_html=True)

        bes_seri = saatlik_seri(df, YON_USK_BES)
        usk_seri = saatlik_seri(df, YON_BES_USK)

        if bes_seri.empty or usk_seri.empty or bes_seri["yolcu"].sum() == 0 or usk_seri["yolcu"].sum() == 0:
            st.warning("Her iki yönde de yeterli kayıt bulunamadı.")
        else:
            bes_peak = bes_seri.loc[bes_seri["yolcu"].idxmax()]
            usk_peak = usk_seri.loc[usk_seri["yolcu"].idxmax()]

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="kpi-box"><h2>{int(bes_peak["saat"]):02d}:00</h2><p>Beşiktaş pik saati</p></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="kpi-box"><h2>{int(bes_peak["yolcu"]):,}</h2><p>Beşiktaş pik yolcu</p></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="kpi-box"><h2>{int(usk_peak["saat"]):02d}:00</h2><p>Üsküdar pik saati</p></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="kpi-box"><h2>{int(usk_peak["yolcu"]):,}</h2><p>Üsküdar pik yolcu</p></div>', unsafe_allow_html=True)

            st.markdown("### Yönetici Özet Bulguları")
            bes_kaynak_df = kaynak_hatlar(df, YON_USK_BES, 1)
            usk_kaynak_df = kaynak_hatlar(df, YON_BES_USK, 1)

            if not bes_kaynak_df.empty:
                bk = bes_kaynak_df.iloc[0]
                st.markdown(
                    f'<div class="ozet-kutu"><b>Beşiktaş\'a gelen yolcu:</b> En çok <b>{bk["onceki_hat"]}</b> '
                    f'hattından (%{bk["yuzde"]}). Pik saat <b>{int(bes_peak["saat"]):02d}:00</b> ({int(bes_peak["yolcu"]):,} yolcu).</div>',
                    unsafe_allow_html=True,
                )
            if not usk_kaynak_df.empty:
                uk = usk_kaynak_df.iloc[0]
                st.markdown(
                    f'<div class="ozet-kutu"><b>Üsküdar\'a gelen yolcu:</b> En çok <b>{uk["onceki_hat"]}</b> '
                    f'hattından (%{uk["yuzde"]}). Pik saat <b>{int(usk_peak["saat"]):02d}:00</b> ({int(usk_peak["yolcu"]):,} yolcu).</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("### Saatlik Talep Karşılaştırması")
            h1 = bes_seri.assign(tip="Üsküdar→Beşiktaş (Beşiktaş'a gelen)")
            h2 = usk_seri.assign(tip="Beşiktaş→Üsküdar (Üsküdar'a gelen)")
            birlesik = pd.concat([h1, h2])
            fig = px.bar(
                birlesik, x="saat", y="yolcu", color="tip", barmode="group",
                title="Saatlik Yolcu Talebi", labels={"saat": "Saat", "yolcu": "Yolcu Sayısı"},
                color_discrete_sequence=["#457B9D", "#E63946"],
            )
            fig.update_layout(template="plotly_white", height=420)
            st.plotly_chart(fig, use_container_width=True)

    elif sayfa == "📍 Yolcu Nereden Geliyor?":
        st.markdown('<p class="main-title">Yolcu Kaynak Analizi</p>', unsafe_allow_html=True)
        st.caption("Vapura binmeden önce hangi hat/ulaşım aracı kullanıldığına göre dağılım")

        hedef = st.radio("Hedef iskele", ["Beşiktaş'a gelenler", "Üsküdar'a gelenler"], horizontal=True)
        yon = YON_USK_BES if "Beşiktaş" in hedef else YON_BES_USK

        kaynak = kaynak_hatlar(df, yon, 20)
        if kaynak is None or kaynak.empty:
            st.warning("Bu yönde veri bulunamadı.")
        else:
            c1, c2 = st.columns([1.2, 1])
            with c1:
                fig = px.bar(
                    kaynak, x="yolcu", y="onceki_hat", orientation="h",
                    title=f"En Çok Kullanılan Önceki Hatlar — {hedef}",
                    labels={"onceki_hat": "Önceki Hat", "yolcu": "Yolcu"},
                    color="yolcu", color_continuous_scale="Blues",
                )
                fig.update_layout(template="plotly_white", height=520, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.markdown("#### Tablo")
                st.dataframe(kaynak, use_container_width=True, hide_index=True)
                peak_seri = saatlik_seri(df, yon)
                if not peak_seri.empty:
                    peak = peak_seri.loc[peak_seri["yolcu"].idxmax()]
                    st.info(
                        f"**En yoğun saat:** {int(peak['saat']):02d}:00 — {int(peak['yolcu']):,} yolcu\n\n"
                        f"**1. kaynak hat:** {kaynak.iloc[0]['onceki_hat']} (%{kaynak.iloc[0]['yuzde']})"
                    )

            st.markdown("#### Saat × Kaynak Hat Isı Haritası")
            st.caption("Hangi saatte hangi hat en çok yolcu getiriyor — koyu renk = daha yoğun")
            isi = saat_kaynak_isi(df, yon, 10)
            if isi is not None and not isi.empty:
                fig_isi = px.imshow(
                    isi.values,
                    x=[f"{h:02d}" for h in range(24)],
                    y=isi.index.tolist(),
                    labels=dict(x="Saat", y="Önceki Hat", color="Yolcu"),
                    color_continuous_scale="YlOrRd",
                    aspect="auto",
                )
                fig_isi.update_layout(template="plotly_white", height=420)
                st.plotly_chart(fig_isi, use_container_width=True)
                st.markdown(
                    '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
                    "Tek bakışta hangi hattın hangi saatte vapur talebini beslediğini görürsünüz. "
                    "Örneğin sabah koyu bir kare, o saatte o hattın vapur için kritik olduğunu gösterir.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Isı haritası için yeterli veri yok.")

    elif sayfa == "🔗 Yolculuk Zinciri":
        st.markdown('<p class="main-title">Yolculuk Zinciri Analizi</p>', unsafe_allow_html=True)
        st.caption("Önceki hat → Vapur → Sonraki hat: yolcu tam rotası")

        yon_sec = st.selectbox(
            "Yön",
            [("Beşiktaş → Üsküdar", YON_BES_USK), ("Üsküdar → Beşiktaş", YON_USK_BES)],
            format_func=lambda x: x[0],
            key="koridor_yon",
        )
        yon = yon_sec[1]
        koridor = koridor_rotalari(df, yon, 15)

        if koridor is None or koridor.empty:
            st.warning("Bu yönde rota verisi bulunamadı.")
        else:
            c1, c2 = st.columns([1.2, 1])
            with c1:
                fig = px.bar(
                    koridor, x="yolcu", y="koridor", orientation="h",
                    title=f"En Sık 15 Rota — {yon_sec[0]}",
                    labels={"koridor": "Rota", "yolcu": "Yolcu"},
                    color="yolcu", color_continuous_scale="Teal",
                )
                fig.update_layout(template="plotly_white", height=520, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.dataframe(
                    koridor[["onceki_hat", "sonraki_hat", "yolcu", "yuzde"]],
                    use_container_width=True, hide_index=True,
                )

            top = koridor.iloc[0]
            st.markdown(
                f'<div class="ozet-kutu"><b>En yoğun zincir:</b> {top["koridor"]} — '
                f'{int(top["yolcu"]):,} yolcu (%{top["yuzde"]})</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
                "Yolcu sadece vapura binip inmiyor; önce bir araçla geliyor, vapura biniyor, "
                "sonra başka bir hatla devam ediyor. Vapur planı bu üçlü zincirin ortasında yer alır. "
                "En sık rota, entegrasyon ve aktarma noktalarının önceliğini belirler.</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="oneri-kutu"><b>Operasyonel öneri:</b> '
                "En yoğun 3 koridor için aktarma saatleri ve yönlendirme tabelaları "
                "vapur tarifesiyle uyumlu hale getirilsin.</div>",
                unsafe_allow_html=True,
            )

    elif sayfa == "⏱️ Bekleme Süresi":
        st.markdown('<p class="main-title">İskele Bekleme Süresi Analizi</p>', unsafe_allow_html=True)
        st.caption("Önceki araçtan indikten sonra vapur gelene kadar geçen süre")

        yon_sec = st.selectbox(
            "Yön",
            [("Beşiktaş → Üsküdar", YON_BES_USK), ("Üsküdar → Beşiktaş", YON_USK_BES)],
            format_func=lambda x: x[0],
            key="bekleme_yon",
        )
        yon = yon_sec[1]
        bek = bekleme_analizi(df, yon)

        if bek is None:
            st.warning("Bekleme süresi hesaplanamadı.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Ortalama Bekleme", f"{bek.get('ortalama_dk', 0)} dk")
            m2.metric("Medyan Bekleme", f"{bek.get('medyan_dk', 0)} dk")
            m3.metric("15+ dk Bekleyen", f"%{bek.get('uzun_bekleme_yuzde', 0)}")
            m4.metric("30+ dk Bekleyen", f"%{bek.get('cok_uzun_yuzde', 0)}")

            if not bek.get("saatlik", pd.DataFrame()).empty:
                saatlik_df = bek["saatlik"]
                fig = go.Figure()
                fig.add_trace(go.Bar(x=saatlik_df["saat"], y=saatlik_df["yolcu"], name="Yolcu sayısı", yaxis="y2", marker_color="#a8dadc", opacity=0.5))
                fig.add_trace(go.Scatter(x=saatlik_df["saat"], y=saatlik_df["ortalama"], name="Ort. bekleme (dk)", line=dict(color="#e63946", width=3)))
                fig.update_layout(
                    title="Saatlik Ortalama Bekleme Süresi",
                    xaxis_title="Saat", yaxis_title="Bekleme (dk)",
                    yaxis2=dict(title="Yolcu", overlaying="y", side="right", showgrid=False),
                    template="plotly_white", height=420, legend=dict(orientation="h"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Bekleme süresi grafiği için yeterli veri yok.")

        st.markdown(
            '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
            "Bekleme süresi, yolcunun önceki ulaşım aracından indikten sonra vapur gelene kadar "
            "iskelede geçirdiği zamandır. Uzun bekleme = kalabalık iskele, kaçırılan bağlantılar ve "
            "düşük memnuniyet. Pik saatlerde bekleme artıyorsa sefer sayısı yetersiz olabilir.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="oneri-kutu"><b>Operasyonel öneri:</b> '
            "%15'ten fazla yolcunun 15+ dakika beklediği saatlerde sefer sıklığını artırın "
            "veya önceki hat seferleriyle senkronizasyonu gözden geçirin.</div>",
            unsafe_allow_html=True,
        )

    elif sayfa == "👥 Yolcu Profili":
        st.markdown('<p class="main-title">Yolcu Profili Analizi</p>', unsafe_allow_html=True)
        st.caption("Kart tipi, aktarma derinliği ve gidiş-dönüş davranışı")

        tab1, tab2, tab3 = st.tabs(["Kart Tipi", "Aktarma Derinliği", "Gidiş-Dönüş"])

        with tab1:
            yon_sec = st.selectbox(
                "Yön (kart tipi)",
                [("Tümü", None), ("Beşiktaş → Üsküdar", YON_BES_USK), ("Üsküdar → Beşiktaş", YON_USK_BES)],
                format_func=lambda x: x[0],
                key="kart_yon",
            )
            kart = kart_tipi_dagilimi(df, yon_sec[1])
            if kart is not None and not kart.empty:
                c1, c2 = st.columns(2)
                with c1:
                    fig = px.pie(kart, values="yolcu", names="kart_tipi", title="Kart Tipi Dağılımı", hole=0.4)
                    fig.update_layout(template="plotly_white", height=380)
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.dataframe(kart, use_container_width=True, hide_index=True)

                if yon_sec[1]:
                    ks = kart_tipi_saatlik(df, yon_sec[1])
                    if ks is not None and not ks.empty:
                        fig2 = px.line(ks, x="saat", y="yolcu", color="kart_tipi", markers=True, title="Saatlik Kart Tipi Profili")
                        fig2.update_layout(template="plotly_white", height=380)
                        st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Kart tipi verisi yok.")

            st.markdown(
                '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
                "Öğrenci, tam bilet veya abonman oranı; hangi yolcu grubunun hangi saatte "
                "vapur kullandığını gösterir. Örneğin sabah öğrenci yoğunluğu yüksekse, "
                "o saatlerde kapasite ve tarife politikası buna göre şekillenmelidir.</div>",
                unsafe_allow_html=True,
            )

        with tab2:
            yon_a = st.selectbox(
                "Yön (aktarma)",
                [("Beşiktaş → Üsküdar", YON_BES_USK), ("Üsküdar → Beşiktaş", YON_USK_BES)],
                format_func=lambda x: x[0],
                key="aktarma_yon",
            )
            akt = aktarma_dagilimi(df, yon_a[1])
            if akt is not None and not akt.empty:
                fig = px.bar(akt, x="aktarma_grup", y="yolcu", text="yuzde", title="Vapura Gelmeden Önce Aktarma Sayısı")
                fig.update_traces(texttemplate="%{text}%", textposition="outside")
                fig.update_layout(template="plotly_white", height=380)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aktarma verisi yok.")
            st.markdown(
                '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
                "Doğrudan gelen yolcu tek araçla iskeleye ulaşmış demektir. "
                "1 veya 2+ aktarma yapanlar uzak koridorlardan geliyor; vapur kaçırma riski "
                "ve bağlantı süresi planlaması bu grup için kritiktir.</div>",
                unsafe_allow_html=True,
            )

        with tab3:
            gd = gidis_donus_ozet(df)
            c1, c2, c3 = st.columns(3)
            c1.metric("Benzersiz Kart", f"{gd.get('toplam_benzersiz_kart', 0):,}")
            c2.metric("Gidiş-Dönüş Yapan", f"{gd.get('gidis_donus_kart', 0):,}")
            c3.metric("Gidiş-Dönüş Oranı", f"%{gd.get('gidis_donus_yuzde', 0)}")
            st.markdown(
                '<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>'
                "Aynı gün hem Beşiktaş→Üsküdar hem Üsküdar→Beşiktaş yapan yolcular "
                "(pendler / işe gidip dönenler). Sabah ve akşam pik saatleri bu grubun "
                "gidiş ve dönüş ihtiyacını yansıtır; iki yön birbirinden bağımsız planlanmamalıdır.</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="oneri-kutu"><b>Operasyonel öneri:</b> '
                "Sabah Beşiktaş ve akşam Üsküdar yoğunluklarını çift yönlü talep olarak birlikte planlayın.</div>",
                unsafe_allow_html=True,
            )

    elif sayfa == "📈 Zaman Serisi Analizi":
        st.markdown('<p class="main-title">Zaman Serisi Analizi</p>', unsafe_allow_html=True)
        st.caption("15 dakikalık dilimlerde yolcu talebi ve hareketli ortalama trendi")

        yon_sec = st.selectbox(
            "Yön seçin",
            [("Beşiktaş → Üsküdar", YON_BES_USK), ("Üsküdar → Beşiktaş", YON_USK_BES)],
            format_func=lambda x: x[0],
        )
        yon = yon_sec[1]
        seri = zaman_serisi_ozet(df, yon)

        if seri is not None and not seri.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=seri["saat_etiket"], y=seri["yolcu"], name="15 dk talep", marker_color="#a8dadc"))
            fig.add_trace(go.Scatter(x=seri["saat_etiket"], y=seri["hareketli_ort"], name="Hareketli ortalama (1 saat)", line=dict(color="#e63946", width=3)))
            fig.update_layout(
                title=f"15 Dakikalık Zaman Serisi — {yon_sec[0]}",
                xaxis_title="Saat", yaxis_title="Yolcu",
                template="plotly_white", height=450,
                xaxis=dict(tickangle=45, nticks=24),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Saatlik Özet Tablo")
            saatlik = saatlik_seri(df, yon)
            if saatlik is not None and not saatlik.empty:
                st.dataframe(saatlik, use_container_width=True, hide_index=True)
        else:
            st.warning("Zaman serisi verisi oluşturulamadı.")

        st.markdown(
            """
            **Nasıl okunur?** Kırmızı çizgi (hareketli ortalama) talep trendini gösterir.
            Yukarı çıkış = yoğunluk artıyor. Tek günlük veri olduğu için bu desen o günün profilidir;
            hafta içi / hafta sonu farkı için daha fazla günlük veri gerekir.
            """
        )

    elif sayfa == "🎯 Sefer Tahmini (Saat X'e kaç yolcu?)":
        st.markdown('<p class="main-title">Sefer Ekleme Tahmini</p>', unsafe_allow_html=True)
        st.caption("Seçilen saat ve yön için ek sefer planlamasına yönelik operasyonel tahmin")

        c1, c2, c3 = st.columns(3)
        with c1:
            yon_label = st.selectbox("Yön", ["Beşiktaş → Üsküdar", "Üsküdar → Beşiktaş"])
            yon = YON_BES_USK if "Üsküdar" in yon_label.split("→")[1] else YON_USK_BES
        with c2:
            saat = st.slider("Saat", 0, 23, 14)
        with c3:
            dakika = st.selectbox("Dakika", [0, 15, 30, 45], index=0)

        sonuc = tahmin_sefer_yolcu(df, yon, saat, dakika)
        cumle = karar_ozet_cumlesi(df, yon, saat, dakika)

        st.markdown("### Karar Destek Özeti")
        if cumle:
            st.markdown(f'<div class="ozet-kutu">{cumle}</div>', unsafe_allow_html=True)
        else:
            st.info("Özet bilgisi üretilemedi.")

        if sonuc:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tahmini Yolcu (tek sefer)", sonuc.tahmini_yolcu)
            m2.metric("Alt Sınır (%95)", sonuc.alt_sinir)
            m3.metric("Üst Sınır (%95)", sonuc.ust_sinir)
            m4.metric("Saatlik Toplam Yolcu", sonuc.mevcut_saat_talep)
            st.caption(
                "Tahmini yolcu: seçilen dakikada eklenen tek sefere binecek kişi sayısı. "
                "Saatlik toplam yolcu: o saatin tamamında (00–59 dk) ilgili yönde binen tüm yolcular."
            )

            st.markdown("#### Teknik Detay")
            st.write(f"- **Yöntem:** {sonuc.yontem}")
            st.write(f"- **Önerilen sefer sıklığı bu saatte:** saatte ~{sonuc.onerilen_sefer_sayisi} sefer")
            st.warning(
                "Bu tahmin tek günlük veriye dayanır. Kesin rakam değil, karar desteği amaçlıdır. "
                "Hava durumu, tatil, etkinlik gibi faktörler sonucu değiştirebilir."
            )

            st.markdown("#### Saat Bazlı Tahmin Karşılaştırması")
            kars = []
            for h in range(24):
                t = tahmin_sefer_yolcu(df, yon, h, 0)
                kars.append({"saat": f"{h:02d}:00", "tahmin": t.tahmini_yolcu, "alt": t.alt_sinir, "ust": t.ust_sinir})
            if kars:
                kdf = pd.DataFrame(kars)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["tahmin"], mode="lines+markers", name="Tahmin", line=dict(color="#e63946", width=2)))
                fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["ust"], mode="lines", name="Üst sınır", line=dict(dash="dot", color="#aaa")))
                fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["alt"], mode="lines", name="Alt sınır", fill="tonexty", line=dict(dash="dot", color="#aaa")))
                fig.update_layout(title="24 Saat Sefer Başına Tahmini Yolcu", template="plotly_white", height=380, xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Sefer tahmini sonucu alınamadı.")

    elif sayfa == "🕐 Tarife Önerisi":
        st.markdown('<p class="main-title">Optimal Sefer Tarifesi Önerisi</p>', unsafe_allow_html=True)
        tarife = tarife_onerisi(df)
        if tarife is not None and not tarife.empty:
            yon_filt = st.selectbox("Yön", tarife["yon"].unique())
            tsub = tarife[tarife["yon"] == yon_filt]

            fig = px.bar(
                tsub, x="saat", y="talep", color="onerilen_frekans",
                title=f"Talep ve Önerilen Frekans — {yon_filt}",
                labels={"saat": "Saat", "talep": "Yolcu Talebi"},
                text="onerilen_frekans",
            )
            fig.update_layout(template="plotly_white", height=420, xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                tsub[["saat", "talep", "talep_katsayisi", "onerilen_frekans", "saatte_sefer", "sefer_basina_yolcu"]],
                use_container_width=True, hide_index=True,
            )

            yogun = tsub.nlargest(3, "talep")
            st.success(
                f"**Öncelikli saatler ({yon_filt}):** "
                + ", ".join(f"{r['saat']} ({int(r['talep'])} yolcu, {r['onerilen_frekans']})" for _, r in yogun.iterrows())
            )
        else:
            st.info("Tarife önerisi için yeterli veri yok.")

    elif sayfa == "✅ Güvenilirlik Raporu":
        st.markdown('<p class="main-title">İstatistiksel Güvenilirlik</p>', unsafe_allow_html=True)
        st.caption("Bu analizlerin ne kadar güvenilir olduğu ve sınırları")

        rapor = guvenilirlik_raporu(df)
        if rapor is not None and not rapor.empty:
            for _, row in rapor.iterrows():
                seviye = row["Güven Seviyesi"]
                css = "guven-iyi" if seviye == "Güçlü" else "guven-orta" if seviye in ("Orta", "Orta güven", "Kullanılabilir") else "guven-sinirli"
                st.markdown(f"**{row['Kriter']}** — <span class='{css}'>{seviye}</span>", unsafe_allow_html=True)
                st.write(f"_{row['Durum']}_ — {row['Açıklama']}")
                st.markdown("")
        else:
            st.info("Güvenilirlik raporu oluşturulamadı.")

        st.markdown("### Özet Karar")
        st.info(
            "**Güvenilir olan:** Yolcu sayıları, kaynak hat dağılımı, pik saatler, saatlik profil.\n\n"
            "**Dikkatli kullanılması gereken:** Tek sefer tahmini ve uzun vadeli zaman serisi — "
            "çünkü veri tek güne ait. Karar verirken aralık kullanın (ör. 45–65 yolcu), tek rakam değil."
        )

        if ozet["gun_sayisi"] <= 1:
            st.warning(
                f"Veri yalnızca **{ozet['tarih_baslangic']}** tarihini kapsıyor. "
                "Daha güvenilir tahmin için en az 4–8 haftalık veri önerilir."
            )

    elif sayfa == "🔮 What-If Analizi":
        st.markdown('<p class="main-title">What-If Senaryoları</p>', unsafe_allow_html=True)
        st.caption("Sefer sıklığındaki değişimin bekleme süresine ve yolcu/sefere etkisi")

        c1, c2 = st.columns(2)
        with c1:
            yon_label = st.selectbox("Yön", ["Beşiktaş → Üsküdar", "Üsküdar → Beşiktaş"], key="whatif_yon")
            yon = YON_BES_USK if "Üsküdar" in yon_label.split("→")[1] else YON_USK_BES
        with c2:
            saat = st.slider("Saat", 0, 23, 8, key="whatif_saat")

        tarife = tarife_onerisi(df)
        tsub = tarife[(tarife["yon"] == yon_label) & (tarife["saat_int"] == saat)]

        if tsub.empty:
            st.warning("Bu saat için tarife verisi bulunamadı.")
        else:
            base_sefer = int(tsub.iloc[0]["saatte_sefer"])
            saatlik_talep = int(tsub.iloc[0]["talep"])

            st.markdown(f"**Mevcut durum:** Saatte **{base_sefer}** sefer, toplam **{saatlik_talep}** yolcu")

            degisim = st.slider("Sefer sayısındaki değişim (%)", -50, 100, 0, 10, key="whatif_pct")
            yeni_sefer = max(1, round(base_sefer * (1 + degisim / 100)))

            headway_min = 60 / yeni_sefer
            ortalama_bekleme = headway_min / 2
            yolcu_per_sefer = round(saatlik_talep / yeni_sefer)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Yeni Sefer Sayısı", f"{yeni_sefer}")
            with col2:
                st.metric("Ortalama Bekleme Süresi (tahmini)", f"{ortalama_bekleme:.1f} dk",
                          delta=f"{ortalama_bekleme - (60/base_sefer)/2:.1f} dk")
            with col3:
                st.metric("Sefer Başına Yolcu", f"{yolcu_per_sefer}",
                          delta=f"{yolcu_per_sefer - round(saatlik_talep/base_sefer)}")

            st.markdown("---")
            st.caption(
                "Not: Bekleme süresi, yolcuların rastgele geldiği ve seferlerin eşit aralıklı olduğu varsayımıyla "
                "ortalama bekleme = sefer aralığı / 2 olarak hesaplanmıştır."
            )

    elif sayfa == "🗺️ Rota Haritası":
        st.markdown('<p class="main-title">Vapur Hattı ve Bağlantı Haritası (Gelişmiş)</p>', unsafe_allow_html=True)
        st.caption("Beşiktaş – Üsküdar arası feribot güzergâhı ve kaynak hatlar.")
        besiktas_lat, besiktas_lon = 41.0441, 29.0063
        uskudar_lat, uskudar_lon = 41.0258, 29.0156

        fig = go.Figure()
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon, uskudar_lon], lat=[besiktas_lat, uskudar_lat],
            mode='lines', line=dict(width=4, color='#1d3557'), name='Vapur Hattı'))
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon], lat=[besiktas_lat], mode='markers+text',
            marker=dict(size=14, color='#e63946'), text=['Beşiktaş'], textposition='top right', name='Beşiktaş'))
        fig.add_trace(go.Scattermapbox(
            lon=[uskudar_lon], lat=[uskudar_lat], mode='markers+text',
            marker=dict(size=14, color='#457b9d'), text=['Üsküdar'], textposition='top left', name='Üsküdar'))
        # Marmaray
        fig.add_trace(go.Scattermapbox(
            lon=[29.0150], lat=[41.0250], mode='markers',
            marker=dict(size=8, color='#ffa500', symbol='triangle'), name='Marmaray Üsküdar'))
        # Kaynak hatlar
        kaynak_df = kaynak_hatlar(df, YON_USK_BES, 5)
        hat_koord = {
            "Marmaray": (41.0250, 29.0150),
            "Metrobüs": (41.0450, 29.0100),
            "Otobüs": (41.0420, 29.0080),
            "Taksim": (41.0370, 28.9850),
            "Kadıköy": (40.9900, 29.0250),
        }
        for _, row in kaynak_df.iterrows():
            hat = row["onceki_hat"]
            if hat in hat_koord:
                lat, lon = hat_koord[hat]
                fig.add_trace(go.Scattermapbox(
                    lon=[lon], lat=[lat], mode='markers+text',
                    marker=dict(size=10, color='green'), text=[hat], textposition='bottom center',
                    name=f"Kaynak: {hat}"))

        fig.update_layout(
            mapbox=dict(style='open-street-map', center=dict(lat=41.03495, lon=29.01095), zoom=12),
            margin=dict(l=0, r=0, t=0, b=0), height=550,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="anlam-kutu"><b>Harita hakkında:</b> Yeşil noktalar en yoğun kaynak hatlarını gösterir.</div>', unsafe_allow_html=True)

    elif sayfa == "🙂 Yolcu Memnuniyet Endeksi":
        st.markdown('<p class="main-title">Yolcu Memnuniyet Endeksi</p>', unsafe_allow_html=True)
        st.caption("Bekleme süresi, aktarma sayısı ve yoğunluğa dayalı 0‑100 arası puan.")
        mem = memnuniyet_skoru(df)
        if mem.empty:
            st.warning("Memnuniyet verisi hesaplanamadı.")
        else:
            yon_sec = st.selectbox("Yön", mem["yon"].unique(), key="memnuniyet_yon")
            veri = mem[mem["yon"] == yon_sec]
            fig = px.bar(veri, x="saat", y="skor", color="skor",
                         color_continuous_scale="RdYlGn", range_color=[0, 100],
                         title=f"Memnuniyet Endeksi – {yon_sec}")
            fig.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(veri, use_container_width=True)
            csv = veri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "memnuniyet.csv", "text/csv")

    elif sayfa == "⚠️ Anomali Tespiti":
        st.markdown('<p class="main-title">Anomali Tespiti (IQR)</p>', unsafe_allow_html=True)
        st.caption("Saatlik yolcu sayılarında aşırı yüksek veya düşük değerler.")
        anom = anomali_tespiti(df)
        if anom.empty:
            st.warning("Anomali verisi hesaplanamadı.")
        else:
            yon_sec = st.selectbox("Yön", anom["yon"].unique(), key="anomali_yon")
            veri = anom[anom["yon"] == yon_sec]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=veri["saat"], y=veri["yolcu"], name="Yolcu"))
            fig.add_hline(y=veri["esik_ust"].iloc[0], line_dash="dash", line_color="red", annotation_text="Üst eşik")
            fig.add_hline(y=veri["esik_alt"].iloc[0], line_dash="dash", line_color="blue", annotation_text="Alt eşik")
            fig.update_layout(title=f"Anomali Tespiti – {yon_sec}", template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(veri[veri["anomali"] != "Normal"], use_container_width=True)
            csv = veri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "anomali.csv", "text/csv")

    elif sayfa == "⛴️ Sefer Dakiklik (Simülasyon)":
        st.markdown('<p class="main-title">Sefer Dakiklik Raporu (Simülasyon)</p>', unsafe_allow_html=True)
        st.warning("Bu sayfa simüle edilmiş verilerle çalışır, gerçek vapur saatleri yoktur.")
        dakiklik = sefer_dakiklik_simulasyonu(df)
        if dakiklik.empty:
            st.warning("Simülasyon oluşturulamadı.")
        else:
            yon_sec = st.selectbox("Yön", dakiklik["yon"].unique(), key="dakiklik_yon")
            veri = dakiklik[dakiklik["yon"] == yon_sec]
            fig = px.histogram(veri, x="gecikme_dk", nbins=20, title=f"Gecikme Dağılımı – {yon_sec}")
            fig.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(veri.groupby("saat")["gecikme_dk"].mean().reset_index(), use_container_width=True)
            csv = veri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "dakiklik.csv", "text/csv")

    elif sayfa == "🌧️ Hava Durumu Etkisi":
        st.markdown('<p class="main-title">Hava Durumu Etkisi Simülasyonu</p>', unsafe_allow_html=True)
        yagis = st.slider("Yağış şiddeti (%)", 0, 100, 30, 10, key="hava_yagis")
        sim = hava_durumu_simulasyonu(df, yagis)
        if sim.empty:
            st.warning("Simülasyon oluşturulamadı.")
        else:
            yon_sec = st.selectbox("Yön", sim["yon"].unique(), key="hava_yon")
            veri = sim[sim["yon"] == yon_sec]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=veri["saat"], y=veri["yolcu_normal"], name="Normal"))
            fig.add_trace(go.Bar(x=veri["saat"], y=veri["yolcu_yagmurlu"], name="Yağmurlu"))
            fig.update_layout(title=f"Talep Değişimi – {yon_sec} (Yağış %{yagis})", barmode="group", template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True)
            csv = veri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "hava_durumu.csv", "text/csv")

    elif sayfa == "📊 Koridor Kapasite Doluluğu":
        st.markdown('<p class="main-title">Koridor Kapasite Kullanımı</p>', unsafe_allow_html=True)
        st.caption("Vapur kapasitesi varsayılan 600 yolcu üzerinden doluluk oranları.")
        kap_df = koridor_kapasite(df)
        if kap_df.empty:
            st.warning("Koridor verisi bulunamadı.")
        else:
            yon_sec = st.selectbox("Yön", kap_df["yon"].unique(), key="kapasite_yon")
            veri = kap_df[kap_df["yon"] == yon_sec].head(15)
            fig = px.bar(veri, x="doluluk", y="koridor", orientation="h",
                         title=f"Doluluk Oranları – {yon_sec}",
                         color="doluluk", color_continuous_scale="OrRd")
            fig.update_layout(template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(veri, use_container_width=True)
            csv = veri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "koridor_kapasite.csv", "text/csv")

    elif sayfa == "📥 Rapor İndirme Merkezi":
        st.markdown('<p class="main-title">Rapor İndirme Merkezi</p>', unsafe_allow_html=True)
        st.caption("Tüm önemli tabloları CSV olarak dışa aktarın.")
        # Tarife önerisi
        tahmin_df = tarife_onerisi(df)
        if not tahmin_df.empty:
            st.download_button("📥 Tarife Önerisi CSV", tahmin_df.to_csv(index=False).encode('utf-8'), "tarife_onerisi.csv")
        # Memnuniyet
        mem_df = memnuniyet_skoru(df)
        if not mem_df.empty:
            st.download_button("📥 Memnuniyet Skoru CSV", mem_df.to_csv(index=False).encode('utf-8'), "memnuniyet.csv")
        # Anomali
        anom_df = anomali_tespiti(df)
        if not anom_df.empty:
            st.download_button("📥 Anomali Tespiti CSV", anom_df.to_csv(index=False).encode('utf-8'), "anomali.csv")
        # Koridor kapasite
        kor_df = koridor_kapasite(df)
        if not kor_df.empty:
            st.download_button("📥 Koridor Kapasite CSV", kor_df.to_csv(index=False).encode('utf-8'), "koridor.csv")
        # Kaynak hatlar
        kaynak_df = kaynak_hatlar(df, YON_USK_BES, 20)
        if not kaynak_df.empty:
            st.download_button("📥 Kaynak Hatlar CSV", kaynak_df.to_csv(index=False).encode('utf-8'), "kaynak_hatlar.csv")

    elif sayfa == "📈 Talep Tahmin Modeli":
        st.markdown('<p class="main-title">Basit Talep Tahmin Modeli</p>', unsafe_allow_html=True)
        st.warning("Bu model tek günlük veri ile eğitildiği için yalnızca o günün desenini yansıtır. Gerçek kullanım için çok günlü veri gerekir.")
        yon_sec = st.selectbox("Yön", ["Beşiktaş → Üsküdar", "Üsküdar → Beşiktaş"], key="ml_yon")
        yon = YON_BES_USK if "Üsküdar" in yon_sec.split("→")[1] else YON_USK_BES
        tahmin_seri = talep_tahmin_basit(df, yon)
        if tahmin_seri.empty:
            st.warning("Tahmin yapılamadı. scikit-learn yüklü değil veya veri yetersiz.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tahmin_seri["saat"], y=tahmin_seri["yolcu"], name="Gerçek"))
            fig.add_trace(go.Scatter(x=tahmin_seri["saat"], y=tahmin_seri["tahmin"], name="Tahmin"))
            fig.update_layout(title=f"Talep Tahmini – {yon_sec}", template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(tahmin_seri, use_container_width=True)
            csv = tahmin_seri.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV İndir", csv, "talep_tahmin.csv", "text/csv")

except Exception as e:
    st.error(f"Bir hata oluştu: {str(e)}")
    st.exception(e)
