import { DocumentsView } from "@/components/DocumentsView";
import { RequireAuth } from "@/components/RequireAuth";

export default function HomePage() {
  return (
    <RequireAuth>
      <DocumentsView />
    </RequireAuth>
  );
}
