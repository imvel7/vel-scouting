# VEL SCOUT — Kaynak Kataloğu ve Video Kullanım Hakları Standardı

**Doküman:** VEL-SOURCES-RIGHTS-01  
**Sürüm:** 1.0  
**Tarih:** 12 Kasım 2026  
**Durum:** Veri modeli ve operasyon standardı; veritabanı/UI uygulaması migration geçmişi uzlaştırılana kadar beklemede.

## 1. Amaç

Vel Scout'un maç keşif sisteminde üç farklı soruyu birbirine karıştırmamak:

1. **Kaynak nerede?** Maçları yayımlayan, arşivleyen, indeksleyen veya lisanslayan kuruluş/platform hangisi?
2. **İzleme erişimi var mı?** İlgili maç videosu belirtilen ülkede açılabiliyor mu; ücretsiz mi, hesap veya abonelik istiyor mu; gerçekten tam maç mı?
3. **Hangi kullanım hakları var?** İçerik manuel scouting, otomatik video analizi, ticari ürün içinde analiz, indirme/depolama, klip çıkarma veya yeniden dağıtım için kullanılabiliyor mu?

Birinci ve ikinci sorunun cevabı, üçüncü soruya otomatik olarak “evet” vermez. Bir sayfanın herkese açık olması veya ücretsiz izlenebilmesi Vel Scout'a video indirme, AI ile işleme, ticari analiz veya yeniden yayımlama hakkı vermez.

## 2. Dört ayrı kayıt katmanı

### A. `video_sources` — kaynak sağlayıcı kataloğu

Kaynak sağlayıcıyı maçtan bağımsız bir kez tanımlar. Örnek: UEFA.tv, FIFA+, Premier League Archive, TFF'nin resmî kanalı, kulüp kanalı veya Football Archive keşif indeksi.

Önerilen alanlar:

| Alan | Amaç |
|---|---|
| `id` | UUID |
| `source_key` | Değişmeyen kısa anahtar; tekil |
| `display_name` | Kaynağın görünen adı |
| `operator_name` | İşleten kurum/kuruluş |
| `source_type` | `official_archive`, `official_channel`, `discovery_index`, `licensed_provider`, `research_dataset`, `other` |
| `canonical_url` | Kaynağın ana sayfası/kataloğu |
| `terms_url` | Kullanım koşulları veya lisans şartları |
| `officiality_status` | `official`, `third_party_index`, `unknown` |
| `discovery_method` | İlk sürümde `manual`; yalnızca izinli API/partner beslemesi daha sonra eklenebilir |
| `coverage_notes` | Lig, sezon, yaş grubu ve coğrafi kapsam notları |
| `review_status` | `candidate`, `reviewed`, `inactive` |
| `terms_last_checked_at` | Koşulların son kontrol zamanı |
| `created_at`, `updated_at` | Kayıt geçmişi |

### B. `videos` — belirli maçın belirli video kaydı

Mevcut `videos` tablosu maç ile tekil video bağlantısını tutmaya devam eder. Yeni `video_source_id` alanı, kaydı katalogdaki sağlayıcıya bağlar. Eski `source_name` alanı geriye uyumluluk için korunur; eski satırlara yalnızca gerçekten doğrulanmış eşleşmeler bağlanır.

Aynı maçın birden fazla resmî kaynağı olabilir. Her kaynak ayrı video satırı olarak tutulur. Başlık, orijinal bağlantı, süre, görüntü türü ve tamlık bilgisi video kaydında kalır.

### C. `video_access_checks` — ülkeye göre izleme erişimi

Mevcut tablo bu işin temelini zaten karşılıyor. Her kontrol:
- ülke kodunu,
- erişim sonucunu,
- hesap/abonelik gereksinimini,
- fiyat durumunu,
- görüntünün tam maç mı, kısmi mi veya özet mi olduğunu,
- kontrol zamanını ve notları

ayrı bir geçmiş kaydı olarak tutar.

Bu tablo yalnızca **izleme erişimini** ifade eder; AI işleme veya ticari kullanım izni değildir.

### D. `video_rights_assessments` — kullanım hakkı değerlendirmesi

Hak kontrolü kaynak sağlayıcıya dair genel varsayım olarak değil, mümkün olduğunca belirli video/içerik ve kullanım amacı için yapılır. Tek bir platformdaki iki farklı video farklı lisans koşullarına sahip olabilir.

Önerilen kullanım türleri:

| `right_type` | Anlamı |
|---|---|
| `manual_scouting` | İç scouting amacıyla insan tarafından izleme ve değerlendirme |
| `automated_analysis` | Bilgisayarlı görü/AI ile otomatik video işleme |
| `commercial_use` | Ücretli veya ticari Vel Scout hizmetinde sonuçlardan yararlanma |
| `download_storage` | Video dosyasını indirme veya kalıcı/önbellek depolama |
| `clip_extraction` | Video parçaları/kesitleri çıkarma |
| `redistribution` | Görüntüyü veya kesitleri başkalarına yayımlama/dağıtma |

Her kullanım türü için ayrı durum:

- `granted`: Açık ve izlenebilir dayanakla izin verildi.
- `prohibited`: İlgili kullanım açıkça yasak.
- `unknown`: Yeterli kanıt yok veya koşullar belirsiz.
- `not_reviewed`: Henüz incelenmedi.

Önerilen diğer alanlar: `video_id`, `right_type`, `status`, `basis_type` (yazılı izin, sözleşme/lisans, sağlayıcı koşulları, açık lisans, uzman incelemesi veya bilinmiyor), `evidence_url`, `evidence_note`, `checked_by`, `checked_at`, `valid_from`, `valid_until`, `territory_scope`, `country_code`.

**Varsayılan durum her zaman `unknown` olmalıdır.** Link kaydı oluşturmak izin kaydı oluşturmaz. Kullanım hakkı açıkça doğrulanmamışsa sistem indirme, otomatik analiz veya ticari kullanım için “izin var” sonucu üretmemelidir. Hukuki değerlendirme gerektiren durumlar uzman incelemesine bırakılır.

## 3. İlk kaynak kataloğu — kaynak türüne göre

Aşağıdaki kayıtlar sağlayıcı/keşif adayıdır; bir maça ait video bulunduğu veya Vel Scout'un o videoyu işleme hakkı olduğu anlamına gelmez.

### Resmî video arşivleri ve yayıncılar

| Kaynak | Katalogdaki rol | İlk kullanım |
|---|---|---|
| [FIFA+](https://www.plus.fifa.com/en/catalogue/archive) | Resmî uluslararası turnuva arşivi | Genç millî takımlar, U17/U20 ve FIFA turnuvaları |
| [UEFA.tv Re-Runs](https://www.uefa.tv/section/Re-Runs) | Resmî UEFA arşivi | UEFA kulüp ve millî takım organizasyonlarında seçili tekrarlar |
| [Premier League Archive](https://www.premierleague.com/en/welcome/the-archive/content-format-all/2025-26) | Resmî lig arşivi | Premier League maçları; sezon ve maç kapsamı ayrı doğrulanır |
| [TFF](https://www.youtube.com/@TFF) | Federasyonun resmî video kanalı | Türkiye millî takımları ve yayımlanan gelişim/altyapı içerikleri |
| Kulüp ve liglerin resmî kanalları | Resmî yayıncı/kanal | Özellikle akademi, rezerv, kadın takımı, hazırlık ve yerel maç keşfi |

### Resmî bağlantı keşif indeksi

| Kaynak | Katalogdaki rol | Kullanım sınırı |
|---|---|---|
| [Football Archive — Full Matches](https://footballarchive.org/stats/full-matches/) | Başka kaynaklardaki maç/video bağlantılarını keşfetme indeksi | Video hak sahibi veya barındırıcı olarak varsayılmaz; her bağlantı asıl yayıncıda doğrulanır |

### Lisanslı profesyonel sağlayıcı

| Kaynak | Katalogdaki rol | Kullanım sınırı |
|---|---|---|
| [Hudl Wyscout](https://www.hudl.com/products/wyscout) | Lisanslı profesyonel video/veri sağlayıcısı | Ücretsiz, açık veya AI işleme izni varmış gibi varsayılmaz; fiyat ve lisans ayrıca incelenir |

### Araştırma veri setleri — maç kütüphanesiyle karıştırılmamalı

| Kaynak | Veri türü | Vel Scout'taki olası rol |
|---|---|---|
| [SoccerNet](https://www.soccer-net.org/) | Araştırma amaçlı maç videosu ve anotasyon veri setleri | İzin verilen koşullarda CV/olay tespiti prototip kıyaslaması |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Seçilmiş maçlar için yapılandırılmış olay verisi | Video dışı olay/istatistik veri modeli denemeleri |
| [Metrica Sports Sample Data](https://github.com/metrica-sports/sample-data) | Anonim örnek maç, olay ve takip verileri | Takip/koordinat işleme prototipi; gerçek futbolcu kimliği ve canlı scouting yerine geçmez |

Araştırma veri setleri, güncel futbolcu için ücretsiz ve lisanslı tam maç video arşivi olarak gösterilmemelidir. Veri setinin araştırmaya açık olması da ticari kullanım izni verdiği anlamına gelmez.

## 3.1. Resmî kullanım koşulları kontrolü — 12 Kasım 2026

Bu bölüm, sağlayıcıların yayımladığı genel koşulların ilk taramasıdır; hukuki görüş veya belirli bir videoya özel lisans kararı değildir. Her video ve kullanım türü için ayrıca izin/dayanak kontrolü gerekir.

| Kaynak | Resmî koşullar sayfası | Bu ilk taramada görülen sınır | Katalog işlemi |
|---|---|---|---|
| FIFA+ | [FIFA+ Terms of Service](https://inside.fifa.com/terms-of-service-fifaplus) | Platform/içerik kullanımı kişisel ve ticari olmayan amaçlarla sınırlandırılmış. Hesap kaydı 18+ veya ebeveyn/yasal vasi açık izni ve gözetimi gerektiriyor. | URL kaydedildi; aday statüsü korundu. Yaş koşulu atlatılmaz; reşit olmayanların hesap erişimi ebeveyn iznine bağlıdır. |
| UEFA.tv | [UEFA.tv General Terms of Use](https://www.uefa.com/uefatvtermsconditions/) | Sınırlı, geri alınabilir, özel ve ticari olmayan izleme lisansı; transfer, çıkarma, yeniden iletme, kopyalama ve dağıtım kısıtları; hesap ve ülke koşulları. | URL kaydedildi; video işleme/ticari kullanım izni varsayılmadı. |
| Premier League Archive | [Premier League Terms of Use](https://www.premierleague.com/en/terms-and-conditions) | Makul kişisel kullanım dışındaki ticari kullanım, yeniden kullanım/dağıtım ve içerikten veritabanı oluşturma için önceden yazılı onay gerekiyor; deep-link koşulları da sınırlı. | URL kaydedildi; yazılı onay olmadan içerik kopyalama, veri tabanı oluşturma veya ticari kullanım planlanmaz. |
| TFF Official YouTube | [YouTube Terms of Service](https://www.youtube.com/t/terms) | Kişisel/ticari olmayan izleme ve YouTube'un gömülü oynatıcısı; indirme/kopyalama ve otomatik erişim yalnızca hizmetin açıkça izin verdiği, yazılı izin veya uygulanabilir hukuk istisnaları kapsamında. 18 yaş altı kullanıcı için ebeveyn/yasal vasi izni şartı var. | URL kaydedildi; indirme/scraping yapılmaz, reşit olmayanların erişiminde ebeveyn izni koşulu gözetilir. |
| Hudl Wyscout | [Hudl User Terms of Service](https://www.wyscout.hudl.com/terms) | Koşullar, açıkça izin verilmediği veya yazılı izin alınmadığı sürece otomatik yöntemler (AI araçları dâhil) ile hizmetten veri erişimi/toplama/çıkarma ve Hudl içeriğini ML/AI modeli geliştirmede kullanmayı kısıtlıyor. Müşteri anlaşması da önemlidir. | URL kaydedildi; otomatik video analizi/AI geliştirme izni varsayılmadı; lisans/yazılı izin olmadan sistem girdisi sayılmaz. |
| SoccerNet | [SoccerNet FAQ](https://www.soccer-net.org/faq) | Korumalı video için NDA gerekir; videoların telif hakları yayıncı/liglerdedir. SoccerNet, veri setini araştırma amaçlı ve ticari olmayan kullanım için tanımlar; araştırma amaçlı model eğitimi mümkündür. | URL kaydedildi; yalnızca ilgili araştırma koşulları içinde prototip/benchmark adayı; ticari Vel Scout kullanımına uygun sayılmaz. |
| Metrica Sports Sample Data | [Sample Data repository](https://github.com/metrica-sports/sample-data) | README küçük, anonimleştirilmiş ve senkronize örnek maç/veri dosyalarını anlatıyor; “Legal stuff” notunda sorumlu kullanım ve kaynak gösterimi isteniyor ancak açık bir lisans metni belirtilmiyor. | Açık lisans bulunamadı; terms URL boş, tüm haklar unknown kalır. Ticari/üretim kullanımı için sağlayıcıdan açıklık alınmalı. |
| Football Archive | [Full Matches index](https://footballarchive.org/stats/full-matches/) | Bu incelemede doğrulanmış bir kullanım koşulu sayfası bulunamadı; site yalnızca üçüncü taraf maç video sayfalarına yönlendiren keşif indeksi olarak ele alınır. | Terms URL boş; her video asıl yayıncıda ayrı kontrol edilir. |

**Önemli yorum:** Bu genel sayfalar bazı kullanımları açıkça sınırlandırsa da, bunlar otomatik olarak her bir maç videosu için ayrı hak kaydı oluşturmaz. Kaynak URL'sini kaydetmek, içeriği işleme izni vermez. Bu nedenle `video_rights_assessments` satırları, maç videosu bazında kanıt toplanana kadar `unknown` kalır.

## 4. Kaynak değerlendirme sırası

Her yeni kaynak için şu kontrol sırası uygulanır:

1. Kaynak sahibi/işleten kuruluşun kim olduğu belirlenir.
2. URL resmî katalog, yayıncı sayfası veya yalnızca keşif indeksi olarak sınıflandırılır.
3. Kapsanan ligler, sezonlar, yaş grupları ve ülkeler kaydedilir.
4. Maç bazında tamlık, süre ve kesinti durumu kontrol edilir.
5. Türkiye'den oynatma, hesap gereksinimi ve ücret durumu ayrı erişim kaydına yazılır.
6. Manuel scouting, otomatik analiz, ticari kullanım, indirme/depolama, klip çıkarma ve dağıtım hakları ayrı ayrı incelenir.
7. Her kararın kanıt bağlantısı, kontrol tarihi ve doğrulayanı kaydedilir.
8. Kanıt yetersizse durum `unknown` kalır; sistem izin varmış gibi davranmaz.

İlk sürümde kaynak keşfi manuel/yardımlı olacaktır. Sağlayıcı şartları izin vermedikçe scraping, video indirme, kopyalama, cache veya arşivleme otomasyonu yapılmaz. YouTube gibi platformlarda API ile video meta verisi okumak, videoyu indirme veya saklama izni olarak yorumlanmaz.

## 5. Hedef admin deneyimi

Özel admin panelinde ayrı bir **Kaynak Kataloğu** ekranı olmalı:

- Kaynak adı, türü, resmîlik durumu ve ana URL.
- Kapsam ve keşif notları.
- Kullanım koşulu URL'si ve son kontrol zamanı.
- Kaynağa bağlı maç videolarının sayısı.
- Son doğrulama durumu.

Maç video ekranında:
- Kaynak kataloğundan sağlayıcı seçimi.
- Orijinal maç/video sayfası URL'si.
- İçerik türü ve tamlık.
- Ülkeye göre erişim geçmişi.
- Kullanım hakları matrisi ve kanıt bağlantıları.

Kamuya açık oyuncu sayfasına kaynak kataloğu, video URL'si, erişim kontrolü veya özel hak notu taşınmaz.

## 6. Uygulama öncesi canlı veri tabanı bulguları — 12 Kasım 2026

Canlı Supabase denetiminde:
- `videos` ve `video_access_checks` tabloları mevcut.
- İkisi de RLS etkin ve `private.is_vel_staff()` kullanan personel yönetim politikasıyla korunuyor.
- `videos` içinde `source_name`, `video_url`, `video_type`, `duration_minutes`, `access_status`, `rights_status` ve not alanları var.
- `video_access_checks` ülke, erişim, hesap, ücret ve kapsama durumlarını geçmiş kayıtları halinde tutabiliyor.
- Mevcut `rights_status` alanı yalnızca `link_only`, `permission_granted`, `unknown` ayrımını yapabiliyor; kullanım amacına göre ayrı hakları ispatlamaya yetmiyor.

Bu bulgulara göre mevcut erişim geçmişi yeniden yazılmayacak. Yeni kaynak kataloğu ve video kullanım hakkı değerlendirmesi eklemeli biçimde tasarlanacak.

## 7. Migration geçmişi kurtarma ve uygulama durumu

### Tarihsel migration kaynakları geri yüklendi

12 Kasım 2026 öncesinde canlı migration defterinde sekiz kayıt bulunmasına rağmen `main` dalında yalnızca ilk iki SQL dosyası izleniyordu. Eksik altı dosya artık asıl uygulanma sürüm ve adlarıyla `supabase/migrations/` altına geri kondu:

- `20261111085851_create_atomic_scout_report_bundle.sql`
- `20261111104333_create_multi_match_scout_report_rpc.sql`
- `20261111105655_use_existing_secure_scout_report_bundle.sql`
- `20261111105858_fix_report_bundle_uuid_aggregate.sql`
- `20261111110233_add_multi_match_report_guard.sql`
- `20261111110636_enforce_multi_match_rubric_methodology.sql`

İlk iki dosya, Supabase veritabanında saklanan gerçek uygulama SQL ifadelerinden (`pg_stat_statements`) geri kuruldu. Son dört dosya, projedeki `feat/multi-match-report-synthesis` geliştirme dalındaki karşılık gelen migration dosyalarıyla eşleştirildi. Son canlı fonksiyon tanımları yeniden okundu ve kritik noktalar doğrulandı:
- `create_scout_report_bundle()` SECURITY INVOKER, boş `search_path` ve UUID agregasyon düzeltmesine sahip.
- `create_multi_match_scout_report_bundle()` SECURITY INVOKER, boş `search_path` ve rubrik/metodoloji eşleşme kontrolüne sahip.
- Emekliye ayrılmış geçici `create_multi_match_scout_report()` fonksiyonu artık mevcut değil.

Bu kurtarma, geçmiş migration SQL'ini tahmin ederek yeniden yazmak yerine uygulama geçmişine dayandırır. Bununla birlikte bu ortamda Supabase CLI bulunmadığı için temiz bir yerel veritabanında baştan sona `db reset` / replay çalıştırılmadı. Canlı veritabanındaki remote migration geçmişi ve şema/fonksiyon durumu doğrulandı; temiz yerel replay ayrı bir yeniden üretilebilirlik kontrolü olarak açık kalır.

### Kaynak kataloğu ve hak değerlendirme migration'ı

Yeni eklemeli migration canlı Supabase üzerinde başarıyla uygulandı:
- `20261112092105_create_video_source_registry_and_rights_assessments.sql`

Migration, `video_sources` ve `video_rights_assessments` tablolarını ekler, `videos.video_source_id` alanını oluşturur, her yeni video için altı kullanım hakkını `unknown` başlatan tetikleyiciyi kurar ve mevcut video satırlarını altı bilinmeyen hak kaydıyla geriye dönük tamamlar. Aynı SQL dosyası `main` dalında da izlenmektedir.

Uygulama sonrasında canlı migration defteri dokuz kayıt gösterir; ilk sekiz tarihsel sürüm ve yeni dokuzuncu migration depo dosyalarıyla eşleşir.

### Güvenlik ve test durumu

- `video_sources` ve `video_rights_assessments` RLS etkin özel tablolardır.
- Anonim SELECT ayrıcalığı yoktur; personel olmayan authenticated hesabın gerçek Data API testi henüz yapılmamıştır.
- `video_rights_assessments` personel için SELECT + INSERT ile sınırlıdır; UPDATE/DELETE izni yoktur. Kararlar geçmişe eklenir.
- Yeni video eklenmesiyle altı `unknown` hakkın otomatik oluşması, gerçek authenticated staff rolü altında transaction içinde test edildi; test transaction'ı rollback ile kapatıldı ve kalıcı deneme videosu bırakılmadı.
- İki mevcut video korunmuştur; her biri için altı kullanım hakkı `unknown` olarak kaydedilmiştir. Eski kaynak adları doğrulanmış sağlayıcı eşlemesi olmadığı için otomatik olarak `video_source_id` alanına bağlanmamıştır.
- Admin paneline kaynak kataloğu ve hak geçmişi ekranları eklendi. GitHub Pages dağıtımı ve canlı tarayıcı/Data API testi bu kayıttan bağımsız olarak doğrulanmalıdır.

Her yeni tablo RLS, grants ve gerçek API görünürlüğü birlikte doğrulanmadan tamamlanmış sayılmaz. Supabase'in güncel rehberi grants ile RLS'nin birlikte kontrol edilmesini önerir: https://supabase.com/docs/guides/database/postgres/row-level-security

## 8. Bu aşamanın tamamlanma ölçütü

- Kaynak sağlayıcılar ile tekil maç videoları birbirinden ayrılmıştır.
- İzleme erişimi ile altı farklı kullanım hakkı birbirinden ayrılmıştır.
- Sekiz başlangıç kaynağı yalnızca `candidate` durumunda kataloglanmıştır; hiçbiri otomatik olarak analiz veya ticari kullanım için onaylanmamıştır.
- Canlı veritabanındaki iki mevcut video için toplam 12 kullanım hakkı kaydı `unknown` olarak oluşturulmuştur.
- Yeni videolara altı `unknown` hakkı otomatik ekleyen tetikleyici personel rolüyle test edilmiştir.
- Kaynak ve hak tabloları staff-only RLS ile korunur; hak geçmişi append-only tasarlanmıştır.
- Dokuz remote migration kaydı ile dokuz SQL dosyası `main` dalında bulunmaktadır.
- Admin paneline katalog ekleme, katalogdan video kaynağı seçme ve hak değerlendirmesi geçmişine yeni karar ekleme işlevleri eklenmiştir.
- Anonim HTTP/Data API tarayıcı testi, non-staff authenticated testi ve GitHub Pages dağıtım sonrası panel kontrolü beklemektedir.
- Video dosyası kopyalama, indirme, saklama veya otomatik tarama için izinsiz bir mekanizma oluşturulmamıştır.

**Sonraki teknik adım:** Kaynak kataloğunun aday kayıtlarını maç ve video bazında manuel olarak doğrulamak; ardından admin panelinin canlı dağıtımda Data API testlerini tamamlamak ve yalnızca izinli video akışlarıyla bilgisayarlı görü prototipine geçmek.
