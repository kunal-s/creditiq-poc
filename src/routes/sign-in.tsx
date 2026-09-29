import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/config/terminology";
import { signIn } from "@/domain/session";

export const Route = createFileRoute("/sign-in")({
  head: () => ({ meta: [{ title: `${t("page.signIn.title")} — ${t("tenant.product.name")}` }] }),
  component: SignInPage,
});

function SignInPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Until the page is interactive the form must not submit natively.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await signIn(email, password);
      navigate({ to: "/" });
    } catch {
      toast.error(t("signIn.failed"), { description: t("signIn.failedHelp") });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded bg-primary text-sm font-bold text-primary-foreground">
            {t("tenant.brand.mark")}
          </span>
          <span className="text-lg font-semibold tracking-tight text-foreground">
            {t("tenant.product.name")}
          </span>
          <span className="text-sm text-muted-foreground">
            {t("tenant.bank.name")} · {t("tenant.bank.unit")}
          </span>
        </div>
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-border bg-surface p-6"
        >
          <div className="space-y-1.5">
            <Label htmlFor="email">{t("signIn.email")}</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={`you@${t("tenant.bank.emailDomain")}`}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">{t("signIn.password")}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={!ready || submitting}>
            {submitting ? t("signIn.submitting") : t("page.signIn.title")}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-muted-foreground">{t("signIn.help")}</p>
      </div>
    </div>
  );
}
