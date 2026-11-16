/**
 * Start the in-browser mock API when the bundle was built with
 * `VITE_DEMO_MODE=true`. The service worker is registered relative to the
 * deployed base path so the same build works on GitHub Pages sub-paths.
 */
export async function enableDemoMode(): Promise<void> {
  if (import.meta.env.VITE_DEMO_MODE !== "true") {
    return;
  }
  const { worker } = await import("../mocks/browser");
  await worker.start({
    onUnhandledRequest: "bypass",
    serviceWorker: {
      url: `${import.meta.env.BASE_URL}mockServiceWorker.js`
    }
  });
}
