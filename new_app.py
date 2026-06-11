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

# ---------- CSS (okunurluk garantili) ----------
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
    """Yönetici brifingi kartı: bulgu + sade açıklama + öneri."""
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

# --- Sidebar ---
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
        "🔮 What-If Analizi",        # Yeni
        "🗺️ Rota Haritası",          # Yeni
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Veri Bilgisi")
st.sidebar.metric("Toplam Kayıt", f"{ozet['toplam_kayit']:,}")
st.sidebar.metric("Analiz Günü", ozet["tarih_baslangic"])
st.sidebar.caption(f"Beşiktaş→Üsküdar: {ozet['bes_usk']:,} | Üsküdar→Beşiktaş: {ozet['usk_bes']:,}")

# --- Sayfalar (genişletilmiş) ---
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

        # Mevcut tarife önerisinden saatlik sefer sayısını alalım
        tarife = tarife_onerisi(df)
        tsub = tarife[(tarife["yon"] == yon_label) & (tarife["saat_int"] == saat)]

        if tsub.empty:
            st.warning("Bu saat için tarife verisi bulunamadı.")
        else:
            base_sefer = int(tsub.iloc[0]["saatte_sefer"])
            saatlik_talep = int(tsub.iloc[0]["talep"])

            st.markdown(f"**Mevcut durum:** Saatte **{base_sefer}** sefer, toplam **{saatlik_talep}** yolcu")

            # Kullanıcıdan yüzde değişim iste
            degisim = st.slider("Sefer sayısındaki değişim (%)", -50, 100, 0, 10, key="whatif_pct")
            yeni_sefer = max(1, round(base_sefer * (1 + degisim / 100)))

            # Yeni durum hesapla
            headway_min = 60 / yeni_sefer               # dakika cinsinden sefer aralığı
            ortalama_bekleme = headway_min / 2          # basit kuyruk modeli
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
                "ortalama bekleme = sefer aralığı / 2 olarak hesaplanmıştır. Gerçek değerler farklılık gösterebilir."
            )

    elif sayfa == "🗺️ Rota Haritası":
        st.markdown('<p class="main-title">Vapur Hattı ve Bağlantı Haritası</p>', unsafe_allow_html=True)
        st.caption("Beşiktaş – Üsküdar arası feribot güzergâhı")

        # Koordinatlar (yaklaşık)
        besiktas_lat, besiktas_lon = 41.0441, 29.0063
        uskudar_lat, uskudar_lon = 41.0258, 29.0156

        # Harita oluştur
        fig = go.Figure()

        # Vapur rotası çizgisi
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon, uskudar_lon],
            lat=[besiktas_lat, uskudar_lat],
            mode='lines',
            line=dict(width=4, color='#1d3557'),
            name='Vapur Hattı'
        ))

        # Beşiktaş iskelesi
        fig.add_trace(go.Scattermapbox(
            lon=[besiktas_lon],
            lat=[besiktas_lat],
            mode='markers+text',
            marker=dict(size=14, color='#e63946'),
            text=['Beşiktaş'],
            textposition='top right',
            name='Beşiktaş İskelesi'
        ))

        # Üsküdar iskelesi
        fig.add_trace(go.Scattermapbox(
            lon=[uskudar_lon],
            lat=[uskudar_lat],
            mode='markers+text',
            marker=dict(size=14, color='#457b9d'),
            text=['Üsküdar'],
            textposition='top left',
            name='Üsküdar İskelesi'
        ))

        # Önemli aktarma noktalarını da haritaya ekleyelim (Marmaray, Metro vb.)
        # Örnek: Marmaray Üsküdar istasyonu yakını
        marmaray_lat, marmaray_lon = 41.0250, 29.0150
        fig.add_trace(go.Scattermapbox(
            lon=[marmaray_lon],
            lat=[marmaray_lat],
            mode='markers',
            marker=dict(size=8, color='#ffa500', symbol='triangle'),
            name='Marmaray Üsküdar'
        ))

        # Harita düzeni
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

        st.markdown("---")
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
