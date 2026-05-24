"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard, Map, Calendar, ShieldCheck,
  Globe2, BookOpen,
} from "lucide-react";

const ITEMS = [
  { href: "/", label: "Executive Summary", Icon: LayoutDashboard },
  { href: "/map", label: "World Map", Icon: Map },
  { href: "/timeline", label: "Deadline Timeline", Icon: Calendar },
  { href: "/services", label: "By Service", Icon: ShieldCheck },
  { href: "/jurisdictions", label: "Jurisdictions", Icon: Globe2 },
  { href: "/methodology", label: "Methodology", Icon: BookOpen },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="w-60 bg-certik-panel border-r border-certik-border h-screen sticky top-0 flex flex-col">
      <Link href="/" className="px-5 py-5 border-b border-certik-border flex items-center gap-2">
        <span className="bg-certik-red px-2 py-1 rounded text-white font-bold text-sm">CertiK</span>
        <span className="text-white font-semibold text-sm">Reg Intel</span>
      </Link>
      <ul className="flex-1 py-3">
        {ITEMS.map(({ href, label, Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                className={clsx(
                  "flex items-center gap-3 px-5 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-certik-red/10 text-white border-l-2 border-certik-red"
                    : "text-zinc-400 hover:bg-certik-border/30 hover:text-white",
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="px-5 py-3 border-t border-certik-border text-[10px] text-certik-muted">
        Source: <span className="font-mono">scraper_obsidian_compliance</span>
      </div>
    </nav>
  );
}
