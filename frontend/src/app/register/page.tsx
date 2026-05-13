"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";

export default function RegisterPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const router                  = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 8)  { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    try {
      await authApi.register(email, password);
      router.push("/login?redirect=/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? "Email already registered." : err.detail);
      } else {
        setError("Registration failed. Check that the backend is running.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="card__head">
          <span>Anomaly Wiki</span>
          <span style={{ fontSize: 10 }}>Researcher registration</span>
        </div>
        <div className="card__body">
          <div className="kicker" style={{ marginBottom: 16 }}>New researcher account</div>
          <div className="callout callout--info" style={{ marginBottom: 16 }}>
            <div className="callout__title">Note</div>
            <div style={{ fontSize: 13 }}>All new accounts are assigned the <b>Researcher</b> role. Contact an Editor or Admin for elevated access.</div>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="researcher@zone.int" />
            </div>
            <div className="form-field">
              <label htmlFor="password">Password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
            </div>
            <div className="form-field">
              <label htmlFor="confirm">Confirm password</label>
              <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </div>
            {error && <div className="form-error">{error}</div>}
            <button
              type="submit"
              className="btn btn--primary"
              style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
              disabled={loading}
            >
              {loading ? "Registering…" : "Create account"}
            </button>
          </form>
          <div className="row" style={{ marginTop: 16, justifyContent: "center" }}>
            <span className="muted xsmall">Already have an account?</span>
            <Link href="/login" className="mono xsmall">Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
