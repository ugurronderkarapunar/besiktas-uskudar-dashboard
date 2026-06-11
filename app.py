# -*- coding: utf-8 -*-
"""Beşiktaş-Üsküdar Vapur Hattı — Yönetici Dashboard (Streamlit)."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_service import (
    YON_BES_USK,
    YON_USK_BES,
    guvenilirlik_raporu,
    kaynak_hatlar,
    load_data,
    karar_ozet_cumlesi,
    saatlik_seri,
    tahmin_sefer_yolcu,
    tarife_onerisi,
    veri_ozeti,
    zaman_serisi_ozet,
)

st.set_page_config(
    page_title="Beşiktaş-Üsküdar Hat Analizi",
    page_icon="⛴️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title { font-size: 1.9rem; font-weight: 700; color: #1d3557; margin-bottom: 0; }
    .sub-title { color: #6c757d; font-size: 1rem; margin-top: 4px; }
    .kpi-box {
        background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
        color: white; padding: 1.2rem; border-radius: 12px; text-align: center;
    }
    .kpi-box h2 { margin: 0; font-size: 2rem; }
    .kpi-box p { margin: 4px 0 0; opacity: 0.9; font-size: 0.85rem; }
    .ozet-kutu {
        background: #fff3cd; border-left: 5px solid #e63946;
        padding: 1rem 1.2rem; border-radius: 8px; font-size: 1.05rem;
        line-height: 1.6; color: #333;
    }
    .guven-iyi { color: #2d6a4f; font-weight: 600; }
    .guven-orta { color: #e9c46a; font-weight: 600; }
    .guven-sinirli { color: #e63946; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Veri yükleniyor...")
def get_data():
    return load_data()


df = get_data()
ozet = veri_ozeti(df)

# --- Sidebar ---
st.sidebar.markdown("## ⛴️ Menü")
sayfa = st.sidebar.radio(
    "Sayfa seçin",
    [
        "🏠 Genel Özet",
        "📍 Yolcu Nereden Geliyor?",
        "📈 Zaman Serisi Analizi",
        "🎯 Sefer Tahmini (Saat X'e kaç yolcu?)",
        "🕐 Tarife Önerisi",
        "✅ Güvenilirlik Raporu",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Veri Bilgisi")
st.sidebar.metric("Toplam Kayıt", f"{ozet['toplam_kayit']:,}")
st.sidebar.metric("Analiz Günü", ozet["tarih_baslangic"])
st.sidebar.caption(f"Beşiktaş→Üsküdar: {ozet['bes_usk']:,} | Üsküdar→Beşiktaş: {ozet['usk_bes']:,}")

# --- Sayfalar ---
if sayfa == "🏠 Genel Özet":
    st.markdown('<p class="main-title">Beşiktaş – Üsküdar Vapur Hattı Yönetici Özeti</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Tek günlük yolcu hareket verisine dayalı karar destek paneli</p>', unsafe_allow_html=True)
    st.markdown("")

    bes_peak = saatlik_seri(df, YON_USK_BES).loc[saatlik_seri(df, YON_USK_BES)["yolcu"].idxmax()]
    usk_peak = saatlik_seri(df, YON_BES_USK).loc[saatlik_seri(df, YON_BES_USK)["yolcu"].idxmax()]
    bes_kaynak = kaynak_hatlar(df, YON_USK_BES, 1).iloc[0]
    usk_kaynak = kaynak_hatlar(df, YON_BES_USK, 1).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="kpi-box"><h2>{int(bes_peak["saat"]):02d}:00</h2><p>Beşiktaş pik saati</p></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="kpi-box"><h2>{int(bes_peak["yolcu"]):,}</h2><p>Beşiktaş pik yolcu</p></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="kpi-box"><h2>{int(usk_peak["saat"]):02d}:00</h2><p>Üsküdar pik saati</p></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="kpi-box"><h2>{int(usk_peak["yolcu"]):,}</h2><p>Üsküdar pik yolcu</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Yönetici Özet Bulguları")
    st.markdown(
        f'<div class="ozet-kutu">'
        f"<b>Beşiktaş'a gelen yolcu:</b> En çok <b>{bes_kaynak['onceki_hat']}</b> hattından geliyor "
        f"({int(bes_kaynak['yolcu']):,} yolcu, %{bes_kaynak['yuzde']}). "
        f"En yoğun saat <b>{int(bes_peak['saat']):02d}:00</b> ({int(bes_peak['yolcu']):,} yolcu)."
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")
    st.markdown(
        f'<div class="ozet-kutu">'
        f"<b>Üsküdar'a gelen yolcu:</b> En çok <b>{usk_kaynak['onceki_hat']}</b> hattından geliyor "
        f"({int(usk_kaynak['yolcu']):,} yolcu, %{usk_kaynak['yuzde']}). "
        f"En yoğun saat <b>{int(usk_peak['saat']):02d}:00</b> ({int(usk_peak['yolcu']):,} yolcu)."
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Saatlik Talep Karşılaştırması")
    h1 = saatlik_seri(df, YON_USK_BES).assign(tip="Üsküdar→Beşiktaş (Beşiktaş'a gelen)")
    h2 = saatlik_seri(df, YON_BES_USK).assign(tip="Beşiktaş→Üsküdar (Üsküdar'a gelen)")
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
        peak = saatlik_seri(df, yon).loc[saatlik_seri(df, yon)["yolcu"].idxmax()]
        st.info(
            f"**En yoğun saat:** {int(peak['saat']):02d}:00 — {int(peak['yolcu']):,} yolcu\n\n"
            f"**1. kaynak hat:** {kaynak.iloc[0]['onceki_hat']} (%{kaynak.iloc[0]['yuzde']})"
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
    st.dataframe(saatlik_seri(df, yon), use_container_width=True, hide_index=True)

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
    st.markdown(f'<div class="ozet-kutu">{cumle}</div>', unsafe_allow_html=True)

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

    # Karşılaştırma: farklı saatler
    st.markdown("#### Saat Bazlı Tahmin Karşılaştırması")
    kars = []
    for h in range(24):
        t = tahmin_sefer_yolcu(df, yon, h, 0)
        kars.append({"saat": f"{h:02d}:00", "tahmin": t.tahmini_yolcu, "alt": t.alt_sinir, "ust": t.ust_sinir})
    kdf = pd.DataFrame(kars)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["tahmin"], mode="lines+markers", name="Tahmin", line=dict(color="#e63946", width=2)))
    fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["ust"], mode="lines", name="Üst sınır", line=dict(dash="dot", color="#aaa")))
    fig.add_trace(go.Scatter(x=kdf["saat"], y=kdf["alt"], mode="lines", name="Alt sınır", fill="tonexty", line=dict(dash="dot", color="#aaa")))
    fig.update_layout(title="24 Saat Sefer Başına Tahmini Yolcu", template="plotly_white", height=380, xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

elif sayfa == "🕐 Tarife Önerisi":
    st.markdown('<p class="main-title">Optimal Sefer Tarifesi Önerisi</p>', unsafe_allow_html=True)
    tarife = tarife_onerisi(df)
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

elif sayfa == "✅ Güvenilirlik Raporu":
    st.markdown('<p class="main-title">İstatistiksel Güvenilirlik</p>', unsafe_allow_html=True)
    st.caption("Bu analizlerin ne kadar güvenilir olduğu ve sınırları")

    rapor = guvenilirlik_raporu(df)
    for _, row in rapor.iterrows():
        seviye = row["Güven Seviyesi"]
        css = "guven-iyi" if seviye == "Güçlü" else "guven-orta" if seviye in ("Orta", "Orta güven", "Kullanılabilir") else "guven-sinirli"
        st.markdown(f"**{row['Kriter']}** — <span class='{css}'>{seviye}</span>", unsafe_allow_html=True)
        st.write(f"_{row['Durum']}_ — {row['Açıklama']}")
        st.markdown("")

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
