import type { Meta } from "@/lib/api";

export default function DemoBanner({ meta }: { meta: Meta }) {
  if (!meta.is_mock) return null;
  return (
    <div role="status" className="border-b border-warn/40 bg-warn/10 px-4 py-2 text-xs text-warn">
      <strong className="mr-2 uppercase tracking-wide">Demo data</strong>{meta.notice}
    </div>
  );
}
