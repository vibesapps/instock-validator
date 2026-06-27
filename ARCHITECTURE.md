# instock.ai — Mimari Kararlar ve Deploy Süreci

_Hazırlanma tarihi: 27 Haziran 2026_

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
[Firefox (Playwright)]
      │
      ▼
[BrightData Residential Proxy - TR]
      │
      ▼
[Zara / Stradivarius]
      │
      ▼
[SQLite WAL — data/instock.db]
      │
      ▼
[summary.py — 6 saatte bir rapor]
```

---

## Alınan Kararlar ve Gerekçeler

### 1. Tarayıcı: Firefox (Chromium'dan geçildi)

**Karar:** Playwright ile Firefox headless.

**Neden Chromium'dan geçildi:**
Zara ve Stradivarius Akamai bot koruması kullanıyor. Akamai, HTTP isteği gelmeden önce TLS handshake'i (JA3/JA4 parmak izi) inceliyor. Headless Chromium'un TLS parmak izi Akamai'nin engelliyor; bu yüzden `playwright-stealth` veya `--disable-blink-features` gibi JavaScript seviyesindeki önlemler işe yaramıyor. Firefox'un TLS parmak izi farklı ve henüz engel listesinde yok. Geçiş sonucu: 403 → 200.

**Alternatif değerlendirilenler:**
- `playwright-stealth` → Sadece JS katmanını etkiliyor, TLS'e dokunmuyor. Etkisiz.
- Chromium + `--no-zygote` / `--single-process` → Renderer crash'lerine yol açıyor.
- BrightData Scraping Browser → Daha pahalı premium ürün, bu aşamada overkill.

---

### 2. Proxy: BrightData Residential (Türkiye IP)

**Karar:** BrightData residential proxy, Türkiye ülke kodu zorunlu.

**Neden gerekli:**
GCP datacenter IP'leri Akamai tarafından anında tanınıp bloklanıyor (HTTP 403). Residential proxy, gerçek bir Türk kullanıcı gibi görünmesini sağlıyor.

**Neden Türkiye IP'si:**
Zara TR ve Stradivarius TR, Türkiye kaynaklı trafiğe daha az şüpheyle yaklaşıyor. Username'e `-country-tr` eklenerek BrightData'dan TR IP havuzu seçiliyor.

**Maliyet:** Pay-as-you-go, $8/GB. Bir haftalık test için tahmini $2–5.

**Proxy URL formatı:**
```
http://brd-customer-XXX-zone-instock-country-tr:PASS@brd.superproxy.io:33335
```

**Teknik not:** Playwright proxy config'i `{"server": "http://host:port", "username": "...", "password": "..."}` formatında bekliyor. URL içine gömülü credential (`user:pass@host`) çalışmıyor → `ProxyManager.next()` bunu parse edip ayırıyor.

---

### 3. SSL: `ignore_https_errors=True`

**Karar:** Playwright context'inde HTTPS hataları görmezden geliniyor.

**Neden:**
BrightData, HTTPS trafiğini kendi sertifikasıyla intercept ediyor (MITM proxy). Chromium/Firefox bu sertifikayı tanımıyor ve `ERR_CERT_AUTHORITY_INVALID` hatası veriyor. Scraping use case'inde bu güvenlik riski değil — zaten public web sitelerini çekiyoruz.

**Alternatif:** BrightData CA sertifikasını sisteme kurmak. Fazla karmaşık, fayda yok.

---

### 4. `wait_until`: `networkidle` → `domcontentloaded`

**Karar:** `page.goto()` çağrısında `wait_until="domcontentloaded"` kullanılıyor.

**Neden:**
`networkidle` Akamai'nin challenge JavaScript'inin tüm arka plan isteklerini bitirmesini bekliyor. Bu asla bitmediği için 30 saniye timeout doluyordu. `domcontentloaded` ana HTML gelince devam ediyor — ban tespiti için yeterli, ürün verisi için de yeterli.

---

### 5. Altyapı: GCE e2-small + Docker Compose

**Karar:** Google Cloud Engine e2-small VM (2GB RAM), tek container, Docker Compose.

**Neden Cloud Run / GKE değil:**
- SQLite dosyası kalıcı volume gerektiriyor → Cloud Run'ın ephemeral filesystem'i uygun değil.
- APScheduler uzun-süre çalışan bir süreç → Cloud Run'ın request-based model'i uygun değil.
- GKE bu aşama için overkill.

**Neden e2-micro değil:**
Firefox headless bellek tüketimi ~600-800MB. e2-micro (1GB RAM) + OS overhead → OOM. e2-small (2GB RAM) yeterli.

**Maliyet:** ~$14/ay.

---

### 6. Veri Katmanı: SQLite WAL Mode

**Karar:** SQLite, WAL (Write-Ahead Logging) modu.

**Neden:**
Sıfır altyapı maliyeti. Validasyon spike'ı için PostgreSQL/MySQL gereksiz. WAL modu eş zamanlı okuma-yazma'ya izin veriyor (scraper yazar, report.py okur). Veri `data/instock.db` dosyasında, Docker volume ile host'ta kalıcı.

---

## Deploy Akışı

```
Lokal → GitHub push
           │
    git pull (VM)
           │
    docker compose run --build (test)
           │
    docker compose up -d (servis)
```

Güncelleme için:
```bash
git pull && docker compose up -d --build
```

---

## Başarı Kriterleri (6 Saatlik Test)

| Renk | Kriter |
|------|--------|
| 🟢 GREEN | success_rate ≥ 85%, ban/saat ≤ 0.16 (günlük 4), uptime ≥ 95% |
| 🟡 YELLOW | success_rate 60-85%, ban/saat 0.16-0.5, uptime 85-95% |
| 🔴 RED | Herhangi biri altında → veri katmanı bu haliyle çalışmaz |

6 saat = ~12 scrape turu. Her tur 2 site × ürün sayısı istek.

---

## Açık Riskler

1. **BrightData free tier IP kalitesi** — Free krediler biterken IP havuzu daralabilir. Gerçek ücretli kullanımda test edilmedi.
2. **Firefox parmak izi** — Akamai sürekli güncelleniyor. Firefox'u da tanımaya başlarsa yeni bir yaklaşım gerekir.
3. **Ürün URL stabilitesi** — Zara/Stradivarius ürünleri sezonda değişiyor. Takip listesi manuel güncelleme gerektiriyor.
4. **SQLite ölçeklenebilirliği** — Yüzlerce ürün eklenirse performans düşebilir. Validasyon için sorun değil.
