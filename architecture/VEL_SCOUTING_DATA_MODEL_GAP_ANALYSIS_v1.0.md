# VEL SCOUTING — Canlı Veri Modeli Fark Analizi

**Doküman:** VEL-DATA-01  
**Sürüm:** 1.0  
**Tarih:** 10 Kasım 2026  
**Durum:** Canlı şemaya dayalı analiz ve önerilen tasarım; henüz veritabanı migration'ı değildir.

---

## 1. Yönetici özeti

Canlı Supabase projesindeki 11 tablo incelendi. Mevcut yapı, futbolcu profili, maç kataloğu, oyuncu-maç katılımı, video kaynak bağlantısı ve serbest metin gözlemleri için iyi bir başlangıç sağlıyor. Ancak gerçek bir scouting değerlendirmesinin baştan sona izlenebilmesi için henüz yeterli değil.

Temel eksik, tabloların bulunmaması değil; **değerlendirme sürecinin ayrı ve izlenebilir bir varlık olarak modellenmemiş olması**.

Mevcut durumda:
- Video kaynağı maça bağlı; fakat hangi scout oturumunda hangi kaynağın kullanıldığı kayıtlı değil.
- Gözlem oyuncu-maç katılımına bağlı; fakat bir değerlendiriciye veya değerlendirme oturumuna bağlı değil.
- Gözlemde dakika alanı var; saniye hassasiyetinde video konumu ve maç saati ayrı tutulmuyor.
- Kriter adı serbest metin; sürümlenmiş kriter kataloğu ve kriter puanlama kaydı bulunmuyor.
- Gözlemde pozitif/negatif/belirsiz değerlendirmesi var; 1–6 puan bandı, N/E ve N/A ayrımı ve ağırlıklı kriter hesabı ayrı bir yapıda tutulmuyor.
- Scout raporu bir futbolcuya bağlı; raporu hangi maç oturumlarının ve kriter kanıtlarının desteklediği ilişkisel olarak kayıtlı değil.
- Video erişim/hak bilgisi tek bir güncel satırda tutuluyor; ülkeye göre erişim testi geçmişi bulunmuyor.
- Admin arayüzü henüz maç, oyuncu-maç, video ve gözlem tablolarını kullanmıyor. Kamu sayfasında da video alanı sorgulanmıyor.

**Öneri:** Mevcut 11 tabloyu yeniden yazmak yerine, onlara eklenen ve geçmiş veriyi bozmayan yeni değerlendirme tabloları ile küçük, geriye uyumlu alan eklemeleri tasarlamak. Önce özel değerlendirme akışı, ardından rapor ilişkilendirmesi ve yönetim arayüzü geliştirilmelidir.

## 2. Canlı şema envanteri

İnceleme, doğrudan `vel-scouting` Supabase projesinde yapıldı. Aşağıdaki tablo ve ilişkiler canlı katalogdan doğrulandı.

| Tablo | Mevcut işlev | Değerlendirme |
|---|---|---|
| `players` | Futbolcu temel bilgileri ve profil durumu | Profil başlangıcı için yeterli |
| `clubs` | Kulüp temel bilgileri | Başlangıç için yeterli |
| `competitions` | Organizasyon/lig | Başlangıç için yeterli |
| `seasons` | Sezon | Başlangıç için yeterli |
| `matches` | Maç, takımlar, skor, tarih, yaş kategorisi | Temel maç kataloğu mevcut |
| `player_matches` | Futbolcu-maç bağlantısı, kulüp, pozisyon/rol, dakika | Katılımı temsil ediyor; ilk/sonradan oyuna giriş bilgisi eksik |
| `videos` | Maça bağlı kaynak adı, URL, video türü, süre, erişim ve hak durumu | Kaynak kütüphanesinin çekirdeği mevcut |
| `observations` | Oyuncu-maç ilişkisine bağlı dakika, kategori, kriter ve not | Serbest metinli ilk gözlem kaydı |
| `scout_reports` | Futbolcu raporu, genel not, güçlü yönler, gelişim alanları, durum | Yayına dönük özet için mevcut |
| `report_versions` | Raporun JSON anlık görüntüsü ve sürüm numarası | Sürümleme temeli mevcut |
| `user_roles` | `admin` ve `editor` rolleri | Mevcut erişim modeli korunabilir |

### Mevcut ilişkiler

- `players.current_club_id → clubs.id`
- `matches.home_club_id / away_club_id → clubs.id`
- `matches.competition_id → competitions.id`
- `matches.season_id → seasons.id`
- `player_matches.player_id → players.id`
- `player_matches.match_id → matches.id`
- `player_matches.club_id → clubs.id`
- `videos.match_id → matches.id`
- `observations.player_match_id → player_matches.id`
- `scout_reports.player_id → players.id`
- `report_versions.report_id → scout_reports.id`

Ayrıca `player_matches` için futbolcu+maç tekilliği; `report_versions` için rapor+sürüm tekilliği mevcut. Bunlar korunmalı.

## 3. Gereksinim–mevcut yapı farkı

| Gereksinim | Bugünkü karşılık | Eksik / risk | Öncelik |
|---|---|---|---|
| Bir futbolcunun bir maçtaki katılımı | `player_matches` | Başlangıç dakikası, bitiş dakikası ve ilk 11/yedek/oyuna giriş bilgisi yok | Orta |
| Bir maç için birden fazla resmî video kaynağı | `videos` | İlişki kurulabiliyor; ancak kaynakların scout oturumunda hangisinin kullanıldığı yok | Yüksek |
| Ülkeye göre erişim doğrulaması | `videos.access_status`, `last_checked_at` | Ülke, kontrol eden, hesap/abonelik gereksinimi ve geçmiş kontroller yok | Yüksek |
| Video izleme hakkı ile yeniden kullanım hakkını ayırmak | `videos.rights_status` | Mevcut üç durum kapsamı açıklamak için yetersiz; bağlantı sahibi olmak hak sahibi olmak değildir | Yüksek |
| Bir değerlendirme oturumu | Yok | Değerlendirici, metodoloji sürümü, durum ve oturum geçmişi kayıtlı değil | Kritik |
| Video zamanına hassas gözlem | `observations.minute` | Yalnızca tam dakika; video konumu, maç saati ve devre ayrımı yok | Kritik |
| Sabit ve sürümlenmiş kriter kataloğu | `observations.category/criterion` metni | Yazım farklılıkları, kriter tanımı/ağırlığı/sürümü üzerinde merkezi kontrol yok | Kritik |
| Kriter başına 1–6 puan | Yok | Gözlem duygusu ile puan birbirine karışabilir; puan çıpaları veritabanında izlenmiyor | Kritik |
| N/E ve N/A ayrımı | Yok | Gözlenemeyen kriter ile uygulanamaz kriter ayrıştırılamıyor | Kritik |
| Bir kritere birden fazla olay kanıtı | Gözlem satırları kısmen karşılıyor | Olayların tek kriter puanına ve aynı oturuma bağlanması yok | Yüksek |
| Çok maçlı rapor kanıtı | Rapor yalnızca futbolcuya bağlı | Raporu destekleyen oturumlar ayrı ilişkiyle gösterilemiyor | Yüksek |
| Değerlendiriciler arası karşılaştırma | Yok | Bağımsız değerlendirmeler ve uzlaşma süreci modellenmemiş | Orta |
| Kamuya özel veri ayrımı | RLS politikaları | Mevcut sınırlar iyi bir başlangıç; gerçek API kullanıcı testleri ayrıca gerekli | Yüksek |

## 4. Önerilen hedef veri modeli

### 4.1. `scouting_sessions` — değerlendirme oturumu

Bir scout'un belirli bir futbolcunun belirli bir maç performansını, belirli bir metodoloji sürümüyle incelediği çalışma kaydı.

Önerilen alanlar:
- `id` UUID primary key
- `player_match_id` FK → `player_matches.id`
- `evaluator_user_id` FK → `auth.users.id`
- `rubric_version_id` FK → `rubric_versions.id`
- `status`: `draft`, `in_review`, `completed`, `locked`
- `started_at`, `completed_at`, `created_at`, `updated_at`
- Gerekiyorsa yalnızca personelin göreceği oturum notu

Aynı futbolcu-maç için birden fazla oturum açılabilmeli. Bu, bağımsız değerlendirici ve yeniden değerlendirme ihtiyacını karşılar. Oturum tamamlandığında kullanılan kriter sürümü değişmemelidir.

### 4.2. `scouting_session_videos` — oturumda kullanılan kaynaklar

Bir maçın birden fazla video kaynağı olabilir. Oturum birden fazla kaynak kullanabilmeli; hangi kaynağın hangi oturumda kullanıldığı açıkça saklanmalı.

Önerilen alanlar:
- `id`
- `session_id` FK → `scouting_sessions.id`
- `video_id` FK → `videos.id`
- `is_primary`
- `usage_note` — örneğin ilk yarı veya belirli kamera açısı
- `created_at`

Veritabanı seviyesinde oturumun oyuncu-maç kaydı ile seçilen videonun aynı maça ait olduğu doğrulanmalıdır. İlk tasarımda bunun için uygun bileşik foreign key/unique anahtarları değerlendirilecek; yalnızca arayüz kontrolüne güvenilmeyecektir.

### 4.3. `rubric_versions` — metodoloji sürümleri

Metodoloji sürümünü yalnızca serbest metin olarak rapora yazmak yerine merkezi ve değiştirilemez sürüm kaydı.

Önerilen alanlar:
- `id`
- `version_code` — ör. `CB-1.0`
- `position_group`
- `status`: `draft`, `active`, `retired`
- `published_at`, `created_at`
- `change_summary`

Yayımlanmış bir rubrik sürümü sonradan sessizce değiştirilmemeli. Düzeltme gerektiğinde yeni sürüm açılmalı.

### 4.4. `rubric_criteria` — kriter kataloğu

Her kriter, ait olduğu metodoloji sürümünden bağımsız olmayan bir kayıt olmalı.

Önerilen alanlar:
- `id`
- `rubric_version_id` FK
- `criterion_code` — sürüm içinde sabit anahtar
- `category`
- `criterion_name`
- `definition`
- `weight`
- `score_anchors` JSONB — 1–6 puan bantlarının davranışsal tanımları
- `sort_order`

Tekillik: `rubric_version_id + criterion_code`.

Puan çıpaları yalnızca etiketten ibaret olmamalı; her puan seviyesi gözlenebilir davranışla tanımlanmalı. Stoper rubriğindeki 37 alt kriter bu yapıya taşınabilecek ilk set olur. Diğer pozisyon gruplarının çıpaları tamamlanmadan kriter setleri varsayımla oluşturulmamalı.

### 4.5. `criterion_scores` — kriter başına değerlendirme

Bir oturumda bir kriter için tek bir nihai/geçici kriter puanı tutulmalı; olaya dayalı birden fazla gözlem ayrı satırlarda saklanabilmeli.

Önerilen alanlar:
- `id`
- `session_id` FK → `scouting_sessions.id`
- `criterion_id` FK → `rubric_criteria.id`
- `score` — 1–6 arasında tam sayı; her zaman zorunlu olmayabilir
- `applicability`: `scored`, `not_observed`, `not_applicable`
- `rationale` — puanın kısa gerekçesi
- `created_at`, `updated_at`

Kurallar:
- `scored` ise puan 1–6 arasında olmalı.
- `not_observed` veya `not_applicable` ise puan boş kalmalı.
- N/E ve N/A hiçbir zaman 0 puan gibi hesaplanmamalı.
- Her oturum + kriter için en fazla bir puan kaydı olmalı.
- Uygulanabilir kriter ağırlığı kapsamı ayrıca hesaplanmalı; kapsam yetersizse sistem genel puan üretmemeli.

### 4.6. `observations` — mevcut kayıtları bozmadan zenginleştirme

Mevcut tabloyu silmek veya yeniden adlandırmak yerine aşağıdaki nullable alanlarla genişletmek önerilir:
- `session_id` FK → `scouting_sessions.id`
- `session_video_id` FK → `scouting_session_videos.id` (gözlemin hangi kaynak görüntüden geldiği)
- `criterion_id` FK → `rubric_criteria.id`
- `video_offset_seconds` — oynatıcı içindeki mutlak saniye
- `match_clock_seconds` — maç saati karşılığı
- `period_code` — `first_half`, `second_half`, uzatma/devre dışı veya bilinmiyor gibi kontrollü değer

Mevcut `minute`, `category`, `criterion`, `situation`, `observation`, `evaluation` ve `evidence_level` alanları geriye uyumluluk için korunmalı. Yeni akışta `criterion_id` ve oturum bağlantısı esas olmalı; eski satırlar otomatik olarak tahmini kriter kimliği veya saniye ile doldurulmamalı.

**Zaman ayrımı önemlidir:** video içindeki 00:35:10 konumu ile maç saatindeki 35. dakika aynı alan değildir. Video başında yayın grafiği veya kesinti varsa iki değer farklılaşır. Bu yüzden video offset ve maç saati ayrı tutulmalıdır.

### 4.7. `scout_report_sessions` — raporun kanıt oturumları

Bir rapor birden fazla maçtan ve değerlendirme oturumundan beslenebilir. Bunu yalnızca JSON snapshot içine gömmek yerine ilişkisel olarak izlemek önerilir.

Önerilen alanlar:
- `report_id` FK → `scout_reports.id`
- `session_id` FK → `scouting_sessions.id`
- `contribution_note` — rapora hangi kanıt katkısını sağladığı
- `created_at`

Tekillik: `report_id + session_id`.

Böylece bir raporun kaç maç/oturum kanıtıyla hazırlandığı ve her iddianın hangi değerlendirme oturumlarına dayandığı gösterilebilir. `report_versions.report_snapshot` ise yayınlandığı andaki notları, kriter puanlarını, kapsamı, metodoloji sürümünü ve oturum kimliklerini dondurulmuş halde saklamaya devam eder.

### 4.8. `video_access_checks` — kaynak erişim kontrol geçmişi

Mevcut `videos` tablosu bağlantı ve güncel durum özetini taşımaya devam edebilir. Erişim kontrolü geçmişi ayrı, eklemeli bir tabloya yazılmalı.

Önerilen alanlar:
- `id`
- `video_id` FK → `videos.id`
- `country_code` — ör. `TR`
- `checked_by` FK → `auth.users.id`
- `checked_at`
- `access_result`: `available`, `unavailable`, `restricted`, `unknown`
- `account_requirement`: `none`, `free_account`, `subscription`, `institutional`, `unknown`
- `price_status`: `free`, `paid`, `unknown`
- `coverage_status`: `full_match`, `partial`, `highlights`, `unknown`
- `notes`

Bu tablo geçmişi silmeden erişimin Türkiye'de ve başka ülkelerde ne zaman nasıl doğrulandığını gösterir. Erişim izni ile içerik üzerindeki yeniden kullanım hakkı ayrı tutulur. `rights_status` için “link_only” değeri video içeriğini kopyalama veya yayımlama izni olarak yorumlanmamalıdır.

## 5. Önerilen ilişki akışı

```text
players
  └── player_matches ── matches
        ├── videos
        └── scouting_sessions
              ├── scouting_session_videos ── videos
              ├── criterion_scores ── rubric_criteria ── rubric_versions
              └── observations
                    ├── session_video
                    └── criterion

scout_reports
  ├── scout_report_sessions ── scouting_sessions
  └── report_versions (frozen JSON snapshot)

videos
  └── video_access_checks
```

## 6. Admin paneli ile uyum

Canlı `admin.html` dosyasında şu an `matches`, `player_matches`, `videos` veya `observations` kullanım akışı bulunmuyor. Bu nedenle yalnızca tablo açmak scouting kütüphanesini kullanıma hazır hale getirmeyecek.

Önerilen ekran sırası:
1. **Maç kataloğu:** maç, organizasyon, sezon, takımlar, tarih, yaş grubu.
2. **Oyuncu katılımı:** maçtaki oyuncu, oynadığı kulüp, pozisyon/rol, dakika.
3. **Video kaynakları:** resmî kaynak URL'si, tamlık, süre, erişim/hak durumu, son kontrol.
4. **Scout oturumu:** değerlendirici, oyuncu-maç, rubrik sürümü, oturum durumu.
5. **Zaman damgalı kanıt:** video zamanı, maç zamanı, kriter ve gözlem notu.
6. **Kriter puanları:** 1–6 çıpaları, N/E/N/A, kapsam.
7. **Rapor derleme:** çok maçlı kanıt bağlantıları, sürümleme, editoryal onay.

Kamuya açık `index.html` video tablosu veya video URL'si sorgulamamalı. Özel ekran için yeni sorgular yalnızca authenticated personel bağlamında kullanılmalı.

## 7. Güvenlik ve mahremiyet tasarımı

Yeni eklenecek her özel tablo için:
- RLS oluşturulurken aynı migration içinde etkinleştirilmeli.
- Anon için tablo erişimi verilmemeli.
- Authenticated CRUD izinleri RLS ile yalnızca mevcut `admin/editor` personel üyeliğine bağlanmalı.
- Video URL'leri, özel kaynak notları ve ham gözlemler public JavaScript/JSON içine yazılmamalı.
- Değerlendirici alanları istemciden serbestçe seçilememeli; oturum açmış kullanıcının `auth.uid()` değeri kullanılmalı.
- `user_metadata` rol belirlemek için kullanılmamalı.
- Genç futbolcuların doğum tarihi gibi kişisel verileri kamuya açık profilde gereksiz ayrıntıyla gösterilmemeli.

Canlı migration'larda `postgres` SQL/migration yolu kullanılmalı; `supabase_admin` varsayılan ACL sınırlaması çözülene kadar yeni public tabloların varsayılan izinleri ayrıca kontrol edilmelidir.

## 8. Geriye uyumlu uygulama sırası

**Bu belge tasarım kararıdır; henüz yeni tablo veya sütun oluşturulmamıştır.**

Önerilen migration sırası:

1. **Rubrik altyapısı:** `rubric_versions`, `rubric_criteria` tablolarını oluştur; yalnızca tamamlanmış pozisyon rubriklerini ekle.
2. **Oturum ve kaynak ilişkisi:** `scouting_sessions`, `scouting_session_videos`, `video_access_checks` tablolarını oluştur.
3. **Kriter değerlendirmesi:** `criterion_scores` tablosunu ekle.
4. **Gözlem genişletmesi:** mevcut `observations` tablosuna nullable session/video/criterion/time alanlarını ekle.
5. **Rapor kanıtı:** `scout_report_sessions` bağlantısını ekle; snapshot üretimini ilişki listesini içerecek şekilde geliştir.
6. Her aşamada yeni tabloların RLS, grants, policy ve API görünürlüğünü doğrula.
7. Önce admin panelini özel maç/kaynak/oturum akışına bağla; public siteye yeni özel alan ekleme.
8. Anon, yetkisiz authenticated ve staff testleri tamamlanmadan özel kaynak UI'sini hazır sayma.

Veri kaybı gerektiren `DROP`, zorunlu alanı eski satırlara tahmini değerle doldurma veya mevcut gözlem/raporları dönüştürme işlemi yapılmamalı. Önce nullable alan ve paralel yeni tablolar, ardından kontrollü geçiş tercih edilmeli.

## 9. Açık kararlar ve ilk uygulama kapsamı

İlk gerçek uygulama için önerilen kapsam:
- Bir oyuncu + bir maç katılımı + bir scout oturumu.
- Bir oturumda bir veya birden fazla resmî video kaynağı.
- Saniye hassasiyetinde gözlem ve kriter bağlantısı.
- Sürümü sabitlenmiş kriter puanları.
- Raporun dayandığı oturumların açık ilişkisi.

İlk sürüme şunları eklemeyi ertele:
- Yeni `scout` rolü (mevcut `editor` yeterli).
- Otomatik video kazıma.
- Video dosyalarını barındırma veya indirme.
- Otomatik futbolcu potansiyel/transfer tahmini.
- İki değerlendirici olmadan değerlendiriciler arası güvenilirlik iddiası.

**Önemli operasyonel dürüstlük:** Bir scout oturumunda değerlendirici alanı, görüntüyü gerçekten inceleyen yetkili hesabı göstermelidir. Bir kaynağın yalnızca URL'sinin kayıtlı olması video içeriğinin incelendiğini kanıtlamaz. İçerik erişilebilir ve gerçekten analiz edilmiş değilse hiçbir gözlem veya puan üretilmiş gibi gösterilmemelidir.

## 10. Sonuç

Mevcut veritabanı terk edilmeyecek. `matches`, `player_matches`, `videos`, `observations`, `scout_reports` ve `report_versions` tabloları doğru temel ilişkileri sağlıyor. Eksik katman, değerlendirme oturumu, sürümlenmiş kriter, puan, video zaman konumu, erişim denetim geçmişi ve rapor-kanît bağlantısı.

**Bir sonraki teknik çıktı:** Bu tasarıma göre ilk migration setini hazırlamak; önce yalnızca oturum, rubrik ve erişim geçmişi tablolarını ekleyerek RLS testini tamamlamak. UI, testler geçtikten sonra geliştirilecek.
