# VEL SCOUTING — Davinson Sánchez Pilot Kurulum Kontrol Listesi

**Kayıt:** VEL-PILOT-CB-SETUP-01  
**Sürüm:** 1.0  
**Tarih:** 11 Kasım 2026  
**Durum:** Admin paneli kurulum akışı hazır; gerçek kayıtlar henüz oluşturulmadı.

## 1. Amaç

Bu kontrol listesi, Davinson Sánchez için seçilen Galatasaray 5–2 Juventus maçını Vel Scout admin panelinde doğru kayıtlarla pilot scouting oturumuna dönüştürür. Yalnızca veri hazırlığı ve iş akışı içindir; oyuncuya puan veya performans hükmü vermez.

**Pilot maç:** Galatasaray 5–2 Juventus  
**Tarih:** 17 Şubat 2026  
**Organizasyon:** UEFA Champions League  
**Sezon:** 2025/26  
**Oyuncu:** Davinson Sánchez — Galatasaray, stoper  
**Video kaynağı:** UEFA.tv Re-Runs — kullanıcı 10 Kasım 2026'da Türkiye'den tam maç kaydına eriştiğini doğruladı.

## 2. Admin panelinde kayıt sırası

Önce GitHub Pages üzerinde yayımlanmış admin panelini yetkili admin/editor hesabıyla aç. Panel henüz yayımlanmamışsa bu sürümün GitHub Pages dağıtımına geçmesini bekle; kaynak dosyadaki değişikliği canlıya geçmiş kabul etme.

### A. Kulüpler ve oyuncu

1. Kulüp listesinde **Galatasaray** ve **Juventus** kayıtlarını kontrol et. Mevcut kayıt varsa yeniden oluşturma; eksik olanı ekle.
2. Oyuncu listesinde **Davinson Sánchez** kaydını kontrol et. Kayıt varsa onu kullan; yoksa taslak oyuncu profili oluştur.
3. Gerekli temel alanlar: ad soyad, uyruk olarak Colombia, ana mevki olarak CB ve mevcut kulüp olarak Galatasaray. Gerekli olmayan doğum tarihi veya kişisel alanları sırf formu doldurmak için ekleme. Profili pilot aşamasında taslak bırak.

### B. Organizasyon ve sezon

**Organizasyon kaydı**
- Ad: UEFA Champions League
- Bölge: Europe
- Tür: Club competition

**Sezon kaydı**
- Ad: 2025/26
- Başlangıç/bitiş tarihleri: doğrulanmış sezon tarihleri elindeyse gir; emin değilsen boş bırak.

Listede aynı organizasyon veya sezon zaten bulunuyorsa ikinci kayıt oluşturma.

### C. Maç kaydı

Maç kayıt formunda şu değerleri kullan:

| Alan | Değer |
|---|---|
| Ev sahibi | Galatasaray |
| Deplasman | Juventus |
| Tarih | 17 Şubat 2026 |
| Organizasyon | UEFA Champions League |
| Sezon | 2025/26 |
| Durum | Tamamlandı |
| Ev sahibi skoru | 5 |
| Deplasman skoru | 2 |
| Süre | 90 |
| Yaş kategorisi | Senior |

Saat alanına yalnızca resmî maç sayfasından doğruladığın başlama saatini Türkiye yerel saati olarak gir. Saatten emin değilsen tahmin yürütme; resmî fikstürü kontrol etmeden maç kaydını oluşturma.

### D. Oyuncu-maç katılımı

- Oyuncu: Davinson Sánchez
- Maç: Galatasaray 5–2 Juventus
- Maçta temsil ettiği kulüp: Galatasaray
- Oynadığı mevki: CB
- Oynadığı dakika: 90

Bu bağlantı oyuncunun o maça katıldığını kaydeder; maç içindeki rol davranışları ayrıca gözlemlenmelidir.

### E. Video ve erişim kaydı

Video kaynak kaydını oluştururken:

- Maç: Galatasaray 5–2 Juventus
- Kaynak: UEFA.tv
- Bağlantı: https://www.uefa.tv/section/Re-Runs
- Video türü: Tam maç
- Hak durumu: Yalnızca bağlantı (link_only)
- Süre: İsteğe bağlı; boş bırakılabilir.

Kaynağın resmî oynatıcısını aç. Videonun başlangıcını, devre arasından sonraki bölümü ve maç sonunu kontrol ederek gerçekten tam ve oynatılabilir olduğunu yeniden doğrula. Erişim kontrol kaydında yalnızca o anda bizzat doğruladığın ülke, hesap gereksinimi, ücret ve içerik kapsamını seç. Türkiye'de erişimi tekrar kontrol etmediysen eski kontrolü yeni tarihli kontrol gibi kaydetme.

**Hak sınırı:** Ücretsiz izleme, videoyu indirme, kopyalama, klipleme, yeniden barındırma veya yayımlama hakkı vermez. Video yalnızca yetkili scout'un kaynak sağlayıcının orijinal oynatıcısında izlemesi için bağlantılanır.

### F. Scouting oturumu ve video bağlantısı

- Oyuncu-maç kaydı: yukarıdaki Davinson Sánchez katılımı
- Rubrik: **CB-METH-0.8-ANCHORS-1.0** (panelde pilot stoper rubriği olarak görünmeli)
- Oturum durumu: Taslak
- Özel not: “İlk maç iş akışı pilotu. İlk izleme puansız yapılacak; gözlem, bağlam ve yorum ayrı kaydedilecek. Tek maçtan nihai oyuncu notu veya kalıcı ana rol çıkarılmayacak.”

Oturum oluşturulduktan sonra UEFA.tv video kaydını bu oturuma bağla. Aynı maça ait video ve oturum seçildiğini kontrol et.

## 3. Görüntü inceleme protokolü

1. İlk izlemeyi normal hızda yap ve şimdilik puan verme.
2. İlk yarı için `CB-GS-JUV-20260217_FIRST_HALF_GUIDE.md` belgesindeki resmî olay işaretlerini yalnızca videoda gezinmek için kullan.
3. Resmî maç olayını, Davinson'un bireysel gözlemi olarak kaydetme. Oyuncunun olaydaki somut rolü videoda açıkça görülmelidir.
4. İkinci izlemeyi, gerçekten görülen aksiyonlarda zaman damgalı kayıt oluşturmak için kullan.
5. Gözlem satırlarında video zamanı ile maç saatini ayrı gir. Gözlemi, takım/rakip bağlamını ve sonucu birbirinden ayır.
6. Kadraj dışında kalan veya görüntü kalitesi nedeniyle seçilemeyen davranışı tahmin etme; görüntü sınırlılığı olarak kaydet.
7. 67. dakikadaki Juventus kırmızı kartından önceki ve sonraki bölümleri aynı maç bağlamı gibi değerlendirme. Sayısal üstünlük sonrası değişen oyun koşulunu not et.

## 4. Tamamlanma ve rapor kapısı

Bu tek maç, yalnızca admin iş akışının uçtan uca denenmesi için kullanılabilir.

- Rol davranışını tanımlamak için en az üç farklı maçta tekrar eden kanıt gerekir.
- A kanıt seviyesi için en az altı tam maç şartı korunur.
- Puan verilen her kriter, ilgili zaman damgalı gözlemle desteklenmelidir.
- N/E, yeterli gözlem fırsatı bulunmamasıdır; otomatik olarak düşük puan değildir.
- N/A yalnızca kriter gerçekten uygulanamazsa ve gerekçesi varsa kullanılır.
- Oturum, bütün kriter durumları ve tamamlanma kontrolleri karşılanmadan tamamlanmış/kilitli yapılmamalıdır.
- Bu tek maçtan nihai genel puan, transfer uygunluğu, potansiyel veya kalıcı ana rol kararı çıkarılmamalıdır.

## 5. İlgili proje belgeleri

- [Stoper pilot gözlem şablonu](VEL_CENTRE_BACK_PILOT_OBSERVATION_TEMPLATE_v1.0.md)
- [Davinson Sánchez video kaynak denetimi](VEL_DAVINSON_SANCHEZ_VIDEO_SOURCE_AUDIT_01.md)
- [Davinson Sánchez maç veri notu](VEL_DAVINSON_SANCHEZ_MATCH_DATA_NOTE_01.md)
- [İlk yarı gözlem rehberi](CB-GS-JUV-20260217_FIRST_HALF_GUIDE.md)
- [Özel scouting video mimarisi](../architecture/VEL_PRIVATE_SCOUTING_VIDEO_ARCHITECTURE_v1.0.md)
- [Proje yol haritası](../ROADMAP.md)

**Kapanış durumu:** Bu belge kurulum adımlarını tanımlar. Veritabanında gerçek maç/katılım/video/oturum kaydı oluşturulduğu veya maçın izlendiği anlamına gelmez.
