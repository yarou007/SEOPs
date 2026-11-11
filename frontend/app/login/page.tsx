import { KeyRound } from "lucide-react";
import { LoginForm } from "@/components/login-form";

export const metadata = { title: "Sign in" };
export default function Login() {
  return (
    <main
      id="main"
      className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
    >
      <div className="hidden flex-col justify-between bg-ink p-12 text-ink-foreground lg:flex">
        <p className="flex items-center gap-2.5 text-lg font-semibold">
          <span className="flex size-8 items-center justify-center rounded-md bg-brass text-ink">
            <KeyRound size={17} aria-hidden />
          </span>
          SEOPs
        </p>
        <p className="max-w-[22ch] text-4xl font-semibold leading-tight tracking-[-0.02em]">
          See how your websites do on Google, and what to fix next.
        </p>
        <p className="text-sm text-ink-muted">
          Search Console, Google Analytics and Ahrefs in one place, with AI
          advice.
        </p>
      </div>
      <div className="flex items-center justify-center px-4 py-12">
        <section className="w-full max-w-sm">
          <p className="mb-8 flex items-center gap-2 text-lg font-semibold lg:hidden">
            <span className="flex size-8 items-center justify-center rounded-md bg-brass text-ink">
              <KeyRound size={17} aria-hidden />
            </span>
            SEOPs
          </p>
          <h1 className="text-2xl font-semibold">Sign in</h1>
          <p className="mt-2 text-muted">
            Use the email and password your team gave you.
          </p>
          <LoginForm />
        </section>
      </div>
    </main>
  );
}
