import type { AskRequest, AskResponse, RetrievedSource } from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRetrievedSource(value: unknown): value is RetrievedSource {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.repository === "string" &&
    typeof value.file_path === "string" &&
    typeof value.symbol_type === "string" &&
    (typeof value.symbol_name === "string" || value.symbol_name === null) &&
    typeof value.start_line === "number" &&
    typeof value.end_line === "number" &&
    typeof value.content === "string" &&
    typeof value.cosine_distance === "number"
  );
}

function isAskResponse(value: unknown): value is AskResponse {
  return (
    isRecord(value) &&
    typeof value.answer === "string" &&
    Array.isArray(value.sources) &&
    value.sources.every((source: unknown) => isRetrievedSource(source))
  );
}

function getErrorDetail(value: unknown): string | null {
  if (isRecord(value) && typeof value.detail === "string") {
    return value.detail;
  }
  return null;
}

export async function askQuestion(request: AskRequest): Promise<AskResponse> {
  let response: Response;

  try {
    response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw new Error("Could not reach the Codebase QA backend.");
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(`The backend returned HTTP ${response.status}.`);
    }
    throw new Error("The backend returned an unreadable response.");
  }

  if (!response.ok) {
    throw new Error(
      getErrorDetail(payload) ?? `The backend returned HTTP ${response.status}.`,
    );
  }

  if (!isAskResponse(payload)) {
    throw new Error("The backend returned an unexpected response.");
  }

  return payload;
}
