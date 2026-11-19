import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

const searchRequest = z.strictObject({
  query: z.string().max(200),
  section: z.string().max(80).optional(),
});

export const searchComplianceCardsFn = createServerFn({ method: "POST" })
  .validator((input: { query: string; section?: string }) => searchRequest.parse(input))
  .handler(async ({ data }) => {
    const { searchComplianceCardsFromDisk } = await import("./cards.server");
    return searchComplianceCardsFromDisk(data.query, data.section);
  });
