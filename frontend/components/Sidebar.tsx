"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  FolderSearch,
  History,
  LayoutDashboard,
  LogOut,
  ScanText,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/format";
import { getEmployees } from "@/lib/data";
import { useSession } from "@/lib/session";
import { Avatar } from "./ui";

interface NavItem {
  href: string;
  label: string;
  icon: typeof FolderSearch;
}

const EMPLOYEE_NAV: NavItem[] = [
  { href: "/files", label: "My files", icon: FolderSearch },
  { href: "/stats", label: "My stats", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/scan", label: "Live PII scan", icon: ScanText },
  { href: "/admin/users", label: "Data owners", icon: Users },
  { href: "/admin/history", label: "Scan history", icon: History },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { authUser, viewedUser, isAdmin, logout, switchViewedUser } = useSession();
  const nav = isAdmin ? ADMIN_NAV : EMPLOYEE_NAV;
  const employees = getEmployees();

  return (
    <aside className="flex h-screen w-60 flex-none flex-col border-r border-line bg-surface">
      {/* Brand */}
      <div className="flex items-center gap-2.5 border-b border-line-soft px-4 py-4">
        <div className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-accent text-white">
          <ShieldCheck className="h-4.5 w-4.5" strokeWidth={2.2} />
        </div>
        <div className="min-w-0">
          <div className="truncate text-[0.86rem] font-semibold tracking-tight text-ink">
            GDPR Discovery
          </div>
          <div className="truncate text-[0.64rem] text-ink-faint">Bosch · Data Protection</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        <div className="px-2.5 pb-1.5 text-[0.62rem] font-semibold uppercase tracking-[0.09em] text-ink-faint">
          {isAdmin ? "Administration" : "Workspace"}
        </div>
        {nav.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "mb-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[0.82rem] font-medium transition-colors",
                active
                  ? "bg-accent-soft text-accent-strong"
                  : "text-ink-muted hover:bg-surface-2 hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4 flex-none" />
              {item.label}
            </Link>
          );
        })}

        {/* Employee "view as" switcher (demo only — no real access control) */}
        {!isAdmin && (
          <div className="mt-5 border-t border-line-soft px-1 pt-3">
            <label className="mb-1.5 block px-1.5 text-[0.62rem] font-semibold uppercase tracking-[0.09em] text-ink-faint">
              Viewing as (demo)
            </label>
            <select
              value={viewedUser?.id ?? ""}
              onChange={(e) => {
                switchViewedUser(e.target.value);
                if (pathname.startsWith("/files/")) router.push("/files");
              }}
              className="input py-1.5 text-[0.78rem]"
            >
              {employees.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </nav>

      {/* User chip */}
      <div className="border-t border-line-soft p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-1.5 py-1">
          <Avatar name={authUser?.name ?? "?"} size={32} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[0.8rem] font-semibold text-ink">{authUser?.name}</div>
            <div className="truncate text-[0.68rem] text-ink-faint">
              {isAdmin ? "Data Protection Officer" : authUser?.department}
            </div>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="grid h-8 w-8 flex-none place-items-center rounded-lg text-ink-faint transition-colors hover:bg-surface-2 hover:text-danger"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
