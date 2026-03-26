import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MentorDB",
  description: "Search structured faculty profiles and source-backed admissions evidence."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
