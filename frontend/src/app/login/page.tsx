"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth";
import { ApiError } from "@/lib/api/errors";

function LoginForm() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const { login }               = useAuthStore();
  const router                  = useRouter();
  const params                  = useSearchParams();
  const redirect                = params.get("redirect") ?? "/";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await authApi.login(email, password);
      login(access_token);
      router.push(redirect);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Invalid credentials." : err.detail);
      } else {
        setError("Login failed. Check that the backend is running.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          id="email" type="email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="researcher@zone.int" autoComplete="email" required
        />
      </div>
      <div className="form-field">
        <label htmlFor="password">Password</label>
        <input
          id="password" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password" required
        />
      </div>
      {error && <div className="form-error">{error}</div>}
      <button
        type="submit"
        className="btn btn--primary"
        style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
        disabled={loading}
      >
        {loading ? "Authenticating…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="card__head">
          <span>Anomaly Wiki</span>
          <span style={{ fontSize: 10 }}>Field Research Terminal</span>
        </div>
        <div className="card__body">
          <div className="kicker" style={{ marginBottom: 16 }}>Researcher authentication</div>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
          <div className="row" style={{ marginTop: 16, justifyContent: "center" }}>
            <span className="muted xsmall">No account?</span>
            <Link href="/register" className="mono xsmall">Register as Researcher</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
