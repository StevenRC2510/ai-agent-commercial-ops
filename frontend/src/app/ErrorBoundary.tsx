import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/** Renders an explicit Spanish fallback instead of a blank screen on an unhandled render error. */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(
      "Unhandled error in the frontend tree:",
      error,
      info.componentStack,
    );
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" className="p-8">
          <h1 className="text-xl font-semibold">Algo salió mal</h1>
          <p className="mt-2 text-sm text-gray-600">
            Ocurrió un error inesperado. Intenta recargar la página.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
