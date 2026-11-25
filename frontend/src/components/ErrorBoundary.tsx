import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  /** Hata durumunda gösterilecek içerik. */
  fallback: ReactNode;
  /** Bu değer değiştiğinde (ör. başka bir sekme ya da kayıt) hata durumu sıfırlanır. */
  resetKey?: unknown;
  children: ReactNode;
}

/**
 * Beklenmeyen bir görüntüleme hatasının tüm sayfayı boş bırakmasını önler.
 * Örneğin arka uçtan gelen modül verisi beklenen biçimde değilse yalnızca
 * ilgili bölüm yedek içerikle değiştirilir.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, { failed: boolean; key: unknown }> {
  state = { failed: false, key: this.props.resetKey };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  static getDerivedStateFromProps(props: ErrorBoundaryProps, state: { failed: boolean; key: unknown }) {
    return props.resetKey !== state.key ? { failed: false, key: props.resetKey } : null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Görüntüleme hatası:', error, info.componentStack);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
