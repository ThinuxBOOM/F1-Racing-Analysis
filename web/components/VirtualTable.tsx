"use client";
import { useMemo, useRef, useState, useEffect } from "react";

// Minimal windowing table: renders only visible rows for long lists
// (e.g. 500+ pace laps) so the page stays fast on low-end devices.
export default function VirtualTable<T>({
  rows, rowHeight = 28, height = 360, header, renderRow,
}: {
  rows: T[]; rowHeight?: number; height?: number;
  header: React.ReactNode; renderRow: (row: T, i: number) => React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(0);
  const total = rows.length;
  const visible = Math.ceil(height / rowHeight) + 4;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => setTop(el.scrollTop);
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const start = Math.max(0, Math.floor(top / rowHeight) - 2);
  const slice = useMemo(() => rows.slice(start, start + visible), [rows, start, visible]);

  return (
    <div>
      <div className="overflow-x-auto">
        <div className="min-w-full text-sm">
          <div className="label grid" style={{ gridTemplateColumns: "inherit" }}>{header}</div>
          <div ref={ref} style={{ height, overflowY: "auto" }} className="relative">
            <div style={{ height: total * rowHeight, position: "relative" }}>
              <div style={{ transform: `translateY(${start * rowHeight}px)` }}>
                {slice.map((r, k) => (
                  <div key={start + k} style={{ height: rowHeight }} className="border-t border-line">
                    {renderRow(r, start + k)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <p className="mt-1 text-[11px] text-mute">Showing {slice.length} of {total} rows (virtualised).</p>
    </div>
  );
}
