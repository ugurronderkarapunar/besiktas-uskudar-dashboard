# -*- coding: utf-8 -*-
"""Veri yükleme, istatistik ve tahmin servisi."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time
from pathlib import Path
import warnings

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

    # ---------- Sütun adı eşleştirmeleri ----------
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

    # ---------- Zorunlu alan kontrolleri ve türetmeler ----------

    # 1. İşlem zamanı -> saat, tarih, dakika
    if "islem_zamani" not in df.columns:
        warnings.warn("'islem_zamani' sütunu yok. Zaman bilgisi üretilemiyor. Varsayılan 00:00 atanıyor.")
        df["islem_zamani"] = pd.NaT
    df["islem_zamani"] = pd.to_datetime(df["islem_zamani"], format="mixed", errors="coerce")
    df["tarih"] = df["islem_zamani"].dt.date
    df["saat"] = df["islem_zamani"].dt.hour.fillna(0).astype(int)
    df["dakika"] = df["islem_zamani"].dt.minute.fillna(0).astype(int)
    df["dakika_toplam"] = df["saat"] * 60 + df["dakika"]
    df["saat_dakika"] = df["islem_zamani"].dt.strftime("%H:%M")

    # 2. Yön bilgisi (olmazsa uygulama çalışamaz)
    if "yon" not in df.columns:
        raise KeyError("Excel'de 'yön' (veya 'yön') sütunu bulunamadı. Lütfen veri setini kontrol edin.")
    df["yon_etiket"] = df["yon"].map(YON_ETIKET)

    # 3. Anonim kart numarası (çok önemli, yoksa satır numarası kullan)
    if "kart_no" not in df.columns:
        warnings.warn("'kart_no' sütunu bulunamadı. Satır indisleri geçici kart numarası olarak kullanılacak.")
        df["kart_no"] = range(len(df))

    # 4. Önceki / sonraki hat
    for col in ("onceki_hat", "sonraki_hat"):
        if col in df.columns:
            df[col] = df[col].fillna("BİLİNMİYOR").astype(str).str.strip()
            df[col] = df[col].replace({"": "BİLİNMİYOR", "nan": "BİLİNMİYOR"})
        else:
            df[col] = "BİLİNMİYOR"

    # 5. Kart tipi
    if "kart_tipi" in df.columns:
        df["kart_tipi"] = df["kart_tipi"].fillna("Belirtilmemiş").astype(str).str.strip()
        df["kart_tipi"] = df["kart_tipi"].replace({"": "Belirtilmemiş", "nan": "Belirtilmemiş", "boş": "Belirtilmemiş"})
    else:
        df["kart_tipi"] = "Belirtilmemiş"

    # 6. Bekleme süresi (dk cinsinden)
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

    # 7. Önceki aktarma sayısı
    if "onceki_aktarma" in df.columns:
        df["onceki_aktarma"] = pd.to_numeric(df["onceki_aktarma"], errors="coerce").fillna(0).astype(int)
    else:
        df["onceki_aktarma"] = 0

    return df


# ================== Yardımcı fonksiyonlar ==================

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


def _filtre_yon(df: pd.DataFrame, yon: str | None) -> pd.DataFrame:
    return df if yon is None else df[df["yon"] == yon]


def bekleme_analizi(df: pd.DataFrame, yon: str | None = None) -> dict:
    sub = _filtre_yon(df, yon)
    if "bekleme_dk" not in sub.columns or sub["bekleme_dk"].isna().all():
        return {
            "ortalama_dk": 0,
            "medyan_dk": 0,
            "uzun_bekleme_yuzde": 0,
            "cok_uzun_yuzde": 0,
            "saatlik": pd.DataFrame(),
            "toplam": 0,
        }
    sub = sub.dropna(subset=["bekleme_dk"])
    sub = sub[sub["bekleme_dk"] >= 0]
    if sub.empty:
        return {
            "ortalama_dk": 0,
            "medyan_dk": 0,
            "uzun_bekleme_yuzde": 0,
            "cok_uzun_yuzde": 0,
            "saatlik": pd.DataFrame(),
            "toplam": 0,
        }

    saatlik = (
        sub.groupby("saat")["bekleme_dk"]
        .agg(ortalama="mean", medyan="median", yolcu="count")
        .reset_index()
        .round(1)
    )
    uzun = (sub["bekleme_dk"] >= 15).mean() * 100
    return {
        "ortalama_dk": round(sub["bekleme_dk"].mean(), 1),
        "medyan_dk": round(sub["bekleme_dk"].median(), 1),
        "uzun_bekleme_yuzde": round(uzun, 1),
        "cok_uzun_yuzde": round((sub["bekleme_dk"] >= 30).mean() * 100, 1),
        "saatlik": saatlik,
        "toplam": len(sub),
    }


def koridor_rotalari(df: pd.DataFrame, yon: str, top_n: int = 15) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    t = (
        sub.groupby(["onceki_hat", "sonraki_hat"])
        .size()
        .sort_values(ascending=False)
        .reset_index(name="yolcu")
    )
    t["koridor"] = t["onceki_hat"] + " → Vapur → " + t["sonraki_hat"]
    t["yuzde"] = (t["yolcu"] / len(sub) * 100).round(1)
    return t.head(top_n)


def kart_tipi_dagilimi(df: pd.DataFrame, yon: str | None = None) -> pd.DataFrame:
    sub = _filtre_yon(df, yon)
    t = sub.groupby("kart_tipi").size().sort_values(ascending=False).reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t


def kart_tipi_saatlik(df: pd.DataFrame, yon: str, top_tipler: int = 5) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    top = kart_tipi_dagilimi(sub).head(top_tipler)["kart_tipi"].tolist()
    sub = sub[sub["kart_tipi"].isin(top)]
    p = sub.groupby(["saat", "kart_tipi"]).size().reset_index(name="yolcu")
    return p


def aktarma_dagilimi(df: pd.DataFrame, yon: str | None = None) -> pd.DataFrame:
    sub = _filtre_yon(df, yon).copy()
    sub["aktarma_grup"] = sub["onceki_aktarma"].apply(
        lambda x: "Doğrudan (0 aktarma)" if x == 0 else "1 aktarma" if x == 1 else "2+ aktarma"
    )
    t = sub.groupby("aktarma_grup").size().reset_index(name="yolcu")
    t["yuzde"] = (t["yolcu"] / t["yolcu"].sum() * 100).round(1)
    return t


def gidis_donus_ozet(df: pd.DataFrame) -> dict:
    if "kart_no" not in df.columns:
        return {"toplam_benzersiz_kart": 0, "gidis_donus_kart": 0, "gidis_donus_yuzde": 0, "tek_yon_kart": 0}
    kart_yon = df.groupby("kart_no")["yon"].apply(set)
    cift = kart_yon[kart_yon.apply(lambda s: YON_BES_USK in s and YON_USK_BES in s)]
    toplam_kart = df["kart_no"].nunique()
    cift_say = len(cift)
    return {
        "toplam_benzersiz_kart": toplam_kart,
        "gidis_donus_kart": cift_say,
        "gidis_donus_yuzde": round(cift_say / toplam_kart * 100, 1) if toplam_kart else 0,
        "tek_yon_kart": toplam_kart - cift_say,
    }


def saat_kaynak_isi(df: pd.DataFrame, yon: str, top_hats: int = 10) -> pd.DataFrame:
    sub = df[df["yon"] == yon]
    top = kaynak_hatlar(sub, yon, top_hats)["onceki_hat"].tolist()
    sub = sub[sub["onceki_hat"].isin(top)]
    p = sub.pivot_table(index="onceki_hat", columns="saat", values="kart_no", aggfunc="count", fill_value=0)
    p = p.reindex(columns=range(24), fill_value=0)
    return p


def yonetici_bulgular(df: pd.DataFrame) -> list[dict]:
    """Yönetici brifingi için otomatik bulgular ve sade dilde açıklamalar."""
    bulgular = []
    bes_seri = saatlik_seri(df, YON_USK_BES)
    usk_seri = saatlik_seri(df, YON_BES_USK)
    if bes_seri.empty or usk_seri.empty:
        return [{
            "baslik": "Yetersiz veri",
            "bulgu": "Her iki yönde yeterli veri bulunamadı.",
            "anlam": "Analiz için en az bir yönde kayıt olmalı.",
            "oneri": "Veri setini kontrol edin.",
        }]

    bes_peak = bes_seri.loc[bes_seri["yolcu"].idxmax()]
    usk_peak = usk_seri.loc[usk_seri["yolcu"].idxmax()]
    bes_kaynak = kaynak_hatlar(df, YON_USK_BES, 1).iloc[0]
    usk_kaynak = kaynak_hatlar(df, YON_BES_USK, 1).iloc[0]

    bulgular.append({
        "baslik": "Beşiktaş sabah yoğunluğu Marmaray kaynaklı",
        "bulgu": (
            f"Beşiktaş'a gelen yolcuların %{bes_kaynak['yuzde']}'i "
            f"{bes_kaynak['onceki_hat']} hattından geliyor. Pik saat {int(bes_peak['saat']):02d}:00 "
            f"({int(bes_peak['yolcu']):,} yolcu)."
        ),
        "anlam": (
            "Sabah Beşiktaş iskelesine gelen yolcuların büyük bölümü Anadolu yakasından Marmaray ile geliyor. "
            "Vapur tek başına değil; demiryolu + vapur birlikte planlanmalı."
        ),
        "oneri": "07:30–08:30 arası Marmaray–vapur aktarma saatlerini senkronize edin.",
    })

    bulgular.append({
        "baslik": "Üsküdar akşam yoğunluğu dağınık Avrupa beslemesi",
        "bulgu": (
            f"Üsküdar'a gelenlerde 1. kaynak {usk_kaynak['onceki_hat']} (%{usk_kaynak['yuzde']}), "
            f"pik saat {int(usk_peak['saat']):02d}:00 ({int(usk_peak['yolcu']):,} yolcu)."
        ),
        "anlam": (
            "Akşam Üsküdar talebi tek bir hattan değil; Beşiktaş otobüsleri ve Taksim hatlarından besleniyor. "
            "Sadece vapur değil, karşı yakadaki otobüs seferleri de koordinasyon gerektirir."
        ),
        "oneri": "17:00–19:00 bandında Avrupa yakası besleyici hatlarla ortak tarife gözden geçirilsin.",
    })

    bekleme_bes = bekleme_analizi(df, YON_USK_BES)
    bulgular.append({
        "baslik": "İskele bekleme süresi",
        "bulgu": (
            f"Beşiktaş yönünde ortalama bekleme {bekleme_bes['ortalama_dk']} dk, "
            f"medyan {bekleme_bes['medyan_dk']} dk. "
            f"Yolcuların %{bekleme_bes['uzun_bekleme_yuzde']}'i 15 dakikadan fazla bekliyor."
        ),
        "anlam": (
            "Önceki araçtan indikten sonra vapur gelene kadar geçen süre. Uzun bekleme, "
            "yolcu memnuniyetini düşürür ve iskele kalabalığı yaratır."
        ),
        "oneri": "15+ dk bekleyen oranı yüksek saatlerde sefer sıklığını artırın.",
    })

    koridor = koridor_rotalari(df, YON_USK_BES, 1).iloc[0]
    bulgular.append({
        "baslik": "En yoğun yolculuk zinciri",
        "bulgu": (
            f"En sık rota: {koridor['onceki_hat']} → Vapur → {koridor['sonraki_hat']} "
            f"({int(koridor['yolcu']):,} yolcu, %{koridor['yuzde']})."
        ),
        "anlam": (
            "Yolcu sadece vapura binmiyor; önce bir hat, sonra vapur, sonra başka bir hat kullanıyor. "
            "Ulaşım planlaması bu üçlü zincir üzerinden yapılmalı."
        ),
        "oneri": "Bu koridor için aktarma noktalarında bilgilendirme ve sefer uyumu güçlendirilsin.",
    })

    kart = kart_tipi_dagilimi(df, YON_USK_BES).iloc[0]
    bulgular.append({
        "baslik": "Yolcu profili (kart tipi)",
        "bulgu": f"Beşiktaş yönünde en yaygın kart tipi: {kart['kart_tipi']} (%{kart['yuzde']}).",
        "anlam": (
            "Öğrenci, tam veya abonman yoğunluğu; tarife ve kampanya kararlarında "
            "hangi segmentin etkileneceğini gösterir."
        ),
        "oneri": "Pik saatlerde baskın segmente göre kapasite ve iletişim planı yapın.",
    })

    aktarma = aktarma_dagilimi(df, YON_USK_BES)
    dogrudan = aktarma[aktarma["aktarma_grup"].str.contains("Doğrudan")]
    dogrudan_pct = float(dogrudan["yuzde"].iloc[0]) if not dogrudan.empty else 0
    bulgular.append({
        "baslik": "Aktarma derinliği",
        "bulgu": f"Beşiktaş yönünde yolcuların %{dogrudan_pct}'i vapura doğrudan geliyor (öncesinde aktarma yok).",
        "anlam": (
            "Kalan kısım en az bir aktarma yapıyor; uzak koridorlardan gelen yolcu "
            "zamanında vapur kaçırma riski taşır."
        ),
        "oneri": "Çok aktarmalı yolcular için aktarma sürelerini vapur tarifesiyle hizalayın.",
    })

    gd = gidis_donus_ozet(df)
    bulgular.append({
        "baslik": "Gidiş-dönüş yolcuları",
        "bulgu": (
            f"Benzersiz {gd['toplam_benzersiz_kart']:,} kartın %{gd['gidis_donus_yuzde']}'i "
            f"aynı gün hem gidiş hem dönüş yapmış."
        ),
        "anlam": (
            "Bu yolcular pendler (işe gidip dönen); sabah ve akşam sefer planı simetrik olmayabilir "
            "ama iki yön de birbirini besler."
        ),
        "oneri": "Sabah Beşiktaş, akşam Üsküdar piklerini birlikte değerlendirin.",
    })

    ozet = veri_ozeti(df)
    bulgular.append({
        "baslik": "Veri kapsamı sınırı",
        "bulgu": f"Analiz {ozet['tarih_baslangic']} tarihli tek günlük veriye dayanıyor ({ozet['toplam_kayit']:,} kayıt).",
        "anlam": (
            "Bugünkü bulgular o günün fotoğrafıdır. Tatil, hava, etkinlik ve hafta sonu farkı "
            "henüz modele girmedi."
        ),
        "oneri": "4–8 haftalık veriyle hafta içi/sonu ve mevsimsel planlama yapılabilir.",
    })

    return bulgular
