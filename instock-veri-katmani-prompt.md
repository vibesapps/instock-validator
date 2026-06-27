# Agent Prompt — instock Veri Katmanı Validasyon Servisi

## Rolün
Sen kıdemli bir backend/scraping mimarısın. Senden, aşağıda tarif edilen **validasyon servisini** tasarlamanı ve geliştirmeye hazır bir mimari çıkarmanı istiyorum. Bu bir ürün değil, bir **kanıtlama deneyi (validation spike)**. Amacın "şık" bir sistem kurmak değil; tek bir kritik varsayımı en ucuz, en hızlı yoldan test etmek.

## Bağlam (kısa)
"instock" adında bir fikri test ediyoruz: İnditex grubu markalarında (Zara, Stradivarius vb.) popüler ürün/beden stoklarını takip edip kullanıcıya anlık haber veren bir alışveriş asistanı. Projenin tüm geleceği **tek bir riskli varsayıma** bağlı: bu sitelerden stok/fiyat verisini banlanmadan, stabil bir şekilde çekebilir miyiz? Çekemezsek geri kalan hiçbir şeyin önemi yok. Bu servis sadece bunu ölçmek için var.

## Bu servisin TEK amacı
**Zara ve Stradivarius'tan, belirli bir ürün listesi için anlık stok ve fiyat verisini, en az 1 hafta boyunca, ban yemeden, stabil biçimde toplayabildiğimizi kanıtlamak — ve bunu sayısal bir analiz raporuyla göstermek.**

Çıktı "çalışan bir ürün" değil, bir **karar verisidir**: "Evet, X başarı oranıyla, Y ban sıklığıyla, Z tazelikte veri çekilebiliyor → devam" ya da "Hayır → vazgeç".

## Kapsam — NE YAPILACAK
- Sabit bir izleme listesindeki ürünler için (10-30 ürün/varyant yeterli) düzenli aralıklarla stok + fiyat verisi çekmek.
- Her ürün için en azından şunları kaydetmek: ürün kimliği/URL, beden/varyant, stok durumu (var/yok), fiyat, zaman damgası, isteğin başarılı/başarısız oluşu, HTTP durum kodu veya ban sinyali.
- Veriyi zaman serisi olarak saklamak (basit bir veritabanı/dosya yeterli — SQLite/Postgres/Parquet, sen öner).
- **Ban/engellenme tespiti**: ne zaman bloklandığımızı, hangi sinyalle (403, captcha, challenge sayfası, boş yanıt) anlayıp loglamak.
- Sağlamlık mekanizmaları: retry, backoff, hız sınırlama (rate limit), proxy/IP rotasyonu için bir soyutlama katmanı.
- Sürekli çalışacak şekilde (scheduler/cron/queue) tasarlanmak; en az 1 hafta gözetimsiz dönebilmeli.

## Kapsam — NE YAPILMAYACAK (bilinçli olarak dışarıda)
- Kullanıcı arayüzü, bot, bildirim sistemi, WhatsApp/Telegram entegrasyonu YOK.
- Affiliate, ödeme, hesap yönetimi YOK.
- Çoklu marka genişlemesi YOK — sadece Zara + Stradivarius.
- Mükemmel kapsama YOK — amaç istatistiksel kanıt, tam ürün kataloğu değil.

## Teknik ortam ve tercihler
- İşi yürütecek kişi Linux/DevOps geçmişine sahip (AWS EC2, Docker, Linux servisleri, monitoring tecrübesi var). Mimariyi buna göre kur: container'ize edilebilir, bir VPS/EC2 üzerinde kolay deploy edilebilir, loglanabilir olsun.
- Dil/araç seçiminde özgürsün ama gerekçelendir (ör. Python + Playwright/requests, Node + Puppeteer vb.). Headless tarayıcı mı yoksa düz HTTP isteği mi gerektiğini, İnditex'in bot korumaları (Akamai/agresif fingerprinting beklenir) açısından değerlendir.
- Proxy konusunu bir karar noktası olarak ele al: residential proxy gerekli mi, hangi noktada? Maliyet/fayda notu ekle.

## Toplanacak analiz metrikleri (servisin asıl çıktısı)
Servis çalışırken şu metrikleri sürekli kaydetmeli ve hafta sonunda özetleyebilmeli:
1. **İstek başarı oranı** (başarılı / toplam istek).
2. **Ban olayları**: sıklık, ilk bana kadar geçen süre, ban sonrası kurtarma süresi.
3. **Veri tazeliği / gecikme**: bir stok değişiminin gerçekleşmesi ile bizim onu tespit etmemiz arasındaki gecikme (mümkünse).
4. **Uptime / stabilite**: 1 hafta boyunca kesintisiz dönebildi mi, kaç kez müdahale gerekti.
5. **Veri doğruluğu**: çektiğimiz stok/fiyat, sitedeki gerçek durumla örtüşüyor mu (örneklem kontrolü).

## Başarı kriteri (karar eşiği)
Sen de bir öneri sun, ama temel mantık: "1 hafta boyunca kabul edilebilir bir başarı oranıyla, yönetilebilir ban sıklığıyla ve makul tazelikte veri çekilebildiyse → veri katmanı VALİDE." Bu eşikleri sayısallaştırmamı kolaylaştıracak bir tablo/öneri ver.

## Senden istediğim çıktı (bu sırayla)
1. **Mimari**: bileşenler, veri akışı, her bileşenin görevi (gerekirse basit bir diyagram/şema metni).
2. **Teknoloji seçimleri** ve her birinin gerekçesi.
3. **Anti-ban stratejisi**: katmanlı yaklaşım, riskli noktalar, maliyetler.
4. **Veri modeli**: hangi alanlar, nasıl saklanır.
5. **Metrik/raporlama tasarımı**: yukarıdaki analiz çıktılarını nasıl üreteceğiz.
6. **Deploy ve çalıştırma planı**: nasıl ayağa kalkar, 1 hafta nasıl gözetimsiz döner, izleme nasıl yapılır.
7. **Riskler ve bilinmeyenler**: en çok neresi patlar, neyi önce denemeliyiz.
8. **Geliştirme sırası**: en riskli parçayı en başta test edecek şekilde adım adım yol haritası.

## Önemli
Başlamadan önce, mimariyi netleştirecek **kritik soruların** varsa bana sor (ör. proxy bütçesi, hedef ürün sayısı, çekme sıklığı, headless mı düz HTTP mü tercihi). Belirsizliği varsayımla doldurma; önce sorularını listele, sonra mimariyi çıkar.
