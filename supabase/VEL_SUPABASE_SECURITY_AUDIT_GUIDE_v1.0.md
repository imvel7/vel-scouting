# Supabase Güvenlik Denetimi — Kullanım Rehberi

**İlgili dosya:** `supabase/VEL_READ_ONLY_SECURITY_AUDIT_v1.0.sql`  
**Sürüm:** 1.0  
**Amaç:** Vel Scouting'in gerçek Supabase şemasını, RLS durumunu, policy ve izinlerini salt-okunur biçimde incelemek.

## Neden bu kontrolü yapıyoruz?

Kod deposundaki `vel_access_setup.sql` dosyasında:
- `user_roles` tablosu için açıkça `ENABLE ROW LEVEL SECURITY` komutu bulunuyor.
- Diğer mevcut tablolarda personel policy'leri tanımlanmış olsa da aynı dosyada bu tablolar için açık bir `ENABLE ROW LEVEL SECURITY` komutu görünmüyor.
- `authenticated` rolüne özel tablolar üzerinde tablo düzeyinde SELECT/INSERT/UPDATE/DELETE izinleri veriliyor.

PostgreSQL'de policy tanımlı olması tek başına RLS'yi etkinleştirmez. Özel tablolarda RLS kapalıysa policy'ler erişimi sınırlamaz. Ancak canlı projede daha önce ayrıca açılmış olabilir; bu nedenle bunu henüz güvenlik açığı olarak ilan etmiyoruz. Canlı durumu kontrol edeceğiz.

## 1. Denetim dosyasını aç

[Salt-okunur SQL denetim dosyası](VEL_READ_ONLY_SECURITY_AUDIT_v1.0.sql)

Bu dosyadaki bütün sorgular SELECT'tir. Tablo, kayıt, kullanıcı, rol, izin veya policy değiştirmez.

## 2. Supabase SQL Editor'de çalıştır

1. Supabase hesabında `vel-scouting` projesini aç.
2. **SQL Editor** bölümüne gir.
3. Yeni bir query aç.
4. GitHub'daki SQL dosyasının içeriğini kopyalayıp editöre yapıştır.
5. Sorguları ayrı ayrı çalıştır: önce QUERY 1; ardından QUERY 2, QUERY 3 ve QUERY 4.
6. Her sorgunun sonuç tablosunu dışa aktarmak yerine, mümkünse sonuç satırlarını kopyala ve bu sohbete gönder.

Mobil kullanımda tüm sorguları aynı anda çalıştırmak zor gelirse yalnızca QUERY 1'in sonucuyla başla. İlk sorgu tablo varlığını, sütunları, RLS bayraklarını, policy'leri ve tablo izinlerini birlikte gösterir.

## 3. Hangi sonuçları inceleyeceğiz?

Öncelikli tablolar:
- `videos`
- `matches`
- `player_matches`
- `observations`
- `report_versions`
- `user_roles`

Ayrıca `players`, `clubs` ve `scout_reports` tablolarının kamuya açık okuma kurallarını da kontrol edeceğiz.

Güvenlik beklenenleri:
- Özel scouting tablolarında RLS açık olmalı.
- `anon` özel video URL'lerini, maç kaynaklarını veya ham gözlemleri okuyamamalı.
- `authenticated` olup Vel personeli olmayan kullanıcı özel tablolara erişememeli.
- `admin` ve `editor` yalnızca tanımlanan personel yetkilerini kullanabilmeli.
- Kamuya açık sitede yalnızca yayımlanmış profiller ve raporlar görünmeli.
- Kamuya açık bir view veya function özel video alanlarını sızdırmamalı.

**Not:** SQL Editor sorguları katalog durumunu gösterir. Gerçek API davranışını kanıtlamak için sonrasında anon, yetkisiz authenticated ve staff testleri ayrıca yapılacaktır. SQL Editor'ın yönetici oturumuyla çalıştırdığı sorgular bu testlerin yerine geçmez.

## 4. Güvenlik

- Bu dosyayı çalıştırmak için şifre, JWT, service_role key veya başka gizli anahtar gerekmez.
- Hiçbir gizli anahtarı bana veya GitHub'a gönderme.
- Bu denetim tamamlanmadan eski erişim SQL dosyasını tekrar çalıştırma ve yeni policy/migration ekleme.
- Bir sonuçta beklenmeyen erişim görünürse önce çıktıyı inceleyeceğiz; doğrudan canlı veritabanında değişiklik yapmayacağız.

## 5. Denetim sonrası çıktımız

Sonuçları aldıktan sonra:
1. Gerçek şema envanterini çıkaracağız.
2. Her tablo için RLS/policy/grant matrisini oluşturacağız.
3. Güvenlik açıklarını önem derecesine göre ayıracağız.
4. Gerekli düzeltmeleri geriye uyumlu migration olarak hazırlayacağız.
5. Değişiklikleri uygulamadan önce etki ve geri dönüş planını belirleyeceğiz.


## 6. Canlı denetim ve güvenlik sıkılaştırması — 10 Kasım 2026

Canlı proje `xlvteloclijsudxbwszd` üzerinde denetim tamamlandı:

- 11 hedef tablonun tamamında RLS etkin.
- Anonim SELECT yalnızca `players`, `clubs` ve `scout_reports` tablolarında bırakıldı; ilgili yayımlanmış kayıt policy'leri bu tabloları sınırlandırıyor.
- Anonim ve authenticated rollerinden `TRUNCATE`, `REFERENCES`, `TRIGGER` ve `MAINTAIN` izinleri kaldırıldı.
- `is_vel_staff()`, `is_vel_admin()` ve `rls_auto_enable()` fonksiyonları API'ye açık `public` şemasından `private` şemasına taşındı. RLS politikalarının fonksiyon bağımlılıkları korundu.
- `set_updated_at()` fonksiyonunun `search_path` ayarı `pg_catalog` ile sabitlendi.
- PostgreSQL `postgres` rolüyle oluşturulacak yeni `public` tablolar için gereksiz varsayılan tablo izinleri ve yeni RPC fonksiyonları için otomatik EXECUTE izinleri kaldırıldı.

Uygulanan migration: `20261110172515_tighten_vel_rls_function_privileges`.

### Kalan sınırlama

Canlı projede ayrıca `supabase_admin` rolüne ait varsayılan tablo izinleri bulundu. Bağlı yönetim oturumu `postgres` rolüyle çalışıyor ve bu rolün `supabase_admin` üzerinde üyeliği yok; bu nedenle o rolün varsayılan izinleri bu bağlantı üzerinden değiştirilemedi. Supabase Table Editor tarafından `supabase_admin` sahibiyle oluşturulacak yeni public tablolar için bu varsayılanlar ayrıca ele alınmalı. Şimdilik yeni scouting tablolarını bu proje bağlantısında doğrulanan `postgres` SQL/migration yolu ile oluşturun ve her yeni tabloda RLS ile grant'leri kontrol edin.

### Son doğrulama

Migration sonrasında:
- 11/11 hedef tabloda RLS açık kaldı.
- `anon` yalnızca üç kamuya açık tabloda SELECT alabiliyor.
- `anon` ve `authenticated` için kaldırılan dört ek izin hiçbir hedef tabloda kalmadı.
- Personel policy'leri `private.is_vel_staff()`; admin rol policy'si `private.is_vel_admin()` çağırıyor.
- `ensure_rls` event trigger hâlâ etkin ve `private.rls_auto_enable()` fonksiyonuna bağlı.
- Security Advisor'da fonksiyon kaynaklı üç uyarı giderildi. Tek kalan uyarı, Supabase Auth'ta sızdırılmış parola korumasının kapalı olmasıdır.

Bu denetim katalog izinleri ve RLS yapılandırmasını doğrular; gerçek HTTP/Data API davranışı için anon, yetkisiz authenticated ve staff istemcileriyle ayrı uçtan uca testler hâlâ yapılmalıdır.


## 7. Eklemeli scouting modeli migration'ı — 10 Kasım 2026

Canlı projeye `20261110174605_create_vel_scouting_sessions_and_rubrics` migration'ı uygulandı.

- Sekiz yeni tablo oluşturuldu: `rubric_versions`, `rubric_categories`, `rubric_criteria`, `scouting_sessions`, `scouting_session_videos`, `criterion_scores`, `video_access_checks`, `scout_report_sessions`.
- Mevcut `observations` tablosuna oturum, kaynak-video, kriter, video saniyesi, maç saati saniyesi ve devre alanları eklendi. Eski satırlara tahmini değer yazılmadı.
- Sekiz yeni tablonun tamamında RLS açık; anonim role tablo izni verilmedi; authenticated CRUD yalnızca `private.is_vel_staff()` politikasıyla sınırlandırıldı.
- Maç, oyuncu, oturum, rubrik sürümü ve seçilen kaynak arasındaki temel ilişkiler bileşik foreign key'lerle doğrulanıyor.
- Stoper metodolojisinin 37 kriteri, beş kategorisi ve altı puan çıpası bandı veritabanına aktarıldı. Kriter ağırlıkları toplamı %100; kategori ağırlıkları %30/%20/%20/%15/%15.
- Bu rubrik `pilot` durumundadır; saha kalibrasyonu yapılmadan aktif metodoloji olarak kullanılmayacaktır.

### Son katalog doğrulaması

- 8/8 yeni tabloda RLS etkin.
- 8/8 yeni tabloda tek personel policy'si mevcut.
- Anon role yeni tablolarda hiçbir tablo izni verilmedi.
- 1 rubrik sürümü, 5 kategori ve 37 kriter bulundu.
- 37 kriterin ağırlık toplamı 100; eksik puan çıpası seti sayısı 0.
- Migration geçmişinde `20261110174605` kaydı mevcut.

**Henüz tamamlanmayan test:** SQL katalog ve grants denetimi, gerçek HTTP/Data API istekleriyle anon, yetkisiz authenticated ve staff kullanıcı testinin yerine geçmez. Özel video yönetim arayüzü bu davranış testleri ve form iş akışı tamamlanmadan yayımlanmamalıdır.


## 8. Supabase Free plan parola uyarısı

10 Kasım 2026 Security Advisor sonucunda kalan tek uyarı `auth_leaked_password_protection` idi.

Supabase'in güncel parola güvenliği belgesine göre sızdırılmış parola kontrolü Pro plan ve üzeri planlarda sunuluyor: https://supabase.com/docs/guides/auth/password-security

Bu nedenle proje Free planda kaldığı sürece bu kontrolü açamamak beklenen plan sınırlamasıdır; tek başına Vel Scouting veritabanından parola sızdığı anlamına gelmez. Bu uyarıyı gidermek için plan yükseltmesi önerilmiyor.

Free planda yapılabilecek güvenli yapılandırma:
- Minimum parola uzunluğunu en az 8 karakterin üzerinde tut; uygulama hesapları için daha uzun parola tercih et.
- Panelde sunulan parola bileşimi gereksinimlerini etkinleştir.
- Kullanıcıları parolaları başka hizmetlerde tekrar kullanmamaları konusunda bilgilendir.
- Güvenlik Advisor uyarısını plan sınırlaması olarak takip et; plan/ürün özelliği değişmeden giderildi olarak işaretleme.

## 9. Rol/RLS doğrulama notu

Canlı SQL denetiminde işlem bağlamı simülasyonuyla şu sonuçlar görüldü:
- `anon` rolü `scouting_sessions` tablosundan SELECT yapmaya çalıştığında PostgreSQL `permission denied` döndürdü.
- JWT subject olmayan `authenticated` bağlamında `private.is_vel_staff()` false döndü; özel oturum kaydı görünmedi.
- Mevcut admin rolündeki kullanıcı kimliğiyle oluşturulan `authenticated` SQL bağlamında `is_vel_staff()` ve `is_vel_admin()` true döndü; 37 kriter satırı görülebildi.

Bu sonuçlar SQL rol/JWT bağlamı testidir; gerçek HTTP/Data API isteği değildir. Çalışma ortamından Supabase API alan adına DNS çözümlenemediği için uçtan uca HTTP testi yürütülemedi. Yol haritasında API testi tamamlandı olarak işaretlenmemelidir.


## 10. Admin panel üzerinden gerçek Data API kontrolü

Admin sayfasına salt-okunur `Supabase erişim testi` bölümü eklendi. Değişiklik GitHub Pages'e yayımlandıktan ve yetkili hesapla giriş yapıldıktan sonra testler tarayıcıdan Supabase Data API'ye gerçek istek gönderir.

Kontrol edilenler:
- Anonim istemcinin `players`, `clubs` ve `scout_reports` tablolarında okuma yapabilmesi.
- Anonim istemcinin özel değerlendirme, video, gözlem ve rubrik tablolarına erişememesi.
- Oturum açmış personel istemcisinin 37 kriterlik pilot rubriği okuyabilmesi.

Bu test salt-okunurdur; kayıt eklemez veya değiştirmez. Ayrı bir personel olmayan Auth hesabı bulunmadığından yetkisiz authenticated senaryosu panel tarafından test edilmez. Bu senaryo ayrı hesapla daha sonra doğrulanmalıdır.
