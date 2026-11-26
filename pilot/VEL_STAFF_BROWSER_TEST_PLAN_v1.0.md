# Vel Scout – Gerçek personel hesabıyla tarayıcı test planı (v1.0, 26 Kasım 2026)

Amaç: `admin.html` panelinin baştan sona (oyuncu → maç → oturum → puanlama → gözlem → rapor → yayın → arşiv) gerçek bir
Supabase personel hesabıyla çalıştığını kanıtlamak. Veritabanı kuralları testlerle doğrulandı; **bu plan arayüzü** doğrular.

## 0. Hazırlık (proje sahibi yapar; şifre Claude'a verilmez)
1. Supabase → Authentication → Users: iki hesap oluştur: `test-editor@...` ve `test-admin@...` (kendi e-postaların, `+` takısı olur).
2. SQL editöründe rollerini ekle: `insert into user_roles(user_id, role) select id, 'editor' from auth.users where email='test-editor@...';` (admin için `'admin'`). 
3. Test verisi **yalnızca uydurma** olacak: oyuncu adı `ZZ-TEST Oyuncu`, gerçek çocuk/genç oyuncu verisi, gerçek doğum tarihi veya gerçek video bağlantısı kullanılmaz. Video kaydı gerekiyorsa `https://example.invalid/test` gibi sahte bağlantı.
4. Tarayıcıda `admin.html` aç (GitHub Pages adresi). Konsolu (F12) açık tut; kırmızı hata görürsen ekran görüntüsü al.

## Önemli uyarı: yayınlanmış rapor kalıcıdır
Canlı veritabanında doğruladım: yayınlanmış bir rapor (ve ona bağlı oturum, maç ve oyuncu) hiçbir yolla silinemiyor, bakım bağlantısıyla bile
(rapor silinemez → oturum silinemez → oyuncu silinemez). Bu, oyuncu silme prosedürü eksikliğinin sonucudur. Bu yüzden:
- Bölüm A–D (taslak ve inceleme aşamaları) güvenle tekrarlanabilir; bunlar silinebilir.
- Bölüm E (yayın ve arşiv) **yalnızca bir kez** ve yalnızca `ZZ-TEST` oyuncusuyla yapılır; ardından oyuncu profili `archived` yapılır. Kalıntı herkese açık değildir.

## A. Giriş ve yetki
| # | Adım | Beklenen |
|---|------|----------|
| A1 | Yanlış şifreyle giriş | Hata mesajı, panel açılmaz |
| A2 | Editor hesabıyla giriş | Panel açılır, "Hoş geldin" görünür |
| A3 | Oturumu kapat, sayfayı yenile | Panel kilitli, giriş ekranı gelir |
| A4 | Girişsiz `admin.html` | Veri görünmez |

## B. Kayıtlar (editor)
| # | Adım | Beklenen |
|---|------|----------|
| B1 | Yeni oyuncu profili: `ZZ-TEST Oyuncu`, durum `draft` | Başarı mesajı, listede görünür |
| B2 | Yeni maç kaydı, oyuncuyu maça bağla | Bağlantı listede |
| B3 | Yeni scouting oturumu (rubrik seç) | Oturum "Taslak" |
| B4 | Aynı oyuncu-maç için ikinci oturum denemesi | Mantıklı hata veya ayrı oturum; sessiz başarısızlık olmamalı |

## C. Puanlama ve gözlem (editor)
| # | Adım | Beklenen |
|---|------|----------|
| C1 | Hiç kriter kaydetmeden "İncelemeye al" | Reddedilir, "tüm kriterleri kaydet" benzeri mesaj |
| C2 | Tüm kriterleri puanla/N-A/N-E işaretle, "Puanları kaydet" | Kaydedilir |
| C3 | İncelemeye al | Oturum "İncelemede" |
| C4 | Puanlı bir kriter için gözlem eklemeden "Tamamla" | Reddedilir, hangi kriter olduğu söylenir |
| C5 | Zaman damgalı gözlem ekle (dakika 0–150) | Kaydedilir; dakika 151 reddedilir |
| C6 | 9 veya 10 puan: gerekçe 50 karakterden kısa ve 1 gözlem | Reddedilir; düzeltince geçer |
| C7 | "Tamamla" | Oturum "Tamamlandı"; puan/gözlem düzenleme kapanır |
| C8 | "Yeniden aç", sonra tekrar "Tamamla" | Çalışır |

## D. Rapor (editor)
| # | Adım | Beklenen |
|---|------|----------|
| D1 | Tamamlanmış 2+ maçlık oturumlarla taslak rapor oluştur | Rapor "Taslak"; kanıt derecesi hesaplanır, uydurma puan yok |
| D2 | Tam maç onayı vermeden oluştur | Derece boş/C; genel puan yok ("rating yok") |
| D3 | "İncelemeye al" | Rapor "İncelemede" |
| D4 | Tabloda "Yayınla"/"Arşivle" butonları | Editor'da **görünmez** |
| D5 | "Geçmiş" | Sürüm 1, metodoloji sürümü, rubrik kodu, çıpa sürümü görünür |
| D6 | "Taslağa döndür" | Çalışır |

## E. Yayın ve arşiv (admin; yalnızca bir kez, uyarıya bak)
| # | Adım | Beklenen |
|---|------|----------|
| E1 | Admin hesabıyla giriş, raporu "İncelemeye al" | Çalışır |
| E2 | Oyuncu profilini `published` yap, raporu "Yayınla" (onay kutusu) | Başarı mesajı yalnızca gerçekten yayınlandıysa |
| E3 | Herkese açık ana sayfa (girişsiz, gizli pencere) | Oyuncu ve raporu görünür; doğum tarihi/özel not **yok** |
| E4 | Yayınlanmış raporun metnini düzenlemeyi dene | Engellenir |
| E5 | "Düzeltme taslağı" | Yeni taslak, `supersedes` zinciri; eski rapor değişmez |
| E6 | "Arşivle" | Ana sayfadan kaybolur; "Geçmiş" eski sürümleri gösterir |
| E7 | Oyuncu profilini `archived` yap | Ana sayfada oyuncu yok |
| E8 | Editor hesabıyla E2'yi dene | Buton yok; doğrudan API denemesi reddedilir (test edildi) |

## F. Hata davranışı
- Ağı kes (tarayıcı çevrimdışı) ve bir kayıt dene: **başarı mesajı çıkmamalı**.
- Aynı sekmeyi iki pencerede aç, birinde raporu arşivle, diğerinde "Yayınla"ya bas: ikinci pencere hata göstermeli (başarı değil).

## Sonuç kaydı
Her satır için: GEÇTİ / KALDI / ATLANDI + not + ekran görüntüsü. Kalan satırlar Claude'a verilir; her biri küçük, testli bir PR olur.
