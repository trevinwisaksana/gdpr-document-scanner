"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Spinner } from "@/components/ui";
import { useSession } from "@/lib/session";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { ready, isAuthed, isAdmin } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const adminArea = pathname.startsWith("/admin");
  const wrongArea = isAuthed && (isAdmin ? !adminArea : adminArea);

  useEffect(() => {
    if (!ready) return;
    if (!isAuthed) {
      router.replace("/");
    } else if (isAdmin && !adminArea) {
      router.replace("/admin");
    } else if (!isAdmin && adminArea) {
      router.replace("/files");
    }
  }, [ready, isAuthed, isAdmin, adminArea, router]);

  if (!ready || !isAuthed || wrongArea) {
    return (
      <div className="flex h-screen items-center justify-center text-ink-faint">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1180px] px-7 py-7">{children}</div>
      </main>
    </div>
  );
}
