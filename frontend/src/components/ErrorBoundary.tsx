import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error("[ui] crash", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="panel p-6 max-w-md w-full text-center">
          <div className="label mb-3">Something went wrong</div>
          <p className="text-sm text-fg-secondary mb-5 break-words">{this.state.error.message}</p>
          <button className="btn" onClick={this.reset}>
            Reload view
          </button>
        </div>
      </div>
    );
  }
}
