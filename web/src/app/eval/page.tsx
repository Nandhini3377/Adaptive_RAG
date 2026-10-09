import { EvalView } from "@/components/EvalView";
import { RequireAuth } from "@/components/RequireAuth";

export default function EvalPage() {
  return (
    <RequireAuth>
      <EvalView />
    </RequireAuth>
  );
}
