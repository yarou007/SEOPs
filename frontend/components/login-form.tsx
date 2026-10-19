"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export function LoginForm() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      await api.login(String(data.get("email")), String(data.get("password")));
      router.replace("/sites");
      router.refresh();
    } catch (error) {
      setError(
        error instanceof ApiError && error.status === 401
          ? "Invalid email or password."
          : error instanceof Error
            ? error.message
            : "Could not sign in. Please try again.",
      );
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit} className="mt-7 space-y-5">
      <div>
        <label htmlFor="email" className="mb-1.5 block font-medium">
          Email
        </label>
        <input
          className="w-full"
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          disabled={pending}
        />
      </div>
      <div>
        <label htmlFor="password" className="mb-1.5 block font-medium">
          Password
        </label>
        <input
          className="w-full"
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          disabled={pending}
          maxLength={1024}
        />
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-bad-soft p-3 text-sm text-bad">
          {error}
        </p>
      )}
      <button
        type="submit"
        className="button button-primary w-full"
        disabled={pending}
      >
        {pending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
