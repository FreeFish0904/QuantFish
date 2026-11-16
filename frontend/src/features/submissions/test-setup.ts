import { File } from "node:buffer";
import { fetch, FormData, Headers, Request, Response } from "undici";

globalThis.fetch = fetch as unknown as typeof globalThis.fetch;
globalThis.FormData = FormData as unknown as typeof globalThis.FormData;
globalThis.File = File as unknown as typeof globalThis.File;
globalThis.Headers = Headers as unknown as typeof globalThis.Headers;
globalThis.Request = Request as unknown as typeof globalThis.Request;
globalThis.Response = Response as unknown as typeof globalThis.Response;

if (typeof window !== "undefined") {
  window.fetch = fetch as unknown as typeof window.fetch;
  window.FormData = FormData as unknown as typeof window.FormData;
  window.File = File as unknown as typeof window.File;
  window.Headers = Headers as unknown as typeof window.Headers;
  window.Request = Request as unknown as typeof window.Request;
  window.Response = Response as unknown as typeof window.Response;
}
