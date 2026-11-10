-- Vel Scouting additive scouting schema, applied live as 20261110174605.
-- The centre-back anchors are imported as PILOT, not an activated/validated rubric.

ALTER TABLE public.player_matches ADD CONSTRAINT player_matches_scouting_identity_key UNIQUE (id, player_id, match_id);
ALTER TABLE public.videos ADD CONSTRAINT videos_match_identity_key UNIQUE (id, match_id);
ALTER TABLE public.scout_reports ADD CONSTRAINT scout_reports_player_identity_key UNIQUE (id, player_id);

CREATE TABLE public.rubric_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 version_code text NOT NULL UNIQUE,
 position_group text NOT NULL,
 methodology_version text NOT NULL,
 scoring_anchors_version text NOT NULL,
 score_min smallint NOT NULL DEFAULT 1 CHECK (score_min=1),
 score_max smallint NOT NULL DEFAULT 10 CHECK (score_max=10),
 status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pilot','active','retired')),
 source_document text NOT NULL,
 change_summary text,
 created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 UNIQUE(id, position_group)
);

CREATE TABLE public.rubric_categories (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 rubric_version_id uuid NOT NULL REFERENCES public.rubric_versions(id) ON DELETE RESTRICT,
 category_code text NOT NULL,
 category_name text NOT NULL,
 category_weight_percent smallint NOT NULL CHECK (category_weight_percent BETWEEN 1 AND 100),
 sort_order smallint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(rubric_version_id,category_code),
 UNIQUE(id,rubric_version_id)
);

CREATE TABLE public.rubric_criteria (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 rubric_version_id uuid NOT NULL REFERENCES public.rubric_versions(id) ON DELETE RESTRICT,
 rubric_category_id uuid NOT NULL,
 criterion_code text NOT NULL,
 criterion_name text NOT NULL,
 weight_percent smallint NOT NULL CHECK (weight_percent BETWEEN 1 AND 100),
 score_anchors jsonb NOT NULL CHECK (
  jsonb_typeof(score_anchors)='object'
  AND score_anchors ? '1–2' AND score_anchors ? '3–4'
  AND score_anchors ? '5–6' AND score_anchors ? '7–8'
  AND score_anchors ? '9' AND score_anchors ? '10'
 ),
 sort_order smallint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT rubric_criteria_category_version_fk
  FOREIGN KEY(rubric_category_id,rubric_version_id)
  REFERENCES public.rubric_categories(id,rubric_version_id) ON DELETE RESTRICT,
 UNIQUE(rubric_version_id,criterion_code),
 UNIQUE(id,rubric_version_id)
);

CREATE TABLE public.scouting_sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 player_id uuid NOT NULL,
 player_match_id uuid NOT NULL,
 match_id uuid NOT NULL,
 rubric_version_id uuid NOT NULL REFERENCES public.rubric_versions(id) ON DELETE RESTRICT,
 evaluator_user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE RESTRICT,
 status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','in_review','completed','locked')),
 private_notes text,
 started_at timestamptz,
 completed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT scouting_sessions_player_match_fk
  FOREIGN KEY(player_match_id,player_id,match_id)
  REFERENCES public.player_matches(id,player_id,match_id) ON DELETE RESTRICT,
 CONSTRAINT scouting_sessions_completed_time_check
  CHECK(completed_at IS NULL OR started_at IS NULL OR completed_at>=started_at),
 UNIQUE(id,player_match_id),
 UNIQUE(id,player_id),
 UNIQUE(id,match_id),
 UNIQUE(id,rubric_version_id)
);

CREATE TABLE public.scouting_session_videos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 session_id uuid NOT NULL,
 match_id uuid NOT NULL,
 video_id uuid NOT NULL,
 is_primary boolean NOT NULL DEFAULT false,
 usage_note text,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT scouting_session_videos_session_match_fk
  FOREIGN KEY(session_id,match_id)
  REFERENCES public.scouting_sessions(id,match_id) ON DELETE CASCADE,
 CONSTRAINT scouting_session_videos_video_match_fk
  FOREIGN KEY(video_id,match_id)
  REFERENCES public.videos(id,match_id) ON DELETE RESTRICT,
 UNIQUE(session_id,video_id),
 UNIQUE(id,session_id)
);
CREATE UNIQUE INDEX scouting_session_videos_one_primary_idx
 ON public.scouting_session_videos(session_id) WHERE is_primary;

CREATE TABLE public.criterion_scores (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 session_id uuid NOT NULL,
 rubric_version_id uuid NOT NULL,
 criterion_id uuid NOT NULL,
 score smallint,
 applicability text NOT NULL CHECK(applicability IN ('scored','not_observed','not_applicable')),
 rationale text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT criterion_scores_session_version_fk
  FOREIGN KEY(session_id,rubric_version_id)
  REFERENCES public.scouting_sessions(id,rubric_version_id) ON DELETE CASCADE,
 CONSTRAINT criterion_scores_criterion_version_fk
  FOREIGN KEY(criterion_id,rubric_version_id)
  REFERENCES public.rubric_criteria(id,rubric_version_id) ON DELETE RESTRICT,
 CONSTRAINT criterion_scores_score_state_check
  CHECK((applicability='scored' AND score BETWEEN 1 AND 10)
     OR (applicability IN ('not_observed','not_applicable') AND score IS NULL)),
 UNIQUE(session_id,criterion_id)
);

CREATE TABLE public.video_access_checks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 video_id uuid NOT NULL REFERENCES public.videos(id) ON DELETE CASCADE,
 country_code varchar(2) NOT NULL CHECK(country_code ~ '^[A-Z]{2}$'),
 checked_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
 checked_at timestamptz NOT NULL DEFAULT now(),
 access_result text NOT NULL CHECK(access_result IN ('available','unavailable','restricted','unknown')),
 account_requirement text NOT NULL CHECK(account_requirement IN ('none','free_account','subscription','institutional','unknown')),
 price_status text NOT NULL CHECK(price_status IN ('free','paid','unknown')),
 coverage_status text NOT NULL CHECK(coverage_status IN ('full_match','partial','highlights','unknown')),
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.scout_report_sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 report_id uuid NOT NULL,
 session_id uuid NOT NULL,
 player_id uuid NOT NULL,
 contribution_note text,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT scout_report_sessions_report_player_fk
  FOREIGN KEY(report_id,player_id)
  REFERENCES public.scout_reports(id,player_id) ON DELETE CASCADE,
 CONSTRAINT scout_report_sessions_session_player_fk
  FOREIGN KEY(session_id,player_id)
  REFERENCES public.scouting_sessions(id,player_id) ON DELETE RESTRICT,
 UNIQUE(report_id,session_id)
);

ALTER TABLE public.observations
 ADD COLUMN session_id uuid,
 ADD COLUMN session_video_id uuid,
 ADD COLUMN rubric_version_id uuid,
 ADD COLUMN criterion_id uuid,
 ADD COLUMN video_offset_seconds integer,
 ADD COLUMN match_clock_seconds integer,
 ADD COLUMN period_code text,
 ADD CONSTRAINT observations_session_player_match_fk
  FOREIGN KEY(session_id,player_match_id)
  REFERENCES public.scouting_sessions(id,player_match_id) ON DELETE CASCADE,
 ADD CONSTRAINT observations_session_video_fk
  FOREIGN KEY(session_video_id,session_id)
  REFERENCES public.scouting_session_videos(id,session_id) ON DELETE RESTRICT,
 ADD CONSTRAINT observations_session_rubric_fk
  FOREIGN KEY(session_id,rubric_version_id)
  REFERENCES public.scouting_sessions(id,rubric_version_id) ON DELETE RESTRICT,
 ADD CONSTRAINT observations_criterion_rubric_fk
  FOREIGN KEY(criterion_id,rubric_version_id)
  REFERENCES public.rubric_criteria(id,rubric_version_id) ON DELETE RESTRICT,
 ADD CONSTRAINT observations_video_offset_nonnegative_check CHECK(video_offset_seconds IS NULL OR video_offset_seconds>=0),
 ADD CONSTRAINT observations_match_clock_nonnegative_check CHECK(match_clock_seconds IS NULL OR match_clock_seconds>=0),
 ADD CONSTRAINT observations_period_code_check
  CHECK(period_code IS NULL OR period_code IN ('first_half','second_half','extra_time_first_half','extra_time_second_half','penalty_shootout','unknown')),
 ADD CONSTRAINT observations_session_context_check
  CHECK((session_id IS NOT NULL AND rubric_version_id IS NOT NULL)
     OR (session_id IS NULL AND session_video_id IS NULL AND rubric_version_id IS NULL
         AND criterion_id IS NULL AND video_offset_seconds IS NULL
         AND match_clock_seconds IS NULL AND period_code IS NULL)),
 ADD CONSTRAINT observations_video_offset_source_check CHECK(video_offset_seconds IS NULL OR session_video_id IS NOT NULL);

CREATE INDEX scouting_sessions_player_created_idx ON public.scouting_sessions(player_id,created_at DESC);
CREATE INDEX scouting_sessions_player_match_idx ON public.scouting_sessions(player_match_id);
CREATE INDEX scouting_sessions_evaluator_status_idx ON public.scouting_sessions(evaluator_user_id,status);
CREATE INDEX scouting_session_videos_video_idx ON public.scouting_session_videos(video_id);
CREATE INDEX rubric_criteria_version_category_idx ON public.rubric_criteria(rubric_version_id,rubric_category_id,sort_order);
CREATE INDEX criterion_scores_session_idx ON public.criterion_scores(session_id);
CREATE INDEX video_access_checks_video_country_date_idx ON public.video_access_checks(video_id,country_code,checked_at DESC);
CREATE INDEX scout_report_sessions_session_idx ON public.scout_report_sessions(session_id);
CREATE INDEX observations_session_offset_idx ON public.observations(session_id,video_offset_seconds) WHERE session_id IS NOT NULL;

CREATE TRIGGER rubric_versions_set_updated_at BEFORE UPDATE ON public.rubric_versions
 FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER scouting_sessions_set_updated_at BEFORE UPDATE ON public.scouting_sessions
 FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER criterion_scores_set_updated_at BEFORE UPDATE ON public.criterion_scores
 FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

INSERT INTO public.rubric_versions(version_code,position_group,methodology_version,scoring_anchors_version,score_min,score_max,status,source_document,change_summary)
VALUES ('CB-METH-0.8-ANCHORS-1.0','centre_back','0.8','1.0',1,10,'pilot',
 'methodology/VEL_CENTRE_BACK_SCORING_ANCHORS_v1.0.md',
 '37 stoper kriteri ve 1–10 puan çıpaları aktarıldı. Gerçek maç kalibrasyonu tamamlanmadığı için pilot durumda.');

INSERT INTO public.rubric_categories(rubric_version_id,category_code,category_name,category_weight_percent,sort_order)
SELECT v.id,c.category_code,c.category_name,c.category_weight_percent,c.sort_order
FROM public.rubric_versions v
CROSS JOIN (VALUES
 ('tactical_positional','Taktiksel ve pozisyonel uygulama',30,1),
('game_intelligence','Oyun zekâsı ve karar verme',20,2),
('technical','Teknik uygulama',20,3),
('physical_functional','Fiziksel ve fonksiyonel özellikler',15,4),
('competitive_behaviours','Rekabetçi davranışlar',15,5)
) AS c(category_code,category_name,category_weight_percent,sort_order)
WHERE v.version_code='CB-METH-0.8-ANCHORS-1.0';

INSERT INTO public.rubric_criteria(rubric_version_id,rubric_category_id,criterion_code,criterion_name,weight_percent,score_anchors,sort_order)
SELECT v.id,cat.id,c.criterion_code,c.criterion_name,c.weight_percent,c.score_anchors,c.sort_order
FROM public.rubric_versions v
CROSS JOIN (VALUES
 ('tactical_positional','CB-01','Savunma pozisyonu ve vücut yönelimi',5,'{"9":"Farklı hücum durumlarında konumunu sürekli günceller; rakibin hareket yönünü sınırlar ve savunma seçeneklerini daraltır.","10":"Konum ve vücut açısı sürekli avantaj üretir; rakip hücumun seçeneklerini erken kapatır ve takımın savunma yapısını olağanüstü istikrarlı kılar.","1–2":"Sık sık yanlış hatta veya açıyla konumlanır; rakip kolayca önüne/yanına geçer ve temel savunma görevini sürdüremez.","3–4":"Pozisyon alma hataları tekrarlanır; doğru konuma geçişi gecikir ve vücut açısı rakibin tehlikeli ilerleme yönünü açık bırakır.","5–6":"Temel savunma konumunu çoğunlukla korur; ancak topun, rakibin ve takım arkadaşlarının konumuna göre açı/mesafe ayarını tutarsız yapar.","7–8":"Çoğu durumda doğru mesafe ve vücut açısını kurar; rakibi tehlikeli alandan uzak tutar, küçük konum hataları sınırlı etki yaratır."}'::jsonb,1),
('tactical_positional','CB-02','Merkez ve çevre alan kontrolü',4,'{"9":"Topun yeri değişirken merkez/çevre alan dengesini erken ayarlar; doğrudan müdahale etmeden rakibin ilerleme seçeneklerini azaltır.","10":"Alan kontrolü rakibin merkezden ilerleme yollarını sürekli etkisizleştirir; takım arkadaşlarının hareketlerini de kapsayan üst düzey bir denge sağlar.","1–2":"Merkez koridoru ve yakın çevredeki tehlikeli alanları tekrar tekrar boş bırakır; rakip bu boşluklardan kolayca ilerler.","3–4":"Merkez alanı geç fark eder; topa yönelirken çevre korumasını kaybeder ve rakibe belirgin ilerleme alanı verir.","5–6":"Merkez alanı temel düzeyde korur fakat topun yönü değiştiğinde veya takım arkadaşı öne çıktığında boşlukları geç kapatır.","7–8":"Merkez ve yakın çevreyi çoğunlukla dengeli korur; gerektiğinde alan daraltır ve rakibi daha düşük tehditli bölgeye yönlendirir."}'::jsonb,2),
('tactical_positional','CB-03','Savunma derinliği ve çizgi yönetimi',4,'{"9":"Rakip derinlik tehdidini ve takım baskısını erken okuyarak çizgiyi zamanında ayarlar; savunma arkasındaki alanı etkin yönetir.","10":"Çizgi davranışını sürekli ve doğru yönetir; takımın savunma derinliğini yönlendirecek seviyede erken bilgi ve konum avantajı üretir.","1–2":"Savunma çizgisini sık sık bozar; gereksiz öne çıkma veya geç geri düşme ile savunma arkasında tekrarlanan tehlike yaratır.","3–4":"Derinlik ayarını çoğu kez geç yapar; rakip koşulara veya takım arkadaşlarının çıkışına uyum sağlayamaz.","5–6":"Çizgi yüksekliğini genel olarak takip eder ancak baskı, derin koşu ve takım arkadaşının hareketlerine göre ayarlaması dalgalıdır.","7–8":"Çoğu durumda doğru derinliği korur; çizgiyle uyumlu hareket eder ve riskli anlarda gerektiğinde geriye düşer."}'::jsonb,3),
('tactical_positional','CB-04','Ceza sahası savunması',4,'{"9":"Servis öncesi konumunu ayarlar; rakip koşuları, topun yönü ve ikinci top tehdidini erken okuyup tehlikeyi azaltır.","10":"Ceza sahası içinde top ve rakip ilişkisini sürekli kontrol eder; takım savunmasının alan paylaşımını belirgin biçimde güvenceye alır.","1–2":"Ceza sahasında top ve rakip takibini sık sık kaybeder; temel tehlikeli alanları ve servis yollarını koruyamaz.","3–4":"Rakip koşulara geç tepki verir; ön/arka direk veya merkez alan paylaşımında tekrarlanan açıklar verir.","5–6":"Temel alanı savunur fakat top-rakip takibi, seken top ve direk alanları arasında zaman zaman kararsız kalır.","7–8":"Çoğu servis ve koşuda doğru alanı korur; rakip takibini ve topa müdahaleyi dengeli yürütür."}'::jsonb,4),
('tactical_positional','CB-05','Hücumdan savunmaya geçiş ve derinlik koruma',4,'{"9":"Geçişte tehlikeyi erken tanımlar; topa baskı ile derinlik koruma arasında doğru görevi seçer ve takımın yapısını hızla toparlar.","10":"Geçiş anlarında sürekli doğru öncelik belirler; rakibin ilk ilerleme seçeneğini etkisizleştirip savunma dengesini üst düzeyde korur.","1–2":"Top kaybı sonrası sık sık reaksiyonsuz kalır; savunma arkasına koşuları ve merkezden çıkışı kontrol edemez.","3–4":"İlk reaksiyonu çoğu kez geç veya yanlış yöndedir; takımın savunma yerleşimi bozulurken boşlukları kapatamaz.","5–6":"Genellikle savunma görevine döner fakat ilk pası, rakip koşuyu veya gerideki alanı önceliklendirmede tutarsızlık gösterir.","7–8":"Top kaybından sonra çoğunlukla doğru alanı kapatır; derinliği yeniden kurar ve takımın geri yerleşmesine yardım eder."}'::jsonb,5),
('tactical_positional','CB-06','Savunma koordinasyonu ve stoperler arası mesafe',3,'{"9":"Hat kaymalarını erken takip eder; takım arkadaşının müdahalesini güvenceye alır ve savunma zincirinin bütünlüğünü korur.","10":"Koordinasyonuyla savunma hattının birlikte hareket etmesini sağlar; alan paylaşımı ve destek zamanlaması sürekli üst düzeydedir.","1–2":"Diğer savunmacılarla mesafeyi sık sık koparır; aynı alanı paylaşır veya kritik koridoru boş bırakır.","3–4":"Hat kaymalarına geç uyum sağlar; takım arkadaşının çıkışını ve arkasındaki alan paylaşımını çoğu kez telafi edemez.","5–6":"Temel mesafeyi korur ancak topun yönü, rakip koşu ve takım arkadaşının çıkışına göre koordinasyonu dalgalıdır.","7–8":"Çoğu durumda doğru yatay/dikey mesafeyi korur; takım arkadaşının hareketine uygun destek verir."}'::jsonb,6),
('tactical_positional','CB-07','Geniş alan savunması ve koridor kontrolü',3,'{"9":"Geniş alana çıkış ve merkez korumasını dengeler; rakibin seçeneklerini sınırlar ve gerektiğinde savunma hattına zamanında döner.","10":"Geniş alanda hem bire bir hem takım alanını aynı anda yönetir; rakibin ilerleme yönünü ve takımın geri kalanını sürekli avantajlı konumda tutar.","1–2":"Geniş alanda rakibi kolayca geçirtir; iç koridoru ve gerideki alanı aynı anda kontrol edemez.","3–4":"Kanat/yarım alan savunmasında açı ve mesafe hataları tekrarlanır; rakibin çizgiye veya merkeze ilerlemesini yönetemez.","5–6":"Temel bire bir mesafesini korur fakat destek gelene kadar rakibi yönlendirme veya iç koridoru kapatma kalitesi değişkendir.","7–8":"Çoğu durumda rakibi tehlikeli iç alandan uzak tutar; geniş koridorda geciktirme ve geri dönüş görevini yerine getirir."}'::jsonb,7),
('tactical_positional','CB-08','Rakip koşularını takip ve alan paylaşımı',3,'{"9":"Koşu öncesi işaretleri okur; kör taraf ve çapraz hareketleri erken karşılar, görev devrini doğru zamanda yapar.","10":"Rakip hareketlerini ve takım arkadaşlarının sorumluluklarını sürekli birlikte yönetir; koşuların tehlikeli alana ulaşmasını sistematik biçimde önler.","1–2":"Rakip koşuları sık sık gözünden kaçar; aynı oyuncuyu veya boş alanı takip etmeyerek kolay fırsat verir.","3–4":"Koşuları geç fark eder veya yanlış oyuncuyu takip eder; takım arkadaşlarıyla görev paylaşımı bozulur.","5–6":"Temel koşu takibini yapar ancak çapraz koşu, kör taraf ve oyuncu değişimlerinde tutarsız kalır.","7–8":"Çoğu koşuyu doğru takip eder; gerektiğinde rakibi devreder ve alanı takım arkadaşlarıyla paylaşır."}'::jsonb,8),
('game_intelligence','CB-09','Antisipasyon ve hücum niyetini okuma',4,'{"9":"Rakibin aksiyonunu başlamadan önce okuyup konumunu ayarlar; müdahale veya alan kapatma için avantaj kazanır.","10":"Birden fazla olası hücum seçeneğini erken okur; rakibin planını bozacak konum ve zamanlamayı sürekli üretir.","1–2":"Rakibin bir sonraki hareketini çoğunlukla geç fark eder; pozisyonu önceden hazırlayamaz.","3–4":"Rakibin niyetini zaman zaman sezer ancak işaretleri yanlış yorumlayıp geç tepki verir.","5–6":"Bariz pas veya koşu tehditlerini okur; daha karmaşık hareketlerde öngörüsü sınırlı veya tutarsızdır.","7–8":"Çoğu durumda rakibin ilk kontrolü, vücut yönü ve pas seçeneklerinden tehdidi zamanında çıkarır."}'::jsonb,9),
('game_intelligence','CB-10','Pas kanallarını ve rakip bağlantılarını okuma',4,'{"9":"Bir sonraki bağlantıyı öngörür; rakibi daha az tehlikeli paslara yönlendirir ve araya girme fırsatı yaratır.","10":"Rakibin bağlantı zincirini sürekli önceden okur; yalnızca pası değil, sonraki aksiyonu da etkisizleştirir.","1–2":"Tehlikeli pas hatlarını sık sık açık bırakır; rakip merkez veya hat arası bağlantıyı kolayca kurar.","3–4":"Pas kanallarını geç kapatır; topa aşırı odaklanırken alıcı oyuncuyu ve ikinci bağlantıyı kaçırır.","5–6":"En belirgin pas kanallarını kapatır fakat yön değişimi ve üçüncü oyuncu bağlantılarında geç kalabilir.","7–8":"Top, pasör ve alıcı arasındaki ilişkiyi çoğunlukla doğru okur; önemli kanalları zamanında daraltır."}'::jsonb,10),
('game_intelligence','CB-11','Öne çıkma, bekleme veya geriye düşme kararı',4,'{"9":"Rakibin kontrolü, destek koşulları ve savunma çizgisini birlikte değerlendirerek erken ve dengeli karar verir.","10":"Kararları takım savunmasının zamanlamasını belirler; yüksek riskli durumlarda bile doğru önceliği sürekli seçer.","1–2":"Kararları tekrar tekrar yanlıştır; kontrolsüz çıkış veya gereksiz geri çekilme doğrudan tehlike yaratır.","3–4":"Duruma göre yanlış seçeneği sık tercih eder; arkasındaki alanı ve takım arkadaşlarını yeterince hesaba katmaz.","5–6":"Bariz durumlarda doğru karar verir ancak baskı, derin koşu veya destek eksikliğinde seçimleri değişkenlik gösterir.","7–8":"Çoğu pozisyonda çıkış, bekleme ve geriye düşme arasında doğru seçim yapar; riskleri yönetir."}'::jsonb,11),
('game_intelligence','CB-12','Rakibin vücut yönü ve ilk kontrolünü okuma',3,'{"9":"İlk kontrol kalitesini erken okur; rakibi belirli yöne yönlendirip top kazanma veya geciktirme avantajı oluşturur.","10":"Rakibin beden ve top ipuçlarını istikrarlı biçimde yorumlar; bire bir kararını rakibin seçeneklerini daraltacak şekilde önceden kurar.","1–2":"Rakibin vücut yönü ve ilk kontrolünü dikkate almaz; kolay geçilme veya geç müdahale tekrar eder.","3–4":"Bu işaretleri zaman zaman fark eder fakat mesafe ve müdahale zamanını doğru ayarlayamaz.","5–6":"Belirgin kötü ilk kontrolleri değerlendirir; daha küçük yön değişimleri veya aldatıcı hareketlerde geç tepki verir.","7–8":"Rakibin ilk kontrol yönüne ve vücut açısına göre çoğunlukla doğru mesafe ve müdahale seçer."}'::jsonb,12),
('game_intelligence','CB-13','Tehlike önceliği ve ikinci aksiyon farkındalığı',3,'{"9":"İlk ve ikinci tehlikeyi birlikte okur; takım arkadaşının müdahalesini ve seken top alanını önceden güvenceye alır.","10":"Çoklu tehditleri erken önceliklendirir; savunma aksiyon zincirinin devamını da yöneterek ikinci fırsatları büyük ölçüde önler.","1–2":"Öncelikli tehdidi kaçırır; topa gereksiz yönelirken daha tehlikeli oyuncu veya seken topu boş bırakır.","3–4":"Tehlikeleri sıralamakta zorlanır; ilk aksiyona odaklanıp devamındaki koşu veya ikinci topu kaybeder.","5–6":"İlk tehlikeyi çoğunlukla tanır ancak ikinci aksiyon ve alan devrinde geç kalabilir.","7–8":"Öncelikli tehdidi doğru belirler; müdahale, blok veya alan koruma arasında çoğunlukla dengeli seçim yapar."}'::jsonb,13),
('game_intelligence','CB-14','Baskı altında karar ve risk yönetimi',2,'{"9":"Baskı yönünü önceden okur; doğru zamanda pas, taşıma veya oyunu basitleştirme seçer.","10":"Baskı altında seçenekleri çok hızlı tartar; takımın oyununu ilerletirken top kaybı ve geçiş riskini sürekli kontrol eder.","1–2":"Baskı altında kontrolsüz veya yüksek tehlikeli kararlar tekrar eder; top kaybı savunmayı doğrudan açık bırakır.","3–4":"Rakip baskısını ve pas seçeneklerini geç değerlendirir; riskli tercihleri sık yapar.","5–6":"Basit baskı senaryolarını yönetir ancak alternatifleri, takım yerleşimini veya top kaybı riskini her zaman tartamaz.","7–8":"Çoğu durumda güvenli ve ilerletici seçenek arasında uygun denge kurar; gereksiz riski sınırlar."}'::jsonb,14),
('technical','CB-15','Bire bir savunma tekniği',3,'{"9":"Rakibin seçeneklerini daraltır; doğru mesafe ve vücut açısıyla hem top kazanma hem geciktirme başarısı gösterir.","10":"Farklı hız ve yönlerdeki hücumculara karşı tekniğini sürekli uyarlar; rakibi tehlikeli alandan uzak tutar ve takım savunmasını güvenceye alır.","1–2":"Rakip karşısında dengesiz veya yanlış açıyla kalır; kolay geçilir ve tehlikeli bölgeyi açık bırakır.","3–4":"Mesafe ve vücut pozisyonunda sık hata yapar; rakibi geciktirme veya yönlendirme becerisi sınırlıdır.","5–6":"Temel bire bir duruşunu korur; ancak hız değişimi, yönlendirme veya müdahale zamanlamasında tutarsızdır.","7–8":"Çoğu bire birde dengeli kalır; rakibi geciktirir, dışa yönlendirir veya uygun anda müdahale eder."}'::jsonb,15),
('technical','CB-16','Müdahale ve top kazanma tekniği',3,'{"9":"Rakibin kontrol ve dokunuş anını iyi seçer; temiz müdahale veya kontrollü top kazanımıyla geçiş başlatabilir.","10":"Müdahale tekniği çok güvenilir ve seçicidir; doğru anı bekler, topu temiz kazanır ve sonraki aksiyonu da kontrol eder.","1–2":"Müdahalelerde zamanlama ve temas kontrolü ciddi biçimde yetersizdir; gereksiz faul veya geç kalma sık görülür.","3–4":"Topa müdahale girişimleri çoğu kez dengesizdir; topu kazanma yerine rakibe ikinci fırsat verir.","5–6":"Uygun fırsatlarda temel müdahaleyi yapar fakat zamanlama, temas yönü veya topu kontrol etme kalitesi dalgalıdır.","7–8":"Çoğu müdahalede doğru zamanlama ve topa temas sağlar; kazanılan topu güvenli biçimde takımına kazandırır."}'::jsonb,16),
('technical','CB-17','Şut ve pas bloklama',2,'{"9":"Rakibin hazırlığını okuyarak blok açısını erken kurar; tehlikeli pas veya şut seçeneğini etkili biçimde sınırlar.","10":"Blok davranışı zamanlama, açı ve vücut kontrolüyle sürekli doğru uygulanır; rakibin en tehlikeli aksiyonlarını düzenli biçimde etkisizleştirir.","1–2":"Blok pozisyonuna geçemez veya yanlış açıyla yaklaşır; açık şut/pas hatları tekrar tekrar oluşur.","3–4":"Blok girişimlerinde zamanlama ve vücut yerleşimi zayıftır; tehlikeli hatları sık kaçırır.","5–6":"Bariz şut/pas hatlarını kapatır fakat vücut konumu ve karar kalitesi değişkenlik gösterir.","7–8":"Çoğu durumda şut ve pas hattına doğru zamanda girer; kontrolsüz biçimde alan açmaz."}'::jsonb,17),
('technical','CB-18','Hava topu tekniği ve zamanlaması',3,'{"9":"Topun uçuşunu, rakip temasını ve ikinci top alanını birlikte okuyarak hava mücadelesini takım lehine sonuçlandırır.","10":"Hava topu tekniği ve zamanlaması sürekli üst düzeydedir; baskılı durumlarda dahi güvenli temas ve yönlendirme sağlar.","1–2":"Topun uçuşunu ve temas zamanını sık yanlış değerlendirir; hava toplarında temel görevini yerine getiremez.","3–4":"Zıplama ve temas zamanlaması çoğu kez geç veya erken kalır; topu güvenli alana yönlendiremez.","5–6":"Uygun toplarda mücadele eder fakat rakip teması, zamanlama ve yönlendirme tutarsızdır.","7–8":"Çoğu hava topunda doğru zamanlama ve vücut konumu sağlar; topu tehlikeden uzaklaştırır veya takım arkadaşına yönlendirir."}'::jsonb,18),
('technical','CB-19','İlk kontrol ve top hâkimiyeti',2,'{"9":"İlk kontrolle rakip baskıyı boşa çıkarır veya takımın ilerlemesini kolaylaştırır; iki ayağını da işlevsel kullanır.","10":"Kontrol kalitesi zor paslarda ve yoğun baskıda dahi üst düzeydedir; ilk dokunuşla savunma eylemini hücum avantajına dönüştürür.","1–2":"İlk kontrolü sık sık rakibe veya tehlikeli alana bırakır; basit toplarda dahi kontrol kaybı yaşar.","3–4":"Kontrolleri baskı altında veya yön değiştirmede belirgin biçimde ağırdır; sonraki aksiyonu zorlaştırır.","5–6":"Temel kontrolü çoğunlukla yapar ancak vücut açısı ve ilk dokunuşla baskıdan çıkma kalitesi sınırlıdır.","7–8":"Çoğu durumda topu bir sonraki pas veya taşıma için uygun konuma alır; gereksiz temaslardan kaçınır."}'::jsonb,19),
('technical','CB-20','Kısa ve orta mesafe pas',2,'{"9":"Pasın zamanlaması ve ağırlığı takım arkadaşının sonraki aksiyonunu kolaylaştırır; baskı altında da güvenilir bağlantı sağlar.","10":"Kısa ve orta pas kalitesi sürekli yüksek; yön, hız ve zamanlamayla baskıyı aşar ve takımın oyun ritmini belirgin biçimde destekler.","1–2":"Basit paslarda yön, ağırlık veya zamanlama hataları sık tekrar eder; takımın çıkışını zorlaştırır.","3–4":"Paslar çoğu kez hedefin baskı durumunu dikkate almaz; takım arkadaşını zor topa veya baskıya sokar.","5–6":"Temel kısa pas bağlantısını kurar fakat pas ağırlığı, ayağa oynama ve baskı altında güvenilirlik değişkendir.","7–8":"Çoğu kısa/orta pas doğru hedefe ve uygun ağırlıkta gider; takımın yerleşimini korur."}'::jsonb,20),
('technical','CB-21','Hat kıran pas',2,'{"9":"Pas öncesi alanı okur; doğru anda doğru koridora servis yapar ve takımın hatlar arasında ilerlemesini sağlar.","10":"Hat kıran pasları yüksek kalite ve seçicilikle üretir; rakip baskı yapısını çözer, takım arkadaşını avantajlı ve oynanabilir durumda buluşturur.","1–2":"Açık hedefi veya pas hattını göremez; denemeleri çoğunlukla rakibe gider veya takım yapısını riske atar.","3–4":"Hat kıran pas seçimi ve uygulaması zayıftır; hedefin konumu ve baskı durumu yeterince dikkate alınmaz.","5–6":"Uygun fırsatlarda hat kıran pas dener ancak zamanlama, ağırlık ve hedef seçimi tutarlı değildir.","7–8":"Fırsat oluştuğunda doğru hedefe ve çoğunlukla uygun ağırlıkta pas atarak rakip hattı geçer."}'::jsonb,21),
('technical','CB-22','Uzun pas ve oyun yönü değiştirme',1,'{"9":"Rakip baskının kaydığı alanı erken fark eder; uzun pasla takım arkadaşını avantajlı alanda bulur.","10":"Uzun pas ve yön değiştirme hem isabet hem zamanlama hem de taktik etkisi açısından istikrarlı biçimde üst düzeydedir.","1–2":"Uzun pasın yönü ve ağırlığı çoğunlukla kontrolsüzdür; takımın topu kaybetmesine veya baskı altında kalmasına yol açar.","3–4":"Yön değiştirme fırsatlarını yanlış seçer; paslar çoğu kez hedefin koşusuna veya alanına uymaz.","5–6":"Uzun pası temel düzeyde kullanır ancak doğruluk, zamanlama ve hedef seçimi değişkendir.","7–8":"Uygun fırsatlarda oyunun yönünü doğru değiştirir; pasın mesafesi ve ağırlığı çoğunlukla işlevseldir."}'::jsonb,22),
('technical','CB-23','Top taşıma',1,'{"9":"Taşıma kararını doğru zamanlar; rakibi üzerine çekerek alan açar veya hatlar arasında güvenli ilerler.","10":"Top taşıma hem kontrollü hem stratejiktir; rakip baskı yapısını bozar ve takımın hücum yerleşimini belirgin biçimde iyileştirir.","1–2":"Topla ilerlerken sık kontrol kaybı yaşar veya takımın savunma dengesini tehlikeye sokan taşıma kararları verir.","3–4":"Taşıma sırasında baskı ve boş alanı yeterince okuyamaz; kolay top kaybeder veya ilerleme fırsatını kaçırır.","5–6":"Boş alan olduğunda top taşır ancak taşımanın zamanlaması ve sonraki pas/karar kalitesi sınırlıdır.","7–8":"Uygun boşluklarda kontrollü ilerler; rakip baskı hattını aşar veya takımına yeni pas açısı kazandırır."}'::jsonb,23),
('technical','CB-24','Baskı altında top saklama',1,'{"9":"Rakip baskı altında denge ve vücut yönünü etkili kullanır; doğru anda topu bırakıp takımın ilerlemesini sağlar.","10":"Yoğun baskıda dahi top kontrolü ve karar kalitesini korur; topu saklama süresini takım lehine kullanır ve güvenli çıkış sağlar.","1–2":"Baskı geldiğinde topu tekrar tekrar kaybeder; vücudunu ve destek oyuncularını kullanamaz.","3–4":"Temas veya yakın baskıda topu korumakta zorlanır; kontrolsüz uzaklaştırma veya top kaybı sık görülür.","5–6":"Basit baskıda topu koruyabilir ancak destek bekleme, vücut kullanımı ve çıkış seçimi tutarsızdır.","7–8":"Çoğu durumda topu korur, faul almadan bağlantı kurar veya güvenli pasla baskıyı aşar."}'::jsonb,24),
('physical_functional','CB-25','İlk ivmelenme',2,'{"9":"İlk adımlarıyla rakibin kontrol veya koşu avantajını sık kapatır; doğru teknikle hızlanmayı savunma kararına bağlar.","10":"İlk ivmelenme maç bağlamında sürekli belirgin avantaj sağlar; kısa mesafeli tehditleri zamanında karşılar.","1–2":"Kısa mesafede rakip hareketine tepki veremez; ilk adımlarda sık geride kalır.","3–4":"İlk hareketi çoğu kez geç veya etkisizdir; yakın alandaki koşu ve müdahale mesafesini kapatmakta zorlanır.","5–6":"Temel kısa mesafe hızlanması vardır ancak ilk adım ve reaksiyon koşullarında tutarlılık sınırlıdır.","7–8":"Çoğu kısa mesafe savunma aksiyonunda yeterli hızlanma sağlar ve pozisyonunu korur."}'::jsonb,25),
('physical_functional','CB-26','Açık alanda toparlanma hızı',2,'{"9":"Toparlanma koşusunu doğru açıyla birleştirir; rakibin hız avantajını sınırlar ve savunma desteği oluşana kadar geciktirir.","10":"Açık alandaki toparlanma işlevi sürekli güçlüdür; doğru açı ve hızla tehlikeli koşuları etkili biçimde kontrol eder.","1–2":"Savunma arkasında yakalandığında açık alanda toparlanma kapasitesi belirgin biçimde yetersiz kalır.","3–4":"Uzun mesafe koşularda rakipten sık kopar; koşu açısı ve hızını telafi edemez.","5–6":"Uygun pozisyonlarda toparlanır ancak hız, açı veya başlangıç gecikmesi nedeniyle tutarsız kalır.","7–8":"Çoğu açık alan durumunda rakibi takip eder veya tehlikeli ilerlemeyi geciktirecek mesafeyi kapatır."}'::jsonb,26),
('physical_functional','CB-27','Kuvvet ve temas altında denge',3,'{"9":"Teması zamanlama ve vücut yerleşimiyle yönetir; topa erişimini ve savunma pozisyonunu baskı altında da korur.","10":"Temas altında denge ve kuvvet kullanımını çok verimli uygular; rakibin fiziksel avantajını etkisizleştirirken temiz savunma yapar.","1–2":"Temas altında kolayca dengesini ve savunma pozisyonunu kaybeder; rakip basit fiziksel temasta avantaj kazanır.","3–4":"İkili mücadelelerde dengeyi sık kaybeder; vücut konumu ve temas yönetimi zayıftır.","5–6":"Temel teması karşılar ancak güçlü rakip veya yön değişiminde pozisyonunu koruması tutarsızdır.","7–8":"Çoğu temasta dengede kalır; rakibi kontrol ederken gereksiz faul veya pozisyon kaybından kaçınır."}'::jsonb,27),
('physical_functional','CB-28','Çeviklik ve yön değiştirme',2,'{"9":"Rakibin yön değişimlerine kontrollü ayak hareketiyle cevap verir; dengesini kaybetmeden müdahale mesafesini korur.","10":"Çeviklik ve yön değiştirme farklı hızlarda sürekli etkilidir; savunma pozisyonunu bozmadan rakip hareketini sınırlar.","1–2":"Yön değişimlerinde dengesini ve takip hattını sık kaybeder; rakibin ani hareketlerine uyum sağlayamaz.","3–4":"Yan adım ve dönüşlerde gecikir; kalça/ayak yönelimi rakibin hareketini takip etmeyi zorlaştırır.","5–6":"Temel yön değişimlerini yapar ancak hızlı yön değiştirme ve tekrar pozisyon alma kalitesi değişkendir.","7–8":"Çoğu bire bir ve savunma kaymasında dengeli yön değiştirir; savunma açısını korur."}'::jsonb,28),
('physical_functional','CB-29','Sıçrama ve hava mücadelesi uygulaması',2,'{"9":"Rakip ve topun uçuşuna göre sıçrama anını ayarlar; temas sonrası dengeli kalıp topu takım lehine yönlendirir.","10":"Sıçrama, temas ve iniş koordinasyonu sürekli üst düzeydedir; baskılı hava mücadelelerinde de kontrol ve devamlılık sağlar.","1–2":"Sıçrama ve iniş koordinasyonu yetersizdir; hava topuna erişim veya temas sonrası denge sık kaybolur.","3–4":"Zıplama zamanlaması ve iniş kontrolü çoğu kez zayıftır; hava mücadelesinde ikinci aksiyona hazır kalamaz.","5–6":"Temel hava mücadelesine katılır ancak sıçrama zamanlaması, temas veya iniş sonrası denge tutarsızdır.","7–8":"Çoğu hava mücadelesinde zamanında sıçrar, dengeli temas kurar ve ikinci aksiyona hazır kalır."}'::jsonb,29),
('physical_functional','CB-30','Maç boyunca efor devamlılığı',2,'{"9":"Maçın farklı bölümlerinde savunma hareketlerinin yoğunluk ve kalitesini korur; toparlanma sonrası görevine çabuk döner.","10":"Efor devamlılığı maç boyunca çok istikrarlıdır; yoğun geçiş ve savunma sekanslarında dahi hareket kalitesini korur.","1–2":"Maçın önemli bölümlerinde savunma görevlerini fiziksel devamlılık eksikliği nedeniyle sürdüremez.","3–4":"Tekrarlanan savunma hareketlerinde belirgin düşüş yaşar; geç reaksiyon ve görev gecikmesi artar.","5–6":"Temel maç temposunu sürdürür ancak yoğun bölümlerde efor ve hareket kalitesi dalgalanır.","7–8":"Maçın çoğunda rolün gerektirdiği hareketleri yeterli yoğunlukta sürdürür."}'::jsonb,30),
('physical_functional','CB-31','Savunma hareketlerinde koordinasyon ve denge',2,'{"9":"Kayma, dönüş, geri koşu ve müdahale hazırlığını akıcı biçimde birleştirir; dengeyi koruyarak doğru savunma pozisyonuna döner.","10":"Ardışık savunma hareketleri çok koordinelidir; dengesini kaybetmeden farklı aksiyonlara geçer ve takım savunmasını güvenceye alır.","1–2":"Savunma hareketlerinde ayak, gövde ve denge koordinasyonu sık bozulur; basit yön değişimlerinde bile pozisyon kaybeder.","3–4":"Kayma, geri koşu ve müdahale hazırlığında vücut kontrolü zayıftır; hareketler birbirini keser.","5–6":"Temel koordinasyon vardır ancak hızlı ardışık hareketlerde veya temas sonrası denge tutarsızdır.","7–8":"Çoğu savunma hareketinde dengeli ve kontrollüdür; bir aksiyondan diğerine makul hızla geçer."}'::jsonb,31),
('competitive_behaviours','CB-32','Konsantrasyon ve savunma görevine bağlılık',3,'{"9":"Topun olmadığı anlarda da sürekli tarama ve görev takibi yapar; savunma sorumluluğunu farklı oyun durumlarında korur.","10":"Konsantrasyon ve görev takibi maç boyunca istisnai derecede güvenilirdir; takım savunmasının dikkat ve organizasyon standardını yükseltir.","1–2":"Maç içinde görev takibini sık kaybeder; top uzaktayken veya tehlike henüz oluşmamışken hazırlıksız yakalanır.","3–4":"Konsantrasyon dalgalanmaları tekrarlanır; basit oyuncu/alan takibi ve savunma görevinde gecikme görülür.","5–6":"Temel görevini sürdürür ancak uzun süre top dışında kaldığı veya oyun yön değiştirdiği anlarda dikkati azalabilir.","7–8":"Maçın çoğunda görevine bağlı kalır; topun ve rakibin hareketine göre savunma hazırlığını sürdürür."}'::jsonb,32),
('competitive_behaviours','CB-33','Hata sonrası reaksiyon',2,'{"9":"Hata sonrası odağını ve iletişimini hızla toparlar; sonraki savunma aksiyonunda doğru karar ve uygulama gösterir.","10":"Hata sonrası reaksiyonu sürekli profesyonel ve etkilidir; olumsuz pozisyonun sonraki görevlerini etkilemesine izin vermez.","1–2":"Hata sonrası sonraki aksiyona dönemez; benzer dikkatsizlik veya görev kaybı tekrar eder.","3–4":"Bir hata sonrasında reaksiyonu belirgin biçimde gecikir; sonraki pozisyonlarda görev güvenilirliği düşer.","5–6":"Genellikle görevine döner fakat hatadan sonraki ilk aksiyonda kararsızlık veya gecikme görülebilir.","7–8":"Hata sonrası çoğunlukla hızlıca görevine döner; sonraki pozisyonu normal standartta oynar."}'::jsonb,33),
('competitive_behaviours','CB-34','Baskı altında soğukkanlılık',2,'{"9":"Yoğun baskıda bilgi toplar ve doğru seçeneği seçer; takım arkadaşlarını sakin ve organize tutar.","10":"Baskı seviyesinden bağımsız biçimde karar kalitesi ve davranış kontrolünü korur; zor anlarda takımın istikrarına belirgin katkı sağlar.","1–2":"Baskı altında kontrolsüz kararlar ve panik davranışı tekrarlanır; takımın savunma veya çıkışını doğrudan riske atar.","3–4":"Yoğun baskıda aceleci müdahale, hatalı uzaklaştırma veya karar gecikmesi sık görülür.","5–6":"Temel baskı durumlarını yönetir ancak yüksek baskı veya maçın kritik bölümünde karar kalitesi dalgalanır.","7–8":"Çoğu baskı durumunda sakin kalır; basit ve uygun çözümü seçerek takımın düzenini korur."}'::jsonb,34),
('competitive_behaviours','CB-35','İkili mücadele devamlılığı ve kararlılık',3,'{"9":"İlk mücadele sonuçlanmasa bile ikinci aksiyona hızlı döner; top ve alan için kararlı ama kontrollü davranır.","10":"Mücadele devamlılığı sürekli üst düzeydedir; ilk aksiyon, seken top ve yeniden pozisyon alma zincirini etkili biçimde sürdürür.","1–2":"Mücadelelerin devamında sık oyundan düşer; ilk temastan sonra ikinci aksiyonu takip etmez.","3–4":"İkili mücadele ve seken top devamlılığı zayıftır; temas sonrası pozisyona dönmekte geç kalır.","5–6":"Temel mücadeleye katılır ancak ikinci top, tekrar müdahale veya devam koşularında tutarsızdır.","7–8":"Çoğu ikili mücadelede aksiyonu sürdürür; ilk temas sonrası topun ve rakibin hareketini takip eder."}'::jsonb,35),
('competitive_behaviours','CB-36','Savunma sorumluluğu ve görev disiplini',3,'{"9":"Görev ve sorumluluk değişimini erken fark eder; bireysel aksiyon ile takım yapısı arasında doğru denge kurar.","10":"Savunma sorumluluğu sürekli güvenilirdir; farklı maç ve sistemlerde takımın görev bütünlüğünü koruyan referans davranış gösterir.","1–2":"Kendi alan ve görev sorumluluğunu sık terk eder; takım arkadaşlarının görevini de tehlikeye sokar.","3–4":"Görev değişimi ve alan paylaşımında sık hata yapar; takım yapısından bağımsız aksiyonlara yönelir.","5–6":"Temel görev disiplinini korur ancak rol değişimi, çizgi çıkışı veya geçişte sorumluluk paylaşımı tutarsız olabilir.","7–8":"Çoğu durumda kendi görevini yerine getirir; takım arkadaşının hareketine göre alan devrini doğru yapar."}'::jsonb,36),
('competitive_behaviours','CB-37','Saha içi iletişim ve koordinasyon',2,'{"9":"İletişimi erken, kısa ve işlevseldir; çizgi, markaj ve destek hareketlerinin koordinasyonunu belirgin biçimde iyileştirir.","10":"İletişim ve koordinasyonu sürekli üst düzeydedir; takım arkadaşlarının karar süresini kısaltır ve savunma hattını birlikte hareket ettirir.","1–2":"Gerekli savunma iletişimini vermez veya yanlış zamanda/yanlış bilgiyle takım arkadaşlarını zor durumda bırakır.","3–4":"İletişimi gecikmeli ve tutarsızdır; markaj devri, çizgi veya baskı koordinasyonunda kopukluk yaşanır.","5–6":"Temel iletişimi kurar fakat bilgi çoğu kez geç gelir veya takım arkadaşlarının hareketini düzenleyecek kadar net değildir.","7–8":"Çoğu durumda doğru zamanda anlaşılır bilgi verir; savunma hattıyla görev paylaşımını sürdürür."}'::jsonb,37)
) AS c(category_code,criterion_code,criterion_name,weight_percent,score_anchors,sort_order)
JOIN public.rubric_categories cat ON cat.rubric_version_id=v.id AND cat.category_code=c.category_code
WHERE v.version_code='CB-METH-0.8-ANCHORS-1.0';

ALTER TABLE public.rubric_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubric_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubric_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scouting_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scouting_session_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.criterion_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_access_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scout_report_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.observations ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
 public.rubric_versions,public.rubric_categories,public.rubric_criteria,
 public.scouting_sessions,public.scouting_session_videos,public.criterion_scores,
 public.video_access_checks,public.scout_report_sessions
FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE
 public.rubric_versions,public.rubric_categories,public.rubric_criteria,
 public.scouting_sessions,public.scouting_session_videos,public.criterion_scores,
 public.video_access_checks,public.scout_report_sessions TO authenticated;

CREATE POLICY vel_staff_manage_rubric_versions ON public.rubric_versions FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_rubric_categories ON public.rubric_categories FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_rubric_criteria ON public.rubric_criteria FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_scouting_sessions ON public.scouting_sessions FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_scouting_session_videos ON public.scouting_session_videos FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_criterion_scores ON public.criterion_scores FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_video_access_checks ON public.video_access_checks FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
CREATE POLICY vel_staff_manage_scout_report_sessions ON public.scout_report_sessions FOR ALL TO authenticated USING((SELECT private.is_vel_staff())) WITH CHECK((SELECT private.is_vel_staff()));
