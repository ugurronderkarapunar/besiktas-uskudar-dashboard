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
    aktarma_dagilimi,
    bekleme_analizi,
    gidis_donus_ozet,
    guvenilirlik_raporu,
    kart_tipi_dagilimi,
    kart_tipi_saatlik,
    kaynak_hatlar,
    koridor_rotalari,
    load_data,
    karar_ozet_cumlesi,
    saat_kaynak_isi,
    saatlik_seri,
    tahmin_sefer_yolcu,
    tarife_onerisi,
    veri_ozeti,
    yonetici_bulgular,
    zaman_serisi_ozet,
)

st.set_page_config(
    page_title="Beşiktaş-Üsküdar Hat Analizi",
    page_icon="⛴️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- CSS ----------
st.markdown(
    """
    <style>
    .main-title { font-size: 1.9rem; font-weight: 700; color: #1d3557; margin-bottom: 0; }
    .sub-title { color: #4a4a4a; font-size: 1rem; margin-top: 4px; }
    .kpi-box {
        background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
        color: white; padding: 1.2rem; border-radius: 12px; text-align: center;
    }
    .kpi-box h2 { margin: 0; font-size: 2rem; color: white; }
    .kpi-box p { margin: 4px 0 0; opacity: 0.9; font-size: 0.85rem; color: white; }
    .ozet-kutu {
        background: #fff3cd; border-left: 5px solid #e63946;
        padding: 1rem 1.2rem; border-radius: 8px; font-size: 1.05rem;
        line-height: 1.6; color: #222;
    }
    .guven-iyi { color: #2d6a4f; font-weight: 600; }
    .guven-orta { color: #b8860b; font-weight: 600; }
    .guven-sinirli { color: #b22222; font-weight: 600; }
    .anlam-kutu {
        background: #e8f4fd; border-left: 5px solid #457b9d;
        padding: 0.9rem 1.1rem; border-radius: 8px; margin: 0.5rem 0;
        color: #222;
    }
    .oneri-kutu {
        background: #e8f5e9; border-left: 5px solid #2d6a4f;
        padding: 0.9rem 1.1rem; border-radius: 8px; margin: 0.5rem 0;
        color: #222;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def bulgu_karti(b: dict) -> None:
    st.markdown(f"#### {b['baslik']}")
    st.markdown(f'<div class="ozet-kutu"><b>Bulgumuz:</b> {b["bulgu"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="anlam-kutu"><b>Bu ne anlama geliyor?</b><br>{b["anlam"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="oneri-kutu"><b>Operasyonel öneri:</b> {b["oneri"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")


@st.cache_data(show_spinner="Veri yükleniyor...")
def get_data():
    return load_data()


df = get_data()
ozet = veri_ozeti(df)

# --- Sidebar (önemli: yeni sayfalar eklendi) ---
st.sidebar.markdown("## ⛴️ Menü")
sayfa = st.sidebar.radio(
    "Sayfa seçin",
    [
        "📋 Yönetici Brifingi",
        "🏠 Genel Özet",
        "📍 Yolcu Nereden Geliyor?",
        "🔗 Yolculuk Zinciri",
        "⏱️ Bekleme Süresi",
        "👥 Yolcu Profili",
        "📈 Zaman Serisi Analizi",
        "🎯 Sefer Tahmini (Saat X'e kaç yolcu?)",
        "🕐 Tarife Önerisi",
        "✅ Güvenilirlik Raporu",
        "🔮 What-If Analizi",        # ← yeni
        "🗺️ Rota Haritası",          # ← yeni
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Veri Bilgisi")
st.sidebar.metric("Toplam Kayıt", f"{ozet['toplam_kayit']:,}")
st.sidebar.metric("Analiz Günü", ozet["tarih_baslangic"])
st.sidebar.caption(f"Beşiktaş→Üsküdar: {ozet['bes_usk']:,} | Üsküdar→Beşiktaş: {ozet['usk_bes']:,}")

# --- Sayfalar ---
try:
    if sayfa == "📋 Yönetici Brifingi":
        st.markdown('<p class="main-title">Yönetici Brifingi — Öne Çıkan Bulgular</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">Her bulgu: veri → ne anlama geliyor → ne yapılmalı</p>', unsafe_allow_html=True)
        bulgular = yonetici_bulgular(df)
        if bulgular and isinstance(bulgular, list):
            for b in bulgular:
                bulgu_karti(b)
        else:
            st.warning("Henüz yönetici özeti oluşturulamadı.")

    elif sayfa == "🏠 Genel Özet":
        # ... (daha önceki Genel Özet sayfası kodları aynen)
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
        # ... (önceki kod aynen)
        pass

    elif sayfa == "🔗 Yolculuk Zinciri":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "⏱️ Bekleme Süresi":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "👥 Yolcu Profili":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "📈 Zaman Serisi Analizi":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "🎯 Sefer Tahmini (Saat X'e kaç yolcu?)":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "🕐 Tarife Önerisi":
        # ... (önceki kod aynen)
        pass

    elif sayfa == "✅ Güvenilirlik Raporu":
        # ... (önceki kod aynen)
        pass

    # ------------------ YENİ SAYFALAR ------------------
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
        st.markdown('<p class="main-title">Vapur Hattı ve Bağlantı Haritası</p>', unsafe_allow_html=True)
        st.caption("Beşiktaş – Üsküdar arası feribot güzergâhı")

        besiktas_lat, besiktas_lon = 41.0441, 29.0063
        uskudar_lat, uskudar_lon = 41.0258, 29.0156

        fig = go.Figure()
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon, uskudar_lon],
            lat=[besiktas_lat, uskudar_lat],
            mode='lines',
            line=dict(width=4, color='#1d3557'),
            name='Vapur Hattı'
        ))
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon],
            lat=[besiktas_lat],
            mode='markers+text',
            marker=dict(size=14, color='#e63946'),
            text=['Beşiktaş'],
            textposition='top right',
            name='Beşiktaş İskelesi'
        ))
        fig.add_trace(go.Scattermapbox(
            lon=[uskudar_lon],
            lat=[uskudar_lat],
            mode='markers+text',
            marker=dict(size=14, color='#457b9d'),
            text=['Üsküdar'],
            textposition='top left',
            name='Üsküdar İskelesi'
        ))
        # Marmaray Üsküdar
        marmaray_lat, marmaray_lon = 41.0250, 29.0150
        fig.add_trace(go.Scattermapbox(
            lon=[marmaray_lon],
            lat=[marmaray_lat],
            mode='markers',
            marker=dict(size=8, color='#ffa500', symbol='triangle'),
            name='Marmaray Üsküdar'
        ))

        fig.update_layout(
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=(besiktas_lat + uskudar_lat) / 2,
                            lon=(besiktas_lon + uskudar_lon) / 2),
                zoom=12
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=550,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            '<div class="anlam-kutu"><b>Harita hakkında:</b><br>'
            "Haritada Beşiktaş ve Üsküdar iskeleleri ile vapur rotası gösterilmektedir. "
            "Turuncu üçgen Marmaray Üsküdar istasyonunu işaret eder. "
            "Entegrasyon planlaması için kritik bir aktarma noktasıdır.</div>",
            unsafe_allow_html=True,
        )

except Exception as e:
    st.error(f"Bir hata oluştu: {str(e)}")
    st.exception(e)
