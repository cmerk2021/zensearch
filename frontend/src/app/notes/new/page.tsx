"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/ui/card";

export default function NewNotePage() {
  return (
    <Suspense>
      <NewNoteRedirect />
    </Suspense>
  );
}

function NewNoteRedirect() {
  const router = useRouter();
  const params = useSearchParams();
  const workspaceId = params.get("workspace_id");

  useEffect(() => {
    api
      .post<{ id: string }>("/api/v1/notes", {
        title: "",
        content: "",
        workspace_id: workspaceId,
      })
      .then((note) => router.replace(`/notes/${note.id}`))
      .catch(() => router.replace("/notes"));
  }, [router, workspaceId]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner className="h-6 w-6" />
    </div>
  );
}
