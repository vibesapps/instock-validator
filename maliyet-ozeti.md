# instock.ai — Ne Kadara Mal Olur?

Hazırlayan: Claude · 22 Haziran 2026

---

## Ne yapıyoruz, kısaca

Zara ve Stradivarius'taki ürünlerin stoklarını otomatik takip eden bir sistem kuruyoruz.
Sistem her 30 dakikada bir bu sitelere giriyor, "Bu beden hâlâ var mı?" diye kontrol ediyor ve sonuçları kaydediyor.

Bu aşamada amacımız tek bir soruyu cevaplamak:
**Bu siteleri düzenli takip edebilir miyiz, yoksa sistem engellenip kapı mı gösterilir?**

---

## Masraf nelerden oluşuyor?

İki kalemden oluşuyor:

### 1. Sunucu (Sistemin çalıştığı bilgisayar)
Sistemin 7/24 açık kalması için bir yerde çalışması gerekiyor.
Bunu kendi bilgisayarımızda çalıştırmak yerine internetteki bir sunucuya kuruyoruz.

### 2. Proxy (İnternet kimliği)
Zara ve Stradivarius'un sistemleri, aynı IP adresinden çok fazla istek gelirse
o IP'yi engelliyor — tıpkı bir kapıcının "sen bugün çok geldin, gir bakalım" demesi gibi.
Proxy, her seferinde farklı bir IP adresiyle siteye giriyormuş gibi görünmemizi sağlıyor.

---

## Senaryo 1 — Ücretsiz Başlangıç

**Sunucu:** Oracle (büyük bir teknoloji şirketi) ücretsiz sunucu veriyor, sonsuza kadar.
**Proxy:** Yok — kendi IP'mizden giriyoruz.

| | Haftalık | Aylık |
|--|---------|-------|
| Sunucu | $0 | $0 |
| Proxy | $0 | $0 |
| **Toplam** | **$0** | **$0** |

**Risk:** Zara/Stradivarius sistemimizi fark edip engelleyebilir.
Engellenirsek veriler gelmeyi durdurur ama paramız yanmaz.
**"Deneyip görme" aşaması için en mantıklı başlangıç.**

---

## Senaryo 2 — Düşük Maliyetli Koruma

**Sunucu:** Yine ücretsiz Oracle sunucusu.
**Proxy:** Orta kaliteli, gerçek ev internet bağlantılarından geçen bir servis.
_(IPRoyal adında bir şirket bu hizmeti veriyor — aylık kullanıma göre ödeme yapılıyor)_

| | Haftalık | Aylık |
|--|---------|-------|
| Sunucu | $0 | $0 |
| Proxy | ~$2.50 | ~$10.50 |
| **Toplam** | **~$2.50** | **~$10.50** |

**Risk:** Düşük-orta. Büyük ihtimalle 1 hafta boyunca sorunsuz çalışır.
**Validasyon testi için önerilen senaryo.**

---

## Senaryo 3 — Güvenli

**Sunucu:** Yine ücretsiz Oracle sunucusu.
**Proxy:** Dünyanın en büyük proxy sağlayıcısı BrightData — Zara gibi sıkı güvenlikli sitelerde bile çalışmasıyla biliniyor.

| | Haftalık | Aylık |
|--|---------|-------|
| Sunucu | $0 | $0 |
| Proxy | ~$7 | ~$29 |
| **Toplam** | **~$7** | **~$29** |

**Risk:** Çok düşük. "Kesin çalışsın" istiyorsan bu senaryo.

---

## Önerimiz: Sırayla Dene, Gereksiz Harcama Yapma

```
1. Hafta → Ücretsiz başla ($0)
      ↓
   Engellendik mi?
      ↓ Evet
2. Hafta → $10.50/ay'lık proxy dene
      ↓
   Hâlâ sorun var mı?
      ↓ Evet
3. Hafta → $29/ay'lık güvenli proxy'e geç
      ↓
   1 hafta sorunsuz geçtiyse → DEVAM kararı
```

**1 haftalık testin toplam maliyeti:**
- İyi senaryo (engellenmezse): **$0**
- Gerçekçi senaryo: **$2.50 – $7**

---

## Eğer sistem çalışırsa, sonraki aşamada ne değişir?

Bu aşama sadece "çalışır mı?" sorusunu cevaplıyor.
Eğer cevap "evet" ise ve ürünü gerçekten kullanıcılara sunmaya karar verirsek,
maliyetler biraz artar çünkü daha fazla ürün takip ederiz ve bildirim sistemi ekleriz.

Ama o hesabı şimdi yapmaya gerek yok.
**Önce bu testin sonucunu görelim.**

---

*Bu belge teknik detayları içermemektedir. Teknik maliyet analizi için bkz: dahili doküman.*
