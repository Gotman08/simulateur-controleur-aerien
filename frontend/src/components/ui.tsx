/** Primitives UI partagees (DRY) : boutons, sections, badges, champs. */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { Button, TextInput } from "flowbite-react";

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
    <Button
      type="button"
      color="control"
      size="sm"
      aria-label={props["aria-label"] ?? props.title}
      theme={{ base: "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acc disabled:cursor-not-allowed disabled:opacity-45", color: { control: VARIANTS[variant] }, size: { sm: "px-3 py-2 text-[13px]" } }}
      className={className}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <TextInput
      sizing="sm"
      color="control"
      aria-label={props["aria-label"] ?? props.title ?? props.placeholder}
      theme={{ field: { input: { base: "block w-full border disabled:cursor-not-allowed disabled:opacity-50 focus:ring-1 focus:ring-acc focus:border-acc", sizes: { sm: "px-2.5 py-2 text-[13px]" }, colors: { control: "border-edge bg-panel2 text-ink placeholder:text-mut/70" } } } }}
      className={className}
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
