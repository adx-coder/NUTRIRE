import { Component, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { hasError: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#EDE8E0" }}>
        <div className="text-center px-6 max-w-md">
          <div className="text-[48px] mb-4">🌿</div>
          <h1 className="font-display text-2xl font-bold text-ink mb-2">Something went wrong</h1>
          <p className="text-[14px] text-ink/60 mb-6">
            We hit an unexpected issue. Try refreshing, or head back to the start.
          </p>
          <a
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-sage-deep text-white text-[14px] font-semibold shadow-[0_4px_12px_-4px_rgba(58,101,81,0.4)]"
          >
            Go home
          </a>
        </div>
      </div>
    );
  }
}
