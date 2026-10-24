# Team 09 kararlarının yeniden denemesi — 24 Ekim 2026

## Kurulum

Hafta 3 ve 4 motor denetimi olayları ile hafta 4'teki $1,05 milyonluk karar her koşuda aynı bırakıldı. Hafta 8'deki 22–23 Aralık yer hizmetleri grevi her koşuya eklendi. Gerçek `gemini-3.5-flash-lite` modeli, 66 persona ve sosyal etkileşim kullanıldı. Üç farklı seed (1, 2, 3) denenerek aynı seed içindeki seçeneklerin hafta 1–7 geçmişi eşleştirildi. Seed 3 yeni bir replicate ile tekrar üretildi. Tüm koşular hafta 10'a ulaştı, hata sayısı sıfır ve her koşunun haftalık logları tutuldu.

Karşılaştırmadaki sayılar **simülasyonda gözlenen persona kayıtlarıdır**. Havayolunun bütün uçuşları, gerçek bilet gelirleri veya gerçek aylık şikâyet toplamı bu 66 personadan doğrudan ölçülemez. Bu yüzden aşağıdaki gözlemler kurul hedeflerinin gerçekleştiği iddiası değildir.

## Hafta 8 kararı: üç seed'in toplam gözlemleri

| Hafta 8 seçeneği | İkinci karar maliyeti | Grev günü iptali / 48 etkilenen persona uçuşu | Hafta 8–9 çözülen / etkilenen | Hafta 8–9 şikâyet / 396 persona-hafta | Hafta 10 yeniden rezervasyon “evet” / 198 persona |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ek karar yok | $0 | 9 | 27/38 | 27 | 143 |
| Yedek yer hizmetleri + ortak havayolu | $0,75M | 2 | 13/13 | 16 | 154 |
| **Yedek yer hizmetleri + ortak havayolu + çift sadakat puanı** | **$0,85M** | **2** | **13/13** | **11** | **153** |
| Yedek yer hizmetleri + ortak havayolu + ek personel | $0,90M | 2 | 13/13 | 15 | 149 |
| Yedek yer hizmetleri + ortak havayolu + ücretsiz değişiklik | $0,95M | 2 | 13/13 | 14 | 154 |

Her seed'de greve denk gelen 16 persona uçuşu vardı. Ek kararsız iptaller 3/3/3, yedek yer hizmetli seçeneklerde 0/1/1 oldu. Puanlı paketin hafta 8–9 şikâyetleri seed bazında **3/4/4**; yalnızca yedek + ortak havayolu paketinde **6/6/4**. Puanların bu örneklemde ek yararı şikâyette görüldü; aynı operasyon ve 24 saat çözüm sonucunu daha düşük maliyetle veren $0,75M seçeneği de makul bir tasarruf alternatifi.

Seed 3'te ayrıca yedek + ortak + otel, yedek + puan + $75 kredi, kiralık uçak + ortak havayolu, ve aynı puanlı kararın hafta 7 sürümleri denendi. Hafta 7 sürümünde hafta 9'daki ortak havayolu hakkı sona erdiği için hafta 8–9 çözüm **3/4** kaldı; hafta 8 sürümünde **4/4** oldu. Diğer seçenekler, üç seed'de doğrulanmış puanlı paketten daha güçlü bir genel sonuç göstermedi. Tüm bu seçeneklerin ikinci karar maliyeti $1M sınırının altındaydı.

## Tavsiye ve zamanlama

Hafta 8 kararını **hafta 8 başlangıçlı** olarak kaydedin; bugünden geleceğe dönük olarak sisteme girilebilir. Üç eylem: iki bazda grev günleri için yedek yer hizmetleri ($0,50M), iki aksak hafta için ortak havayolunda yeniden rezervasyon ($0,25M), etkilenen yolculara çift sadakat puanı ($0,10M). İkinci karar $0,85M, hafta 4 ile toplam $1,90M.

Hafta 1–7 checkpoint kimlikleri hafta 8 seçenekleri arasında aynı; hafta 8'de ayrışıyor. Grev olayı persona metinlerinde hafta 7'ye kadar yok, hafta 8'den itibaren 66/66 kişide var. Hafta 7 başlangıçlı karar ayrı testte yalnızca hafta 7'den itibaren farklılaşıyor. Bu, önceki haftaların gelecekteki karar veya olaydan etkilenmediğini doğruluyor.

Arayüzde `team09_retest_points_ui` ve `team09_retest_minimal_ui` oturumları hafta 10'a kadar oynatıldı. İkisinde de 10 haftalık oturuma özel log, 3/4/8 olayları ve 4/8 kararları doğrulandı. Seed 3'ün doğrudan anket NPS değeri sırasıyla −10,6 ve −12,1; bunlar eski +12 başlangıç değerine eklenmiş tahminler değildir.
