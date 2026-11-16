export class StudentApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "StudentApiError";
    this.status = status;
  }
}

export async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body = (await response.json()) as Record<string, unknown>;
      if (typeof body.message === "string" && body.message) {
        return body.message;
      }
      if (typeof body.detail === "string" && body.detail) {
        return body.detail;
      }
    }
    const text = await response.text();
    if (text) {
      return text;
    }
  } catch {
    // fall through
  }
  return response.statusText || `Request failed with status ${response.status}`;
}
