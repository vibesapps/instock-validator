# instock.ai — Veri Katmanı Validasyon Spike Raporu

**Tarih:** 28 Haziran 2026  
**Kapsam:** 6 saatlik production testi + maliyet analizi  
**Soru:** Zara ve Stradivarius'tan ban yemeden düzenli stok/fiyat verisi çekebilir miyiz?

---

## 1. Yönetici Özeti

**Sonuç: DEVAM.**

6 saatlik production testinde iki temel kriter yeşil: istek başarı oranı %94.4, ban sayısı sıfır.
Akamai bot koruması httpx + bm-verify bypass yöntemiyle aşıldı.

Maliyet: mevcut implementasyonda **ürün başına $0.79/gün**, basit bir optimizasyon sonrası **$0.24/gün**.

---

## 2. Test Sonuçları

### 2.1 Teknik Doğrulama

| Metrik | Değer | Eşik | Sonuç |
|--------|-------|------|-------|
| İstek başarı oranı | %94.4 | ≥%85 | 🟢 GREEN |
| Ban olayı/gün | 0.00 | ≤1.0 | 🟢 GREEN |
| Uptime (test süresi) | Kesintisiz 6 saat | ≥%95 | 🟢 GREEN |

### 2.2 Veri Kalitesi

| Site | Fiyat | Stok | Yöntem |
|------|-------|------|--------|
| Zara | ✓ TRY (örn. 4.490 TL) | ✓ Var/Yok | HTML regex (`"price":`) |
| Stradivarius | ✓ TRY (örn. 790 TL) | ✓ Var/Yok | JSON-LD `@type=Product` |

### 2.3 Performans

- **Scrape süresi (ürün başına):** ~10-15 saniye (6s bm-verify bekleme + ağ gecikmesi)
- **Tur süresi (27 ürün-beden):** ~10-11 dakika
- **Güncelleme sıklığı:** 30 dakikada bir

---

## 3. Teknik Çözüm

### 3.1 Sorun

Zara ve Stradivarius Akamai bot koruması kullanıyor. İlk istekte `~2KB` HTML interstitial
döndürülüyor. İçindeki `/_sec/verify` XHR sunucu tarafında doğrulanıyor; taklit edilemiyor.
Firefox/Playwright + BrightData MITM kombinasyonunda bu XHR başarısız oluyor → sonsuz reload
döngüsü → veri yok.

### 3.2 Çözüm

`bm-verify` token'ı Akamai sunucusu tarafından HTML'e gömülüyor — JavaScript gerektirmiyor.
httpx (tarayıcısız) ile:

1. GET ürün sayfası → interstitial HTML
2. HTML'den `bm-verify` URL'ini parse et
3. 6 saniye bekle (Akamai'nin timing window'u)
4. Aynı sticky IP ile GET bm-verify URL → gerçek sayfa

Her ürün isteği kendi sticky session'ında (aynı çıkış IP'si) çalışıyor.

---

## 4. Maliyet Analizi

### 4.1 Parametreler

| Parametre | Değer |
|-----------|-------|
| Toplam ürün | 6 (3 Zara + 3 Stradivarius) |
| Toplam ürün-beden çifti | 27 (15 Zara + 12 Stradivarius) |
| Benzersiz URL sayısı | 6 |
| Scrape aralığı | 30 dakika → 48 tur/gün |
| Zara sayfa boyutu (ham) | ~655 KB |
| Stradivarius sayfa boyutu (ham) | ~137 KB |
| Akamai interstitial boyutu | ~2.3 KB |
| BrightData fiyatı | $8 / GB |
| VM fiyatı (GCE e2-small) | $14 / ay |

### 4.2 Günlük Bant Genişliği Hesabı

**Mevcut implementasyon:** 27 ürün-beden çifti → 27 ayrı fetch/tur.
Aynı URL 4-5 kez (her beden için bir kez) çekiliyor.

| Kaynak | Hesap | Bant genişliği |
|--------|-------|----------------|
| 15 Zara fetch/tur | 15 × (2.3 + 655) KB | 9.9 MB/tur |
| 12 Stradivarius fetch/tur | 12 × (2.3 + 137) KB | 1.7 MB/tur |
| **Tur başına toplam** | | **11.6 MB** |
| **Günlük (48 tur)** | 48 × 11.6 MB | **~557 MB** |

> Not: Hesap ham HTML boyutları üzerinden yapılmıştır (worst-case). BrightData sıkıştırılmış
> byte üzerinden faturalandırıyorsa gerçek kullanım %20-30 daha düşük olabilir.

### 4.3 Günlük ve Aylık Maliyet

#### Mevcut Durum

| Kalem | Günlük | Aylık |
|-------|--------|-------|
| BrightData (0.557 GB × $8) | $4.46 | $133.8 |
| GCE e2-small VM | $0.47 | $14.0 |
| **Toplam** | **$4.93** | **$147.8** |
| **Ürün başına** | **$0.82** | **$24.6** |
| **Ürün-beden başına** | **$0.18** | **$5.5** |

#### Optimizasyon Sonrası (URL Deduplication)

**Aynı URL birden fazla beden için tek seferde çekilir; tüm bedenlerin stok bilgisi
tek HTML'den parse edilir.** Bu 6 fetch/tur'a düşürür (27 yerine).

| Kalem | Günlük | Aylık |
|-------|--------|-------|
| BrightData (0.124 GB × $8) | $0.99 | $29.7 |
| GCE e2-small VM | $0.47 | $14.0 |
| **Toplam** | **$1.46** | **$43.7** |
| **Ürün başına** | **$0.24** | **$7.3** |
| **Ürün-beden başına** | **$0.05** | **$1.6** |

**Tasarruf: $3.47/gün (%70 azalma) — kod değişikliği bir günlük iş.**

### 4.4 Ölçekleme Projeksiyonu

100 ürün, her biri ortalama 4.5 beden → 450 product-size pair, 100 benzersiz URL.
50 Zara + 50 Stradivarius karışımı varsayılarak:

| Senaryo | BrightData (günlük) | VM | Toplam/gün | Ürün başına/gün |
|---------|--------------------|----|------------|-----------------|
| Mevcut (dedup yok) | $59.3 | $0.47 | $59.8 | $0.60 |
| Optimize (dedup) | $13.2 | $0.47* | $13.7 | $0.14 |

*100 üründe VM'in yükseltilmesi gerekebilir (e2-medium: ~$33/ay → $1.10/gün).

---

## 5. Risk Değerlendirmesi

| Risk | Olasılık | Etki | Önlem |
|------|----------|------|-------|
| Akamai bm-verify mekanizması değişir | Orta | Yüksek | Hata alertı; alternatif: WASM bypass |
| BrightData IP kalitesi düşer | Düşük | Orta | Birden fazla zone/provider |
| Zara HTML yapısı değişir | Düşük | Düşük | Regex geniş; JSON-LD yoksa test uyarır |
| BrightData kredisi biter | Düşük | Yüksek | Günlük kullanım monitörü |
| Ürün URL'leri sezon değiştirir | Yüksek | Düşük | Manuel güncellik kontrolü |

---

## 6. Öneriler

### Öncelik 1 — Hemen (0 iş günü)
- **Servisi production'da aktif bırak.** Kriterler yeşil.

### Öncelik 2 — Bu hafta (1 iş günü)
- **URL deduplication:** Aynı URL birden fazla beden için tek seferde çekilsin.
  `scrape_all()` içinde URL bazlı gruplama + tek HTML'den tüm bedenleri parse etme.
  Maliyet etkisi: $4.93/gün → $1.46/gün (%70 tasarruf).

### Öncelik 3 — Bu ay (2-3 iş günü)
- **BrightData kullanım alertı:** Günlük bant genişliğini logla; eşik aşılınca bildirim gönder.
- **Ürün URL yenileme:** Sezon değişimlerini yakalamak için ürün sayfası 404 tespiti ekle.
- **Rapor penceresi:** `report.py`'de `--since` bayrağı servise özgü başlangıç zamanına otomatik baksın.

---

## 7. Karar

**DEVAM.**

Teknik fizibilite kanıtlandı. Maliyet makul: mevcut haliyle ürün başı $0.82/gün,
basit optimizasyon sonrası $0.24/gün. 100 ürüne ölçeklendiğinde optimize maliyet $0.14/ürün/gün.

Veri katmanı production kullanımına hazır.
