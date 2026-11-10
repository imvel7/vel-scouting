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
