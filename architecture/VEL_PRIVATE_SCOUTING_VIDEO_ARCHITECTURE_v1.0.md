# VEL SCOUTING — Özel Scouting Video ve Maç Kaynak Sistemi

**Doküman:** VEL-ARCH-VIDEO-01  
**Sürüm:** 1.0  
**Karar tarihi:** 10 Kasım 2026  
**Durum:** Onaylanan ürün yönü için teknik tasarım; henüz uygulama veya güvenlik testi değildir.

---

## 1. Ürün kararı

Vel Scouting bir maç izleme veya video yayın platformu olmayacaktır.

Maç görüntüleri yalnızca yetkilendirilmiş scouting ekibinin futbolcu değerlendirmesi yapabilmesi için kullanılan **özel çalışma materyalidir**. Kamuya açık Vel Scouting sitesi video kataloğu, video oynatıcı veya maç görüntüsü dağıtımı sunmayacaktır.

Yeni sistemin adı:

# Vel Scout Private Match Library

Bu sistemin amacı, ücretsiz ve yasal erişilebilen maç görüntülerini keşfetmek; resmî kaynak bağlantılarını, erişim ve hak bilgilerini özel ortamda yönetmek; maçları oyuncu katılımı ve scout değerlendirmeleriyle ilişkilendirmektir.

### Değişmez ürün ilkeleri

1. **Özel video, herkese açık değildir.** Maç kaynakları ve doğrudan video URL'leri yalnızca yetkili scouting kullanıcılarınca görüntülenir.
2. **Kamuya açık sitede video oynatıcı bulunmaz.** Ziyaretçiler yayımlanmış futbolcu profillerini ve onaylanmış scout raporlarını görür.
3. **Kaynak bağlantısı, içeriğin mülkiyeti değildir.** Ücretsiz izlenebilen video indirilmez, kopyalanmaz, yeniden barındırılmaz veya yayımlanmaz; ayrıca izin verilmiş değilse.
4. **Ücretsiz erişim ile yeniden kullanım hakkı ayrıdır.** İzleme erişimi, ticari kullanım, klip çıkarma, paylaşma veya barındırma hakkı olarak yorumlanmaz.
5. **Kanıt izi korunur.** Her gözlem, maç, oyuncu katılımı, zaman damgası, kriter, metodoloji sürümü ve değerlendiriciyle ilişkilendirilir.
6. **Güvenlik varsayılan olarak kapalıdır.** Bir video kaydı veya kaynak linki açıkça yayımlanmadıkça kamuya açılmaz.
7. **Maliyet hedefi gerçekçidir.** İlk sürüm mevcut ücretsiz GitHub Pages ve Supabase kaynaklarını ve üçüncü tarafların ücretsiz resmî oynatıcılarını kullanır. Ücretsiz kotalar, sağlayıcı şartları ve erişim garantileri sonsuz veya kalıcı kabul edilmez.

## 2. Ürün yüzeyleri: iki ayrı alan

### A. Kamuya açık Vel Scouting

Kamuya açık sitede bulunabilecekler:
- Yayımlanmış futbolcu profilleri.
- Onaylanmış scout raporları ve rapor sürümleri.
- Metodoloji açıklamaları.
- Yayına uygun performans özeti, güçlü yönler ve gelişim alanları.
- İzin ve güvenlik kontrollerinden geçmiş, gerekli ölçüde sadeleştirilmiş kanıt açıklamaları.

Kamuya açık sitede bulunmayacaklar:
- Video oynatıcı veya gömülü maç yayını.
- Doğrudan özel video URL'leri.
- Kaynak hesabı, erişim notu veya lisans yazışmaları.
- Taslak raporlar, ham gözlemler, değerlendirici notları.
- Özel scouting çalışma alanına ait maç/oyuncu eşleştirme notları.

### B. Özel scouting çalışma alanı

Yalnızca yetkilendirilmiş personel:
- Maç ve oyuncu katılım kayıtlarını yönetir.
- Resmî video kaynağı bulur veya ekler.
- Ülke, üyelik, ücret ve erişim durumunu kontrol eder.
- Video türünü ve tamlık durumunu işaretler.
- Yetkili kaynağın orijinal sayfasını açar.
- Zaman damgalı gözlem ve kriter değerlendirmesi kaydeder.
- Taslak scout raporu oluşturur ve inceler.

**Not:** Özel alanda bir video bağlantısının görünmesi, üçüncü taraf sağlayıcının hesabı veya erişim kontrolünü ortadan kaldırmaz. Video, mümkün olduğunda hak sahibinin kendi resmî oynatıcısında açılır.

## 3. Mevcut altyapının başlangıç durumu

Mevcut proje:
- Kamuya açık site: GitHub Pages.
- Yönetim paneli: `admin.html`.
- Veritabanı ve kimlik doğrulama: Supabase.
- Erişim kuralı dosyası: `vel_access_setup.sql`.

Mevcut veritabanında bulunan ana tablolar:
- `matches`
- `player_matches`
- `videos`
- `observations`
- `scout_reports`
- `report_versions`
- `players`
- `clubs`
- `competitions`
- `seasons`
- `user_roles`

Mevcut erişim kuralları dosyasının incelenmesinde:
- `matches`, `player_matches`, `videos` ve `observations` için personel erişimi politikaları bulunuyor.
- `players`, `clubs` ve yayımlanmış `scout_reports` için kamuya açık okuma kuralları var.
- `user_roles` içindeki mevcut roller `admin` ve `editor`.
- Personel kontrolü `is_vel_staff()` fonksiyonuyla, yönetici kontrolü `is_vel_admin()` fonksiyonuyla yapılıyor.

**Önemli sınır:** Bu dosya politikaların mevcut kod tanımını gösterir; canlı Supabase projesindeki gerçek şema, RLS durumu, grants ve davranışın tüm testlerini kanıtlamaz. Kod değişikliğinden önce canlı tablo yapısı ve RLS politikaları yeniden okunmalı, test hesabıyla doğrulanmalıdır.

## 4. Önerilen veri akışı

1. Resmî veya izinli yayın kaynağı keşfedilir.
2. Maç `matches` tablosunda kayıtlıysa seçilir; değilse yetkili kullanıcı maç kaydı açar.
3. Video kaynağı mevcut `videos` tablosuna ilişkilendirilir.
4. Kaynağın erişim ve hak durumu doğrulama kaydına işlenir.
5. Maçın oyuncu katılımı `player_matches` tablosuyla bağlanır.
6. Scout, yetkili kaynaktaki görüntüyü kendi erişimi kapsamında izler.
7. Somut olaylar `observations` tablosuna zaman damgası ve kriterle kaydedilir.
8. Yeterli kanıt oluştuğunda rapor taslağı oluşturulur.
9. İnceleme ve onaydan sonra yalnızca yayına uygun rapor özeti kamuya açılır.

## 5. Video kaynak kayıt standardı

Mevcut `videos` tablosu ilk sürüm için merkezî kayıt noktası olarak değerlendirilecek. Şu alanların mevcut şemada bulunup bulunmadığı gerçek Supabase şeması üzerinden doğrulanmadan SQL çalıştırılmayacak veya sütun varsayılmayacak.

Gerekli kavramlar:
- Kaynak sahibi: FIFA, UEFA, federasyon, lig, kulüp, yayıncı veya diğer yetkili organizasyon.
- Orijinal video sayfası URL'si.
- Video başlığı ve kaynak platformu.
- İçerik türü: tam maç, kesintili tam maç, uzatılmış özet, özet, kısa klip veya canlı yayın kaydı.
- Süre ve biliniyorsa görüntünün kapsadığı maç dakikaları.
- Ülkeye göre erişim: Türkiye'de doğrulandı / engelli / test edilmedi.
- Erişim gereksinimi: hesap yok / ücretsiz hesap / abonelik / kurum lisansı / bilinmiyor.
- Ücret durumu: ücretsiz / ücretli / bilinmiyor.
- Hak durumu: yalnızca izleme koşulları biliniyor / özel kullanım izni var / yeniden kullanım izni var / izin yok / bilinmiyor.
- Son doğrulama tarihi ve doğrulamayı yapan yetkili.
- Erişim kalitesi: tam / kesintili / yalnızca bölüm / doğrulanmadı.
- Notlar: kadraj, kesinti, görüntü kalitesi, erişim ve kaynak kısıtları.

### Tam maç sınıflandırması

- **Tam maç:** Maçın başlangıcından sonuna kadar oyun akışını kapsadığı doğrulanmış kayıt.
- **Kesintili tam maç:** Bazı dakikaları eksik olan kayıt; eksikler açıkça yazılır ve tam maç olarak etiketlenmez.
- **Uzatılmış özet:** Uzun süreli olsa bile bütün oyun akışı doğrulanmıyorsa tam maç değildir.
- **Özet/kısa klip:** Belirli olayları gösterir; genel performans raporu için tam maç yerine geçmez.
- **Bilinmiyor:** Süre veya içerik doğrulanamadıysa bu etiket kullanılır.

## 6. Erişim ve güvenlik modeli

### Mevcut roller

İlk sürümde mevcut `admin` ve `editor` rolleri korunur. Ayrı bir `scout` rolü, yetki sınırları ve iş akışı tanımlanmadan eklenmez.

Önerilen yetki sınırları:
- **Admin:** Kullanıcı/rol yönetimi, kaynak ve maç kayıtlarını yönetme, tüm scouting kayıtlarına erişim.
- **Editor:** Yetkili maç/kaynak/oyuncu ve rapor iş akışını yürütme; rol yönetimi yapamama.
- **Public/anon:** Yalnızca açıkça yayımlanmış oyuncu profilleri, kulüpler ve raporları görme; video, maç kaynakları, ham gözlem ve taslaklara erişememe.

### Güvenlik gereksinimleri

- Her özel tablo için RLS açık olmalı.
- `videos`, `matches`, `player_matches`, `observations` ve `report_versions` kamuya açık sorgulardan kapalı kalmalı.
- Kamuya açık sorgular özel video URL'si içeren alanları hiçbir koşulda döndürmemeli.
- Video URL'leri `index.html`, herkese açık JavaScript dosyaları, herkese açık JSON veya public storage bucket içine yazılmamalı.
- `service_role` veya secret anahtarlar tarayıcıya ya da GitHub'a konmamalı.
- Özel video dosyaları ilk sürümde Vel Scouting sunucularına yüklenmemeli.
- Dış oynatıcı yalnızca yetkili özel alan içinden açılmalı; mümkün olduğunda yeni sekmede orijinal sağlayıcıya yönlendirilmelidir.
- Kaynak hesabı/parolası asla Vel Scouting veritabanında tutulmamalı.
- Hata durumunda erişimi açmak yerine kapalı tutan varsayılan davranış uygulanmalı.

**Gerçekçi güvenlik notu:** Bir URL'nin özel arayüzde saklanması, kaynak sağlayıcının kendi erişim kontrolünü değiştirmez. Bağlantıyı gören yetkili kişi yine sağlayıcının kullanıcı şartlarına ve hak koşullarına tabidir. Yetkili kullanıcının ekranından içeriğin kopyalanmasını teknik olarak tamamen önleme garantisi de verilemez.

## 7. Kamuya rapor yayımlama kuralı

Özel scouting verisi ile kamu raporu farklı veri katmanları olarak tasarlanır.

Kamuya açılabilecekler, editoryal onaydan sonra:
- Mevcut performansın rol bağlamındaki özeti.
- Güçlü yönler ve gelişim alanları.
- Kanıt seviyesi ve incelenen maç adedi.
- Metodoloji sürümü.
- Yayınlanmasına izin verilen ve kişisel veri içermeyen kanıt açıklamaları.

Kamuya otomatik aktarılmayacaklar:
- Video URL'si ve özel kaynak notları.
- Ham gözlem satırları ve değerlendirici iç notları.
- Özel maç/oyuncu takip planları.
- İzin alınmamış klipler, ekran görüntüleri veya yayın parçaları.
- Genç oyuncuların güvenliğini veya mahremiyetini tehlikeye atabilecek bilgiler.

## 8. Tamamen ücretsiz çalışma hedefinin sınırları

İlk sürümün yazılım/altyapı maliyeti, mevcut ücretsiz GitHub Pages ve Supabase kotaları içinde tutulmaya çalışılacaktır. Ancak:
- Ücretsiz video arşivlerinin erişimi ve kataloğu sağlayıcı tarafından değiştirilebilir.
- Ücretsiz hesap veya izleme izni, sürekli erişim garantisi değildir.
- Supabase/GitHub ücretsiz planlarının kota ve şartları vardır.
- Otomatik tarama, sağlayıcıların kullanım şartları ve teknik izinleri uygunsa uygulanır; izinsiz yoğun scraping yapılmaz.
- Ücretli profesyonel kaynaklar ücretsiz kaynak gibi sunulmaz ve satın alma kararı olmadan projeye bağlanmaz.

İlk sürümde en uygun yol, güvenilir kaynakların manuel/yardımlı keşfi, özel kaydı ve periyodik doğrulamasıdır. Otomatik indeksleme ancak kaynak başına izin ve sürdürülebilir teknik yöntem netleşince eklenir.

## 9. Uygulama yol haritası

### Aşama 0 — Ürün ve güvenlik kararı
**Durum: Bu mimari dokümanla tanımlandı.**

- Kamuya açık video oynatıcısı olmayacağı kararı.
- Özel video ve scouting çalışma alanı.
- Video erişimi ile yayın hakkının ayrılması.
- Kamuya açık raporla özel kanıt verisinin ayrılması.

**Tamamlanma ölçütü:** Mimari karar dokümante edilir ve sonraki geliştirme buna göre yapılır.

### Aşama 1 — Canlı Supabase şeması ve RLS denetimi
**Sonraki teknik iş.**

- Gerçek tablo sütunlarını doğrula.
- Mevcut RLS politikalarını ve grants'i incele.
- Anon, normal authenticated ve staff kullanıcılarıyla okuma/yazma testleri tanımla.
- `videos` ve özel tabloların kamuya yanlışlıkla açılmadığını doğrula.
- Mevcut admin/editor rollerinin fiilî yetkilerini kontrol et.

**Tamamlanma ölçütü:** Özel video/maç/gözlem verilerine anon veya yetkisiz kullanıcı erişemiyor; yetkili personel gerekli işlemleri yapabiliyor.

### Aşama 2 — Veri modeli fark analizi
- Mevcut `matches`, `player_matches`, `videos`, `observations` tablolarını gereksinimlerle eşleştir.
- Eksik kaynak doğrulama ve denetim alanlarını belirle.
- Gerekirse yeni kaynak denetim tablosu veya sınırlı sütun ekleme önerisi hazırla.
- Şema değişikliklerini geriye uyumlu migration olarak tasarla.
- Henüz onaylanmamış alanları admin paneline ekleme.

**Tamamlanma ölçütü:** Her maçın birden fazla video kaynağını ve her kaynağın erişim/hak durumunu izlenebilir biçimde tutacak şema tasarımı hazır.

### Aşama 3 — Özel admin video/kaynak yönetimi
- Maç seçme veya maç oluşturma.
- Orijinal kaynak URL'si ve platform bilgisini ekleme.
- Tam maç/kesintili/özet sınıflandırması.
- Ücretsiz hesap/abonelik/Türkiye erişimi durumu.
- Hak durumu ve son kontrol tarihi.
- Yetkili linki açma.
- Kaynak bozulduğunda veya erişim kalktığında durumu güncelleme.

**Tamamlanma ölçütü:** Yetkili kullanıcı özel kaynak kaydı oluşturup güncelleyebiliyor; kamuya açık sitede bu kayıt görünmüyor.

### Aşama 4 — Maç ve futbolcu eşleştirme
- Maç, sezon, organizasyon ve kulüp bilgisi.
- Oyuncunun maçta oynayıp oynamadığı ve dakika aralığı.
- Pozisyon ve o maçtaki rol.
- Aynı maçta birden fazla oyuncunun scouting için bağlanabilmesi.

**Tamamlanma ölçütü:** Bir oyuncunun profilinden yalnızca özel çalışma alanında o oyuncunun ilgili maçları bulunabiliyor; kamuya açık sayfaya video URL'si sızmıyor.

### Aşama 5 — Özel gözlem ve değerlendirme iş akışı
- Zaman damgalı gözlem.
- Pozisyon metodolojisi ve kriter bağlantısı.
- N/E ve N/A gerekçesi.
- Kriter puanları ve kapsam hesabı.
- Değerlendirici kimliği ve metodoloji sürümü.
- Bağımsız değerlendirme/karşılaştırma.

**Tamamlanma ölçütü:** Raporun her iddiası özel maç kanıtına kadar izlenebilir.

### Aşama 6 — Kamuya açık raporlama ayrımı
- Özel rapor taslağından kamu raporu oluşturma.
- Yayın öncesi editoryal ve mahremiyet kontrolü.
- Video URL'si/ham gözlem/özel notların dışarı aktarılmasını engelleme.
- Yalnızca onaylanmış rapor sürümünü yayımlama.

**Tamamlanma ölçütü:** Kamu sayfaları video veya özel scouting kayıtlarına erişmeden onaylanmış raporları sunabiliyor.

### Aşama 7 — Kaynak keşif ve doğrulama ağı
- FIFA+, UEFA.tv, lig ve federasyon katalogları, resmî kulüp kanalları ve Football Archive gibi keşif indeksleri.
- Kaynak başına otomasyon ve erişim koşullarının kontrolü.
- İlk aşamada manuel/yardımlı keşif; daha sonra izinli otomatik kontrol.
- Türkiye'den erişim, ücretsiz olma ve video tamlığı etiketleri.
- Eski/kırık linkler için yeniden kontrol.

**Tamamlanma ölçütü:** Yeni kaynaklar aynı standarda göre kaydediliyor ve doğrulanma tarihi belli.

## 10. Uygulama sırası ve karar kapıları

| Sıra | İş | Durum |
|---|---|---|
| 0 | Özel video kütüphanesi ürün kararını dokümante et | Tamamlandı — v1.0 |
| 1 | Canlı Supabase şema/RLS denetimi | Sıradaki iş |
| 2 | Veri modeli fark analizi | Bekliyor |
| 3 | Özel admin video/kaynak yönetimi | Bekliyor |
| 4 | Maç ve futbolcu eşleştirme | Bekliyor |
| 5 | Gözlem ve değerlendirme akışı | Bekliyor |
| 6 | Kamu raporuyla özel veriyi ayır | Bekliyor |
| 7 | Kaynak keşfi ve doğrulama ağını genişlet | Bekliyor |

**Karar kapısı:** RLS ve grants denetlenmeden özel video URL'lerini admin arayüzüne taşımayacağız. Canlı şemayı doğrulamadan migration yazmayacağız.

## 11. İlk pilotla bağlantı

Davinson Sánchez — Galatasaray 5–2 Juventus (17 Şubat 2026) pilotu, özel kaynak yönetimi ve maç-gözlem ilişkilendirmesi için ilk test vakası olarak kalabilir.

- Kullanıcı UEFA.tv'de tam maç kaydını bulduğunu bildirdi.
- Bu, Türkiye'de oynatma bulunduğuna ilişkin kullanıcı teyididir.
- UEFA yayınını Vel Scouting'e yükleme veya kamuya gömme izni vermez.
- İlk pilot, özel çalışma alanında kaynak bağlantısının güvenli yönetimini ve gözlem kayıt akışını test eder.
- Video görüntüsü gerçekten incelenmeden oyuncu puanı veya taktik gözlem üretilmez.

## 12. Nihai ürün tanımı

**Vel Scout Private Match Library**, Vel Scouting personelinin ücretsiz ve yasal video kaynaklarını keşfetmesini, özel olarak kaydetmesini ve maçları oyuncu gözlemleriyle ilişkilendirmesini sağlayan iç sistemdir.

Kamuya açık Vel Scouting ise video dağıtmaz; yalnızca onaylanmış futbolcu profillerini ve scout raporlarını sunar.
