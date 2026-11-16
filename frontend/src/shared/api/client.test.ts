import { apiClient } from "./client";
import { StudentApiError, extractErrorMessage } from "./errors";

describe("apiClient contract tests", () => {
  it("GET /api/dashboard returns a dashboard payload", async () => {
    const { data, error } = await apiClient.GET("/api/dashboard");

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      submission_count: expect.any(Number),
      team_count: expect.any(Number),
      latest: expect.any(Array),
      status_counts: expect.any(Object),
    });
  });

  it("GET /api/admin/settings returns settings", async () => {
    const { data, error } = await apiClient.GET("/api/admin/settings");

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      course: expect.any(Object),
      execution_limits: expect.any(Object),
    });
  });

  it("GET /api/leaderboard returns ranked rows", async () => {
    const { data, error } = await apiClient.GET("/api/leaderboard", {
      params: { query: { data_track: "learning" } },
    });

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      rows: expect.any(Array),
      count: expect.any(Number),
    });
    expect(data?.rows.length).toBeGreaterThan(0);
    expect(data?.rows[0]).toHaveProperty("rank");
    expect(data?.rows[0]).toHaveProperty("team_name");
  });

  it("GET /api/submissions returns a list of submissions", async () => {
    const { data, error } = await apiClient.GET("/api/submissions");

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      submissions: expect.any(Array),
    });
  });

  it("POST /api/submissions accepts a multipart form body", async () => {
    const formData = new FormData();
    formData.append("team_name", "team-1");
    formData.append("password", "secret");
    formData.append("file", new File(['print("hello")'], "strategy.py"));
    formData.append("data_track", "learning");

    const { data, error } = await apiClient.POST("/api/submissions", {
      body: formData as never,
    });

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      submission_id: expect.any(String),
      team_id: expect.any(String),
      team_name: expect.any(String),
      status: expect.any(String),
      data_track: expect.any(String),
      submitted_at: expect.any(String),
    });
  });

  it("GET /api/submissions/{submissionId} returns detail", async () => {
    const { data, error } = await apiClient.GET("/api/submissions/{submission_id}", {
      params: { path: { submission_id: "sub-1" } },
    });

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      submission_id: "sub-1",
      team_id: expect.any(String),
      team_name: expect.any(String),
      status: expect.any(String),
      submitted_at: expect.any(String),
      original_filename: expect.any(String),
      artifacts: expect.any(Object),
    });
  });

  it("GET /api/compare returns submissions for comparison", async () => {
    const { data, error } = await apiClient.GET("/api/compare", {
      params: { query: { submission_id: ["sub-1", "sub-2"] } },
    });

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      submissions: expect.any(Array),
    });
    expect(data?.submissions.length).toBe(2);
  });

  it("GET /api/admin/teams returns the team roster", async () => {
    const { data, error } = await apiClient.GET("/api/admin/teams");

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      teams: expect.any(Array),
    });
  });

  it("POST /api/admin/teams creates a team", async () => {
    const { data, error } = await apiClient.POST("/api/admin/teams", {
      body: {
        team_name: "Team C",
        password: "secret",
      },
    });

    expect(error).toBeUndefined();
    expect(data).toMatchObject({
      team_id: expect.any(String),
      display_name: expect.any(String),
    });
  });

  it("GET /api/downloads/starter-strategy.py returns a plain text file", async () => {
    const { data, error } = await apiClient.GET("/api/downloads/starter-strategy.py", {
      parseAs: "text",
    });

    expect(error).toBeUndefined();
    expect(data).toContain("价格成交额动量");
    expect(data).toContain("generate_signals(data, date)");
    expect(data).toContain("dnvaltrd");
    expect(data).toContain("numeric_columns");
  });

  describe("error handling", () => {
    it("returns a 404 error payload for an unknown submission", async () => {
      const { data, error, response } = await apiClient.GET("/api/submissions/{submission_id}", {
        params: { path: { submission_id: "not-found" } },
      });

      expect(data).toBeUndefined();
      expect(error).toBeDefined();
      expect(response.status).toBe(404);

      const message =
        typeof error === "object" && error && "message" in error
          ? String(error.message)
          : String(error);
      expect(message).toBe("Submission not found");

      const apiError = new StudentApiError(response.status, message);
      expect(apiError).toBeInstanceOf(StudentApiError);
      expect(apiError.status).toBe(404);
      expect(apiError.name).toBe("StudentApiError");
    });

    it("returns a 500 error payload and exposes StudentApiError", async () => {
      const { data, error, response } = await apiClient.GET("/api/submissions/{submission_id}", {
        params: { path: { submission_id: "server-error" } },
      });

      expect(data).toBeUndefined();
      expect(error).toBeDefined();
      expect(response.status).toBe(500);

      const message = typeof error === "string" ? error : String(error);
      expect(message).toBe("Internal server error");

      const apiError = new StudentApiError(response.status, message);
      expect(apiError).toBeInstanceOf(StudentApiError);
      expect(apiError.status).toBe(500);
    });

    it("extractErrorMessage reads JSON message, detail, text, then statusText", async () => {
      const jsonMessage = new Response(JSON.stringify({ message: "queue offline" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
      expect(await extractErrorMessage(jsonMessage)).toBe("queue offline");

      const jsonDetail = new Response(JSON.stringify({ detail: "validation failed" }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      });
      expect(await extractErrorMessage(jsonDetail)).toBe("validation failed");

      const textError = new Response("plain text error", { status: 500 });
      expect(await extractErrorMessage(textError)).toBe("plain text error");

      const emptyError = new Response(null, { status: 502, statusText: "Bad Gateway" });
      expect(await extractErrorMessage(emptyError)).toBe("Bad Gateway");
    });
  });
});
