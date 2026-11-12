# Vel Scout — CV Prototip Veri Seti Seçimi v1.0

**Tarih:** 12 Kasım 2026  
**Karar:** Teknik CV doğrulaması için birincil aday: SoccerTrack v2  
**Kullanım sınırı:** Bu veri seti, Vel Scout'un gerçek futbolcu değerlendirme havuzu değildir.

## 1. Neden bu veri seti?

SoccerTrack v2, 10 tam uzunlukta panoramik 4K üniversite düzeyi amatör maç (yaklaşık 900 dakika) sunuyor. GSR katmanında kare bazlı saha koordinatları, track ID, forma numarası, rol ve takım tarafı; BAS katmanında 12 top/oyun aksiyonu sınıfı bulunuyor. MOT anotasyonları ise veri setinin tamamını kapsamıyor.

Veri setinin kendi LICENSE-DATA dosyası CC BY 4.0 lisansı belirtiyor. Atıf, lisans bağlantısı ve yapılan değişikliklerin belirtilmesi şartıyla lisans ticari kullanıma da izin veriyor. Depo, maçların üniversite etik kurulu onayı ve bilgilendirilmiş katılımla toplandığını; yayımlanan veride oyuncu isimlerinin bulunmadığını ve forma numarası temelli kimlik kullandığını belirtiyor.

**Kaynaklar**
- Proje: https://atomscott.github.io/SoccerTrack-v2/
- Depo: https://github.com/AtomScott/SoccerTrack-v2
- Veri lisansı: https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA
- Veri deposu: https://huggingface.co/datasets/atomscott/soccertrack-v2
- Makale: https://arxiv.org/abs/2508.01802

## 2. Erişim kapısı — lisans ile indirme iznini karıştırma

Lisansın CC BY 4.0 olması, ham veri dosyalarının kimlik doğrulaması olmadan indirilebileceği anlamına gelmiyor. Upstream scripts/download.sh, Hugging Face oturum açma/token kontrolü yapıyor ve veri setinin gated olduğunu, ayrıca veri kümesine erişim isteğinin onaylanması gerektiğini açıkça belirtiyor.

Bu nedenle:
- Veri, erişim onayı alınmadan indirilmeyecek veya işlenmeyecek.
- Erişim token'ı GitHub'a, Vel Scout koduna, HTML'e, Supabase'e veya rapora yazılmayacak.
- İndirme yalnızca yetkili yerel çalışma alanında yapılacak; ham dosyalar public siteye veya Supabase Storage'a yüklenmeyecek.
- CC BY 4.0 atıf şartı ve lisans bağlantısı korunacak; türetilmiş çıktılarda yapılan değişiklikler belirtilecek.
- Erişim talebi veya ek bir koşul/NDA sunulursa, kabul/taahhüt gerektiren kısmı sorumlu yetişkin ve gerekiyorsa kurum/hukuk danışmanı incelemeden kabul edilmeyecek.

## 3. Vel Scout için uygun kapsam

**Uygun**
- Panoramik videodan kare/zaman metadata'sı okuma.
- Sağlanan GSR anotasyonlarını doğrulama ve saha koordinatlarını normalleştirme.
- BAS aksiyon etiketlerini zaman çizgisine yerleştirme.
- Player/ball tracking ve event-spotting prototiplerinin teknik doğrulaması.
- Video–anotasyon senkronizasyonu ve veri kalitesi ölçümü.

**Uygun değil**
- Bu veri setini isimli profesyonel veya genç futbolcu arşivi gibi sunmak.
- Forma numarası/track ID'yi gerçek dünyadaki bir kişinin kimliğiyle eşleştirmek.
- Bu veri setinden Davinson Sánchez veya başka bir gerçek futbolcu için performans notu, rol kararı ya da scout raporu çıkarmak.
- Anotasyon kapsamını aşarak tüm oyuncular için eksiksiz bounding box veya tüm maçlar için tam MOT varmış gibi davranmak.

Bu veri, model ve veri hattının çalıştığını sınar; gerçek scout metodolojisinin saha geçerliliğini kanıtlamaz.

## 4. Bilinen veri-formatı riskleri

Upstream depo, yayımlanan gerçek dosyalarla kendi format dokümanları arasında önemli farklar bulunduğunu açıkça bildiriyor:

1. **GSR kök yapısı:** Gerçek GSR dosyaları düz kayıt dizisi değil; info, images, annotations, categories içeren SoccerNet-COCO benzeri bir JSON nesnesi.
2. **GSR alanları:** image_id metin olabilir; rol, forma ve takım bilgileri attributes altındadır; bbox_image ve bbox_pitch dizi değil nesne biçimindedir. bbox_pitch içindeki orta-alt koordinat çifti esas alınmalıdır.
3. **GSR kayıt türleri:** object dışında pitch ve camera anotasyonları da bulunur; hepsi futbolcu olarak sayılmamalıdır.
4. **Bellek:** Bazı GSR yarı dosyaları yaklaşık 2,7 GB olabilir. Bunlar json.load() ile belleğe alınmamalı; akışlı parser kullanılmalıdır.
5. **Görüntü boyutları:** Upstream dokümanı, 10 maçın 9'unda images.width/height metadata'sının gerçek görüntü geometrisiyle uyuşmadığını bildiriyor. Gerçek video boyutu ffprobe ile kontrol edilmeden koordinatlar görüntü pikseline dönüştürülmemeli.
6. **BAS alan adları/etiketler:** Yayımlanan BAS dosyalarında olay listesi actions olabilir; etiketler büyük harfli gelebilir. Hem actions hem annotations kabul edilmeli, etiketler büyük/küçük harften bağımsız normalize edilmeli.
7. **Yarı zaman hizalaması:** Upstream GSR/BAS dokümanları ve uygulaması arasında ikinci yarı zamanının başlangıcı konusunda çelişki bulunuyor. Sabit 45 dakika çıkararak kare eşleştirmesi kesin kabul edilmemeli. Gerçek eşleme için maç metadata'sındaki dönem/kare başlangıç bilgisi doğrulanmalı.

Bu riskler çözülmeden anotasyonlar scout kanıtına veya oyuncu puanına dönüştürülmeyecek.

## 5. İlk teknik prototipin kapsamı

Erişim onayı geldikten sonra tek maçla başla; önce tüm 10 maçı indirme.

**Aşama A — Veri doğrulama**
- GSR JSON yapısı, kare sayısı, anotasyon sayısı ve kayıt türleri.
- Player/goalkeeper rolü, takım tarafı, track ID ve saha koordinatı tutarlılığı.
- BAS sınıf seti, etiket sayımları, zaman sıralaması ve görünürlük alanları.
- Video FPS, süre, çözünürlük ve anotasyon metadata karşılaştırması.
- Yarı bazında zaman eşlemesinin ham metadata ile doğrulanması.

**Aşama B — CV baseline**
- Önce anotasyonları kullanarak veri okuyucu ve görselleştirme testi.
- Ardından, lisans/erişim koşulları içinde, mevcut anotasyonlarla takip/aksiyon tespiti baseline'ı.
- Çıktılar: veri kalite raporu, zaman hizalama raporu, track sürekliliği ve aksiyon sınıfı değerlendirmesi.
- Her metrikte ölçülen anotasyon kapsamı ve eksik etiketler ayrıca açıklanacak.

**Aşama C — Vel Scout'a aktarım kararı**
- Yalnızca teknik doğrulama başarılıysa, gerçek maç videosu için ayrı hak ve erişim araştırmasına geç.
- SoccerTrack sonuçları oyuncu scouting puanı, potansiyel veya transfer kararı olarak kullanılmayacak.

## 6. Çalıştırma aracı

vision/soccertrack_v2/validate_dataset.py, erişimi onaylanmış ve yerel olarak indirilmiş veri üzerinde çalıştırılacak. Araç:
- GSR dosyalarını akışlı okur; dev JSON dosyalarını RAM'e yüklemez.
- BAS'ta hem actions hem annotations anahtarını destekler.
- Üst/büyük harf farkını normalize eder.
- İsteğe bağlı ffprobe ile video metadata'sını karşılaştırır.
- Belirsiz ikinci yarı eşlemesini otomatik doğru varsaymaz.
- Yalnızca JSON kalite raporu üretir; dosya yüklemez, silmez veya Supabase'e veri göndermez.

Bağımlılık: requirements-vision.txt içindeki ijson.

## 7. Atıf

Veri kullanıldığında en azından şu bilgiler görünür olmalı:

> SoccerTrack v2 by Atom Scott et al. Dataset licensed under CC BY 4.0. Source: https://github.com/AtomScott/SoccerTrack-v2 . Changes, if any, must be indicated. Academic work should also cite https://arxiv.org/abs/2508.01802 .

**Durum:** Kaynak kataloğuna soccertrack-v2 olarak eklendi. İdempotent referans kaydı supabase/seeds/010_soccertrack_v2_source.sql dosyasında izlenir. Ham veri indirilmedi; erişim onayı ve yerel doğrulama bekliyor.
