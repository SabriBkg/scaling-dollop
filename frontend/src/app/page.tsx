import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/constants";

// Root page — redirect to login (Story 1.2 will add JWT check before redirect)
export default function Home() {
  redirect(ROUTES.LOGIN);
}
