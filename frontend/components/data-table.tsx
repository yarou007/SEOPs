"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { formatNumber, formatPercent, formatPosition } from "@/lib/format";
import { PAGE_SIZE } from "@/lib/params";
import { EmptyState } from "./states";

export interface Column<T> {
  key: keyof T & string;
  label: string;
  kind: "text" | "number" | "percent" | "position";
  sortable?: boolean;
}
export function DataTable<T extends object>({
  title,
  rows,
  columns,
  rowKey,
  offset,
  offsetKey,
  defaultSort,
}: {
  title: string;
  rows: T[];
  columns: Column<T>[];
  rowKey: keyof T & string;
  offset: number;
  offsetKey: string;
  defaultSort: keyof T & string;
}) {
  const [sort, setSort] = useState<{
    key: keyof T & string;
    direction: "asc" | "desc";
  }>({ key: defaultSort, direction: "desc" });
  const pathname = usePathname();
  const search = useSearchParams();
  const visible = useMemo(
    () =>
      rows.slice(0, PAGE_SIZE).sort((a, b) => {
        const left = a[sort.key],
          right = b[sort.key];
        if (left == null) return right == null ? 0 : 1;
        if (right == null) return -1;
        const value =
          typeof left === "number" && typeof right === "number"
            ? left - right
            : String(left).localeCompare(String(right));
        return sort.direction === "asc" ? value : -value;
      }),
    [rows, sort],
  );
  function href(next: number) {
    const params = new URLSearchParams(search.toString());
    params.set(offsetKey, String(next));
    return `${pathname}?${params}`;
  }
  function display(value: unknown, kind: Column<T>["kind"]) {
    if (kind === "text") return value == null ? "—" : String(value);
    const number = typeof value === "number" ? value : null;
    return kind === "percent"
      ? formatPercent(number)
      : kind === "position"
        ? formatPosition(number)
        : formatNumber(number);
  }
  return (
    <section className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-xs text-muted">Sort applies to this page.</p>
      </div>
      {!visible.length ? (
        <EmptyState>No data in this range.</EmptyState>
      ) : (
        <div className="table-wrap max-h-[540px]">
          <table aria-label={title} className="min-w-[620px]">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    className={column.kind === "text" ? "" : "numeric"}
                    aria-sort={
                      column.sortable
                        ? sort.key === column.key
                          ? sort.direction === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                        : undefined
                    }
                  >
                    {column.sortable ? (
                      <button
                        className="inline-flex items-center gap-1 hover:text-foreground"
                        onClick={() =>
                          setSort({
                            key: column.key,
                            direction:
                              sort.key === column.key &&
                              sort.direction === "desc"
                                ? "asc"
                                : "desc",
                          })
                        }
                      >
                        {column.label}
                        <span aria-hidden="true">
                          {sort.key === column.key
                            ? sort.direction === "desc"
                              ? "↓"
                              : "↑"
                            : "↕"}
                        </span>
                      </button>
                    ) : (
                      column.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={String(row[rowKey])}>
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={
                        column.kind === "text"
                          ? "min-w-[180px] max-w-[360px] break-words [overflow-wrap:anywhere]"
                          : "numeric"
                      }
                    >
                      {display(row[column.key], column.kind)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div
        aria-label={`${title} pagination`}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <p className="text-xs text-muted">
          {visible.length
            ? `${formatNumber(offset + 1)}–${formatNumber(offset + visible.length)} shown`
            : "0 rows shown"}
        </p>
        <div className="flex gap-2">
          {offset > 0 ? (
            <Link
              scroll={false}
              className="button text-xs"
              href={href(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Link>
          ) : (
            <span className="button text-xs opacity-40" aria-disabled="true">
              Previous
            </span>
          )}
          {rows.length > PAGE_SIZE ? (
            <Link
              scroll={false}
              className="button text-xs"
              href={href(offset + PAGE_SIZE)}
            >
              Next
            </Link>
          ) : (
            <span className="button text-xs opacity-40" aria-disabled="true">
              Next
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
