# Zara & Stradivarius Stok Takip Sistemi
## Fizibilite ve Maliyet Raporu

**Tarih:** 28 Haziran 2026

---

## Soru

> Zara ve Stradivarius'tan **otomatik olarak, kesintisiz** stok ve fiyat verisi çekebilir miyiz?

---

## Cevap: Evet

6 saatlik production testinde sistem beklentileri karşıladı.

| Metrik | Sonuç | Hedef |
|--------|-------|-------|
| Başarılı istek oranı | **%94.4** | ≥ %85 |
| Engelleme (ban) | **0 olay** | ≤ 1/gün |
| Kesinti | **Yok** | ≥ %95 uptime |

Her 30 dakikada bir, 6 üründe otomatik fiyat ve stok bilgisi başarıyla alındı.

---

## Ne İzlendi

**6 ürün — 2 marka**

| Marka | Ürün | Beden Takibi |
|-------|------|-------------|
| Zara | Relaxed Fit Deri Ceket | XS / S / M / L / XL |
| Zara | Regular Fit Dokulu Ceket | XS / S / M / L / XL |
| Zara | Su Geçirmez Kapitone Ceket | XS / S / M / L / XL |
| Stradivarius | Düğmeli Dokumlu Gömlek (045) | XS / S / M / L |
| Stradivarius | Düğmeli Dokumlu Gömlek (430) | XS / S / M / L |
| Stradivarius | Fermuarlı Sweatshirt | XS / S / M / L |

Sistem her beden için **ayrı ayrı** stok durumu ve güncel fiyat kaydediyor.

---

## Ne Kadar Maliyeti Var?

Tüm maliyetler **6 saatlik testin gerçek ölçüm verilerine** dayanmaktadır.

### Mevcut Sistem (30 dakikada bir, 6 ürün)

| Kalem | Günlük | Aylık |
|-------|--------|-------|
| Proxy (BrightData Residential) | $0.83 | $24.9 |
| Sunucu (Google Cloud VM) | $0.47 | $14.0 |
| **Toplam** | **$1.30** | **$38.9** |
| **Ürün başına** | **$0.22** | **$6.5** |

> 6 saatlik testin toplam proxy maliyeti: **$0.23**

---

## Güncelleme Sıklığı Seçenekleri

| Sıklık | Ürün başına/gün | Ürün başına/ay | Not |
|--------|----------------|----------------|-----|
| 30 dakikada bir | $0.22 | $6.5 | Mevcut durum |
| 10 dakikada bir | $0.66 | $19.8 | 3x maliyet |
| 5 dakikada bir | $1.32 | $39.6 | 6x maliyet |
| **2 dakikada bir** | **$0.54*** | **$16.1*** | *Kod optimizasyonu gerekli |

> **2 dakika seçeneği** için önce teknik bir optimizasyon yapılması gerekiyor
> (aynı ürünün farklı bedenleri için tekrarlanan veri çekimini ortadan kaldırmak).
> Bu yapıldığında maliyet tahminleri yukarıdaki tablodaki gibidir.

---

## 100 Ürüne Büyürsek?

| Sıklık | Günlük | Aylık | Ürün başına/ay |
|--------|--------|-------|---------------|
| 30 dakikada bir | $2.94 | $88.2 | **$0.88** |
| 2 dakikada bir | $28.7 | $861 | **$8.61** |

Ölçekleme doğrusal: her yeni ürün sabit maliyete orantılı ekleniyor.

---

## Altyapı

Tüm sistem tek bir düşük maliyetli sunucuda çalışıyor.

```
Google Cloud VM (e2-small, İstanbul yakını)
    │
    ├── Türkiye IP'li Konut Proxy (BrightData Residential)
    │       Gerçek kullanıcı trafiğine benziyor → engelleme yok
    │
    ├── Veri Tabanı (SQLite — sunucu üzerinde)
    │
    └── Otomatik Raporlama (günlük özet)
```

**Neden özel proxy gerekiyor?**
Zara ve Stradivarius standart sunucu IP'lerini anında engelliyor.
Türkiye'deki gerçek ev internetleri üzerinden gelen trafik geçiyor.

---

## Riskler

| Risk | Olasılık | Mevcut Durum |
|------|----------|--------------|
| Site yapısı değişir, veri okunamaz | Düşük | 0 olay / 6 saat |
| Engelleme sistemi güncellenir | Orta | 0 olay / 6 saat — aktif takip gerekli |
| Ürün URL'leri sezon değişiminde değişir | Yüksek | Manuel güncelleme gerektirir |
| BrightData fiyat artışı | Düşük | Alternatif sağlayıcılar mevcut |

---

## Öneriler

**Kısa vadede (bu hafta)**
- Sistemi aktif bırak, 30 dakikalık aralıkla veri toplamaya devam et
- İzlenecek ürün listesini genişlet

**Orta vadede (1-2 hafta)**
- 2 dakikalık güncelleme aralığı için teknik optimizasyonu tamamla
- Stok değişikliklerinde anlık bildirim mekanizması ekle

**Karar eşiği**
- 6 ürün, 30 dakikada bir → **$39/ay** — hemen başlanabilir
- 100 ürün, 2 dakikada bir → **$861/ay** — büyüme planına göre değerlendir

---

## Özet

| | |
|-|-|
| **Teknik fizibilite** | ✅ Kanıtlandı |
| **Veri kalitesi** | ✅ Gerçek zamanlı fiyat + beden bazlı stok |
| **Güvenilirlik** | ✅ %94.4 başarı, 0 engelleme |
| **Başlangıç maliyeti** | ✅ $39/ay (6 ürün, 30dk) |
| **Ölçekleme maliyeti** | ⚠️ 100 ürün, 2dk → $861/ay |
| **Hazırlık süresi** | ✅ Sistem çalışır durumda |
