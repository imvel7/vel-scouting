# VEL SCOUTING — Metodoloji Bütünsel Kalite Kontrol Raporu

**Doküman:** VEL-QA-METH-01  
**Sürüm:** 1.0  
**Tarih:** 10 Kasım 2026  
**Kapsam:** Ortak değerlendirme çerçevesi ve yedi pozisyon ailesinin depo tutarlılığı, puan ağırlıkları, kanıt kuralları, rol sınırları ve raporlama yapısı.

---

## 1. Yönetici özeti

Vel Scouting'in pozisyon metodolojilerinin ilk taslak seti kontrol edildi. Depodaki altı v1.0 pozisyon metodolojisinin her birinde beş değerlendirme alanının ağırlıkları %100'e tamamlanıyor; alt kriter tablolarındaki ağırlıkların toplamı da ilgili değerlendirme alanının ağırlığıyla eşleşiyor.

Kontrol sırasında iki yapısal düzeltme yapıldı:

1. Ortak çerçevedeki alan puanı formülü açık ve hesaplanabilir bir ağırlıklı ortalama olarak yeniden yazıldı; N/E ile N/A ayrımı ve %80 kriter kapsamı tanımlandı.
2. Stoper metodolojisi daha önce proje çalışmasında hazırlanmış olmasına rağmen GitHub'daki metodoloji klasöründe bulunmuyordu. Stoper metodolojisi v0.8, ortak çerçeveye referans veren bir doküman olarak depoya eklendi.

Pozisyonlar arasındaki sık rol çakışmalarını yönetmek için ayrıca ortak bir pozisyon/rol sınırları dokümanı eklendi.

**Denetim sonucu:** Yapısal ve ağırlık aritmetiği kontrolü geçti. Ancak metodolojiler henüz üretim kullanımına tamamen hazır kabul edilmemelidir. Her kriter için 1–10 puanın somut davranış çıpaları ve örnekleri ayrı ayrı tamamlanmalı; ardından gerçek maçlarla pilot kalibrasyon yapılmalıdır.

Bu rapor, futbol performansının saha içi uzmanlar tarafından doğrulandığı veya metodolojilerin gerçek maçlarda test edildiği anlamına gelmez. Bu aşama doküman ve mantıksal tutarlılık kontrolüdür.

## 2. Kontrol edilen dokümanlar

- Ortak oyuncu değerlendirme çerçevesi v1.0
- Stoper değerlendirme metodolojisi v0.8
- Bek ve kanat bekleri metodolojisi v1.0
- Ön libero ve merkez orta saha metodolojisi v1.0
- On numara ve hücumcu orta saha metodolojisi v1.0
- Kanat oyuncuları metodolojisi v1.0
- Santrfor metodolojisi v1.0
- Kaleci metodolojisi v1.0
- Pozisyon ve rol sınırları v1.0

## 3. Puan ağırlığı kontrolü

Aşağıdaki tabloda her pozisyon ailesinin beş değerlendirme alanı ve genel puandaki ağırlıkları gösterilir.

| Pozisyon ailesi | Taktiksel | Karar verme | Teknik | Fiziksel | Rekabetçi | Toplam |
|---|---:|---:|---:|---:|---:|---:|
| Stoper | 30 | 20 | 20 | 15 | 15 | **100** |
| Bek / kanat bek | 25 | 20 | 20 | 20 | 15 | **100** |
| Ön libero / merkez orta saha | 25 | 25 | 25 | 15 | 10 | **100** |
| On numara / hücumcu orta saha | 25 | 25 | 25 | 10 | 15 | **100** |
| Kanat | 25 | 20 | 25 | 15 | 15 | **100** |
| Santrfor | 25 | 20 | 25 | 15 | 15 | **100** |
| Kaleci | 25 | 20 | 30 | 15 | 10 | **100** |

Her pozisyon dokümanındaki kriter tabloları ayrıca kontrol edildi. Her değerlendirme alanının alt kriter ağırlıkları, ilgili alanın genel puandaki ağırlığına eşit toplam veriyor. Bu, tabloların aritmetik yapısının tutarlı olduğunu gösterir.

Ağırlıkların pozisyonlar arasında farklı olması bilinçli bir tasarım tercihidir. Örneğin kalecide teknik alanın, merkez orta sahada ise taktiksel/karar verme alanlarının daha yüksek ağırlık taşıması rol gerekliliklerinden kaynaklanır. Farklı pozisyonların genel puanları doğrudan birbirleriyle sıralanmamalıdır.

## 4. Ortak puanlama ve kapsam kuralı

Ortak çerçevedeki alan puanı formülü netleştirildi:

**Alan puanı = Σ (kriter puanı × kriter ağırlığı) / Σ (değerlendirilmiş kriter ağırlıkları)**

**Kriter kapsamı = Değerlendirilen uygulanabilir kriter ağırlıkları / Toplam uygulanabilir kriter ağırlıkları × 100**

Bir alanın puanlanabilmesi için kriter kapsamı en az %80 olmalıdır. Genel puan yalnızca bütün zorunlu alanlar bu eşiği karşıladığında hesaplanır.

- **N/E:** Kriter rol için geçerlidir ancak gözlem fırsatı veya güvenilir görüntü yoktur. Kapsam paydasında kalır, puana girmez.
- **N/A:** Kriter kayıtlı rol için gerçekten uygulanamaz. Gerekçesi yazılır ve o rapordaki kapsam/puan paydasından çıkarılır.
- N/A, görüntü eksikliği veya gözlem zorluğunu saklamak için kullanılamaz.
- Eksik kriterler sıfır, beş veya alan ortalamasıyla doldurulmaz.

## 5. Kanıt standardı kontrolü

Bütün pozisyon metodolojileri ortak A/B/C örneklem standardına bağlanıyor:

- **A:** En az 6 tam maç ve farklı koşulları kapsayan örneklem.
- **B:** 3–5 tam maç; sonuçlar geçici kabul edilir.
- **C:** 1–2 tam maç veya ağırlıklı olarak özet/kısa klip; kesin genel puan ve kesin oyuncu hükmü verilmez.

Pozisyon metodolojilerindeki rol doğrulama kontrolü, role özgü davranışların en az üç ayrı maçta gözlenmesini istiyor. Bu kural, A/B/C kanıt seviyesinin yerine geçmez; rolün sürekliliğini doğrulamak için ek kontroldür.

Maç sayısı tek başına yeterli değildir. Kamera açısı, oyuncunun görüntüde kalma süresi, rakip seviyesi, oyun tarzı ve rolün gerçekten gözlenip gözlenmediği raporda belirtilmelidir.

## 6. Pozisyonlar arası rol sınırları

En fazla karışabilecek alanlar için karar kuralları ayrı dokümana alındı:

- Bek/kanat bek ile kanat oyuncusu
- Ön libero/merkez orta saha ile hücumcu orta saha
- Hücumcu 8 ile 10 numara
- İkinci forvet bağlantısı ile santrfor
- Geniş alan stoperi ile bek
- Kaleci içindeki çizgi, süpürme ve oyun kurulum rolleri

Ana karar ölçütü nominal pozisyon veya forma numarası değil; oyuncunun maçtaki başlangıç alanı, topsahibi olma görevi, rakip topa sahipken sorumluluğu ve geçiş davranışıdır. Her maçtaki pozisyon/rol kaydı sezonluk ana rolden ayrı tutulmalıdır.

## 7. Tespit edilen açık konular

### 7.1. Kriter bazında 1–10 davranış çıpaları — yüksek öncelik

Mevcut dokümanlarda ortak 1–10 ölçeği ve kriter açıklamaları bulunuyor; ancak her alt kriter için 1–2, 3–4, 5–6, 7–8, 9 ve 10 puan seviyelerini somutlaştıran ayrı davranış örnekleri henüz tamamlanmış değil.

Örnek: “Hat kıran pas” kriterinde 5 puan ile 8 puan arasındaki farkın hangi gözlenebilir karar ve uygulama davranışlarından oluştuğu ayrıca tanımlanmalı.

Bu iş yapılmadan yönetim panelinde kriter puanı girişi açılırsa farklı scoutlar aynı performansa farklı puanlar verebilir. Bu nedenle ayrıntılı puan çıpaları veri modeli ve arayüzün üretim sürümünden önce hazırlanmalıdır.

### 7.2. Stoper metodolojisinin sürüm uyumu

Stoper dokümanı v0.8, diğer pozisyon dokümanları v1.0 sürümündedir. Bu bilinçli olarak ilk metodoloji sürümünü korur; ancak kriter çıpaları ve pilot test tamamlandığında stoper dokümanı da ortak çerçevenin olgunlaşmış sürümüyle birlikte gözden geçirilmelidir.

### 7.3. Saha içi kalibrasyon

Ağırlıkların aritmetik olarak doğru olması, ağırlıkların saha gerçekliğine göre en iyi seçim olduğunu tek başına kanıtlamaz. Her pozisyonda gerçek maçlardan örnek raporlar hazırlanmalı; gözlemciler arası puan farklılıkları ve kriterlerin ayırt ediciliği incelenmelidir.

### 7.4. Veri kaynağı ve video standardı

Video hakları, kaynak bağlantıları ve erişim durumu ayrı kaydedilmelidir. İstatistik kullanıldığında sağlayıcı, metrik tanımı, kapsam ve tarih bilgisi saklanmalıdır. Görüntü veya veri bulunmaması performans eksiği olarak yorumlanmamalıdır.

## 8. Önerilen kalite kapıları

| Kapı | Tamamlanma koşulu | Mevcut durum |
|---|---|---|
| 1. Doküman envanteri | Bütün pozisyon metodolojileri depoda bulunuyor | **Tamamlandı** |
| 2. Ağırlık aritmetiği | Alan ve kriter ağırlıkları doğru toplam veriyor | **Tamamlandı** |
| 3. Ortak hesaplama | N/E, N/A, %80 kapsam ve genel puan formülü net | **Tamamlandı** |
| 4. Rol sınırları | Pozisyon çakışmaları için ortak karar kuralı var | **Tamamlandı** |
| 5. Kriter puan çıpaları | Her kriterin puan seviyeleri somut davranışla tanımlı | **Bekliyor** |
| 6. Pilot kalibrasyon | Gerçek maçlarda rapor ve gözlem tutarlılığı testli | **Bekliyor** |
| 7. Üretim veri modeli | Onaylanmış metodolojiyle veritabanı/arayüz eşleşiyor | **Bekliyor** |

## 9. Sonuç ve sonraki iş

Doküman envanteri, ağırlık toplamları, ortak puan formülü, kanıt standardı ve ana pozisyon sınırları açısından ilk kalite kontrolü geçti.

**Bir sonraki iş:** Her pozisyonun alt kriterleri için somut 1–10 davranış çıpalarını hazırlamak. Bunu pozisyon aileleri üzerinden ilerleyerek yapacağız. İlk pilot, stoper metodolojisinden seçilecek; çünkü Vel Scouting'in ilk ayrıntılı pozisyon çalışması bu grupta başladı.

Kriter çıpaları ve pilot test tamamlanmadan mevcut basit scout raporu formu, nihai değerlendirme sistemi olarak kabul edilmemelidir.
