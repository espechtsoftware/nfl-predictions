import { Component, ReactNode } from "react";

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

interface ErrorBoundaryState {
  readonly error: Error | null;
}

/** Renders render-time failures honestly instead of a blank page. */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  render() {
    if (this.state.error !== null) {
      return (
        <div className="state state-error" data-testid="state-error" role="alert">
          <p>The page failed to render.</p>
          <p className="state-detail">{this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
