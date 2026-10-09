import { Suspense } from "react";

import { ChatView } from "@/components/ChatView";
import { RequireAuth } from "@/components/RequireAuth";

export default function ChatPage() {
  return (
    <RequireAuth>
      {/* ?doc= preselects a document; reading it needs a Suspense boundary */}
      <Suspense fallback={<p className="text-sm text-ink-soft">Loading…</p>}>
        <ChatView />
      </Suspense>
    </RequireAuth>
  );
}
