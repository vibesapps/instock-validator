# instock.ai — Mimari Kararlar ve Deploy Süreci

_Hazırlanma tarihi: 27 Haziran 2026 — Son güncelleme: 28 Haziran 2026_

---

## Proje Amacı

Bir haftalık veri katmanı validasyon spike'ı. Tek soru:
**Zara ve Stradivarius'tan ban yemeden düzenli stok/fiyat verisi çekebilir miyiz?**

Bu belge cevap değil, hedefe giden yolda alınan teknik kararları belgeler.

---

## Mimari Özeti

```
[APScheduler 30dk]
      │
      ▼
[httpx AsyncClient]
      │  ① GET ürün sayfası → Akamai interstitial (~2KB)
      │  ② bm-verify URL'i HTML'den parse et
      │  ③ 6s bekle
      │  ④ GET bm-verify URL (aynı sticky IP) → gerçek HTML
      ▼
[BrightData Residential Proxy - TR, sticky session]
      │
      ▼
[Zara / Stradivarius]
      │  JSON-LD @type=Product → price + availability
      │  veya regex "price": "..." → fallback
      ▼
[SQLite WAL — data/instock.db]
      │
      ▼
[summary.py — 6 saatte bir rapor]
```

---

## Alınan Kararlar ve Gerekçeler

### 1. Scraper: httpx (Browser'dan geçildi)

**Karar:** Playwright/Firefox kaldırıldı. Tüm scraping `httpx.AsyncClient` ile yapılıyor.

**Neden browser'dan vazgeçildi — Akamai analizi:**

Hem Zara hem Stradivarius Akamai bot koruması kullanıyor. İnceleme sırasında
şu akış tespit edildi:

1. İlk GET isteğine Akamai, `~2KB` HTML interstitial döndürüyor (HTTP 200).
2. Interstitial'da senkron XHR var: `xhr.open("POST", "/_sec/verify?provider=interstitial", false)`.
3. XHR başarılı olursa `<meta http-equiv="refresh" content="5; URL='...?bm-verify=TOKEN'>` meta-refresh'i tetikliyor.
4. XHR başarısız olursa `catch(e) { window.location.reload(); }` → sonsuz reload döngüsü.

BrightData'nın standart HTTP MITM proxy'si XHR'ı bozuyor:
- TLS fingerprint değiştiğinden Akamai sunucu tarafında `_sec/verify` doğrulamasını reddediyor
- Bu, fake 200 döndürme, reload() engelleme, sticky session gibi tüm client-side yaklaşımları işe yaramıyor

**Çözüm — bm-verify bypass:**

Kritik keşif: `bm-verify` token'ı **JavaScript tarafından üretilmiyor**, Akamai sunucusu tarafından
HTML'e gömlüyor. Dolayısıyla httpx ile şu akış çalışıyor:

```
GET ürün sayfası  →  interstitial HTML (bm-verify token'ı içinde)
                            │
                    token'ı HTML'den parse et
                            │
                         6s bekle
                            │
GET bm-verify URL  →  gerçek ürün sayfası ✓
```

Şart: her iki istek **aynı exit IP**'den gelmeli (sticky session).
httpx'te XHR olmadığından `/_sec/verify` hiç çağrılmıyor; Akamai token'ı IP tutarlılığına
bakarak doğruluyor.

**Smoke test sonuçları (28 Haziran 2026):**
| Site | success | price | in_stock | süre |
|------|---------|-------|----------|------|
| Zara | True | 4490 TRY | True | 14.4s |
| Stradivarius | True | 790 TRY | True | 10.2s |

**Denenen ve çalışmayan yaklaşımlar:**

| Yaklaşım | Sonuç | Neden |
|----------|-------|-------|
| Firefox + BrightData MITM | Sonsuz reload | XHR sunucu doğrulaması başarısız |
| Sticky session (Firefox) | Sonsuz reload | TLS MITM sorununu çözmüyor |
| `_sec/verify` fake intercept | Sonsuz interstitial | Akamai sunucu tarafında doğruluyor |
| `window.location.reload` engelleme | Çalışmıyor | Reload başka mekanizmalarla da tetikleniyor |
| itxrest REST API (product ID) | 404 | URL'deki referans no ≠ itxrest internal ID |
| httpx direkt ürün sayfası | Akamai interstitial | Aynı bm-verify token akışı gerekli |
| httpx + bm-verify follow | **✓ ÇALIŞIYOR** | Token IP-bound, sticky session yeterli |

---

### 2. Proxy: BrightData Residential (Türkiye IP, Sticky Session)

**Karar:** BrightData residential proxy, Türkiye ülke kodu + sticky session zorunlu.

**Neden sticky session:**
bm-verify token'ı, Akamai tarafından istek yapan IP'ye bağlanıyor. İki ardışık istek
farklı exit IP'den gelirse token geçersizleşiyor. BrightData username'e
`-session-RANDOM` eklenerek her browser context kendi sticky IP'sini alıyor.

Kullanılan format:
```
http://brd-customer-XXX-zone-instock-country-tr-session-abc123:PASS@brd.superproxy.io:33335
```

**Neden Türkiye IP'si:**
Zara TR ve Stradivarius TR, Türkiye kaynaklı trafiğe daha az şüpheyle yaklaşıyor.
Username'e `-country-tr` eklenerek BrightData'dan TR IP havuzu seçiliyor.

**Not — MITM artık sorun değil:**
httpx ile `verify=False` kullanılıyor. BrightData'nın SSL MITM'i artık XHR'ı bozmadığı
için sorun çıkarmıyor; sadece sertifika doğrulamasını devre dışı bırakıyoruz.

**Maliyet:** Pay-as-you-go, $8/GB. Bir haftalık test için tahmini $2–5.

---

### 3. Veri Çıkarma: JSON-LD + Regex Fallback

**Karar:** `parse_product_data()` önce JSON-LD `@type=Product`, sonra regex ile arama yapıyor.

**Stradivarius:** JSON-LD içinde `offers.price` ve `offers.availability` doğrudan geliyor:
```json
{
  "@type": "Product",
  "offers": {
    "priceCurrency": "TRY",
    "price": "790",
    "availability": "http://schema.org/InStock"
  }
}
```

**Zara:** JSON-LD yok, 655KB HTML içindeki `"price": "4490"` pattern'ını
`parse_price_from_text()` regex'i buluyor. Availability aynı şekilde regex ile.

**Boyut karşılaştırması:**
| | Interstitial | Gerçek sayfa |
|--|-------------|-------------|
| Zara | 2.3 KB | 655 KB |
| Stradivarius | 2.3 KB | 137 KB |

---

### 4. Altyapı: GCE e2-small + Docker Compose

**Karar:** Google Cloud Engine e2-small VM (2GB RAM), tek container, Docker Compose.

**httpx geçişinin altyapıya etkisi:**
Firefox/Playwright kaldırıldığında RAM tüketimi önemli ölçüde düştü (~600MB tasarruf).
e2-micro'ya (1GB) geçiş değerlendirilebilir ama mevcut e2-small stabil çalışıyor.

**Neden Cloud Run / GKE değil:**
- SQLite dosyası kalıcı volume gerektiriyor → Cloud Run'ın ephemeral filesystem'i uygun değil.
- APScheduler uzun-süre çalışan bir süreç → Cloud Run'ın request-based model'i uygun değil.

**Maliyet:** ~$14/ay (e2-small).

---

### 5. Veri Katmanı: SQLite WAL Mode

**Karar:** SQLite, WAL (Write-Ahead Logging) modu.

**Neden:**
Sıfır altyapı maliyeti. WAL modu eş zamanlı okuma-yazma'ya izin veriyor
(scraper yazar, report.py okur). Veri `data/instock.db` dosyasında,
Docker volume ile host'ta kalıcı.

---

## Deploy Akışı

```
Lokal → GitHub push
           │
    git pull (VM)
           │
    docker compose run --rm instock-validator python scripts/smoke_test.py
           │ (her iki site OK mu?)
           ▼
    docker compose up -d

Güncelleme (sadece kod değişti, requirements.txt değişmedi):
    git pull   # scripts/ ve src/ volume-mount olduğundan yeterli

Güncelleme (requirements.txt değişti):
    git pull && docker compose up -d --build
```

---

## Başarı Kriterleri (6 Saatlik Test)

| Renk | Kriter |
|------|--------|
| 🟢 GREEN | success_rate ≥ 85%, ban/saat ≤ 0.16 (günlük 4), uptime ≥ 95% |
| 🟡 YELLOW | success_rate 60-85%, ban/saat 0.16-0.5, uptime 85-95% |
| 🔴 RED | Herhangi biri altında → veri katmanı bu haliyle çalışmaz |

6 saat = ~12 scrape turu. Her tur 6 ürün × ortalama 5 beden = 30 istek.
Her istek ~10-15s (6s bm-verify wait + 8-20s random delay).

---

## Açık Riskler

1. **bm-verify token ömrü** — Token'ın geçerlilik süresi bilinmiyor. 6s yeterli görünüyor
   ama ağ gecikmesi artarsa sürenin uzatılması gerekebilir.
2. **IP rotasyonu ve bm-verify** — BrightData sticky session tutarlı IP sağlıyor ama
   oturum süresi dolduğunda yeni token almak gerekecek (mevcut flow zaten her istekte
   yeni sticky session açıyor, sorun yok).
3. **Zara veri kalitesi** — Zara JSON-LD kullanmıyor, HTML'deki regex ile price bulunuyor.
   Zara sayfa yapısı değişirse regex güncellemesi gerekebilir.
4. **Akamai bm-verify mekanizması** — Akamai bu token doğrulama yöntemini güncellerse
   (IP dışında JS challenge eklenirse) bypass çalışmayabilir.
5. **Ürün URL stabilitesi** — Zara/Stradivarius ürünleri sezonda değişiyor. Takip listesi
   manuel güncelleme gerektiriyor.
6. **SQLite ölçeklenebilirliği** — Yüzlerce ürün eklenirse performans düşebilir.
   Validasyon için sorun değil.
