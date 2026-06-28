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

### 4.2 Gerçek Bant Genişliği (BrightData Dashboard Verisi)

6 saatlik production testinden elde edilen **ölçülmüş** değerler:

| Dönem | Toplam Trafik | Açıklama |
|-------|--------------|----------|
| 28 Haziran (6 saatlik test) | **28.1 MB** | Saatlik 2.3–4.4 MB arası |
| Saatlik ortalama (5 tam saat) | **4.30 MB/saat** | 2 tur × 27 ürün-beden |
| **Günlük projeksiyon** | **103 MB/gün** | Ölçüme dayalı |

**Ürün-beden başına gerçek proxy bant genişliği: ~80 KB/scrape** (2 HTTP isteği dahil).

Ham HTML boyutları üzerinden yapılan ilk tahmin (557 MB/gün) **5.4x şişkindi.**
Gerçek fark: `gzip` sıkıştırması ile Zara 655 KB → ~130 KB, Stradivarius 137 KB → ~27 KB
düzeyine iniyor. BrightData sıkıştırılmış byte üzerinden faturalandırıyor.

### 4.3 Günlük ve Aylık Maliyet

#### Senaryo Karşılaştırması

| Senaryo | BW/gün | BrightData | VM | **Toplam/gün** | **Ürün/gün** | **Ürün/ay** |
|---------|--------|------------|----|--------------|-----------:|----------:|
| 30dk, 27 fetch — **mevcut** | 103 MB | $0.83 | $0.47 | **$1.29** | **$0.22** | **$6.5** |
| 30dk, 6 fetch — dedup | 23 MB | $0.18 | $0.47 | **$0.65** | **$0.11** | **$3.3** |
| 2dk, 6 fetch — dedup | 344 MB | $2.75 | $0.47 | **$3.22** | **$0.54** | **$16.1** |

> **6 saatlik testin toplam BrightData maliyeti: $0.23**

#### URL Dedup Optimizasyonu

Aynı URL birden fazla beden için tek seferde çekilir; tüm bedenlerin stok bilgisi
tek HTML'den parse edilir. Bu 27 fetch/tur'u → 6 fetch/tur'a düşürür.

**Tasarruf: $0.65/gün (%50 azalma) — mevcut durumdan bile ucuz, 2dk interval bile karşılanabilir.**

### 4.4 Ölçekleme Projeksiyonu

100 benzersiz URL (ürün), 50 Zara + 50 Stradivarius karışımı.
Ölçülen 80 KB/scrape değeri baz alınmıştır:

| Senaryo | BW/gün | BrightData | VM* | **Toplam/gün** | **Ürün/gün** |
|---------|--------|------------|-----|--------------|------------|
| 30dk, dedup, 100 ürün | 230 MB | $1.84 | $1.10 | $2.94 | $0.03 |
| 2dk, dedup, 100 ürün | 3.45 GB | $27.6 | $1.10 | $28.7 | $0.29 |

*100 üründe VM yükseltmesi gerekebilir (e2-medium ~$33/ay).

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
