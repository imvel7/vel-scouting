# VEL SCOUTING — Puanlama Çıpaları Kalibrasyon Test Protokolü

**Doküman:** VEL-CALIB-01 · **Sürüm:** 1.0 (taslak) · **Tarih:** 24 Kasım 2026
**Kapsam:** Bek/kanat bek, defansif/merkez orta saha, hücumcu orta saha/10 numara, kanat, santrfor ve kaleci puanlama çıpaları (stoper çıpaları da aynı protokolle doğrulanır).
**Durum kuralı:** Bu protokol tamamlanıp sonuçlar kayda geçmeden hiçbir çıpa belgesi "nihai" sayılmaz ve hiçbir rol Supabase rubriğine yüklenmez. Altı rol belgesi **TASLAK** olarak kalır.

> Aşağıdaki eşik değerleri **önerilen başlangıç değerleridir**; futbol uzmanı ve metodoloji sahibi tarafından onaylanmadan karar ölçütü olarak kullanılmaz.

## 1. Amaç

Çıpaların, farklı değerlendiricilerin aynı maç davranışına benzer puan vermesini sağlayıp sağlamadığını ölçmek; belirsiz veya ayırt etmeyen ifadeleri bulup düzeltmek.

Bu protokol oyuncu kalitesini değil, **belgenin güvenilirliğini** ölçer.

## 2. Roller

| Rol | Görev | Not |
|---|---|---|
| Metodoloji sahibi | Protokolü onaylar, eşikleri belirler, çıpa değişikliklerini kabul eder | Değerlendirici olarak puan vermez |
| Değerlendiriciler (en az 3, tercihen 4–5) | Bağımsız puanlar | Çıpa belgesini yazan kişi değerlendirici olmaz; en az biri o pozisyonda deneyimli olmalı |
| Kalibrasyon yöneticisi | Klipleri hazırlar, kodlar, veriyi toplar, analizi yapar | Puan vermez |
| Hakem (adjudicator) | Anlaşmazlık oturumunu yönetir | Kendi puanını gerekçe için kullanmaz |

## 3. Materyal ve hukuki sınırlar

1. Yalnızca **hakları değerlendirilmiş** videolar kullanılır (`video_rights_assessments` kaydı olan ve kullanım amacına izin veren). Hak durumu belirsiz video kullanılmaz.
2. **Genç oyuncu verisi veya Afriskaut görüntüsü kullanılmaz.** Kalibrasyon, gizlilik kontrol listesindeki kapılar geçilene kadar yetişkin ve yasal olarak kullanılabilir kaynaklarla yapılır.
3. Videolar indirilip paylaşılmaz; mevcut kayıt ve erişim koşulları geçerlidir. Bağlantının varlığı kullanım izni değildir.
4. Oyuncu kimlikleri kodlanır; değerlendiriciye isim, takım skoru veya sonuç bilgisi verilmez (maç sonucu bilmek puanı etkiler).

## 4. Örneklem tasarımı (rol başına)

| Öğe | Öneri | Gerekçe |
|---|---|---|
| Oyuncu-maç birimi | En az 12 farklı oyuncu-maç, en az 6 farklı maç | Tek maça veya tek oyuncuya bağımlılığı azaltır |
| Kalite çeşitliliği | Bilinçli olarak zayıf, orta ve güçlü performans içeren birimler | Tüm puan bandının kullanıldığını görmek için |
| Rol çeşitliliği | Metodolojideki rol profillerinden en az ikisi | Rol bağımlı çıpaların testi |
| Rakip ve bağlam | Farklı rakip düzeyleri ve maç durumları | Bağlamı ayırma kuralının testi |
| Video türü | Tam maç öncelikli; klip yalnızca kıyas amaçlı ayrı etiketle | Kanıt seviyesi kuralları |
| Gözlem süresi | Her birim için aynı süre veya aynı olay penceresi | Değerlendirici yükü eşit olsun |

Her kriterin **yeterli fırsat** içeren birimlerde test edilmesi gerekir; fırsat yoksa o kriter için N/E beklenir ve bu bir uyuşmazlık sayılmaz.

## 5. Adımlar

1. **Eğitim (1 oturum):** Ortak çerçeve, rol metodolojisi ve çıpa belgesi okunur. Eğitim klibi puanlanmaz; kriter sözlüğü tartışılır. Eğitimde kullanılan klipler testte kullanılmaz.
2. **Pilot puanlama (2–3 birim):** Yalnızca prosedür ve form hatalarını bulmak için. Sonuçlar analize girmez.
3. **Bağımsız puanlama:** Her değerlendirici her birimi, her kriter için `1–10`, `N/E` veya `N/A` (gerekçeyle) olarak puanlar. Her puan için **zaman damgalı gözlem** ve kısa gerekçe yazılır (üretimdeki kurallarla aynı: 9–10 için daha güçlü kanıt). Değerlendiriciler birbiriyle konuşmaz.
4. **Veri toplama:** Mevcut oturum modeli kullanılabilir, ancak kalibrasyon oturumları **ayrı etiketli test kayıtlarıdır**; gerçek oyuncu raporlarına karıştırılmaz ve rapora dönüştürülmez.
5. **Analiz:** Bölüm 6.
6. **Anlaşmazlık oturumu:** Bölüm 7.
7. **Çıpa revizyonu ve yeniden test:** Bölüm 8.
8. **Karar ve kayıt:** Bölüm 9.

## 6. Analiz

Hesaplamalar kriter bazında ve alan (kategori) bazında yapılır. Hesabı yapan betik bu repoda test edilmiş olmalı ve gerçek veriden önce sentetik veriyle doğrulanmalıdır.

| Ölçü | Tanım | Başlangıç eşiği (öneri) |
|---|---|---|
| Uyum (ağırlıklı kappa veya ICC) | Değerlendiriciler arası puan uyumu | ≥ 0,60 kabul edilebilir; ≥ 0,75 iyi |
| Mutlak fark | Aynı birimde en yüksek ve en düşük puan arasındaki fark | Birimlerin en az %80'inde ≤ 2 puan |
| Bant uyumu | Puanların aynı çıpa bandına (1–2, 3–4, 5–6, 7–8, 9, 10) düşme oranı | ≥ %70 |
| N/E ve N/A tutarlılığı | Değerlendiricilerin aynı birimde aynı durumu seçmesi | ≥ %80 |
| Bant kullanımı | Kullanılan puan bantları dağılımı | 9–10 yalnızca kanıtlı birimlerde; zayıf birimlerde 1–4 görülmeli |
| Ayırt edicilik | Önceden bilinen zayıf ve güçlü birimlerin ayrışması | Güçlü grup ortalaması zayıf gruptan anlamlı yüksek |

Küçük örneklemde istatistik güven aralığı geniştir; bu yüzden sonuç tek bir sayı ile değil, **güven aralığı ve alt grup dökümü** ile raporlanır. Eşik karşılanmayan kriter "yeniden yazılacak" listesine girer.

## 7. Anlaşmazlık oturumu

- Fark ≥ 3 puan olan veya farklı bantlara düşen kriter/birimler listelenir.
- Hakem, her değerlendiriciden zaman damgalı kanıtı sırayla ister; puan değiştirme baskı altında yapılmaz.
- Sonuç iki türden biri olarak kaydedilir: (a) **değerlendirici hatası** (çıpa doğru, uygulama yanlış), (b) **çıpa sorunu** (ifade belirsiz, çakışıyor veya rol bağlamını kapsamıyor).
- Yalnızca (b) türü çıpa metnini değiştirir; her değişiklik gerekçeyle sürüm notuna yazılır.

## 8. Revizyon ve yeniden test

- Revize edilen çıpalar yeni sürüm numarası alır (örneğin `1.1`) ve eski sürüm korunur; eski sürümle üretilmiş raporlar eski sürümü göstermeye devam eder.
- Yeniden test **yeni** oyuncu-maç birimleriyle yapılır (aynı birimleri görmek öğrenme etkisi yaratır).
- En fazla iki revizyon turundan sonra eşik karşılanmıyorsa kriter ya birleştirilir, ya yeniden tanımlanır ya da metodoloji sahibine döndürülür.

## 9. Kabul ve kayıt

Bir rol, ancak aşağıdakilerin hepsi doğruysa "pilot" durumuna alınabilir:

1. Uzman incelemesi yazılı olarak kayıtlı.
2. Bölüm 6 eşikleri kriterlerin en az %90'ında karşılandı; karşılanmayan kriterler için gerekçeli kabul kararı var.
3. Test verisi, betik, sonuç tablosu ve karar tutanağı repoda (kişisel veri ve video içeriği olmadan) saklı.
4. Rubrik yükleme migration'ı geri alınan işlemde test edildi; geri alma yolu yazılı.
5. Metodoloji sahibi durumu açıkça "pilot" olarak onayladı.

"Pilot" durumu da nihai değildir: gerçek kullanımda ilk 20 raporun gözden geçirilmesi ve ikinci bir kalibrasyon turu zorunludur.

## 10. Bilinen sınırlar

- Küçük gruplarla yapılan test, belgenin bütün pozisyon ve rakip koşullarında güvenilir olduğunu kanıtlamaz.
- Değerlendiriciler arası uyum, puanın **doğruluğunu** değil **tutarlılığını** gösterir; doğruluk için ayrıca uzman referans puanı gerekir.
- Kaleci çıpalarında fırsat azlığı N/E oranını yükseltir; bu oran ayrıca raporlanır.
- Hak durumu uygun yeterli video bulunamazsa test ertelenir; eksik materyal başka kaynaktan "tahminle" doldurulmaz.
