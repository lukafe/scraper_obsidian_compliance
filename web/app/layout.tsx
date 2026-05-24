import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CertiK — Crypto Regulation Market Intel",
  description:
    "Where to expand, what to sell first — security-focused regulatory intelligence for 23 jurisdictions.",
};

export default function RootLayout({
  children,
}: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-certik-dark text-white min-h-screen`}>
        <div className="flex">
          <Nav />
          <main className="flex-1 min-w-0 max-w-[1600px] mx-auto px-8 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
