import createClient from "openapi-fetch";

import type { paths } from "./generated/api-types";

export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request: Request) => globalThis.fetch(request),
});
