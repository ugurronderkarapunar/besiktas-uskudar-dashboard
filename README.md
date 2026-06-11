# Beşiktaş-Üsküdar Vapur Hattı Dashboard

Beşiktaş–Üsküdar vapur hattı yolcu hareket verisine dayalı interaktif karar destek paneli.

## Yerel çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır.

Windows: `BASLAT.bat` dosyasına çift tıklayın.

## Streamlit Cloud

Bu repo Streamlit Community Cloud ile deploy edilebilir. Ana dosya: `app.py`

## Sayfalar

- **Yönetici Brifingi** — Bulgu + ne anlama geliyor + operasyonel öneri
- **Genel Özet** — KPI ve özet bulgular
- **Yolcu Nereden Geliyor?** — Kaynak hat + saat×hat ısı haritası
- **Yolculuk Zinciri** — Önceki hat → Vapur → Sonraki hat
- **Bekleme Süresi** — İskelede bekleme analizi
- **Yolcu Profili** — Kart tipi, aktarma, gidiş-dönüş
- **Zaman Serisi** — 15 dk'lık talep deseni
- **Sefer Tahmini** — Ek sefer başına tahmini yolcu
- **Tarife Önerisi** — Yoğunluğa göre sefer sıklığı
- **Güvenilirlik Raporu** — İstatistiksel sınırlar

## Veri

Ham veri `data/veri.xlsx` dosyasında tutulur (Sayfa2).
