import { LabView } from "@/components/LabView";
import { RequireAuth } from "@/components/RequireAuth";

export default function LabPage() {
  return (
    <RequireAuth>
      <LabView />
    </RequireAuth>
  );
}
