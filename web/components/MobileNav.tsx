import Link from "next/link";

const LINKS = [
  ["/", "Dashboard"], ["/drivers/DA1", "Drivers"], ["/head-to-head", "H2H"],
  ["/teams", "Teams"], ["/cars", "Cars"], ["/races", "Races"],
  ["/tyres", "Tyres"], ["/telemetry", "Tele"], ["/strategy", "Strat"],
  ["/season-analysis", "Season"], ["/predictions", "Pred"], ["/circuits", "Circuits"], ["/methodology", "Method"],
];

export default function MobileNav() {
  return (
    <nav className="sticky top-0 z-10 border-b border-line bg-panel/95 backdrop-blur md:hidden">
      <div className="flex items-center justify-between px-4 py-2">
        <span className="text-sm font-semibold">PACE LAB</span>
        <span className="text-[10px] text-mute">Independent F1 analytics</span>
      </div>
      <div className="flex gap-1 overflow-x-auto px-3 pb-2">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href}
            className="whitespace-nowrap rounded border border-line bg-panel2 px-2 py-1 text-xs text-ink">
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
