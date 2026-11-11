"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function Logout({ className = "" }: { className?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setPending(true);
    setError("");
    try {
      await api.logout();
      router.replace("/login");
      router.refresh();
    } catch {
      setError("Could not sign out. Try again.");
      setPending(false);
    }
  }
  return (
    <div>
      <button
        className={`button text-xs ${className}`}
        onClick={logout}
        disabled={pending}
      >
        {pending ? "Signing out…" : "Log out"}
      </button>
      {error && (
        <p role="alert" className="mt-1 text-xs text-bad-soft">
          {error}
        </p>
      )}
    </div>
  );
}
