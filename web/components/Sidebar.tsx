import Link from "next/link";

const NAV: { href: string | null; label: string }[] = [
  { href: "/", label: "Dashboard" },
  { href: "/drivers/DA1", label: "Drivers" },
  { href: "/head-to-head", label: "Head-to-Head" },
  { href: "/teams", label: "Teams" },
  { href: "/cars", label: "Cars" },
  { href: "/circuits", label: "Circuits" },
  { href: "/races", label: "Races" },
  { href: "/tyres", label: "Tyres" },
  { href: "/telemetry", label: "Telemetry" },
  { href: "/strategy", label: "Strategy" },
  { href: "/season-analysis", label: "Season Analysis" },
  { href: "/predictions", label: "Predictions" },
  { href: "/methodology", label: "Methodology" },
];

export default function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 border-r border-line bg-panel md:block">
      <div className="px-5 py-5">
        <div className="text-sm font-semibold tracking-wide">PACE LAB</div>
        <div className="mt-0.5 text-[11px] text-mute">Independent F1 analytics</div>
      </div>
      <nav className="px-2 text-sm">
        {NAV.map((n) =>
          n.href ? (
            <Link key={n.label} href={n.href} className="block rounded px-3 py-2 text-ink hover:bg-panel2">{n.label}</Link>
          ) : (
            <div key={n.label} className="flex items-center justify-between px-3 py-2 text-mute/60">
              {n.label}<span className="text-[10px] uppercase">soon</span>
            </div>
          )
        )}
      </nav>
      <p className="mt-6 px-5 text-[10px] leading-relaxed text-mute">
        Independent analytics project. Not affiliated with, or endorsed by, Formula 1 or any team.
      </p>
    </aside>
  );
}
