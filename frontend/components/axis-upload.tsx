"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function AxisUpload({
  slug,
  kind,
}: {
  slug: string;
  kind: "internal-links" | "backlinks";
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const router = useRouter();
  return (
    <form
      className="axis-upload"
      onSubmit={async (event) => {
        event.preventDefault();
        const file = new FormData(event.currentTarget).get("csv");
        if (!(file instanceof File) || !file.size) {
          setMessage("Choose a CSV export first.");
          return;
        }
        if (file.size > 2_000_000) {
          setMessage("Choose a CSV smaller than 2 MB.");
          return;
        }
        setBusy(true);
        setMessage("");
        try {
          const bytes = new Uint8Array(await file.arrayBuffer());
          const encoding =
            bytes[0] === 255 && bytes[1] === 254
              ? "utf-16le"
              : bytes[0] === 254 && bytes[1] === 255
                ? "utf-16be"
                : "utf-8";
          const csv = new TextDecoder(encoding, { fatal: true }).decode(bytes);
          await api.uploadAxisCsv(slug, kind, csv);
          setMessage("Export saved. The latest evidence is now selected.");
          router.refresh();
        } catch (error) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Could not import this CSV.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor={`csv-${kind}`}>
        {kind === "internal-links"
          ? "Site Audit CSV"
          : "Backlinks CSV for this website"}{" "}
        <span className="text-muted">(up to 2 MB)</span>
      </label>
      <div className="flex flex-wrap gap-3">
        <input
          id={`csv-${kind}`}
          name="csv"
          type="file"
          accept=".csv,.tsv,text/csv,text/tab-separated-values"
          required
          disabled={busy}
        />
        <button className="button" disabled={busy}>
          {busy ? "Importing…" : "Upload export"}
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </form>
  );
}
