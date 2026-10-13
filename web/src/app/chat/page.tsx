import { Suspense } from "react";

import { ChatView } from "@/components/ChatView";
import { RequireAuth } from "@/components/RequireAuth";
import { Loading } from "@/components/ui";

export default function ChatPage() {
  return (
    <RequireAuth>
      {/* ?doc= preselects a document; reading it needs a Suspense boundary */}
      <Suspense fallback={<Loading />}>
        <ChatView />
      </Suspense>
    </RequireAuth>
  );
}
