import { Component } from "react";
import { Button } from "./ui.jsx";

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
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-paper px-6 text-center text-ink">
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-acc">System notice</p>
            <h1 className="mt-2 font-display text-3xl font-normal">Something went wrong.</h1>
            <p className="mt-1 font-mono text-xs text-ink-3">Reload the page to try again.</p>
          </div>
          <Button onClick={() => window.location.reload()}>Reload</Button>
        </div>
      );
    }
    return this.props.children;
  }
}
