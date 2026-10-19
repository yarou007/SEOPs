import "server-only";
import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { createApi, ApiError } from "./api";
import type { Result } from "./types";

export async function serverApi() {
  const cookie = (await headers()).get("cookie") ?? "";
  // Node fetch needs an absolute URL. Resolve the same relative /api path through
  // this Next server and its rewrite, without trusting an incoming Host header.
  const origin = `http://127.0.0.1:${process.env.PORT ?? "3000"}`;
  return createApi((path, init) =>
    fetch(new URL(path, origin), {
      ...init,
      headers: { ...init.headers, cookie },
    }),
  );
}

export async function requireUser() {
  try {
    return await (await serverApi()).me();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }
}

export async function result<T>(
  promise: Promise<T>,
  siteScoped = false,
): Promise<Result<T>> {
  try {
    return { data: await promise, error: null };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) redirect("/login");
      if (error.status === 404 && siteScoped) notFound();
      return { data: null, error: error.message, status: error.status };
    }
    throw error;
  }
}
