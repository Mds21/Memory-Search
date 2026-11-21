import Shell from "@/components/Shell";
import { UploadsProvider } from "@/lib/uploads";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <UploadsProvider><Shell>{children}</Shell></UploadsProvider>;
}
