import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import DemoBanner from "@/components/DemoBanner";
import { api, Meta } from "@/lib/api";

export const metadata: Metadata = {
  title: "Pace Lab: F1 performance analytics",
  description: "Independent analysis of why drivers and cars perform the way they do. Not affiliated with Formula 1.",
};

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  let meta: Meta | null = null;
  try { meta = await api<Meta>("/meta"); } catch { /* API offline: page-level errors explain it */ }
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="min-w-0 flex-1">
            {meta && <DemoBanner meta={meta} />}
            <main className="mx-auto max-w-6xl px-4 py-6 md:px-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
