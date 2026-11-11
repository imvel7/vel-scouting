# VEL SCOUTING — Davinson Sánchez Pilot Ön Kontrolü

**Kayıt:** VEL-PILOT-CB-PRECHECK-01  
**Kontrol tarihi:** 11 Kasım 2026  
**Durum:** Mevcut oyuncu ve kulüp kayıtları kontrol edildi; admin sayfasının canlı dağıtımı doğrulanamadı.

## 1. Mevcut Supabase kayıtları

Salt-okunur sorgularla aşağıdaki kayıt durumu görüldü:

| Kayıt | Durum | İşlem |
|---|---|---|
| Davinson Sánchez Mina | Mevcut, ana mevki CB, profil taslak | Yeniden oluşturma; mevcut oyuncu kaydını kullan |
| Galatasaray | Mevcut kulüp kaydı | Yeniden oluşturma |
| Juventus | Bulunamadı | Admin panelinden bir kez ekle |
| UEFA Champions League | Organizasyon kaydı bulunamadı | Admin panelinden bir kez ekle |
| 2025/26 | Sezon kaydı bulunamadı | Admin panelinden bir kez ekle |
| Galatasaray 5–2 Juventus | Maç kaydı bulunamadı | Kulüp/organizasyon/sezon kayıtlarından sonra oluştur |
| Davinson Sánchez oyuncu-maç katılımı | Bulunamadı | Maç oluşturulduktan sonra ekle |
| UEFA.tv video kaydı | Bulunamadı | Maç oluşturulduktan sonra ekle |
| Scouting oturumu | Bulunamadı | Katılım ve video kaydı tamamlandıktan sonra taslak oluştur |

Kontrol edilen tablolarda bu pilot için mevcut maç, oyuncu-maç, video, gözlem ve scouting-session verisi bulunmuyordu. Bu kontrol veri oluşturmadı veya değiştirmedi.

## 2. Pilot için kullanılacak mevcut oyuncu profili

Mevcut Davinson Sánchez Mina profili taslak durumdadır. Pilot scouting için bu yeterlidir; kamuya açık hâle getirmek veya profil bilgilerini genişletmek gerekmez. Oyuncu kaydını kullanırken yeni bir kopya oluşturma.

## 3. Admin dağıtım kontrolü

Güncel admin dosyası GitHub main dalında bulunuyor ve son kayıtlı sürümde organizasyon/sezon kayıt ekranları mevcut. Ancak GitHub Pages'in bu commit'i yayımlayıp yayımlamadığı, bu denetimde canlı sayfadan doğrulanamadı. Repository kaynak kodunun güncel olması, Pages dağıtımının tamamlandığını tek başına kanıtlamaz.

Beklenen GitHub Pages yolu:
- Site: https://imvel7.github.io/vel-scouting/
- Admin paneli: https://imvel7.github.io/vel-scouting/admin.html

Bu adresler beklenen standart Pages adresleridir; canlı erişim teyidi olarak değerlendirilmemelidir. Panel açıldığında organizasyon ve sezon kayıt formlarının görünmesi gerekir. Yetkili hesaptan oturum açma kontrolü kullanıcı tarayıcısında yapılmalıdır. Parola, oturum çerezi veya erişim anahtarı paylaşılmamalıdır.

## 4. Panel açıldıktan sonra kayıt sırası

1. Juventus kulübünü ekle (Italy).
2. UEFA Champions League organizasyonunu ekle (Europe; tür: club competition).
3. 2025/26 sezonunu ekle. Tarih alanları doğrulanmış değilse boş bırak.
4. Galatasaray–Juventus maçını kaydet: 17 Şubat 2026, 5–2, tamamlandı, Senior, 90 dakika; organizasyon ve sezon bağlantılarını seç. Maç saati alanına yalnızca güvenilir fikstür kaydından doğrulanan Türkiye yerel saatini gir.
5. Mevcut Davinson Sánchez Mina profilini seçip Galatasaray 5–2 Juventus maçına CB olarak bağla. Oyuncu katılım dakikasını maç raporuyla doğrula.
6. UEFA.tv Re-Runs kaydını resmî kaynak sayfasına bağlantı olarak ekle; türünü tam maç seç, hak durumunu yalnızca bağlantı olarak bırak. Kesintisiz oynatma ve Türkiye erişimini bizzat tekrar kontrol et.
7. Video erişim kontrolünde yalnızca fiilen doğrulanan ülke, hesap, ücret ve kapsam durumunu kaydet.
8. Taslak scouting oturumu oluştur ve aynı maçın video kaydını oturuma bağla.

## 5. Güvenlik ve doğruluk sınırı

- Bu ön kontrol yalnızca metadata sayımıdır; canlı admin oturumu veya gerçek tarayıcı yetkisi testi değildir.
- Veri girişleri admin panelinden, yetkili hesabın RLS politikaları altında yapılmalıdır.
- Hiçbir özel erişim belirteci, parola veya oturum çerezi kayda konmamalıdır.
- UEFA.tv bağlantısının kaydedilmesi videonun indirilmesi, kopyalanması, kliplenmesi veya yeniden yayımlanması izni vermez.
- Maç videosu izlenmeden Davinson Sánchez hakkında gözlem, puan veya performans sonucu üretilmemelidir.

**Sonuç:** Oyuncu ve Galatasaray kayıtları yeniden oluşturulmayacak. Önce Pages dağıtımı ve yetkili admin erişimi doğrulanacak; ardından yalnızca eksik katalog/maç kayıtları eklenecek.
