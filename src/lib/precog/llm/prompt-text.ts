/**
 * Helpers every server function that asks Voyager shares: fencing owner-typed
 * text, reading the JSON reply, and falling back to the local answer. Every
 * prompt wraps owner-typed text in <owner_text> (or <owner_data>) tags and
 * tells the model it is data, never instructions.
 */
import type { LlmAccess } from "./guard.server";
import { DailyLimitReached, type DailyLimitInfo, type ModelAccess } from "./types";
import { modelEndpoint } from "./model-endpoint";

/** Why an answer came from Voyager or the local rules, with the ceiling met when it was today's budget. */
export interface ModelFallbackStatus {
  modelStatus: ModelAccess;
  dailyLimit?: DailyLimitInfo;
}

/**
 * Owner-typed text for inside an <owner_text> block, with any opening or
 * closing owner_text or owner_data tag removed (any case, any spacing,
 * attributes or a slash before ">", "owner-text" too) so the text cannot end
 * the block early or open a second one. A "<" still left in front of "owner"
 * (a tag with no ">") becomes "‹". Run it over the whole block's content,
 * not field by field, so no field is missed.
 */
export function ownerText(value: string): string {
  // Repeated until nothing changes: removing one tag must not join the text
  // around it into another ("</owner_te</owner_text>xt>").
  let text = value;
  for (let next = text.replace(OWNER_TAG, ""); next !== text; next = text.replace(OWNER_TAG, "")) {
    text = next;
  }
  return text.replace(OWNER_TAG_START, "‹");
}

/**
 * A value as JSON for an <owner_data> block. Every "<" is escaped as \u003c,
 * which keeps the JSON valid and makes a tag inside a name impossible.
 */
export function ownerJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

/** The model's JSON object, with a Markdown code fence around it tolerated; null when it does not parse to an object. */
export function parseJsonReply(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(
      text
        .trim()
        .replace(/^```(?:json)?/, "")
        .replace(/```$/, ""),
    );
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/**
 * The local answer unless a model server is configured, the caller is allowed and `worthAsking`
 * holds; otherwise Voyager's answer, or the local one when Voyager returns nothing
 * usable or fails. `ask` must call the model through callModel(access, ...),
 * which spends the daily budget. Either way the result carries the caller's
 * Voyager status, or "daily_limit" with the ceiling met when today's model
 * budget was used up.
 */
export async function withModelFallback<T extends object>(
  access: LlmAccess,
  local: T,
  worthAsking: boolean,
  ask: (access: LlmAccess) => Promise<T | null>,
): Promise<T & ModelFallbackStatus> {
  const model = access.model;
  if (model !== "allowed" || !worthAsking || !modelEndpoint()) {
    return { ...local, modelStatus: model };
  }
  try {
    const answer = await ask(access);
    return { ...(answer ?? local), modelStatus: model };
  } catch (error) {
    if (error instanceof DailyLimitReached) {
      return { ...local, modelStatus: error.model, dailyLimit: error.dailyLimit };
    }
    return { ...local, modelStatus: model };
  }
}

/**
 * Any opening or closing owner tag, in any case, with stray spaces, slashes,
 * invisible format characters or attributes ("</OWNER_TEXT >",
 * "</owner_text data=1>", "</owner_text/>", "<owner-data>").
 */
const OWNER_TAG = /<[\s/\p{Cf}]*owner[\s_\-\p{Cf}]*(?:text|data)(?![\p{L}\p{N}_])[^<>]*>/giu;
/** A "<" that opens something reading as an owner tag, with or without its ">". */
const OWNER_TAG_START = /<(?=[\s/\p{Cf}]*owner)/giu;
