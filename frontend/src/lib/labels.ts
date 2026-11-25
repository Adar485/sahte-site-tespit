import type {
  AnalysisMode,
  AnalysisStage,
  FindingSeverity,
  KeyPhrase,
  ModuleKey,
  ModuleStatus,
  ResultFilter,
  RiskLevel,
} from '../types/analysis';

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: 'Düşük risk',
  suspicious: 'Şüpheli',
  high: 'Yüksek phishing riski',
};

export const RISK_SHORT_LABELS: Record<RiskLevel, string> = {
  low: 'Düşük risk',
  suspicious: 'Şüpheli',
  high: 'Yüksek risk',
};

export const FAILED_LABEL = 'Analiz tamamlanamadı';
export const PARTIAL_LABEL = 'Kısmi analiz';

export const MODULE_LABELS: Record<ModuleKey, string> = {
  url: 'URL analizi',
  visual: 'Görsel analiz',
  text: 'Metin analizi',
  html: 'HTML yapısı analizi',
};

export const MODULE_ORDER: ModuleKey[] = ['url', 'visual', 'text', 'html'];

export const MODULE_STATUS_LABELS: Record<ModuleStatus, string> = {
  pending: 'Sırada',
  running: 'Sürüyor',
  completed: 'Tamamlandı',
  unavailable: 'Veri yok',
  skipped: 'Çalıştırılmadı',
  failed: 'Hata',
};

export const STAGE_ORDER: AnalysisStage[] = ['url_check', 'page_fetch', 'content_inspection', 'scoring'];

export const STAGE_LABELS: Record<AnalysisStage, string> = {
  url_check: 'URL kontrolü',
  page_fetch: 'Sayfa içeriği',
  content_inspection: 'Görsel, metin ve yapı incelemesi',
  scoring: 'Sonucun hazırlanması',
};

export const STAGE_DESCRIPTIONS: Record<AnalysisStage, string> = {
  url_check: 'Adresin yazımı, alan adı ve yönlendirmeler inceleniyor.',
  page_fetch: 'Sayfa güvenli bir ortamda açılıyor ve içeriği alınıyor.',
  content_inspection: 'Ekran görüntüsü, görünür metin ve HTML yapısı karşılaştırılıyor.',
  scoring: 'Bulgular birleştirilerek genel değerlendirme hazırlanıyor.',
};

export const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  info: 'Bilgi',
  low: 'Düşük önem',
  medium: 'Dikkat',
  high: 'Önemli',
};

export const PHRASE_CATEGORY_LABELS: Record<KeyPhrase['category'], string> = {
  urgency: 'Aciliyet baskısı',
  credentials: 'Kimlik bilgisi talebi',
  payment: 'Ödeme talebi',
  reward: 'Ödül vaadi',
  neutral: 'Olağan ifade',
};

export const FILTER_LABELS: Record<ResultFilter, string> = {
  all: 'Tümü',
  low: 'Düşük risk',
  suspicious: 'Şüpheli',
  high: 'Yüksek risk',
  failed: 'Tamamlanamadı',
};

export const ANALYSIS_MODE_LABELS: Record<AnalysisMode, string> = {
  full: 'Tam analiz',
  url_only: 'Yalnızca URL',
};

/** Arka uç öneri metni göndermediğinde risk düzeyine göre gösterilen genel öneri. */
export const DEFAULT_RECOMMENDATIONS: Record<RiskLevel, string> = {
  low: 'Düşük risk, sitenin güvenli olduğu anlamına gelmez. Kişisel bilgilerinizi yalnızca adresini kendiniz yazdığınız ya da doğruladığınız sitelerle paylaşın.',
  suspicious: 'Bu sayfaya bilgi girmeden önce adresi dikkatle kontrol edin. Emin değilseniz kurumun adresini tarayıcıya kendiniz yazın.',
  high: 'Bu sayfaya parola, kart bilgisi ya da doğrulama kodu girmeyin. Bilgi girdiyseniz parolanızı hemen değiştirin.',
};
