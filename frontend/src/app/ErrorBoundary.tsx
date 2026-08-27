import { Component, type ErrorInfo, type ReactNode } from "react";

import type { ErrorBoundaryProps, ErrorBoundaryState } from "./ErrorBoundary.types";
import { BODY, FALLBACK_BODY, FALLBACK_TITLE, TITLE, WRAPPER } from "./ErrorBoundary.constants";

// The only class in the codebase: React offers no hook for componentDidCatch.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled error in the frontend tree:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" className={WRAPPER}>
          <h1 className={TITLE}>{FALLBACK_TITLE}</h1>
          <p className={BODY}>{FALLBACK_BODY}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
