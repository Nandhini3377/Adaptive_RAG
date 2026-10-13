import { Suspense } from "react";

import { DocumentDetail } from "@/components/DocumentDetail";
import { RequireAuth } from "@/components/RequireAuth";
import { Loading } from "@/components/ui";

export default function DocumentPage() {
  return (
    <RequireAuth>
      {/* The document id comes from the URL, so Next.js needs a Suspense boundary */}
      <Suspense fallback={<Loading />}>
        <DocumentDetail />
      </Suspense>
    </RequireAuth>
  );
}
