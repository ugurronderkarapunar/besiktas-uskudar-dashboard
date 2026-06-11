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

- **Genel Özet** — KPI ve yönetici özet bulguları
- **Yolcu Nereden Geliyor?** — Kaynak hat analizi
- **Zaman Serisi** — 15 dk'lık talep deseni
- **Sefer Tahmini** — Ek sefer başına tahmini yolcu
- **Tarife Önerisi** — Yoğunluğa göre sefer sıklığı
- **Güvenilirlik Raporu** — İstatistiksel sınırlar

## Veri

Ham veri `data/veri.xlsx` dosyasında tutulur (Sayfa2).
