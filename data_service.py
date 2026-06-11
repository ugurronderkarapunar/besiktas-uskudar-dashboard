# -*- coding: utf-8 -*-
"""Veri yükleme, istatistik ve tahmin servisi."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

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
    raise FileNotFoundError(
        "Excel dosyası bulunamadı. 'data' klasörüne veri.xlsx koyun."
    )


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
    df = pd.read_excel(path, sheet_name="Sayfa2")
    df.columns = [str(c).strip() for c in df.columns]
    rename = {
        "yön": "yon",
        "saat_2.sıra": "saat_vapur",
        "saat_1.sıra": "saat_onceki",
        "onceki_hat_adi_ok_1.sıra": "onceki_hat",
        "onceki_operator_adi": "onceki_operator",
        "onceki_operator_grubu": "onceki_operator_grubu",
        "kart_tipi": "kart_tipi",
        "BEKLEME SAATİ": "bekleme_suresi",
        "merkez_trn_ts": "islem_zamani",
        "merkez_hat_adi": "vapur_hatti",
        "merkez_aktarma_no": "aktarma_sayisi",
    }
    for old, new in rename.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    df["islem_zamani"] = pd.to_datetime(df["islem_zamani"], format="mixed", errors="coerce")
    df["tarih"] = df["islem_zamani"].dt.date
    df["saat"] = df["islem_zamani"].dt.hour
    df["dakika"] = df["islem_zamani"].dt.minute
    df["dakika_toplam"] = df["saat"] * 60 + df["dakika"]
    df["saat_dakika"] = df["islem_zamani"].dt.strftime("%H:%M")
    df["onceki_hat"] = df["onceki_hat"].fillna("BİLİNMİYOR").astype(str).str.strip()
    df["onceki_hat"] = df["onceki_hat"].replace({"": "BİLİNMİYOR", "nan": "BİLİNMİYOR"})
    df["yon_etiket"] = df["yon"].map(YON_ETIKET)
    return df


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
    h = sub.groupby("saat").size().reindex(range(24), fill_value=0).reset_index(name="yolcu")
    h["yon"] = YON_ETIKET.get(yon, yon)
    h["yuzde"] = (h["yolcu"] / h["yolcu"].sum() * 100).round(1)
    return h


def onbes_dakika_seri(df: pd.DataFrame, yon: str) -> pd.DataFrame:
    sub = df[df["yon"] == yon].copy()
    sub["dilim"] = (sub["dakika_toplam"] // 15) * 15
    seri = sub.groupby("dilim").size().reset_index(name="yolcu")
    seri["saat_etiket"] = seri["dilim"].apply(lambda x: f"{x // 60:02d}:{x % 60:02d}")
    seri["saat"] = seri["dilim"] // 60
    return seri


def kaynak_hatlar(df: pd.DataFrame, yon: str, top_n: int = 15) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    t = sub.groupby("onceki_hat").size().sort_values(ascending=False).reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t.head(top_n)


def guvenilirlik_raporu(df: pd.DataFrame) -> pd.DataFrame:
    ozet = veri_ozeti(df)
    gun = ozet["gun_sayisi"]
    n = ozet["toplam_kayit"]

    maddeler = [
        ("Örneklem büyüklüğü", f"{n:,} kayıt", "Güçlü", "19 binden fazla gözlem; tanımlayıcı istatistikler güvenilir."),
        (
            "Veri süresi",
            f"{gun} gün ({ozet['tarih_baslangic']})",
            "Sınırlı" if gun <= 1 else "Orta",
            "Tek günlük veri: günlük/haftalık mevsimsellik yakalanamaz. Tahminler aynı günün desenine dayanır.",
        ),
        (
            "Tanımlayıcı analiz",
            "Kaynak hat, saat dağılımı",
            "Güvenilir",
            "Kim nereden geliyor, hangi saatte yoğunluk var — bu sorulara net cevap verilebilir.",
        ),
        (
            "Zaman serisi tahmini",
            "Saatlik / 15 dk desen",
            "Orta güven",
            "Tek gün verisiyle desen çıkarılır; %95 güven aralığı Poisson dağılımına dayanır.",
        ),
        (
            "Sefer ekleme tahmini",
            "Saat X'e sefer koyarsak kaç yolcu?",
            "Orta güven",
            "Mevcut saat talebi ÷ önerilen sefer sayısı mantığı; gerçek dünyada hava, tatil, etkinlik etkiler.",
        ),
        (
            "Öneri",
            "Karar desteği",
            "Kullanılabilir",
            "Yönetici özeti 'yaklaşık X yolcu, %95 ihtimalle Y–Z arası' şeklinde sunulmalı; kesin rakam değil.",
        ),
    ]
    return pd.DataFrame(maddeler, columns=["Kriter", "Durum", "Güven Seviyesi", "Açıklama"])


def tahmin_sefer_yolcu(
    df: pd.DataFrame,
    yon: str,
    hedef_saat: int,
    hedef_dakika: int = 0,
    pencere_dk: int = 15,
) -> TahminSonucu:
    """Belirli saatte ek sefer koyulursa beklenen yolcu sayısı."""
    sub = df[df["yon"] == yon].copy()
    hedef_dk = hedef_saat * 60 + hedef_dakika
    alt = hedef_dk - pencere_dk
    ust = hedef_dk + pencere_dk

    pencere = sub[(sub["dakika_toplam"] >= alt) & (sub["dakika_toplam"] <= ust)]
    saat_talep = int(sub[sub["saat"] == hedef_saat].shape[0])

    # Mevcut sefer yoğunluğu: aynı saatteki benzersiz dakika dilimleri
    ayni_saat = sub[sub["saat"] == hedef_saat]
    mevcut_sefer = max(ayni_saat["dakika_toplam"].nunique() // 5, 1)
    if saat_talep == 0:
        mevcut_sefer = 1

    # 15 dk penceredeki gözlem sayısı
    pencere_yolcu = len(pencere)
    if pencere_yolcu > 0:
        tahmin = max(1, round(pencere_yolcu / max(mevcut_sefer, 1)))
    else:
        # Komşu saatlerden ağırlıklı tahmin
        komsu = sub[sub["saat"].between(max(0, hedef_saat - 1), min(23, hedef_saat + 1))]
        tahmin = max(1, round(len(komsu) / (3 * max(mevcut_sefer, 1))))

    # Poisson güven aralığı (yaklaşık)
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
        yon=yon_adi,
        hedef_saat=saat_str,
        tahmini_yolcu=tahmin,
        alt_sinir=alt_sinir,
        ust_sinir=ust_sinir,
        guven_yuzde=95,
        aciklama=aciklama,
        yontem="15 dk pencere + saatlik talep / mevcut sefer yoğunluğu (Poisson CI)",
        mevcut_saat_talep=saat_talep,
        onerilen_sefer_sayisi=onerilen,
    )


def karar_ozet_cumlesi(df: pd.DataFrame, yon: str, saat: int, dakika: int = 0) -> str:
    t = tahmin_sefer_yolcu(df, yon, saat, dakika)
    yon_kisa = "Beşiktaş'tan Üsküdar'a" if yon == YON_BES_USK else "Üsküdar'dan Beşiktaş'a"
    return (
        f"Saat {t.hedef_saat} itibarıyla {yon_kisa} yönünde ek sefer planlanması halinde "
        f"yaklaşık {t.tahmini_yolcu} yolcu biner (%95 güven: {t.alt_sinir}–{t.ust_sinir}). "
        f"İlgili saatte saatlik toplam yolcu sayısı {t.mevcut_saat_talep}."
    )


mudur_ozet_cumlesi = karar_ozet_cumlesi


def zaman_serisi_ozet(df: pd.DataFrame, yon: str) -> pd.DataFrame:
    seri = onbes_dakika_seri(df, yon)
    seri["hareketli_ort"] = seri["yolcu"].rolling(4, min_periods=1, center=True).mean().round(1)
    seri["yon"] = YON_ETIKET.get(yon, yon)
    return seri


def tarife_onerisi(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for yon in [YON_BES_USK, YON_USK_BES]:
        h = saatlik_seri(df, yon)
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
            rows.append(
                {
                    "yon": YON_ETIKET[yon],
                    "saat": f"{saat:02d}:00",
                    "saat_int": saat,
                    "talep": talep,
                    "talep_katsayisi": round(katsayi, 2),
                    "onerilen_frekans": frekans,
                    "saatte_sefer": sefer,
                    "sefer_basina_yolcu": max(1, round(talep / sefer)),
                }
            )
    return pd.DataFrame(rows)
