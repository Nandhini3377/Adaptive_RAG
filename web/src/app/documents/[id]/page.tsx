import { Suspense } from "react";

import { DocumentDetail } from "@/components/DocumentDetail";
import { RequireAuth } from "@/components/RequireAuth";

export default function DocumentPage() {
  return (
    <RequireAuth>
      {/* The document id comes from the URL, so Next.js needs a Suspense boundary */}
      <Suspense fallback={<p className="text-sm text-ink-soft">Loading…</p>}>
        <DocumentDetail />
      </Suspense>
    </RequireAuth>
  );
}
