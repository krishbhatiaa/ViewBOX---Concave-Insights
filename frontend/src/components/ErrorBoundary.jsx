import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("ViewBox render error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center dark:bg-slate-950">
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Something went wrong.</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Reload the page to try again.</p>
          </div>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="min-h-11 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
