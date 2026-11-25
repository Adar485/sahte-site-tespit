# Sahte Site Avcıları — Frontend

React + TypeScript + Vite + Tailwind CSS (v4) + Lucide ile yazılmış arayüz.
Bu sürüm **demo veri** ile çalışır; gerçek web sitesi analizi yapılmaz.

## Kurulum ve çalıştırma

Gereksinim: Node.js 20 veya üzeri.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Diğer komutlar:

```bash
npm run build      # tür denetimi + üretim derlemesi (dist/)
npm run preview    # derlenmiş sürümü http://localhost:4173 adresinde sunar
npm run typecheck  # yalnızca TypeScript denetimi
```

## Demo senaryoları

Ana sayfadaki "Örnek adreslerle deneyin" listesi her durumu gösterir:

| Adres | Sonuç |
| --- | --- |
| `www.example.com` | Düşük risk |
| `example-destek.test/hesap/guncelle` | Şüpheli |
| `http://examp1e.test/giris` | Yüksek phishing riski (yönlendirmeli) |
| `kampanya.example.net/odul-kazandiniz` | Kısmi analiz: yalnızca URL |
| `bos-sayfa.example.org` | Ekran görüntüsü ve metin eksik |
| `ulasilamayan.invalid` | Sayfaya ulaşılamadı |
| `yavas.example.net` | Zaman aşımı |
| Listede olmayan herhangi bir adres | Analiz servisine ulaşılamıyor |

Tüm alan adları ayrılmış örnek alan adlarıdır (example.*, .test, .invalid).
Geçmiş ve demo sonuçları tarayıcının `localStorage` alanında tutulur. Geçmiş boşken
"Örnek geçmiş yükle" düğmesiyle örnek kayıtlar eklenebilir.

## Yapı

```
src/
  types/analysis.ts      İstek, sonuç, modül bulgusu ve geçmiş tipleri (API sözleşmesi)
  services/
    types.ts             AnalysisService arayüzü ve ServiceError
    apiService.ts        Gerçek API istemcisi (POST /api/analyze, GET /api/result/{id})
    index.ts             Sağlayıcı seçimi (demo / api)
    historyStore.ts      Yerel analiz geçmişi
  demo/
    fixtures.ts          Örnek senaryolar
    demoService.ts       AnalysisService'in demo uygulaması
  hooks/                 Analiz başlatma, sonuç sorgulama, geçmiş
  components/            Arayüz bileşenleri (result/ altında sonuç ekranı parçaları)
  pages/                 Analiz, sonuç, geçmiş ve 404 sayfaları
  lib/                   URL doğrulama, biçimlendirme, Türkçe etiketler
```

Arayüz bileşenleri yalnızca `services/index.ts` üzerinden veri alır; demo verisine doğrudan bağlı değildir.

## Gerçek API'ye geçiş

`.env.example` dosyasını `.env.local` olarak kopyalayıp şunu ayarlayın:

```
VITE_ANALYSIS_MODE=api
VITE_API_BASE_URL=http://localhost:8000
```

Arayüzün beklediği uç noktalar:

- `POST /api/analyze` — gövde `{ "url": "https://..." }`, yanıt `{ "id": "...", "state": "queued" | "running" }`
- `GET /api/result/{id}` — sonuç hazır değilse `{ id, state: "running", stage, submittedUrl }`,
  hazırsa `{ id, state: "done", result: AnalysisResult }`. Sonuç bulunamazsa `404`.

`stage` değerleri: `url_check`, `page_fetch`, `content_inspection`, `scoring`.
Tüm alanlar `src/types/analysis.ts` içinde tanımlıdır. Arayüz, sonuç hazır olana kadar
1,5 saniyede bir sorgu yapar. API modunda demo bildirimi ve örnek adres listesi gizlenir.
