# Vel Scouting - Telefonla kurulum

Bu paket, mevcut Supabase projen ve daha once olusturulmus 10 tablo uzerine ilk herkese acik site surumunu kurmak icindir.

## Pakette ne var?

- `index.html`: Oyuncu profillerini ve yayinlanmis scout raporlarini gosteren site.
- `vel_access_setup.sql`: Mevcut tablolara erisim kurallari ekler. Taslak oyuncu profillerini, ozel gozlemleri ve yayinlanmamis raporlari herkese acmaz.

## 1. SQL dosyasini hazirla

1. Supabase projenin Dashboard ekranini ac.
2. Sol menuden **SQL Editor** bolumune gir.
3. **New query** veya **Create a new snippet** secenegine dokun.
4. Bu paketteki `vel_access_setup.sql` dosyasini acip tum icerigini kopyala.
5. Kodun en altina yakin su satiri bul:

   `values ('PASTE_YOUR_AUTH_USER_UUID_HERE', 'admin')`

6. Tirnaklarin arasindaki `PASTE_YOUR_AUTH_USER_UUID_HERE` yazisini, daha once Authentication > Users bolumunde gordugun kendi kullanici UUID'in ile degistir. Tek tirnaklari silme.
7. Kodu SQL Editor'e yapistir. Kirmizi U+200E uyari metinleri gorursen Run'a basmadan once haber ver; bozuk kopyalamayla devam etme.
8. Her sey duzgun gorunuyorsa **Run** tusuna bir kez bas. Basarili olursa SQL Editor sonucunda hata gorunmez.

Bu SQL scripti mevcut 10 tabloyu silmez veya yeniden olusturmaz. `user_roles` adinda bir rol tablosu ekler. Script, kendi olusturdugu policy adlarini once kaldirdigi icin yeniden calistirilabilir; yine de ilk denemede bir kez calistirmak yeterlidir.

## 2. Siteyi GitHub'a yukle

1. GitHub hesabini telefondan ac.
2. Yeni bir repository olustur: `vel-scouting`.
3. Repository'yi **Public** sec ve README ekleme secenegini simdilik kapali birak.
4. Repository acilinca **Add file > Upload files** bolumune gir.
5. Bu paketten `index.html` dosyasini secip yukle ve **Commit changes** tusuna bas.
6. `KURULUM.md` dosyasini da ayni sekilde yukleyebilirsin; bu dosya yalnizca rehberdir.

## 3. GitHub Pages'i ac

1. Repository icinde **Settings** bolumune gir.
2. **Pages** secenegini bul.
3. **Build and deployment** altinda Source olarak **Deploy from a branch** sec.
4. Branch olarak `main`, klasor olarak `/(root)` sec ve **Save** tusuna bas.
5. Biraz sonra ayni Pages ekraninda sitenin adresi gorunur. Adres genellikle `https://GITHUB-KULLANICI-ADIN.github.io/vel-scouting/` seklindedir.

## 4. Supabase baglantisini ekle

1. Supabase Dashboard'da `vel-scouting` projesini ac.
2. Project URL ve **publishable key** bilgilerini bul. Eski arayuzde buna `anon public` key denebilir.
3. GitHub repository'de `index.html` dosyasini acip kalem (Edit) simgesine dokun.
4. Dosyanin alt taraflarinda `SUPABASE_URL` ve `SUPABASE_PUBLIC_KEY` satirlarini bul.
5. `YOUR_SUPABASE_PROJECT_URL` yerine Project URL'ni; `YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY` yerine publishable/anon public key'ni yaz.
6. **Commit changes** ile kaydet.

**Guvenlik:** Site dosyasina yalnizca publishable veya eski anon public key konur. `service_role`, `secret` veya gizli anahtari asla siteye, GitHub'a ya da bana gonderme. Public anahtarin guvenligi RLS kurallarina dayanir.

## 5. Ilk oyuncu profilini yayinlama

Bu ilk surum yalnizca `profile_status = 'published'` olan oyunculari ve `report_status = 'published'` olan raporlari gosterir. Taslaklar herkese acilmaz. Ilk oyuncu verisini ekleme ve scout raporu girisi icin yonetim panelini sonraki asamada kuracagiz; simdilik Supabase Table Editor kullanilacaksa yalnizca senin yonetici oturumunla kullan.

## Notlar

- GitHub Pages site barindirmasini ucretsiz sunar; adres GitHub alt alan adidir. Ozel alan adi ayri bir konudur.
- Bu ilk surum oyuncu listesi, arama, mevki filtresi, yayinlanmis rapor goruntuleme ve metodoloji tanitimini icerir.
- Potansiyel, transfer uygunlugu, video yonetimi ve gelismis yonetim paneli henuz bu ilk surumde yoktur.
