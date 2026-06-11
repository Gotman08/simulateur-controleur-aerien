/** Primitives UI partagees (DRY) : boutons, sections, badges, champs. */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

const VARIANTS = {
  default: "bg-panel2 border-edge text-ink hover:border-acc/60",
  primary: "bg-acc/15 border-acc/60 text-acc hover:bg-acc/25",
  danger: "bg-dang/10 border-dang/50 text-dang hover:bg-dang/20",
  ghost: "bg-transparent border-transparent text-mut hover:text-ink hover:border-edge",
} as const;

export function Btn({
  variant = "default",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof VARIANTS }) {
  return (
    <button
      className={`rounded-md border px-3 py-1.5 text-[13px] transition-colors
        disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`rounded-md border border-edge bg-panel2 px-2.5 py-1.5 text-[13px] text-ink
        outline-none placeholder:text-mut/60 focus:border-acc/60 ${className}`}
      {...props}
    />
  );
}

export function Section({ title, right, children }: {
  title: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="border-b border-edge px-4 py-3">
      <h2 className="mb-2 flex items-center justify-between text-[11px] font-semibold
        uppercase tracking-wider text-mut">
        {title}
        {right}
      </h2>
      {children}
    </section>
  );
}

export function Badge({ tone = "mut", children, className = "", ...props }: {
  tone?: "ok" | "warn" | "dang" | "acc" | "mut"; children: ReactNode; className?: string;
} & ButtonHTMLAttributes<HTMLSpanElement>) {
  const tones = {
    ok: "border-rdr/50 text-rdr",
    warn: "border-warn/50 text-warn",
    dang: "border-dang/50 text-dang",
    acc: "border-acc/50 text-acc",
    mut: "border-edge text-mut",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5
        font-mono text-[10.5px] tracking-wide ${tones[tone]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}

export const Row = ({ className = "", children }: { className?: string; children: ReactNode }) => (
  <div className={`mt-2 flex items-center gap-2 ${className}`}>{children}</div>
);

export const fmtTime = (s: number | undefined | null) => {
  const v = Math.max(0, Math.round(s ?? 0));
  return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
};
