import { LoginForm } from "@/components/login-form";

export const metadata = { title: "Sign in" };
export default function Login() {
  return (
    <main
      id="main"
      className="flex min-h-dvh items-center justify-center px-4 py-12"
    >
      <section className="panel w-full max-w-sm p-6 sm:p-8">
        <p className="mb-8 text-lg font-bold tracking-tight">SEOPs</p>
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-muted">
          Access your sites and SEO performance.
        </p>
        <LoginForm />
      </section>
    </main>
  );
}
